"""Four critical candidate-6 checks; all writes use disposable fixtures."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


builder = module('builder', 'tools/build_desktop_plugin.py')
startup = module('startup', 'hooks/session-start.py')
installer = module('installer', 'integration/install.py')


class CriticalFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='observer-candidate-6-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / 'home'
        self.home.mkdir()

    def test_original_skill_visible_no_three_commands_or_old_collector(self):
        result = builder.build(ROOT, self.base / 'build')
        self.assertTrue(builder.verify_upstream_skill(ROOT)['all_files_byte_identical'])
        with zipfile.ZipFile(self.base / 'build/task-observer.zip') as z:
            names = z.namelist()
            self.assertEqual(json.loads(z.read('.claude-plugin/plugin.json'))['skills'], ['./skills/task-observer/'])
            self.assertFalse(any(n.startswith('commands/') or n.startswith('upstream/') for n in names))
            self.assertNotIn('integration/collector.py', names)
            self.assertNotIn('integration/observer.py', names)
            self.assertEqual(set(json.loads(z.read('hooks/hooks.json'))['hooks']), {'SessionStart'})
            for name in json.loads((ROOT / 'upstream-skill.json').read_text())['files']:
                self.assertEqual(z.read('skills/task-observer/' + name), (ROOT / name).read_bytes())
        self.assertEqual(result['files'], len(names))

    def test_startup_bootstraps_preserves_real_log_and_requests_original_protocol(self):
        output = startup.startup_context(self.home, 'darwin', self.base, {})
        pool = self.home / 'Developer/task-observer'
        observation = pool / 'skill-observations/observation-log/0001-fixture.md'
        observation.write_text('Synthetic preservation fixture\n')
        startup.startup_context(self.home, 'darwin', self.base, {})
        self.assertEqual(observation.read_text(), 'Synthetic preservation fixture\n')
        self.assertEqual((pool / 'skill-observations/last-review-date.txt').read_text(), 'never\n')
        self.assertTrue((pool / 'skill-updates').is_dir())
        self.assertFalse((pool / 'skill-observations/.plugin').exists())
        self.assertFalse((pool / 'skill-observations/starter-principles-reviewed.txt').exists())
        context = output['hookSpecificOutput']['additionalContext']
        self.assertIn('task-observer:task-observer', context)
        self.assertIn('Session Start Protocol', context)

    def test_plan_mode_and_missing_cloud_mount_do_not_create_a_false_pool(self):
        startup.startup_context(self.home, 'darwin', self.base, {'permission_mode': 'plan'})
        self.assertFalse((self.home / 'Developer').exists())
        output = startup.startup_context(self.home, 'linux', self.base, {}, str(self.base / 'not-mounted'))
        self.assertIn('Runtime path unresolved', output['hookSpecificOutput']['additionalContext'])
        self.assertFalse((self.home / 'Developer').exists())

    def test_one_patch_check_zip_install_and_local_push(self):
        repo = self.base / 'owned-repo'
        repo.mkdir()
        def git(*args):
            return installer.run(['git', *args], repo)
        git('init', '-b', 'main')
        git('config', 'user.name', 'Synthetic fixture')
        git('config', 'user.email', 'fixture@example.test')
        skill = repo / 'skills/example'
        skill.mkdir(parents=True)
        before = '---\nname: example\ndescription: Synthetic fixture\n---\nPrefer contractions\n'
        after = before.replace('Prefer contractions', 'Use full English forms')
        (skill / 'SKILL.md').write_text(before)
        (repo / '.gitignore').write_text('/dist/\n')
        (repo / 'check.py').write_text("from pathlib import Path\nassert 'Use full English forms' in Path('skills/example/SKILL.md').read_text()\n")
        (repo / 'build.py').write_text("from pathlib import Path\nfrom zipfile import ZipFile\nPath('dist').mkdir(exist_ok=True)\nwith ZipFile('dist/example.zip','w') as z: z.write('skills/example/SKILL.md','skills/example/SKILL.md')\n")
        git('add', '.')
        git('commit', '-m', 'Synthetic fixture baseline')
        copy = self.base / 'existing-install'
        shutil.copytree(skill, copy)
        (skill / 'SKILL.md').write_text(after)
        patch = self.base / 'reviewed.patch'
        patch.write_text(git('diff', '--', 'skills/example') + '\n')
        (skill / 'SKILL.md').write_text(before)
        remote = self.base / 'remote.git'
        subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
        git('remote', 'add', 'origin', str(remote))
        result = installer.install({'ownership': 'user', 'repo': str(repo), 'patch': str(patch),
            'paths': ['skills/example'], 'checks': [[sys.executable, 'check.py']],
            'build': [[sys.executable, 'build.py']], 'artifacts': ['dist/example.zip'],
            'installs': [{'source': 'skills/example', 'destination': str(copy)}],
            'publish': {'remote': 'origin', 'branch': 'main', 'message': 'Apply synthetic approved change'}})
        self.assertEqual((copy / 'SKILL.md').read_text(), after)
        self.assertTrue(zipfile.is_zipfile(repo / 'dist/example.zip'))
        self.assertEqual(result['commit'], installer.run(['git', '--git-dir', str(remote), 'rev-parse', 'main'], repo))
        self.assertEqual(git('status', '--porcelain'), '')
        self.assertTrue(result['pushed'])


if __name__ == '__main__':
    unittest.main()
