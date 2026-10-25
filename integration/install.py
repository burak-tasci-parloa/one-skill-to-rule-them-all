#!/usr/bin/env python3
"""Apply an explicitly approved patch with existing repo checks/builds and installs.

Approval is obtained in the host conversation, not manufactured by this helper.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


def run(argv, repo):
    if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) for arg in argv):
        raise ValueError('commands must be explicit argv arrays')
    result = subprocess.run(argv, cwd=repo, text=True, capture_output=True, timeout=120)
    if result.returncode:
        raise ValueError((result.stderr or result.stdout).strip())
    return result.stdout.strip()


def relative(value):
    path = Path(value)
    if not value or path.is_absolute() or '..' in path.parts or '.git' in path.parts or path == Path('.'):
        raise ValueError('expected a specific repo-relative path: ' + str(value))
    return path


def members(root):
    files = {}
    for p in root.rglob('*'):
        if p.is_symlink():
            raise ValueError('resolve linked skill members before installation: ' + str(p))
        if p.is_file() and not any(x in p.relative_to(root).parts for x in ['.git', '__pycache__', '.DS_Store']):
            files[p.relative_to(root)] = p.read_bytes()
    return files


def install(plan):
    if plan.get('ownership') != 'user':
        raise ValueError('only confirmed user-owned sources may be installed')
    repo = Path(plan['repo']).expanduser().resolve()
    if run(['git', 'rev-parse', '--show-toplevel'], repo) != str(repo):
        raise ValueError('repo must be the canonical Git root')
    if (repo / 'upstream-skill.json').exists():
        raise ValueError('the pinned Observer source is not an installation target')
    if run(['git', 'status', '--porcelain', '--untracked-files=all'], repo):
        raise ValueError('source has local changes; reconcile them first without discarding work')
    paths = [str(relative(p)) for p in plan['paths']]
    if not paths:
        raise ValueError('name the approved source paths')
    patch = str(Path(plan['patch']).expanduser().resolve(strict=True))
    copies = []
    for item in plan.get('installs', []):
        source = (repo / relative(item['source'])).resolve()
        target = Path(item['destination']).expanduser().resolve()
        if not source.is_relative_to(repo) or not (source / 'SKILL.md').is_file() or not (target / 'SKILL.md').is_file():
            raise ValueError('install needs an existing source skill and existing physical installation')
        if any(x in str(target) + '/' for x in ['/plugins/cache/', '/plugins/synced/']):
            raise ValueError('do not edit plugin caches; deliver their ZIP to the user')
        if source != target and (source in target.parents or target in source.parents):
            raise ValueError('source and installation may not overlap')
        if source != target:
            members(source)
            members(target)
            copies.append((source, target))
    stat = run(['git', 'apply', '--numstat', '-z', '--', patch], repo)
    changed = [record.split('\t', 2)[2] for record in stat.split('\0') if record]
    if not changed or any(not any(name == p or name.startswith(p + '/') for p in paths) for name in changed):
        raise ValueError('patch contains paths outside the approved selection')
    run(['git', 'apply', '--check', '--', patch], repo)
    run(['git', 'apply', '--', patch], repo)
    for command in plan.get('checks', []) + plan.get('build', []):
        run(command, repo)
    artifacts = []
    for name in plan.get('artifacts', []):
        artifact = (repo / relative(name)).resolve(strict=True)
        if not artifact.is_relative_to(repo) or not artifact.is_file():
            raise ValueError('artifact must be a file inside the source repo')
        if artifact.suffix == '.zip':
            with zipfile.ZipFile(artifact) as bundle:
                if bundle.testzip():
                    raise ValueError('invalid ZIP: ' + name)
        artifacts.append(str(artifact))
    for source, target in copies:
        expected = members(source)
        for name in set(members(target)) - set(expected):
            (target / name).unlink()
        shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git', '__pycache__', '.DS_Store'))
        if members(target) != expected:
            raise ValueError('installed copy did not verify: ' + str(target))
    result = {'source': str(repo), 'installed': [str(target) for _, target in copies], 'artifacts': artifacts}
    if plan.get('publish'):
        publish = plan['publish']
        branch, remote = publish['branch'], publish['remote']
        if not branch or branch.startswith('-') or not remote or remote.startswith('-'):
            raise ValueError('publish needs the explicitly approved remote and branch')
        run(['git', 'add', '--'] + paths, repo)
        run(['git', 'commit', '-m', publish['message']], repo)
        result['commit'] = run(['git', 'rev-parse', 'HEAD'], repo)
        run(['git', 'push', remote, result['commit'] + ':refs/heads/' + branch], repo)
        observed = run(['git', 'ls-remote', remote, 'refs/heads/' + branch], repo).split()
        if not observed or observed[0] != result['commit']:
            raise ValueError('remote commit could not be verified')
        result['pushed'] = True
    return result


if __name__ == '__main__':
    try:
        print(json.dumps(install(json.loads(Path(sys.argv[1]).read_text())), indent=2))
    except Exception as exc:
        print('Installation incomplete: ' + str(exc) + '\nInspect the source Git diff and installed paths before continuing. No automatic rollback, retry, lock deletion or permission bypass was attempted.', file=sys.stderr)
        sys.exit(1)
