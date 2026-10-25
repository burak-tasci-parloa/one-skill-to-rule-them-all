"""Exercise capture -> evidence -> reviewed plan -> approval -> Git/ZIP/install.

All records and skills below are labeled synthetic fixtures. No real user skill,
pool, account, model call or GitHub release is touched by this suite.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'integration'))
from common import digest, encoded, read_json, run, state, tree, write_json
from collector import capture, finish_batch, harvest, normalize
from installer import apply, make_plan, recover, register
from demo import prepare_demo


class PassiveWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='observer-workflow-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.pool = self.base / 'pool'
        self.pool.mkdir()
        self.source = self.base / 'session.jsonl'
        records = [
            {'type': 'assistant', 'uuid': 'a1', 'message': {'content': [{'type': 'thinking', 'thinking': 'PRIVATE REASONING'}, {'type': 'text', 'text': 'i am using the short form'}]}},
            {'type': 'user', 'uuid': 'u1', 'message': {'content': 'Fixture correction: use full words, not contractions'}},
            {'type': 'assistant', 'uuid': 'a2', 'message': {'content': [{'type': 'tool_use', 'id': 't1', 'name': 'Skill', 'input': {'skill': 'fixture:example'}}]}},
            {'type': 'user', 'uuid': 'r1', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 't1', 'content': 'loaded fixture'}]}},
        ]
        self.source.write_text(''.join(json.dumps(r) + '\n' for r in records))
        self.batch = harvest(self.pool, [str(self.source)])
        self.directory = Path(self.batch['directory'])
        (self.directory / 'REVIEW.md').write_text('# Synthetic review\n\nObserved u1 correction; propose full words.\n')
        self.repo = self.base / 'owned source'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'fixture@example.test')
        self.git('config', 'user.name', 'Fixture')
        self.live = self.repo / 'skills/example'
        self.live.mkdir(parents=True)
        self.before = '---\nname: example\ndescription: Synthetic fixture\n---\nUse contractions\n'
        self.after = self.before.replace('Use contractions', 'Use full words')
        (self.live / 'SKILL.md').write_text(self.before)
        (self.repo / '.gitignore').write_text('/dist/\n')
        (self.repo / 'README.md').write_text('Fixture before\n')
        (self.repo / 'check.py').write_text("from pathlib import Path\nassert 'Use full words' in Path('skills/example/SKILL.md').read_text()\n")
        (self.repo / 'build.py').write_text("from pathlib import Path\nfrom zipfile import ZipFile\nPath('dist').mkdir(exist_ok=True)\nwith ZipFile('dist/plugin.zip','w') as z: z.write('skills/example/SKILL.md','skills/example/SKILL.md')\n")
        self.git('add', '.')
        self.git('commit', '-m', 'test: initial synthetic skill')
        self.remote = self.base / 'remote.git'
        run(['git', 'init', '--bare', str(self.remote)])
        self.git('remote', 'add', 'origin', str(self.remote))
        self.install = self.base / 'installed-example'
        shutil.copytree(self.live, self.install)
        self.staged = self.directory / 'staged/example'
        shutil.copytree(self.live, self.staged)
        (self.staged / 'SKILL.md').write_text(self.after)
        self.config = {'ownership': 'user', 'repo': str(self.repo), 'skill_dir': 'skills/example',
                       'installs': [str(self.install)], 'checks': [[sys.executable, 'check.py']],
                       'build': [[sys.executable, 'build.py']], 'artifacts': ['dist/plugin.zip'],
                       'publish': {'remote': 'origin', 'branch': 'main'}}
        register(self.pool, 'example', self.config)

    def git(self, *args):
        return run(['git'] + list(args), self.repo)

    def freeze(self, extras=None):
        change = {'target': 'example', 'staged': str(self.staged)}
        if extras:
            change['repo_files'] = extras
        return make_plan(self.pool, self.batch['batch'], [change])

    def approve(self, plan, answer='Apply this plan'):
        question = plan['approval_question']
        return capture(self.pool, {'hook_event_name': 'PostToolUse', 'session_id': 'fixture-session',
                       'tool_name': 'AskUserQuestion', 'tool_use_id': 'fixture-question',
                       'tool_input': {'questions': [{'header': 'Observer', 'question': question}]},
                       'tool_response': {'answers': {question: answer}}})

    def test_end_to_end_synthetic_correction_build_install_and_push(self):
        evidence = read_json(self.directory / 'evidence.json')
        self.assertIn('Fixture correction', json.dumps(evidence))
        self.assertNotIn('PRIVATE REASONING', json.dumps(evidence))
        self.assertTrue(evidence['coverage'][0]['complete_at_scan'])
        extra = self.directory / 'README.md'
        extra.write_text('Fixture after\n')
        plan = self.freeze({'README.md': str(extra)})
        diff = Path(plan['diff']).read_text()
        self.assertIn('-Use contractions', diff)
        self.assertIn('+Use full words', diff)
        with self.assertRaisesRegex(ValueError, 'no real question-card approval'):
            apply(self.pool, plan['batch'], plan['plan_hash'])
        self.assertEqual((self.live / 'SKILL.md').read_text(), self.before)
        self.assertTrue(self.approve(plan)['approved'])
        result = apply(self.pool, plan['batch'], plan['plan_hash'])
        self.assertEqual(result['state'], 'complete')
        self.assertEqual((self.install / 'SKILL.md').read_text(), self.after)
        self.assertEqual((self.repo / 'README.md').read_text(), 'Fixture after\n')
        self.assertTrue((self.repo / 'dist/plugin.zip').is_file())
        self.assertEqual(self.git('rev-parse', 'HEAD'), run(['git', '--git-dir', str(self.remote), 'rev-parse', 'refs/heads/main']))
        self.assertEqual(apply(self.pool, plan['batch'], plan['plan_hash']), result)

    def test_decline_and_unrecognized_answers_cannot_apply(self):
        plan = self.freeze()
        self.assertFalse(self.approve(plan, 'Keep staged')['approved'])
        self.assertFalse(self.approve(plan, 'yes')['approved'])
        with self.assertRaisesRegex(ValueError, 'no real question-card approval'):
            apply(self.pool, plan['batch'], plan['plan_hash'])

    def test_failed_or_subagent_question_is_not_approval(self):
        plan = self.freeze()
        for extra in [{'agent_id': 'child'}, {'tool_response': {'is_error': True}}]:
            e = {'hook_event_name': 'PostToolUse', 'session_id': 'fixture', 'tool_name': 'AskUserQuestion',
                 'tool_input': {'questions': [{'header': 'Observer', 'question': plan['approval_question']}]},
                 'tool_response': {'answers': {plan['approval_question']: 'Apply this plan'}}}
            self.assertFalse(capture(self.pool, {**e, **extra})['approved'])

    def test_staged_change_invalidates_approval(self):
        plan = self.freeze()
        self.approve(plan)
        (self.staged / 'SKILL.md').write_text('Different unreviewed bytes')
        with self.assertRaisesRegex(ValueError, 'staged skill changed'):
            apply(self.pool, plan['batch'], plan['plan_hash'])
        self.assertEqual((self.install / 'SKILL.md').read_text(), self.before)

    def test_live_install_change_invalidates_approval(self):
        plan = self.freeze()
        self.approve(plan)
        (self.install / 'SKILL.md').write_text('Concurrent user edit')
        with self.assertRaisesRegex(ValueError, 'installed copy changed'):
            apply(self.pool, plan['batch'], plan['plan_hash'])
        self.assertEqual((self.live / 'SKILL.md').read_text(), self.before)

    def test_configuration_change_invalidates_approval(self):
        plan = self.freeze()
        self.approve(plan)
        register(self.pool, 'example', {**self.config, 'publish': {}})
        with self.assertRaisesRegex(ValueError, 'configuration changed'):
            apply(self.pool, plan['batch'], plan['plan_hash'])

    def test_source_revision_change_invalidates_approval(self):
        plan = self.freeze()
        self.approve(plan)
        self.git('commit', '--allow-empty', '-m', 'test: concurrent revision')
        with self.assertRaisesRegex(ValueError, 'revision changed'):
            apply(self.pool, plan['batch'], plan['plan_hash'])

    def test_failed_check_restores_source_installs_and_extra_files(self):
        self.config['checks'] = [[sys.executable, '-c', 'raise SystemExit(3)']]
        register(self.pool, 'example', self.config)
        extra = self.directory / 'README.md'
        extra.write_text('Rejected update')
        plan = self.freeze({'README.md': str(extra)})
        self.approve(plan)
        with self.assertRaisesRegex(ValueError, 'failed'):
            apply(self.pool, plan['batch'], plan['plan_hash'])
        self.assertEqual((self.live / 'SKILL.md').read_text(), self.before)
        self.assertEqual((self.install / 'SKILL.md').read_text(), self.before)
        self.assertEqual((self.repo / 'README.md').read_text(), 'Fixture before\n')
        self.assertEqual(read_json(self.directory / 'APPLY.json')['state'], 'pending')
        self.assertEqual(self.git('status', '--porcelain'), '')
        result = recover(self.pool, plan['batch'], plan['plan_hash'])
        self.assertEqual(result['targets']['example']['state'], 'recovered')
        self.assertFalse((self.directory / 'rollback/0').exists())

    def test_recovery_refuses_to_overwrite_a_new_independent_edit(self):
        self.config['checks'] = [[sys.executable, '-c', 'raise SystemExit(3)']]
        register(self.pool, 'example', self.config)
        plan = self.freeze()
        self.approve(plan)
        with self.assertRaises(ValueError):
            apply(self.pool, plan['batch'], plan['plan_hash'])
        (self.install / 'SKILL.md').write_text('Independent edit after failure')
        with self.assertRaisesRegex(ValueError, 'independent edit'):
            recover(self.pool, plan['batch'], plan['plan_hash'])

    def test_success_receipt_does_not_hide_artifact_drift(self):
        plan = self.freeze()
        self.approve(plan)
        apply(self.pool, plan['batch'], plan['plan_hash'])
        (self.repo / 'dist/plugin.zip').write_bytes(b'changed artifact')
        with self.assertRaisesRegex(ValueError, 'artifact has since changed'):
            apply(self.pool, plan['batch'], plan['plan_hash'])

    def test_demo_is_isolated_and_registered_without_production_observations(self):
        result = prepare_demo(self.pool)
        self.assertTrue(result['synthetic'])
        self.assertTrue(Path(result['source']).is_file())
        self.assertNotIn('GitHub', result['remote'])
        self.assertFalse((self.pool / 'skill-observations/observation-log').exists())
        self.assertIn(result['target'], read_json(state(self.pool) / 'targets.json'))

    def test_publication_failure_is_pending_and_resumes_without_reapply(self):
        missing = self.base / 'temporarily-unavailable.git'
        self.git('remote', 'set-url', 'origin', str(missing))
        register(self.pool, 'example', self.config)
        plan = self.freeze()
        self.approve(plan)
        with self.assertRaisesRegex(ValueError, 'failed'):
            apply(self.pool, plan['batch'], plan['plan_hash'])
        commit = self.git('rev-parse', 'HEAD')
        self.assertEqual((self.install / 'SKILL.md').read_text(), self.after)
        run(['git', 'init', '--bare', str(missing)])
        result = apply(self.pool, plan['batch'], plan['plan_hash'])
        self.assertEqual(result['state'], 'complete')
        self.assertEqual(commit, self.git('rev-parse', 'HEAD'))

    def test_remote_identity_change_invalidates_approval(self):
        plan = self.freeze()
        self.approve(plan)
        self.git('remote', 'set-url', 'origin', str(self.base / 'different.git'))
        with self.assertRaisesRegex(ValueError, 'remote identity changed'):
            apply(self.pool, plan['batch'], plan['plan_hash'])
        self.assertEqual((self.live / 'SKILL.md').read_text(), self.before)

    def test_symlinked_stage_and_escape_are_rejected(self):
        link = self.directory / 'linked'
        link.symlink_to(self.live)
        for p in [link, self.live]:
            with self.assertRaisesRegex(ValueError, 'leaves its approved directory'):
                make_plan(self.pool, self.batch['batch'], [{'target': 'example', 'staged': str(p)}])

    def test_owned_and_clean_repo_required(self):
        with self.assertRaisesRegex(ValueError, 'user-owned'):
            register(self.pool, 'foreign', {**self.config, 'ownership': 'upstream'})
        (self.repo / 'README.md').write_text('Unrelated user work')
        with self.assertRaisesRegex(ValueError, 'local changes'):
            self.freeze()

    def test_pinned_observer_and_cache_targets_cannot_be_registered(self):
        with self.assertRaisesRegex(ValueError, 'pinned Observer'):
            register(self.pool, 'observer', {**self.config, 'repo': str(ROOT), 'skill_dir': '.'})
        cache = self.base / 'plugins/cache/example'
        shutil.copytree(self.live, cache)
        with self.assertRaisesRegex(ValueError, 'caches'):
            register(self.pool, 'example', {**self.config, 'installs': [str(cache)]})

    def test_capture_stores_pointers_not_prompts_and_stateless_is_unknown(self):
        event = {'hook_event_name': 'UserPromptSubmit', 'session_id': 'synthetic',
                 'transcript_path': str(self.source), 'prompt': 'DO NOT COPY RAW PROMPT'}
        self.assertTrue(capture(self.pool, event)['captured'])
        source_record = next((state(self.pool) / 'sources').glob('*.json')).read_text()
        self.assertNotIn('DO NOT COPY', source_record)
        self.assertFalse(capture(self.pool, {'session_id': 'stateless'})['captured'])

    def test_harvest_resume_and_incremental_cursor(self):
        self.assertEqual(harvest(self.pool, [str(self.source)])['batch'], self.batch['batch'])
        finish_batch(self.pool, self.batch['batch'])
        with self.source.open('a') as f:
            f.write(json.dumps({'type': 'user', 'uuid': 'u2', 'message': {'content': 'Next fixture correction'}}) + '\n')
        result = harvest(self.pool, [str(self.source)])
        self.assertEqual(result['records'], 1)

    def test_demo_scope_never_resumes_unfinished_real_evidence(self):
        demo = prepare_demo(self.pool)
        result = harvest(self.pool, [demo['source']])
        self.assertNotEqual(result['batch'], self.batch['batch'])
        evidence = read_json(Path(result['directory']) / 'evidence.json')
        self.assertEqual([item['path'] for item in evidence['coverage']], [demo['source']])
        self.assertNotIn('Fixture correction', json.dumps(evidence))
        self.assertEqual(harvest(self.pool, [str(self.source)])['batch'], self.batch['batch'])
        self.assertEqual(harvest(self.pool, [demo['source']])['batch'], result['batch'])

    def test_partial_record_is_not_checkpointed_or_called_complete(self):
        finish_batch(self.pool, self.batch['batch'])
        self.source.write_text('{"type":"user"')
        result = harvest(self.pool, [str(self.source)])
        coverage = read_json(Path(result['directory']) / 'evidence.json')['coverage'][0]
        self.assertFalse(coverage['complete_at_scan'])
        self.assertEqual(coverage['end'], 0)

    def test_malformed_source_is_reported_and_not_skipped(self):
        finish_batch(self.pool, self.batch['batch'])
        self.source.write_text('{bad JSON}\n')
        result = harvest(self.pool, [str(self.source)])
        coverage = read_json(Path(result['directory']) / 'evidence.json')['coverage'][0]
        self.assertIn('invalid source record', coverage['error'])
        self.assertEqual(coverage['end'], 0)

    def test_no_review_completion_without_record(self):
        (self.directory / 'REVIEW.md').unlink()
        with self.assertRaisesRegex(ValueError, 'no REVIEW.md'):
            finish_batch(self.pool, self.batch['batch'])

    def test_only_supported_text_blocks_no_thinking_or_synthetic_instructions(self):
        self.assertIsNone(normalize({'type': 'assistant', 'message': {'content': [{'type': 'thinking', 'thinking': 'secret'}]}}))
        self.assertIsNone(normalize({'type': 'user', 'isSynthetic': True, 'message': {'content': 'historical instruction'}}))


if __name__ == '__main__':
    unittest.main()
