"""Project-local credential parsing, precedence, and secret boundaries."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from zhenzhen_image_mcp.config import KEY_NAME, api_key, project_directory
from zhenzhen_image_mcp.server import mcp


class EnvFileTests(unittest.TestCase):
    def test_wheel_root_uses_project_venv_not_host_working_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve()
            (project / "pyproject.toml").write_text("[project]\nname='zhenzhen-image'", encoding="utf-8")
            module = project / ".venv/Lib/site-packages/zhenzhen_image_mcp/config.py"
            with (
                patch("zhenzhen_image_mcp.config.__file__", str(module)),
                patch("sys.prefix", str(project / ".venv")),
                patch("sys.base_prefix", str(project / "python")),
            ):
                self.assertEqual(project_directory(), project)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for mock in (
            patch("zhenzhen_image_mcp.config.PROJECT_DIR", self.root),
            patch("zhenzhen_image_mcp.config.user_variable", return_value="user-old"),
            patch.dict(os.environ, {KEY_NAME: "process-old"}),
        ):
            mock.start()
            self.addCleanup(mock.stop)

    def write(self, text):
        (self.root / ".env").write_text(text, encoding="utf-8-sig")

    def test_local_key_wins_and_environment_is_unchanged(self):
        self.write(f'{KEY_NAME}="local-current"\n')
        self.assertEqual(api_key(), "local-current")
        self.assertEqual(os.environ[KEY_NAME], "process-old")

    def test_absent_file_or_absent_field_uses_process_then_user(self):
        self.assertEqual(api_key(), "process-old")
        self.write("OTHER=value\n")
        self.assertEqual(api_key(), "process-old")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(api_key(), "user-old")
            with patch("zhenzhen_image_mcp.config.user_variable", return_value=None):
                with self.assertRaises(ValueError):
                    api_key()

    def test_blank_malformed_or_duplicate_never_falls_back(self):
        for text in (
            f"{KEY_NAME}=\n",
            f"{KEY_NAME}\n",
            f'{KEY_NAME}="unterminated-private-value',
            f"{KEY_NAME}=one\n{KEY_NAME}=two",
            f'{KEY_NAME}="line1\\nline2"',
            f'{KEY_NAME}="${{OTHER}}"',
            f"{KEY_NAME}=key with spaces",
        ):
            with self.subTest(text=text):
                self.write(text)
                with self.assertRaises(ValueError) as cm:
                    api_key()
                self.assertNotIn("unterminated-private-value", str(cm.exception))

    def test_comments_quotes_export_and_literal_dollar(self):
        self.write(f"# comment\nexport {KEY_NAME} = 'token$literal' # comment\n")
        self.assertEqual(api_key(), "token$literal")

    def test_file_is_reread_after_update(self):
        self.write(f"{KEY_NAME}=first\n")
        self.assertEqual(api_key(), "first")
        self.write(f"{KEY_NAME}=second\n")
        self.assertEqual(api_key(), "second")

    def test_different_working_directory_does_not_select_other_file(self):
        with tempfile.TemporaryDirectory() as other:
            Path(other, ".env").write_text(f"{KEY_NAME}=wrong-project", encoding="utf-8")
            old = Path.cwd()
            try:
                os.chdir(other)
                self.assertEqual(api_key(), "process-old")
                self.write(f"{KEY_NAME}=right-project")
                self.assertEqual(api_key(), "right-project")
            finally:
                os.chdir(old)

    def test_unreadable_directory_and_invalid_encoding_fail_closed(self):
        with patch.object(Path, "open", side_effect=PermissionError("private-secret")):
            with self.assertRaisesRegex(ValueError, "permissions"):
                api_key()
        (self.root / ".env").write_bytes(b"\xff\xfe\xff")
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            api_key()

    def test_file_size_is_bounded(self):
        (self.root / ".env").write_bytes(b"#" * 65537)
        with self.assertRaisesRegex(ValueError, "64 KiB"):
            api_key()

    def test_invalid_process_does_not_fall_back_to_user(self):
        for value in ("", "invalid key", "bad\nvalue"):
            with self.subTest(value=value), patch.dict(os.environ, {KEY_NAME: value}):
                with self.assertRaises(ValueError):
                    api_key()
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("zhenzhen_image_mcp.config.user_variable", return_value=""),
        ):
            with self.assertRaises(ValueError):
                api_key()


class EnvFileProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_file_failure_is_visible_without_key_disclosure(self):
        with (
            tempfile.TemporaryDirectory() as root,
            patch("zhenzhen_image_mcp.config.PROJECT_DIR", Path(root)),
        ):
            Path(root, ".env").write_text(f'{KEY_NAME}="private-unclosed-secret', encoding="utf-8")
            async with Client(mcp, mode="legacy") as client:
                result = await client.call_tool(
                    "submit_image_generation",
                    {"model": "gpt-image-2.5-flare", "prompt": "test", "output_dir": root},
                )
            self.assertTrue(result.is_error)
            message = result.content[0].text
            self.assertIn("Invalid project .env syntax", message)
            self.assertNotIn("private-unclosed-secret", message)
