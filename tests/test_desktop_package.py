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
        for name in [".claude-plugin", "references", "scripts", "hooks", "integration", "commands"]:
            shutil.copytree(ROOT / name, self.repo / name)
        for name in ["SKILL.md", "LICENSE", "DESKTOP-PLUGIN.md", "upstream-skill.json"]:
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
            self.assertEqual(manifest["skills"], [])
            self.assertIn("upstream/task-observer/SKILL.md", bundle.namelist())
            self.assertNotIn("SKILL.md", bundle.namelist())
            hooks = json.loads(bundle.read("hooks/hooks.json"))["hooks"]
            self.assertEqual(set(hooks), {"SessionStart", "UserPromptSubmit", "Stop", "PostToolUse"})
            self.assertTrue(hooks["Stop"][0]["hooks"][0]["async"])
            self.assertNotIn("PreToolUse", hooks)
            self.assertIn("commands/review.md", bundle.namelist())
            self.assertIn("commands/apply.md", bundle.namelist())
            self.assertIn("hooks/session-start.py", bundle.namelist())
            for file in (self.repo / "references").glob("*"):
                self.assertEqual(bundle.read("upstream/task-observer/references/" + file.name), file.read_bytes())
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

    def test_source_manifest_does_not_implicitly_load_the_live_protocol(self):
        manifest = json.loads((self.repo / ".claude-plugin/plugin.json").read_text())
        self.assertEqual(manifest["skills"], [])
        for name in ['review', 'apply', 'status']:
            command = (self.repo / 'commands' / (name + '.md')).read_text()
            self.assertIn('disable-model-invocation: true', command)

    def test_packaged_capture_is_passive_and_original_skill_is_unchanged(self):
        lock = json.loads((self.repo / 'upstream-skill.json').read_text())
        original = {name: (self.repo / name).read_bytes() for name in lock['files']}
        self.build()
        plugin = self.repo / 'dist/plugin'
        home = Path(self.temp.name) / 'home'
        home.mkdir()
        workspace = home / 'Developer/task-observer'
        env = {**os.environ, 'HOME': str(home), 'CLAUDE_PLUGIN_ROOT': str(plugin),
               'TASK_OBSERVER_WORKSPACE': str(workspace)}
        payload = json.dumps({'hook_event_name': 'SessionStart', 'source': 'startup',
                              'session_id': 'fixture', 'transcript_path': str(home / 'session.jsonl')})
        result = subprocess.run(['/bin/bash', str(plugin / 'integration/observer.sh'), 'capture'],
                                input=payload, env=env, text=True, capture_output=True, check=True)
        self.assertEqual(result.stdout, '')  # No Skill invocation, question or protocol context.
        if sys.platform == 'darwin':
            sources = list((workspace / 'skill-observations/.plugin/sources').glob('*.json'))
            self.assertEqual(len(sources), 1)
            self.assertFalse((workspace / 'skill-observations/starter-principles-reviewed.txt').exists())
        self.assertEqual(original, {name: (self.repo / name).read_bytes() for name in lock['files']})
        with zipfile.ZipFile(self.repo / 'dist/task-observer.zip') as bundle:
            for name, data in original.items():
                self.assertEqual(bundle.read('upstream/task-observer/' + name), data)
                self.assertEqual((plugin / 'upstream/task-observer' / name).read_bytes(), data)

    def test_upstream_edit_prevents_a_new_build(self):
        path = self.repo / 'SKILL.md'
        path.write_text(path.read_text() + '\nAn accidental behavioral edit.\n')
        with self.assertRaisesRegex(ValueError, 'Upstream skill content mismatch'):
            self.build()

    def test_added_upstream_reference_prevents_a_new_build(self):
        (self.repo / 'references/custom-instructions.md').write_text('Keep integration outside the skill.\n')
        with self.assertRaisesRegex(ValueError, 'Upstream skill membership mismatch'):
            self.build()

    def test_stale_starter_metadata_cannot_trigger_the_wrong_reconciliation(self):
        path = self.repo / 'upstream-skill.json'
        lock = json.loads(path.read_text())
        lock['starter_set_version'] += 1
        path.write_text(json.dumps(lock))
        with self.assertRaisesRegex(ValueError, 'starter set version mismatch'):
            self.build()

    def test_plugin_version_is_independent_of_the_upstream_skill_version(self):
        path = self.repo / '.claude-plugin/plugin.json'
        manifest = json.loads(path.read_text())
        manifest['version'] = '3.8.5'
        path.write_text(json.dumps(manifest))
        self.build()
        with zipfile.ZipFile(self.repo / 'dist/task-observer.zip') as bundle:
            self.assertEqual(json.loads(bundle.read('.claude-plugin/plugin.json'))['version'], '3.8.5')
            self.assertIn(b'version: "3.8.0"', bundle.read('upstream/task-observer/SKILL.md'))
        self.assertEqual(builder.verify_upstream_skill(self.repo)['upstream_version'], '3.8.0')

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
