"""Exercise startup delivery, persistent storage identity and review boundaries."""
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("startup_hook", ROOT / "hooks/session-start.py")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class StartupHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="observer-startup-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        self.workspace = self.home / "Developer/task-observer"
        self.other = self.base / "unrelated-project"
        self.other.mkdir()

    def initialize(self, root=None):
        root = root or self.workspace
        (root / "skill-observations/observation-log").mkdir(parents=True)
        (root / "skill-updates").mkdir()
        (root / "skill-observations/cross-cutting-principles.md").write_text("# Principles\n\n## Active Principles\n")
        (root / "skill-observations/last-review-date.txt").write_text("never\n")
        return root

    def observation(self, name="0001-test", status="open", root=None, body=""):
        root = root or self.workspace
        path = root / "skill-observations/observation-log" / (name + ".md")
        path.write_text("---\nid: " + str(int(name.split("-")[0])) + "\nstatus: " + status + "\ntitle: Fixture\n---\n" + body)
        return path

    def context(self, **kwargs):
        return hook.activation_context(ROOT, self.home, "darwin", self.other,
                                       today=dt.date(2026, 10, 25), **kwargs)

    def test_first_run_delivers_full_block_without_creating_workspace(self):
        context = self.context()
        self.assertFalse(self.workspace.exists())
        self.assertIn(str(self.workspace), context)
        self.assertIn("template of v3.8.0", context)
        self.assertIn("Task Observer plugin 3.8.4", context)
        self.assertIn("Loading a skill is not complete until", context)
        self.assertIn("A subagent dispatched", context)
        self.assertIn("not initialized/reachable", context)
        self.assertNotIn("0 OPEN observations", context)
        self.assertNotIn("[ABSOLUTE PATH]", context)
        self.assertNotIn("<resolved-runtime-root>", context)
        self.assertLessEqual(len(context), 10000)

    def test_context_is_read_only_and_does_not_claim_protocol_execution(self):
        self.initialize()
        before = {p: p.read_bytes() for p in self.workspace.rglob("*") if p.is_file()}
        context = self.context()
        after = {p: p.read_bytes() for p in self.workspace.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.workspace / hook.PIN).exists())
        self.assertIn("run the", context.lower())
        self.assertIn("0 OPEN observations", context)

    def test_cloud_home_is_never_silently_used_for_a_second_pool(self):
        context = hook.activation_context(ROOT, self.home, "linux", self.other, mounts=[])
        self.assertFalse(self.workspace.exists())
        self.assertIn("runtime path is unresolved", context)
        self.assertNotIn(str(self.workspace), context)
        self.assertIn("[ABSOLUTE PATH]", context)
        self.assertNotIn("0 OPEN observations", context)

    def test_registration_requires_upstream_workspace_creation(self):
        with self.assertRaisesRegex(ValueError, "Workspace creation"):
            hook.register_workspace(self.workspace, ROOT, self.home)
        self.assertFalse(self.workspace.exists())
        self.initialize()
        target = hook.register_workspace(self.workspace, ROOT, self.home)
        first = target.read_bytes()
        hook.register_workspace(self.workspace, ROOT, self.home)
        self.assertEqual(first, target.read_bytes())
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(first)["host_workspace"], str(self.workspace))

    def test_registered_cowork_alias_uses_the_same_host_pin(self):
        alias = self.initialize(self.base / "mounted-folder")
        host = "/Users/example/Developer/task-observer"
        hook.register_workspace(alias, ROOT, self.home, host)
        self.observation(root=alias)
        context = hook.activation_context(ROOT, self.home, "linux", self.other, mounts=[alias])
        self.assertIn(host, context)
        self.assertIn(str(alias), context)
        self.assertIn("1 OPEN observations", context)
        self.assertNotIn("[ABSOLUTE PATH]", context)
        self.assertFalse(self.workspace.exists())

    def test_cloud_directory_name_without_registration_is_not_authority(self):
        impostor = self.initialize(self.base / "task-observer")
        context = hook.activation_context(ROOT, self.home, "linux", self.other, mounts=[impostor])
        self.assertIn("runtime path is unresolved", context)

    def test_two_reachable_registrations_require_reconciliation(self):
        aliases = [self.initialize(self.base / name) for name in ["mount-a", "mount-b"]]
        for alias in aliases:
            hook.register_workspace(alias, ROOT, self.home, "/Users/example/Developer/task-observer")
        with self.assertRaisesRegex(ValueError, "several registered"):
            hook.activation_context(ROOT, self.home, "linux", self.other, mounts=aliases)

    def test_conflicting_registration_is_not_overwritten(self):
        self.initialize()
        pin = hook.register_workspace(self.workspace, ROOT, self.home)
        before = pin.read_bytes()
        with self.assertRaisesRegex(ValueError, "not overwritten"):
            hook.register_workspace(self.workspace, ROOT, self.home,
                                    "/Users/another/Developer/task-observer")
        self.assertEqual(before, pin.read_bytes())

    def test_malformed_registration_does_not_get_adopted(self):
        self.initialize()
        pin = self.workspace / hook.PIN
        for value in [[], {"host_workspace": 123}, {"host_workspace": "/wrong"}]:
            pin.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "invalid workspace registration"):
                self.context()

    def test_ephemeral_override_and_plugin_cache_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "temporary/session"):
            hook.persistent_path(Path("/sessions/test/work"), ROOT, self.home)
        with self.assertRaisesRegex(ValueError, "skill directory"):
            hook.persistent_path(Path("/Users/example/.claude/plugins/cache/x"), ROOT, self.home)
        with self.assertRaisesRegex(ValueError, "plugin installation"):
            hook.persistent_path(ROOT, ROOT, self.home)

    def test_never_and_seven_days_offer_review_without_running_it(self):
        self.initialize()
        self.observation()
        date_file = self.workspace / "skill-observations/last-review-date.txt"
        for date in ["never", "2026-10-18", "2026-09-25"]:
            date_file.write_text(date)
            context = self.context()
            self.assertIn("Offer the original review once", context)
            self.assertEqual(date_file.read_text(), date)
        for date in ["2026-10-19", "2026-10-23", "2026-10-25"]:
            date_file.write_text(date)
            (self.workspace / 'skill-observations/reviews' / date).mkdir(parents=True, exist_ok=True)
            self.assertNotIn("Offer the original review once", self.context())

    def test_only_open_headers_count_not_body_or_archive(self):
        self.initialize()
        self.observation("0001-closed", "actioned", body="status: open\n")
        self.observation("0002-parked", "parked")
        archive = self.workspace / "skill-observations/observation-log/archive"
        archive.mkdir()
        (archive / "0003-old.md").write_text("---\nstatus: open\n---\n")
        context = self.context()
        self.assertIn("0 OPEN observations", context)
        self.assertNotIn("Offer the original review once", context)
        self.observation("0004-open", "open")
        self.assertIn("1 OPEN observations", self.context())

    def test_corrupt_headers_and_dates_do_not_look_healthy(self):
        self.initialize()
        path = self.observation()
        path.write_text("---\nstatus: open\n")
        with self.assertRaisesRegex(ValueError, "header is incomplete"):
            self.context()
        path.unlink()
        (self.workspace / "skill-observations/last-review-date.txt").write_text("invalid")
        with self.assertRaisesRegex(ValueError, "not a date"):
            self.context()

    def test_double_quoted_paths_are_literal_shell_arguments(self):
        path = '/Users/example/quote " $USER `printf wrong` \\ path/Developer/task-observer'
        result = subprocess.check_output(["/bin/bash", "-c", 'printf "%s" "' + hook.shell_double(path) + '"'], text=True)
        self.assertEqual(result, path)

    def test_oversize_context_is_rejected_instead_of_truncated(self):
        long_home = self.base / ("a" * 200) / ("b" * 200)
        with self.assertRaisesRegex(ValueError, "not truncated"):
            hook.activation_context(ROOT, long_home, "darwin", self.other)

    def test_real_wrapper_emits_only_json_and_initializes_only_on_native_macos(self):
        self.initialize()
        env = {**os.environ, "HOME": str(self.home), "CLAUDE_PLUGIN_ROOT": str(ROOT), "TASK_OBSERVER_WORKSPACE": str(self.workspace)}
        result = subprocess.run(["/bin/bash", str(ROOT / "hooks/session-start.sh")],
                                input=json.dumps({"source": "startup", "cwd": str(self.other)}),
                                env=env, text=True, capture_output=True, check=True)
        output = json.loads(result.stdout)
        self.assertEqual(result.stderr, "")
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("0 OPEN observations", output["hookSpecificOutput"]["additionalContext"])
        self.assertEqual((self.workspace / hook.PIN).exists(), sys.platform == 'darwin')

    def test_first_native_start_initializes_storage_without_a_model_or_user_prompt(self):
        self.assertFalse(self.workspace.exists())
        output = hook.startup_context(ROOT, self.home, "darwin", self.other)
        self.assertNotIn("systemMessage", output)
        for rel in hook.WORKSPACE_ITEMS:
            self.assertTrue((self.workspace / rel).exists(), rel)
        directory = self.workspace / "skill-observations"
        self.assertEqual((directory / 'last-review-date.txt').read_text(), 'never\n')
        self.assertEqual(list((directory / 'observation-log').glob('*.md')), [])
        self.assertFalse((directory / 'starter-principles-reviewed.txt').exists())
        self.assertIn('workspace: created=', (directory / 'checkpoints.log').read_text())
        self.assertIn('session-start scan:', (directory / 'checkpoints.log').read_text())
        self.assertEqual(hook.read_pin(self.workspace)['host_workspace'], str(self.workspace))
        self.assertIn('0 OPEN observations', output['hookSpecificOutput']['additionalContext'])

    def test_repeated_startup_preserves_core_files_and_only_adds_real_scan_checkpoints(self):
        hook.startup_context(ROOT, self.home, 'darwin', self.other)
        self.observation(body='Original observation\n')
        principles = self.workspace / 'skill-observations/cross-cutting-principles.md'
        principles.write_text('# Existing adopted principles\n\n## Active Principles\n')
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.workspace.rglob('*') if p.is_file() and p.name != 'checkpoints.log' and '.plugin' not in p.parts}
        hook.startup_context(ROOT, self.home, 'darwin', self.other)
        after = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.workspace.rglob('*') if p.is_file() and p.name != 'checkpoints.log' and '.plugin' not in p.parts}
        self.assertEqual(before, after)

    def test_parallel_first_sessions_create_one_pool_and_one_setup_trace(self):
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: hook.startup_context(ROOT, self.home, 'darwin', self.other), range(2)))
        self.assertTrue(all('systemMessage' not in output for output in results))
        trace = (self.workspace / 'skill-observations/checkpoints.log').read_text()
        self.assertEqual(trace.count('workspace: created='), 1)

    def test_second_machine_uses_its_own_home_without_editing_the_package(self):
        other_home = self.base / 'another-user'
        other_home.mkdir()
        hook.startup_context(ROOT, self.home, 'darwin', self.other)
        hook.startup_context(ROOT, other_home, 'darwin', self.other)
        other_pool = other_home / hook.RELATIVE_WORKSPACE
        self.assertEqual(hook.read_pin(other_pool)['host_workspace'], str(other_pool))
        self.assertNotEqual(hook.read_pin(self.workspace), hook.read_pin(other_pool))

    def test_plan_mode_leaves_no_workspace(self):
        output = hook.startup_context(ROOT, self.home, 'darwin', self.other, permission_mode='plan')
        self.assertFalse(self.workspace.exists())
        self.assertIn('systemMessage', output)

    def test_cowork_requests_access_without_creating_a_cloud_home_pool(self):
        output = hook.startup_context(ROOT, self.home, 'linux', self.other)
        self.assertFalse(self.workspace.exists())
        self.assertIn('systemMessage', output)
        self.assertIn('--start-workspace', output['hookSpecificOutput']['additionalContext'])

    def test_cowork_granted_alias_can_be_initialized_and_reused(self):
        alias = self.base / 'mounted host folder'
        host = '/Users/second-machine/Developer/task-observer'
        hook.initialize_workspace(alias, ROOT, self.home, self.other, host)
        output = hook.startup_context(ROOT, self.home, 'linux', alias)
        self.assertNotIn('systemMessage', output)
        self.assertIn(host, output['hookSpecificOutput']['additionalContext'])
        self.assertFalse(self.workspace.exists())
        self.assertEqual(hook.read_pin(alias)['host_workspace'], host)

    def test_cowork_parent_grant_finds_the_registered_child_next_session(self):
        parent = self.base / 'Developer mount'
        alias = parent / 'task-observer'
        host = '/Users/another-user/Developer/task-observer'
        hook.initialize_workspace(alias, ROOT, self.home, self.other, host)
        context = hook.activation_context(ROOT, self.home, 'linux', self.other, mounts=[parent])
        self.assertIn(str(alias), context)
        self.assertIn(host, context)
        self.assertNotIn('[ABSOLUTE PATH]', context)

    def test_incorrect_storage_types_do_not_count_as_completed_setup(self):
        hook.startup_context(ROOT, self.home, 'darwin', self.other)
        updates = self.workspace / 'skill-updates'
        updates.rmdir()
        updates.write_text('This is a file, not a directory\n')
        self.assertFalse(hook.workspace_complete(self.workspace))
        with self.assertRaisesRegex(ValueError, 'unexpected file type'):
            hook.startup_context(ROOT, self.home, 'darwin', self.other)
        self.assertEqual(updates.read_text(), 'This is a file, not a directory\n')

    def test_existing_other_store_stops_setup_without_a_second_pool(self):
        alternate = self.home / '.claude/skill-observations'
        alternate.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'other observer stores/pins'):
            hook.startup_context(ROOT, self.home, 'darwin', self.other)
        self.assertFalse(self.workspace.exists())

    def test_configured_other_root_stops_setup_even_if_not_yet_created(self):
        (self.other / 'CLAUDE.md').write_text('Observer path: /Users/example/other-pool/skill-observations/\n')
        with self.assertRaisesRegex(ValueError, 'other observer stores/pins'):
            hook.startup_context(ROOT, self.home, 'darwin', self.other)
        self.assertFalse(self.workspace.exists())

    def test_legacy_and_redirected_stores_are_never_overwritten(self):
        directory = self.workspace / 'skill-observations'
        directory.mkdir(parents=True)
        for name in ['log.md', 'MOVED.md']:
            file = directory / name
            file.write_text('Existing history\n')
            with self.assertRaises(ValueError):
                hook.startup_context(ROOT, self.home, 'darwin', self.other)
            self.assertEqual(file.read_text(), 'Existing history\n')
            self.assertFalse((directory / 'observation-log').exists())
            file.unlink()

    def test_setup_refuses_symlinks_into_another_folder(self):
        directory = self.workspace / 'skill-observations'
        directory.mkdir(parents=True)
        victim = self.base / 'must-not-change.txt'
        victim.write_text('Keep this content\n')
        (directory / 'cross-cutting-principles.md').symlink_to(victim)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            hook.startup_context(ROOT, self.home, 'darwin', self.other)
        self.assertEqual(victim.read_text(), 'Keep this content\n')

    def test_setup_uses_literal_paths_with_spaces_and_shell_syntax(self):
        home = self.base / 'home " $USER `echo should-not-run`'
        home.mkdir()
        hook.startup_context(ROOT, home, 'darwin', self.other)
        workspace = home / hook.RELATIVE_WORKSPACE
        self.assertTrue(hook.workspace_complete(workspace))
        self.assertEqual(hook.read_pin(workspace)['host_workspace'], str(workspace))

    def test_explicit_setup_command_runs_the_packaged_procedure(self):
        alias = self.base / 'granted folder'
        host = '/Users/another-user/Developer/task-observer'
        env = {**os.environ, 'HOME': str(self.home), 'CLAUDE_PLUGIN_ROOT': str(ROOT)}
        result = subprocess.run(['/bin/bash', str(ROOT / 'hooks/session-start.sh'),
                                 '--initialize-workspace', str(alias), '--host-workspace', host],
                                env=env, text=True, capture_output=True, check=True)
        self.assertIn('Initialized persistent workspace', result.stdout)
        self.assertTrue(hook.workspace_complete(alias))
        before = {p:p.read_bytes() for p in alias.rglob('*') if p.is_file()}
        result = subprocess.run(['/bin/bash', str(ROOT / 'hooks/session-start.sh'),
                                 '--initialize-workspace', str(alias), '--host-workspace', host],
                                env=env, text=True, capture_output=True, check=True)
        self.assertIn('Verified existing persistent workspace', result.stdout)
        self.assertEqual(before, {p:p.read_bytes() for p in alias.rglob('*') if p.is_file()})

    def test_missing_python_reports_incomplete_activation(self):
        env = {**os.environ, "PATH": str(self.other)}
        result = subprocess.run(["/bin/bash", str(ROOT / "hooks/session-start.sh")],
                                env=env, text=True, capture_output=True, check=True)
        self.assertIn("python3 is unavailable", json.loads(result.stdout)["systemMessage"])

    def test_malformed_hook_payload_reports_incomplete_activation(self):
        result = subprocess.run(["/bin/bash", str(ROOT / "hooks/session-start.sh")], input="{broken",
                                text=True, capture_output=True, check=True)
        self.assertIn("activation incomplete", json.loads(result.stdout)["systemMessage"])

    def test_delegated_worker_does_not_repeat_startup(self):
        result = subprocess.run(["/bin/bash", str(ROOT / "hooks/session-start.sh")],
                                input=json.dumps({"agent_id": "child"}),
                                text=True, capture_output=True, check=True)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
