"""Checks protect Desktop upload compatibility and complete skill delivery."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("desktop_builder", ROOT / "tools/build_desktop_plugin.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class DesktopPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="task-observer-package-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "source"
        self.repo.mkdir()
        for name in [".claude-plugin", "references", "scripts", "hooks"]:
            shutil.copytree(ROOT / name, self.repo / name)
        for name in ["SKILL.md", "LICENSE", "DESKTOP-PLUGIN.md"]:
            shutil.copy2(ROOT / name, self.repo / name)

    def build(self):
        return builder.build(self.repo)

    def test_layout_complete_resources_and_reproducible_bytes(self):
        self.build()
        archive = self.repo / "dist/task-observer.zip"
        first = archive.read_bytes()
        with zipfile.ZipFile(archive) as bundle:
            manifest = json.loads(bundle.read(".claude-plugin/plugin.json"))
            self.assertNotIn("$schema", manifest)
            self.assertEqual(manifest["skills"], ["./skills/task-observer"])
            self.assertIn("skills/task-observer/SKILL.md", bundle.namelist())
            self.assertNotIn("SKILL.md", bundle.namelist())
            hooks = json.loads(bundle.read("hooks/hooks.json"))["hooks"]
            self.assertEqual(set(hooks), {"SessionStart"})
            self.assertIn("hooks/session-start.py", bundle.namelist())
            for file in (self.repo / "references").glob("*"):
                self.assertEqual(bundle.read("skills/task-observer/references/" + file.name), file.read_bytes())
            self.assertEqual(bundle.read("LICENSE"), (ROOT / "LICENSE").read_bytes())
        self.build()
        self.assertEqual(first, archive.read_bytes())

    def test_schema_regression_stops_build(self):
        path = self.repo / ".claude-plugin/plugin.json"
        manifest = json.loads(path.read_text())
        manifest["$schema"] = "https://json.schemastore.org/claude-code-plugin-manifest.json"
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "Unsupported upload manifest keys"):
            self.build()

    def test_source_manifest_explicitly_exposes_the_root_skill(self):
        manifest = json.loads((self.repo / ".claude-plugin/plugin.json").read_text())
        self.assertEqual(manifest["skills"], ["./"])
        discovered = [self.repo / p / "SKILL.md" for p in manifest["skills"]
                      if (self.repo / p / "SKILL.md").is_file()]
        self.assertEqual(len(discovered), 1)

    def test_packaged_hook_uses_the_packaged_skill_directory(self):
        self.build()
        plugin = self.repo / "dist/plugin"
        home = Path(self.temp.name) / "home"
        home.mkdir()
        workspace = home / "Developer/task-observer"
        env = {**os.environ, "HOME": str(home), "CLAUDE_PLUGIN_ROOT": str(plugin),
               "TASK_OBSERVER_WORKSPACE": str(workspace)}
        result = subprocess.run(["/bin/bash", str(plugin / "hooks/session-start.sh")],
                                input='{"source":"startup"}', env=env, text=True,
                                capture_output=True, check=True)
        output = json.loads(result.stdout)
        self.assertNotIn("systemMessage", output)
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn(str(plugin / "skills/task-observer/scripts/skill-load.sh"), context)
        self.assertIn("template of v3.8.4", context)
        self.assertEqual(workspace.exists(), sys.platform == 'darwin')
        if sys.platform == 'darwin':
            self.assertTrue((workspace / 'skill-observations/plugin-activation.json').is_file())

    def test_missing_hook_is_not_silently_omitted(self):
        (self.repo / "hooks/session-start.py").unlink()
        with self.assertRaisesRegex(ValueError, "Missing startup integration"):
            self.build()

    def test_changed_hook_invalidates_existing_archive(self):
        self.build()
        path = self.repo / "hooks/session-start.py"
        path.write_text(path.read_text() + "\n# Changed after build\n")
        with self.assertRaisesRegex(ValueError, "content mismatch"):
            builder.verify(self.repo, self.repo / "dist/task-observer.zip")

    def test_missing_archived_reference_is_rejected(self):
        self.build()
        archive = self.repo / "dist/task-observer.zip"
        with zipfile.ZipFile(archive) as bundle:
            files = {n: bundle.read(n) for n in bundle.namelist() if not n.endswith("references/signals.md")}
        with zipfile.ZipFile(archive, "w") as bundle:
            for name, data in files.items():bundle.writestr(name, data)
        with self.assertRaisesRegex(ValueError, "membership mismatch"):
            builder.verify(self.repo, archive)

    def test_existing_source_change_invalidates_archive(self):
        self.build()
        path = self.repo / "references/signals.md"
        path.write_text(path.read_text() + "\nAdditional source content\n")
        with self.assertRaisesRegex(ValueError, "content mismatch"):
            builder.verify(self.repo, self.repo / "dist/task-observer.zip")

    def test_symlinked_source_is_rejected(self):
        path = self.repo / "references/signals.md"
        path.unlink()
        path.symlink_to(ROOT / "references/signals.md")
        with self.assertRaisesRegex(ValueError, "Symlink in source"):
            self.build()

    def test_unresolved_upload_readme_link_is_rejected(self):
        path = self.repo / "DESKTOP-PLUGIN.md"
        path.write_text(path.read_text() + "\n[Missing guide](missing-guide.md)\n")
        with self.assertRaisesRegex(ValueError, "Unresolved upload README link"):
            self.build()

    def test_unmanaged_staging_content_is_preserved(self):
        staging = self.repo / "dist/plugin"
        staging.mkdir(parents=True)
        sentinel = staging / "keep.txt"
        sentinel.write_text("unrelated content\n")
        with self.assertRaisesRegex(ValueError, "unmanaged staging path"):
            self.build()
        self.assertEqual(sentinel.read_text(), "unrelated content\n")


if __name__ == "__main__":
    unittest.main()
