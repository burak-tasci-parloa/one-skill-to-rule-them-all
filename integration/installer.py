"""Freeze a review, bind real approval to it, then install owned targets."""
import difflib
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile
from urllib.parse import urlsplit

from common import (atomic, batch_path, digest, encoded, inside, lock, now,
                    read_json, run, safe_relative, state, tree, write_json, ROOT)


def target_config(config):
    value = dict(config)
    if value.get('ownership') != 'user':
        raise ValueError('automatic installation is only for explicitly confirmed user-owned targets')
    repo = Path(value['repo']).expanduser().resolve()
    if run(['git', 'rev-parse', '--show-toplevel'], repo) != str(repo):
        raise ValueError('target repo must be its Git root')
    rel = safe_relative(value['skill_dir'])
    source = inside(repo / rel, repo)
    # The upstream Observer is intentionally locked, including in its own fork.
    if repo == ROOT.resolve() or (repo / 'upstream-skill.json').exists():
        raise ValueError('the pinned Observer bundle is not an automatic review target')
    if not (source / 'SKILL.md').is_file():
        raise ValueError('target has no SKILL.md')
    installs = []
    for name in value.get('installs', []):
        p = Path(name).expanduser().resolve()
        if any(s in str(p) + '/' for s in ['/plugins/cache/', '/plugins/synced/']):
            raise ValueError('plugin caches are not editable owned installations')
        if not p.is_dir() or not (p / 'SKILL.md').is_file():
            raise ValueError('install target must already contain the named skill')
        if p != source:
            installs.append(str(p))
    value.update(repo=str(repo), skill_dir=rel.as_posix(), installs=sorted(set(installs)))
    for field in ['checks', 'build']:
        commands = value.get(field, [])
        if not isinstance(commands, list) or any(not isinstance(cmd, list) or not cmd or
           any(not isinstance(arg, str) or '\x00' in arg for arg in cmd) for cmd in commands):
            raise ValueError(field + ' must contain explicit argv arrays, not shell command strings')
        value[field] = commands
    value['artifacts'] = [safe_relative(p).as_posix() for p in value.get('artifacts', [])]
    publish = dict(value.get('publish', {}))
    if publish and (publish.get('remote', 'origin').startswith('-') or
                    publish.get('branch', '').startswith('-') or not publish.get('branch')):
        raise ValueError('publishing needs an explicit remote and branch')
    if publish:
        remote_url = run(['git', 'remote', 'get-url', publish.get('remote', 'origin')], repo)
        parsed = urlsplit(remote_url)
        if parsed.password or (parsed.scheme in ['http', 'https'] and parsed.username):
            raise ValueError('do not store credentials in a remote URL; use the existing credential helper')
        if publish.get('remote_url') and publish['remote_url'] != remote_url:
            raise ValueError('Git remote identity changed after review')
        publish['remote_url'] = remote_url
    if publish.get('release'):
        release = publish['release']
        if not release.get('tag') or not release.get('repo') or not release.get('notes'):
            raise ValueError('a release needs an explicit tag, GitHub repo and notes; no inferred versions')
    value['publish'] = publish
    return value


def register(root, name, config):
    safe_relative(name)
    if '/' in name or name in ['.', '..']:
        raise ValueError('target name must be one path component')
    value = target_config(config)
    path = state(root) / 'targets.json'
    with lock(state(root) / 'targets.lock'):
        targets = read_json(path, {})
        targets[name] = value
        write_json(path, targets)
    return {'target': name, 'configuration': value}


def clean(repo):
    if run(['git', 'status', '--porcelain', '--untracked-files=all'], repo):
        raise ValueError('target repository has local changes; reconcile them before apply: ' + str(repo))


