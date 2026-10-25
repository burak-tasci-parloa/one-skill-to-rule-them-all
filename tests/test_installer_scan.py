"""Verify actual upstream scan execution and complete, bounded result delivery."""
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer_scan', ROOT / 'hooks/session-start.py')
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class InstallerScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='observer-scan-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / 'home'
        self.home.mkdir()
        self.project = self.base / 'project'
        self.project.mkdir()
        self.workspace = self.home / hook.RELATIVE_WORKSPACE
        hook.initialize_workspace(self.workspace, ROOT, self.home, self.project)

    def add_observation(self, index=1, title='A useful finding', status='open', body='BODY MUST STAY OUT'):
        directory = self.workspace / 'skill-observations/observation-log'
        status_line = '' if status is None else 'status: ' + status + '\n'
        path = directory / ('%04d-fixture.md' % index)
        path.write_text('---\nid: %d\n%stitle: %s\nskill: [fixture]\n---\n%s\n' %
                        (index, status_line, title, body))
        return path

    def delivered_text(self, output):
        context = output['hookSpecificOutput']['additionalContext']
        self.assertLessEqual(len(context), hook.CONTEXT_LIMIT)
        reports = list((self.workspace / 'skill-observations/.plugin/startup-scans').glob('*.txt'))
        if reports:
            self.assertEqual(len(reports), 1)
            self.assertIn(str(reports[0]), context)
            self.assertEqual(reports[0].stat().st_mode & 0o777, 0o600)
            return reports[0].read_text()
        return context

    def test_real_scan_checkpoint_and_headers_are_delivered_without_observation_bodies(self):
        self.add_observation()
        output = hook.startup_context(ROOT, self.home, 'darwin', self.project)
        text = self.delivered_text(output)
        self.assertIn('files: 1  parsed: 1', text)
        self.assertIn('title: A useful finding', text)
        self.assertIn('end of scan — files: 1', text)
        self.assertNotIn('BODY MUST STAY OUT', text)
        trace = (self.workspace / 'skill-observations/checkpoints.log').read_text()
        self.assertEqual(trace.count('session-start scan:'), 1)
        self.assertFalse((self.workspace / 'skill-observations/starter-principles-reviewed.txt').exists())

    def test_large_scan_keeps_every_header_and_the_full_original_activation_block(self):
        for index in range(1, 81):
            self.add_observation(index, title=('Finding %d ' % index) + ('important context ' * 20))
        text = self.delivered_text(hook.startup_context(ROOT, self.home, 'darwin', self.project))
        self.assertIn('template of v3.8.0', text)
        self.assertIn('end of scan — files: 80', text)
        for index in range(1, 81):
            self.assertIn('title: Finding %d ' % index, text)
        self.assertNotIn('BODY MUST STAY OUT', text)
        self.assertEqual((self.workspace / 'skill-observations/last-review-date.txt').read_text(), 'never\n')

    def test_small_payload_is_delivered_inline_without_creating_an_output_file(self):
        text = hook.deliver_scan('Activation fixture', 'Complete output\n', self.workspace, ROOT)
        self.assertIn('<task-observer-scan-data>\nComplete output\n', text)
        self.assertFalse((self.workspace / 'skill-observations/.plugin').exists())

    def test_broken_real_scan_does_not_create_a_success_checkpoint(self):
        path = self.add_observation()
        path.write_text('No frontmatter here\n')
        with self.assertRaisesRegex(ValueError, 'scan incomplete'):
            hook.startup_context(ROOT, self.home, 'darwin', self.project)
        trace = (self.workspace / 'skill-observations/checkpoints.log').read_text()
        self.assertNotIn('session-start scan:', trace)

    def test_missing_end_record_is_not_accepted_as_a_successful_scan(self):
        result = subprocess.CompletedProcess([], 0, stdout='partial output\n', stderr='')
        with patch.object(hook.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(ValueError, 'no complete end-of-scan'):
                hook.run_startup_scan(ROOT, self.workspace, self.project)

    def test_failed_or_warned_scan_cannot_be_reported_as_healthy(self):
        for result in [subprocess.CompletedProcess([], 1, 'failure', ''),
                       subprocess.CompletedProcess([], 0, 'partial output', 'permission denied')]:
            with self.subTest(returncode=result.returncode), patch.object(hook.subprocess, 'run', return_value=result):
                with self.assertRaisesRegex(ValueError, 'scan incomplete'):
                    hook.run_startup_scan(ROOT, self.workspace, self.project)

    def test_read_only_plan_does_not_append_a_scan_checkpoint(self):
        checkpoint = self.workspace / 'skill-observations/checkpoints.log'
        before = checkpoint.read_bytes()
        hook.startup_context(ROOT, self.home, 'darwin', self.project, permission_mode='plan')
        self.assertEqual(before, checkpoint.read_bytes())

    def test_unverified_registered_alias_does_not_get_written(self):
        checkpoint = self.workspace / 'skill-observations/checkpoints.log'
        before = checkpoint.read_bytes()
        output = hook.startup_context(ROOT, self.home, 'linux', self.workspace)
        self.assertEqual(before, checkpoint.read_bytes())
        self.assertIn('Installer scan pending', output['hookSpecificOutput']['additionalContext'])

    def test_verified_cloud_start_command_runs_setup_and_scan_without_a_manual_second_step(self):
        alias = self.base / 'granted pool'
        cloud_home = self.base / 'cloud-home'
        cloud_home.mkdir()
        env = {**os.environ, 'HOME': str(cloud_home), 'CLAUDE_PLUGIN_ROOT': str(ROOT)}
        result = subprocess.run(['bash', str(ROOT / 'hooks/session-start.sh'), '--start-workspace', str(alias),
                                 '--host-workspace', '/Users/another-user/Developer/task-observer'],
                                cwd=str(self.project), env=env, text=True, capture_output=True, check=True)
        output = json.loads(result.stdout)
        self.assertNotIn('systemMessage', output)
        self.assertEqual((alias / 'skill-observations/checkpoints.log').read_text().count('session-start scan:'), 1)
        self.assertTrue(hook.workspace_complete(alias))

    def test_missing_status_remains_open_as_upstream_requires(self):
        self.add_observation(status=None)
        self.assertIn('1 OPEN observations', hook.review_state(self.workspace, dt.date(2026, 10, 25)))

    def test_incomplete_or_recordless_review_does_not_count_as_a_recent_review(self):
        self.add_observation()
        folder = self.workspace / 'skill-observations'
        (folder / 'last-review-date.txt').write_text('2026-10-25\n')
        self.assertIn('left no record', hook.review_state(self.workspace, dt.date(2026, 10, 25)))
        (folder / 'reviews/2026-10-25').mkdir(parents=True)
        (folder / 'review-started.txt').write_text('started 2026-10-25\n')
        self.assertIn('Offer the original review once', hook.review_state(self.workspace, dt.date(2026, 10, 25)))
        (folder / 'review-started.txt').write_text('completed 2026-10-25\n')
        self.assertNotIn('Offer the original review once', hook.review_state(self.workspace, dt.date(2026, 10, 25)))

    def test_starter_offer_is_cued_but_no_answer_is_fabricated(self):
        marker = self.workspace / 'skill-observations/starter-principles-reviewed.txt'
        text = hook.deliver_scan('Activation', 'Scan', self.workspace, ROOT)
        self.assertIn('STARTER RECONCILIATION PENDING', text)
        self.assertFalse(marker.exists())
        marker.write_text('4\n')
        self.assertNotIn('STARTER RECONCILIATION PENDING', hook.deliver_scan('Activation', 'Scan', self.workspace, ROOT))
        self.assertEqual(marker.read_text(), '4\n')


if __name__ == '__main__':
    unittest.main()
