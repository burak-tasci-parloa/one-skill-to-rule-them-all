#!/usr/bin/env python3
"""Find/bootstrap the approved pool and request the unchanged Observer skill."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(os.environ.get('CLAUDE_PLUGIN_ROOT', Path(__file__).resolve().parents[1]))
RELATIVE = Path('Developer/task-observer')
PIN = Path('skill-observations/plugin-activation.json')


def skill_directory(root=ROOT):
    return next(p for p in [root / 'skills/task-observer', root] if (p / 'SKILL.md').is_file())


def registration(pool):
    data = json.loads((pool / PIN).read_text())
    host = Path(data['host_workspace'])
    if data.get('format') != 1 or data.get('scope') != 'user' or not host.is_absolute() or host.parts[-2:] != RELATIVE.parts:
        raise ValueError('invalid shared-folder registration; reconcile it before writing')
    return data


def resolve_pool(home, system, cwd, override=None):
    if system == 'darwin':
        pool = Path(override).expanduser() if override else home / RELATIVE
        if not pool.is_absolute():
            raise ValueError('observer workspace must be absolute')
        if (pool / PIN).exists() and Path(registration(pool)['host_workspace']).resolve() != pool.resolve():
            raise ValueError('registration names a different host pool')
        return pool
    # A VM's HOME is not the user's Mac. Reuse only a registered mounted alias.
    candidates = [Path(override).expanduser()] if override else [cwd, *cwd.parents, *Path('/sessions').glob('*/mnt/*'), *Path('/mnt').glob('*')]
    candidates += [p / 'task-observer' for p in list(candidates)]
    found = {p.resolve() for p in candidates if (p / PIN).is_file()}
    if len(found) > 1:
        raise ValueError('several shared-folder aliases found; select the intended one')
    if found:
        pool = found.pop()
        registration(pool)
        return pool
    return None


def initialize(pool, home, host=None):
    pool = pool.expanduser()
    host = Path(host) if host else home / RELATIVE
    if not pool.is_absolute() or not host.is_absolute() or host.parts[-2:] != RELATIVE.parts:
        raise ValueError('setup needs the granted runtime path and absolute host Developer/task-observer path')
    for parent in [pool, *pool.parents]:
        if parent.is_symlink():
            raise ValueError('resolve the physical shared-folder path before setup')
    for name in ['skill-observations', 'skill-updates', 'skill-observations/observation-log',
                 'skill-observations/last-review-date.txt', 'skill-observations/cross-cutting-principles.md']:
        if (pool / name).is_symlink():
            raise ValueError('setup will not write through a linked storage item: ' + name)
    if (pool / PIN).exists():
        if registration(pool)['host_workspace'] != str(host):
            raise ValueError('existing pool registration differs; not overwritten')
    else:
        for base in [home / '.claude', home / '.agents', home / '.codex']:
            if (base / 'skill-observations').exists():
                raise ValueError('an existing observer store needs reconciliation: ' + str(base))
    # Reuse upstream's idempotent setup, preserving observations and starter choices.
    text = (skill_directory() / 'references/observation-log.md').read_text()
    command = text.split('### Workspace creation\n', 1)[1].split('```bash\n', 1)[1].split('\n```', 1)[0]
    escaped = str(pool).replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
    command = command.replace('[ABSOLUTE PATH]', escaped)
    pool.mkdir(parents=True, exist_ok=True)
    subprocess.run(['bash', '-e', '-c', command], check=True, capture_output=True, text=True, timeout=5)
    (pool / 'skill-updates').mkdir(exist_ok=True)
    pin = pool / PIN
    if not pin.exists():
        data = {'format': 1, 'scope': 'user', 'relative_workspace': RELATIVE.as_posix(), 'host_workspace': str(host)}
        with pin.open('x') as f:
            f.write(json.dumps(data, indent=2) + '\n')
        pin.chmod(0o600)


def startup_context(home, system, cwd, event, override=None):
    pool = resolve_pool(home, system, cwd, override)
    problem = ''
    if pool is not None and event.get('permission_mode') != 'plan':
        try:
            initialize(pool, home, registration(pool)['host_workspace'] if (pool / PIN).exists() else None)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            problem = 'Storage setup incomplete: ' + str(exc)
    context = [
        'Task Observer plugin 3.8.4 candidate 6. Load the registered ORIGINAL task-observer skill and execute its Session Start Protocol. Loading alone does not complete it.',
        'Claude Code skill id: task-observer:task-observer; Cowork label: task-observer. The skill files are unchanged at ' + str(skill_directory()) + '.',
        'Use ONE shared pool: ~/Developer/task-observer on the user\'s computer. ' + ('Runtime path: ' + str(pool) if pool else 'Runtime path unresolved: request its folder grant, or Developer for first setup; never create a pool under a VM HOME.'),
        'Storage bootstrap is the only action this helper performs. The original skill handles scans, per-skill lookups, observations, starter choices and review. Run its original scripts; never infer a completed scan/review from this hook.',
        'For a new verified VM grant, run python3 ' + str(ROOT / 'hooks/session-start.py') + ' --initialize <runtime-path> --host-workspace <absolute-host-path> using the folder grant metadata, then load the skill. Quote each path.',
        'If setup/access is unavailable, report the specific missing access and continue the user\'s task using the original degraded/report-back guidance. Do not block ordinary tools or force a review. No scheduler or additional activation hook is needed.',
        'For review, use the original method. Before offering an approved installation, read ' + str(ROOT / 'integration/INSTALL.md') + '. It documents the user-authorized install extension; no separate commands or approval-record system exist.'
    ]
    if event.get('permission_mode') == 'plan':
        context.append('Plan mode: do not create or write observer storage; report setup pending where necessary.')
    if problem:
        context.append(problem)
    return {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': '\n\n'.join(context)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initialize', type=Path)
    parser.add_argument('--host-workspace')
    args = parser.parse_args()
    try:
        if args.initialize:
            if sys.platform != 'darwin' and not args.host_workspace:
                raise ValueError('a VM needs an actual host-folder grant mapping')
            initialize(args.initialize, Path.home(), args.host_workspace)
            print('Shared observer storage initialized/verified: ' + str(args.initialize))
        else:
            event = json.loads(sys.stdin.read() or '{}')
            if not event.get('agent_id'):
                print(json.dumps(startup_context(Path.home(), sys.platform, Path(event.get('cwd') or os.getcwd()), event,
                                                 os.environ.get('TASK_OBSERVER_WORKSPACE'))))
    except Exception as exc:
        message = 'Task Observer startup incomplete: ' + str(exc) + '. Do not claim observation is active; report access/setup pending and continue the user task.'
        if args.initialize:
            print(message, file=sys.stderr)
            return 1
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': message}}))
    return 0  # Never return a denial or block ordinary work.


if __name__ == '__main__':
    sys.exit(main())
