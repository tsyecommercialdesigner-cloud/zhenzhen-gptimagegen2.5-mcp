"""Bounded image IO. Downloads never receive the business API credential."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import io
import ipaddress
import os
import random
import socket
import tempfile
import warnings
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from PIL import Image

from .config import absolute_directory

MAX_IMAGE_BYTES = 50 * 1024 * 1024
MAX_IMAGES = 16
FORMATS = {"PNG": (".png", "image/png"), "JPEG": (".jpg", "image/jpeg"), "WEBP": (".webp", "image/webp")}


def image_info(data: bytes) -> tuple[str, str]:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image is empty or exceeds the local 50 MiB limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as im:
                fmt = im.format
                im.verify()
        if fmt not in FORMATS:
            raise ValueError("Only PNG, JPEG and WebP images are supported locally")
        return FORMATS[fmt]
    except (OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("Invalid or excessively large decoded image") from exc


async def public_url(url: str) -> None:
    u = urlsplit(url)
    if u.scheme not in {"https", "http"} or not u.hostname or u.username or u.password:
        raise ValueError("Image URL must be public HTTP(S), without embedded credentials")
    if any(c in url for c in "\r\n"):
        raise ValueError("Invalid image URL")
    addresses = await asyncio.get_running_loop().getaddrinfo(
        u.hostname, u.port or (443 if u.scheme == "https" else 80), type=socket.SOCK_STREAM
    )
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Private, loopback and reserved image hosts are not permitted")


def validate_mask(data: bytes, first_image: bytes) -> None:
    if image_info(data)[1] != "image/png" or len(data) >= 4 * 1024 * 1024:
        raise ValueError("mask must be a PNG image smaller than 4 MiB")
    with Image.open(io.BytesIO(data)) as mask, Image.open(io.BytesIO(first_image)) as reference:
        if mask.size != reference.size or "A" not in mask.getbands():
            raise ValueError("mask must have alpha and match the first input image dimensions")


class TransientDownloadError(ValueError):
    pass


async def download(url: str) -> bytes:
    """Retry only transient read failures, within one total download budget."""
    async with asyncio.timeout(120):
        for attempt in range(3):
            try:
                return await _download_once(url)
            except (httpx.TransportError, TransientDownloadError):
                if attempt == 2:
                    raise
                await asyncio.sleep(2**attempt + random.uniform(0, 0.25))
    raise ValueError("Image download did not complete")


async def _download_once(url: str) -> bytes:
    # A distinct client, no default authorization, no environment proxy credentials.
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        for _ in range(6):
            await public_url(url)
            async with client.stream("GET", url) as response:
                if response.is_redirect:
                    if "location" not in response.headers:
                        raise ValueError("Image redirect has no Location")
                    url = str(response.url.join(response.headers["location"]))
                    continue
                if response.status_code in {408, 429, 500, 502, 503, 504}:
                    raise TransientDownloadError(f"Image download HTTP {response.status_code}")
                if response.status_code != 200:
                    raise ValueError(f"Image download HTTP {response.status_code}")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_IMAGE_BYTES:
                        raise ValueError("Image download exceeds the local 50 MiB limit")
                image_info(bytes(data))
                return bytes(data)
        raise ValueError("Too many image redirects")


def decode_image(value: str) -> bytes:
    if value.startswith("data:"):
        header, sep, value = value.partition(",")
        if not sep or ";base64" not in header or not header.startswith("data:image/"):
            raise ValueError("Expected a base64 image data URL")
    if len(value) > (MAX_IMAGE_BYTES * 4 // 3 + 8):
        raise ValueError("Base64 image exceeds the local 50 MiB limit")
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid base64 image") from exc
    image_info(data)
    return data


async def read_image(source: str) -> bytes:
    if source.startswith(("https://", "http://")):
        return await download(source)
    if source.startswith("data:"):
        return decode_image(source)
    path = Path(source)
    if not path.is_absolute() or not path.is_file():
        raise ValueError("Input image must be an existing absolute file path, HTTP(S) URL or data URL")
    with path.open("rb") as f:
        data = f.read(MAX_IMAGE_BYTES + 1)
    image_info(data)
    return data


def prepare_directory(directory: Path | str) -> Path:
    path = absolute_directory(directory)
    path.mkdir(parents=True, exist_ok=True)
    # Fail before submitting a paid request if the destination is unwritable.
    with tempfile.TemporaryFile(dir=path):
        pass
    return path


def save_image(data: bytes, directory: Path | str) -> dict:
    ext, mime = image_info(data)
    root = prepare_directory(directory)
    digest = hashlib.sha256(data).hexdigest()
    final = root / f"image-{digest}{ext}"
    if final.exists():
        if final.is_symlink() or hashlib.sha256(final.read_bytes()).hexdigest() != digest:
            raise ValueError("Existing output does not match its content hash; refusing overwrite")
        return {"path": str(final), "mime_type": mime, "bytes": len(data), "sha256": digest, "reused": True}
    fd, tmp = tempfile.mkstemp(prefix=".image-", suffix=".part", dir=root)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        # Atomic publish without overwriting an existing file, also on Windows NTFS.
        try:
            os.link(tmp, final)
        except FileExistsError:
            if final.is_symlink() or hashlib.sha256(final.read_bytes()).hexdigest() != digest:
                raise ValueError("Concurrent output conflict")
        if final.is_symlink() or hashlib.sha256(final.read_bytes()).hexdigest() != digest:
            raise ValueError("Published output hash mismatch; refusing to report success")
    finally:
        Path(tmp).unlink(missing_ok=True)
    return {"path": str(final), "mime_type": mime, "bytes": len(data), "sha256": digest, "reused": False}
