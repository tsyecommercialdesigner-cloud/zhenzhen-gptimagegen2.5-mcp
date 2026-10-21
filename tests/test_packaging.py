import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from zhenzhen_image_mcp.checkpoints import CheckpointStore

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package_user", ROOT / "scripts/package_user.py")
packaging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packaging)


class PackagingTests(unittest.TestCase):
    def test_unique_project_root_private_env_acl_and_checkpoints_survive_overlay(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            archive = base / "member.zip"
            names = packaging.audited_files(ROOT)
            packaging.write_archive(ROOT, archive, names)
            install = base / "install"
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(set(z.namelist()), {f"{packaging.PROJECT_NAME}/{name}" for name in names})
                self.assertEqual(z.read(f"{packaging.PROJECT_NAME}/LICENSE"), (ROOT / "LICENSE").read_bytes())
                z.extractall(install)
            project = install / packaging.PROJECT_NAME
            private = project / ".env"
            private.write_text("ZHENZHEN_GPTIMAGEGEN_API_KEY=upgrade-test-placeholder\n", encoding="utf-8")
            before = private.read_bytes()
            mode = private.stat().st_mode
            acl = subprocess.check_output(["icacls.exe", str(private)]) if os.name == "nt" else None
            checkpoints = CheckpointStore(project / ".runtime")
            checkpoints.reserve(
                "upgrade",
                "thread",
                [
                    {
                        "task_id": "page_01",
                        "fingerprint": "upgrade-probe",
                        "base_url": "https://provider.example/v1",
                        "output_dir": str(project),
                        "group": "reverse",
                    }
                ],
            )
            self.assertTrue(checkpoints.claim("upgrade", "thread", "page_01"))
            checkpoints.finish("upgrade", "thread", "page_01", "provider_upgrade_01")
            checkpoint_before = checkpoints.path.read_bytes()
            with zipfile.ZipFile(archive) as z:
                z.extractall(install)
            self.assertEqual(private.read_bytes(), before)
            self.assertEqual(private.stat().st_mode, mode)
            if acl is not None:
                self.assertEqual(subprocess.check_output(["icacls.exe", str(private)]), acl)
            self.assertTrue((project / "pyproject.toml").is_file())
            self.assertEqual(checkpoints.path.read_bytes(), checkpoint_before)
            self.assertFalse(checkpoints.claim("upgrade", "thread", "page_01"))
            self.assertEqual(
                checkpoints.get("upgrade", "thread", "page_01")["provider_task_id"], "provider_upgrade_01"
            )

    def test_archive_project_name_rejects_paths_and_windows_device_names(self):
        for name in ("", ".", "..", "../escape", "C:/escape", "A\\B", "CON", "LPT1", "name."):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                with self.assertRaises(ValueError):
                    packaging.write_archive(ROOT, Path(temporary) / "unused.zip", [], name)

    def test_allowlist_rejects_bad_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = json.loads((ROOT / "user-files.json").read_text(encoding="utf-8"))
            for name in names:
                dest = root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, dest)
            self.assertEqual(set(packaging.audited_files(root)), set(names))
            bad_lists = [
                [x for x in names if x != "LICENSE"],
                names + [names[0]],
                names + ["../outside.py"],
                names + ["C:/secret"],
                names + [".env"],
                names + ["tests/test_core.py"],
                names + ["src/zhenzhen_image_mcp/missing.py"],
                [x for x in names if not x.endswith("__main__.py")],
                names + [".env"],
                names + [".env.saved.bak"],
            ]
            for bad in bad_lists:
                (root / "user-files.json").write_text(json.dumps(bad), encoding="utf-8")
                with self.assertRaises(ValueError):
                    packaging.audited_files(root)
            (root / "user-files.json").write_text(json.dumps(names), encoding="utf-8")
            (root / ".env.example").write_text(
                "ZHENZHEN_GPTIMAGEGEN_API_KEY=do-not-distribute\nZHENZHEN_GPTIMAGEGEN_API_KEY=\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "empty API key"):
                packaging.audited_files(root)

    def test_all_document_json_is_strict_and_formatted(self):
        count = 0
        for path in [ROOT / "README.md", ROOT / "MANUAL.md"]:
            for raw in re.findall(r"```json\n(.*?)\n```", path.read_text(encoding="utf-8"), re.S):
                obj = json.loads(raw)
                self.assertEqual(raw, json.dumps(obj, indent=2, ensure_ascii=False))
                count += 1
        self.assertGreaterEqual(count, 11)


if __name__ == "__main__":
    unittest.main()