def make_plan(root, batch, changes):
    directory = batch_path(root, batch)
    if not (directory / 'REVIEW.md').is_file():
        raise ValueError('write the findings and choices in REVIEW.md before freezing')
    targets = read_json(state(root) / 'targets.json', {})
    if not changes or len({c['target'] for c in changes}) != len(changes):
        raise ValueError('plan must contain one selected change per target')
    plans, diff = [], []
    used_repos = set()
    for change in changes:
        name = change['target']
        cfg = target_config(targets[name])
        repo = Path(cfg['repo'])
        if str(repo) in used_repos:
            raise ValueError('one repository per plan entry; combine related skill updates into a single reviewed target')
        used_repos.add(str(repo))
        clean(repo)
        source = inside(repo / cfg['skill_dir'], repo)
        staged = inside(Path(change['staged']).expanduser(), directory)
        staged_tree = tree(staged)
        if 'SKILL.md' not in staged_tree or staged == source:
            raise ValueError('staged skill must be a complete, distinct directory')
        source_tree = tree(source)
        if source_tree == staged_tree and not change.get('repo_files'):
            raise ValueError('target has no changes')
        extras = {}
        for name_in_repo, staged_file in change.get('repo_files', {}).items():
            rel = safe_relative(name_in_repo)
            destination = inside(repo / rel, repo)
            if destination == source or source in destination.parents:
                raise ValueError('skill members belong in the staged skill directory')
            f = inside(Path(staged_file), directory)
            if not f.is_file():
                raise ValueError('extra repository file is missing')
            extras[rel.as_posix()] = {'staged': str(f), 'sha256': digest(f.read_bytes()),
                                     'before': digest(destination.read_bytes()) if destination.is_file() else None}
        installs = {p: tree(Path(p)) for p in cfg['installs']}
        entry = {'target': change['target'], 'config': cfg, 'head': run(['git', 'rev-parse', 'HEAD'], repo),
                 'source_before': source_tree, 'staged': str(staged), 'staged_tree': staged_tree,
                 'installs_before': installs, 'repo_files': extras}
        plans.append(entry)
        diff.append('\n# ' + change['target'] + '\n')
        for name_in_skill in sorted(set(source_tree) | set(staged_tree)):
            before, after = source / name_in_skill, staged / name_in_skill
            a = before.read_text(errors='replace').splitlines(True) if before.is_file() else []
            b = after.read_text(errors='replace').splitlines(True) if after.is_file() else []
            diff.extend(difflib.unified_diff(a, b, 'live/' + name_in_skill, 'staged/' + name_in_skill))
            if source_tree.get(name_in_skill, {}).get('mode') != staged_tree.get(name_in_skill, {}).get('mode'):
                diff.append('\nmode {}: {} -> {}\n'.format(name_in_skill, source_tree.get(name_in_skill, {}).get('mode'), staged_tree.get(name_in_skill, {}).get('mode')))
        for rel, extra in extras.items():
            before = repo / rel
            diff.extend(difflib.unified_diff(before.read_text(errors='replace').splitlines(True) if before.is_file() else [],
                       Path(extra['staged']).read_text(errors='replace').splitlines(True), 'repo/' + rel, 'staged/' + rel))
    plan = {'format': 1, 'batch': batch, 'created_at': now(), 'entries': plans}
    plan_hash = digest(encoded(plan))
    atomic(directory / 'PLAN.diff', ''.join(diff).encode())
    write_json(directory / 'plan.json', plan)
    write_json(directory / 'plan-summary.json', {'hash': plan_hash, 'entries': plans,
               'approval_question': 'Approve observer plan ' + plan_hash + '?',
               'warning': 'Review ALL diff and commands. Approval binds these exact bytes, paths and publishing options.'})
    return {'batch': batch, 'plan_hash': plan_hash, 'diff': str(directory / 'PLAN.diff'),
            'summary': str(directory / 'plan-summary.json'), 'approval_question': 'Approve observer plan ' + plan_hash + '?'}


def validate_entry(entry):
    cfg = target_config(entry['config'])
    repo = Path(cfg['repo'])
    clean(repo)
    if run(['git', 'rev-parse', 'HEAD'], repo) != entry['head']:
        raise ValueError('source revision changed; regenerate and approve a fresh plan')
    if tree(repo / cfg['skill_dir']) != entry['source_before']:
        raise ValueError('source changed after review')
    if tree(Path(entry['staged'])) != entry['staged_tree']:
        raise ValueError('staged skill changed after review; approval is stale')
    for name, snapshot in entry['installs_before'].items():
        if tree(Path(name)) != snapshot:
            raise ValueError('installed copy changed after review: ' + name)
    for rel, extra in entry['repo_files'].items():
        current = Path(cfg['repo']) / rel
        if (digest(current.read_bytes()) if current.is_file() else None) != extra['before']:
            raise ValueError('extra repository source changed: ' + rel)
        if digest(Path(extra['staged']).read_bytes()) != extra['sha256']:
            raise ValueError('staged repository file changed: ' + rel)


