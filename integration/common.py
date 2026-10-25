"""Private, local integration state. No changes to the upstream skill."""
import contextlib
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('original_installer', ROOT / 'hooks/session-start.py')
startup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(startup)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.is_file() else default


def private_dir(path):
    path = Path(path)
    for p in [path] + list(path.parents):
        if p.is_symlink():
            raise ValueError('refusing linked integration storage: ' + str(p))
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def atomic(path, data, private=True):
    if private:
        private_dir(path.parent)
    else:
        for parent in [path.parent] + list(path.parent.parents):
            if parent.is_symlink():
                raise ValueError('refusing linked destination parent: ' + str(parent))
        path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('refusing linked state file: ' + str(path))
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        tmp = Path(f.name)
        try:
            os.fchmod(f.fileno(), 0o600)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    os.replace(tmp, path)


def write_json(path, data):
    atomic(path, json.dumps(data, indent=2, ensure_ascii=False).encode() + b'\n')


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


@contextlib.contextmanager
def lock(path):
    import fcntl
    private_dir(path.parent)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('another observer operation is running; retry later')
        yield


def workspace(create=False):
    home = Path.home()
    root, pin = startup.resolve_workspace(ROOT, home, sys.platform, Path.cwd(),
                                         os.environ.get('TASK_OBSERVER_WORKSPACE'))
    if root is None:
        raise ValueError('observer folder not connected; grant ~/Developer/task-observer, then run status/setup')
    if create:
        if sys.platform != 'darwin' and pin is None:
            raise ValueError('unverified cloud HOME is not observer storage')
        startup.initialize_workspace(root, ROOT, home, Path.cwd(), pin['host_workspace'] if pin else None)
    if not startup.workspace_complete(root):
        raise ValueError('observer setup incomplete; run the bundled setup with the actual folder grant')
    return root


def state(root):
    return root / 'skill-observations/.plugin'


def skill():
    return startup.skill_directory(ROOT)


def run(args, cwd=None, timeout=120):
    r = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    if r.returncode:
        raise ValueError('{} failed ({}): {}'.format(args[0], r.returncode, (r.stderr or r.stdout)[-3000:]))
    return r.stdout.strip()


def safe_relative(value):
    p = Path(value)
    if not value or p.is_absolute() or '..' in p.parts or '.git' in p.parts or any(c in value for c in '\x00\r\n'):
        raise ValueError('unsafe relative path: ' + str(value))
    return p


def inside(path, parent):
    p = Path(path)
    if p.is_symlink() or not p.resolve().is_relative_to(parent.resolve()):
        raise ValueError('path leaves its approved directory: ' + str(path))
    return p.resolve()


def tree(path):
    """Exact bytes/modes, without VCS metadata or generated Python caches."""
    path = Path(path)
    if not path.is_dir():
        raise ValueError('missing directory: ' + str(path))
    result = {}
    for p in sorted(path.rglob('*')):
        rel = p.relative_to(path)
        if any(x in rel.parts for x in ['.git', '__pycache__', '.DS_Store']):
            continue
        if p.is_symlink():
            raise ValueError('linked member is not an independent skill copy: ' + str(p))
        if p.is_file():
            result[rel.as_posix()] = {'sha256': digest(p.read_bytes()), 'mode': p.stat().st_mode & 0o777}
    return result


def batch_path(root, batch):
    if not re.fullmatch(r'[0-9a-f]{24}', batch):
        raise ValueError('invalid review batch id')
    p = state(root) / 'batches' / batch
    if not p.is_dir() or p.is_symlink():
        raise ValueError('review batch not found')
    return p