def verify_applied(entry, result):
    cfg = entry['config']
    repo = Path(cfg['repo'])
    for path in [repo / cfg['skill_dir']] + [Path(p) for p in cfg['installs']]:
        if tree(path) != entry['staged_tree']:
            raise ValueError('previously applied target has since changed: ' + str(path))
    for rel, extra in entry['repo_files'].items():
        if digest((repo / rel).read_bytes()) != extra['sha256']:
            raise ValueError('applied repository file has since changed: ' + rel)
    for rel, expected in result.get('artifacts', {}).items():
        if digest((repo / rel).read_bytes()) != expected:
            raise ValueError('built artifact has since changed: ' + rel)


def replace_tree(source, destination):
    """Only operate on members enumerated in an approved, freshness-checked tree."""
    before, after = tree(destination), tree(source)
    for rel in sorted(set(before) - set(after)):
        (destination / rel).unlink()
    for rel, metadata in after.items():
        target = destination / rel
        if target.is_symlink():
            raise ValueError('destination became a symlink: ' + str(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic(target, (source / rel).read_bytes(), private=False)
        target.chmod(metadata['mode'])


def publish_entry(entry, receipt, receipt_file, plan_hash):
    cfg = entry['config']
    repo = Path(cfg['repo'])
    publish = cfg['publish']
    if not publish:
        receipt['publication'] = 'not requested'
        write_json(receipt_file, receipt)
        return
    if not receipt.get('commit'):
        paths = [cfg['skill_dir']] + list(entry['repo_files'])
        run(['git', 'add', '--'] + paths, repo)
        if run(['git', 'diff', '--cached', '--name-only'], repo):
            run(['git', 'commit', '-m', 'chore: apply observer review ' + plan_hash[:12]], repo)
        receipt['commit'] = run(['git', 'rev-parse', 'HEAD'], repo)
        write_json(receipt_file, receipt)
    if not receipt.get('pushed'):
        remote, branch = publish.get('remote', 'origin'), publish['branch']
        run(['git', 'push', remote, receipt['commit'] + ':refs/heads/' + branch], repo)
        observed = run(['git', 'ls-remote', remote, 'refs/heads/' + branch], repo).split()
        if not observed or observed[0] != receipt['commit']:
            raise ValueError('remote revision could not be verified; publication remains pending')
        receipt['pushed'] = True
        write_json(receipt_file, receipt)
    if publish.get('release') and not receipt.get('release_verified'):
        release = publish['release']
        notes = receipt_file.parent / ('release-notes-' + receipt_file.stem + '.md')
        atomic(notes, release['notes'].encode())
        tag, gh_repo = release['tag'], release['repo']
        view_args = ['gh', 'release', 'view', tag, '--repo', gh_repo, '--json', 'tagName,targetCommitish,isDraft,assets']
        probe = __import__('subprocess').run(view_args, cwd=repo, text=True, capture_output=True)
        assets = [str(repo / a) for a in cfg['artifacts']]
        if probe.returncode:
            # Do not interpret auth/network failure as an absent release.
            if 'release not found' not in probe.stderr.lower():
                raise ValueError('release lookup failed; no create attempted: ' + probe.stderr[-1000:])
            args = ['gh', 'release', 'create', tag, '--repo', gh_repo, '--target', receipt['commit'],
                    '--title', release.get('title', tag), '--notes-file', str(notes)]
            if release.get('draft', False):
                args.append('--draft')
            run(args + assets, repo)
        observed = json.loads(run(view_args, repo))
        # Never overwrite an existing differently-targeted release or asset.
        tag_ref = run(['git', 'ls-remote', publish.get('remote', 'origin'),
                       'refs/tags/' + tag, 'refs/tags/' + tag + '^{}'], repo).splitlines()
        commits = [line.split()[0] for line in tag_ref]
        if receipt['commit'] not in commits or observed['isDraft'] != release.get('draft', False):
            raise ValueError('existing release does not match the approved commit/draft state')
        names = {a['name'] for a in observed['assets']}
        missing = [p for p in assets if Path(p).name not in names]
        if missing:
            run(['gh', 'release', 'upload', tag, '--repo', gh_repo] + missing, repo)
        with tempfile.TemporaryDirectory(prefix='observer-release-check-') as temp:
            for p in assets:
                run(['gh', 'release', 'download', tag, '--repo', gh_repo,
                     '--pattern', Path(p).name, '--dir', temp], repo)
                if digest((Path(temp) / Path(p).name).read_bytes()) != digest(Path(p).read_bytes()):
                    raise ValueError('release asset bytes differ; existing asset was not overwritten')
        receipt['release_verified'] = True
        write_json(receipt_file, receipt)
    receipt['publication'] = 'verified'
    write_json(receipt_file, receipt)


def apply(root, batch, expected_hash):
    directory = batch_path(root, batch)
    with lock(state(root) / 'apply.lock'):
        plan = read_json(directory / 'plan.json')
        plan_hash = digest(encoded(plan))
        if plan_hash != expected_hash:
            raise ValueError('plan hash changed; review and approve the current diff')
        approval = read_json(state(root) / 'approvals' / (plan_hash + '.json'), {})
        if (approval.get('plan_hash') != plan_hash or approval.get('method') != 'AskUserQuestion'
                or approval.get('answer') != 'Apply this plan' or not approval.get('tool_use_id')):
            raise ValueError('no real question-card approval for this plan; no files changed')
        configs = read_json(state(root) / 'targets.json', {})
        for entry in plan['entries']:
            if target_config(configs[entry['target']]) != entry['config']:
                raise ValueError('target configuration changed; approval is stale')
        receipt_file = directory / 'APPLY.json'
        receipt = read_json(receipt_file, {'plan_hash': plan_hash, 'targets': {}, 'state': 'pending'})
        if receipt.get('plan_hash') != plan_hash:
            raise ValueError('existing apply receipt belongs to a different plan')
        if receipt['state'] == 'complete':
            for entry in plan['entries']:
                verify_applied(entry, receipt['targets'][entry['target']])
            return receipt
        # Validate all untouched targets before changing the first one.
        for entry in plan['entries']:
            if not receipt['targets'].get(entry['target'], {}).get('local_applied'):
                validate_entry(entry)
        for index, entry in enumerate(plan['entries']):
            name, cfg = entry['target'], entry['config']
            repo, staged = Path(cfg['repo']), Path(entry['staged'])
            result = receipt['targets'].setdefault(name, {})
            target_receipt = directory / ('publish-' + str(index) + '.json')
            try:
                if not result.get('local_applied'):
                    destinations = [repo / cfg['skill_dir']] + [Path(p) for p in cfg['installs']]
                    backup = directory / 'rollback' / str(index)
                    if backup.exists():
                        raise ValueError('an interrupted apply has rollback data; inspect it before retrying')
                    for n, dest in enumerate(destinations):
                        shutil.copytree(dest, backup / str(n))
                    for rel in entry['repo_files']:
                        f = repo / rel
                        if f.exists():
                            target = backup / 'repo-files' / rel
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(f, target)
                    result['state'] = 'installing'
                    write_json(receipt_file, receipt)
                    try:
                        replace_tree(staged, destinations[0])
                        for rel, extra in entry['repo_files'].items():
                            atomic(repo / rel, Path(extra['staged']).read_bytes(), private=False)
                            (repo / rel).chmod(Path(extra['staged']).stat().st_mode & 0o777)
                        for cmd in cfg['checks'] + cfg['build']:
                            run(cmd, repo, timeout=300)
                        allowed = [cfg['skill_dir']] + list(entry['repo_files'])
                        changed = run(['git', 'diff', '--name-only', '-z'], repo).split('\0')
                        changed += run(['git', 'ls-files', '--others', '--exclude-standard', '-z'], repo).split('\0')
                        unexpected = [p for p in changed if p and not any(p == a or p.startswith(a + '/') for a in allowed)]
                        if unexpected:
                            raise ValueError('checks/build changed unapproved repository files: ' + ', '.join(unexpected))
                        for rel, extra in entry['repo_files'].items():
                            if digest((repo / rel).read_bytes()) != extra['sha256']:
                                raise ValueError('build changed an approved file beyond its reviewed bytes: ' + rel)
                        for rel in cfg['artifacts']:
                            p = inside(repo / rel, repo)
                            if not p.is_file():
                                raise ValueError('expected build artifact is missing: ' + rel)
                            if p.suffix == '.zip':
                                with zipfile.ZipFile(p) as z:
                                    if z.testzip() is not None:
                                        raise ValueError('build produced a corrupt ZIP: ' + rel)
                        for dest in destinations[1:]:
                            replace_tree(staged, dest)
                        if any(tree(p) != entry['staged_tree'] for p in destinations):
                            raise ValueError('source/install read-back failed')
                    except BaseException:
                        for n, dest in enumerate(destinations):
                            replace_tree(backup / str(n), dest)
                        for rel, extra in entry['repo_files'].items():
                            if extra['before'] is None:
                                (repo / rel).unlink(missing_ok=True)
                            else:
                                shutil.copy2(backup / 'repo-files' / rel, repo / rel)
                        result['state'] = 'rolled_back'
                        raise
                    result.update(local_applied=True, state='verified',
                                  artifacts={p: digest((repo / p).read_bytes()) for p in cfg['artifacts']})
                    write_json(receipt_file, receipt)
                else:
                    verify_applied(entry, result)
                published = read_json(target_receipt, {})
                publish_entry(entry, published, target_receipt, plan_hash)
                result['publication'] = published.get('publication')
                result.pop('error', None)
                write_json(receipt_file, receipt)
            except Exception as e:
                result['error'] = str(e)
                receipt['state'] = 'pending'
                write_json(receipt_file, receipt)
                raise
        receipt.update(state='complete', completed_at=now())
        write_json(receipt_file, receipt)
        return receipt


def recover(root, batch, expected_hash):
    """Restore an interrupted local install only when members still match its pre/post images."""
    directory = batch_path(root, batch)
    with lock(state(root) / 'apply.lock'):
        plan = read_json(directory / 'plan.json')
        if digest(encoded(plan)) != expected_hash:
            raise ValueError('recovery plan hash does not match')
        receipt_file = directory / 'APPLY.json'
        receipt = read_json(receipt_file)
        if not receipt or receipt['state'] == 'complete':
            raise ValueError('no interrupted local installation to recover')
        for index, entry in enumerate(plan['entries']):
            result = receipt['targets'].get(entry['target'], {})
            backup = directory / 'rollback' / str(index)
            if result.get('local_applied'):
                continue  # A committed/published installation is never reverted by recovery.
            if not backup.is_dir():
                continue
            cfg = entry['config']
            destinations = [Path(cfg['repo']) / cfg['skill_dir']] + [Path(p) for p in cfg['installs']]
            for n, destination in enumerate(destinations):
                before = tree(backup / str(n))
                current = tree(destination)
                for rel, data in current.items():
                    if data not in [before.get(rel), entry['staged_tree'].get(rel)]:
                        raise ValueError('recovery would overwrite an independent edit: ' + str(destination / rel))
            for rel, extra in entry['repo_files'].items():
                p = Path(cfg['repo']) / rel
                current = digest(p.read_bytes()) if p.is_file() else None
                if current not in [extra['before'], extra['sha256']]:
                    raise ValueError('recovery would overwrite an independent repository edit: ' + rel)
            for n, destination in enumerate(destinations):
                replace_tree(backup / str(n), destination)
            for rel, extra in entry['repo_files'].items():
                p = Path(cfg['repo']) / rel
                if extra['before'] is None:
                    p.unlink(missing_ok=True)
                else:
                    shutil.copy2(backup / 'repo-files' / rel, p)
            archive = directory / 'previous-attempts' / (str(index) + '-' + now().replace(':', '-'))
            archive.parent.mkdir(exist_ok=True)
            backup.rename(archive)
            result.update(state='recovered', recovered_at=now())
        receipt['state'] = 'pending'
        write_json(receipt_file, receipt)
        return receipt
