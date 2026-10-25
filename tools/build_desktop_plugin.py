#!/usr/bin/env python3
"""Build and verify a reproducible Desktop plugin from the maintained skill."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from urllib.parse import unquote, urlsplit

PLUGIN = "task-observer"
SKILL_PREFIX = f"skills/{PLUGIN}/"
ALLOWED_KEYS = {"name", "displayName", "description", "version", "author",
                "homepage", "repository", "license", "keywords", "skills"}
EXCLUDED = {".git", "__pycache__", ".DS_Store"}


def verify_upstream_skill(repo):
    """Keep upstream bytes and versions independent of this plugin's version."""
    repo = Path(repo).resolve()
    lock = json.loads((repo / "upstream-skill.json").read_text())
    if lock.get("format") != 1 or not re.fullmatch(r"[0-9a-f]{40}", lock.get("commit", "")):
        raise ValueError("Invalid upstream skill lock")
    sources = {"SKILL.md", "LICENSE"}
    for folder in [repo / "references", repo / "scripts"]:
        for item in folder.rglob("*"):
            if item.is_symlink():
                raise ValueError(f"Symlink in source: {item}")
            if item.is_file() and not any(p in EXCLUDED for p in item.relative_to(repo).parts) and item.suffix != ".pyc":
                sources.add(item.relative_to(repo).as_posix())
    if sources != set(lock["files"]):
        raise ValueError("Upstream skill membership mismatch")
    for name, expected in lock["files"].items():
        item = repo / name
        if item.is_symlink():
            raise ValueError(f"Symlink in source: {item}")
        if not item.is_file() or hashlib.sha256(item.read_bytes()).hexdigest() != expected["sha256"]:
            raise ValueError(f"Upstream skill content mismatch: {name}")
        if item.stat().st_mode & 0o777 != int(expected["mode"], 8):
            raise ValueError(f"Upstream skill permissions mismatch: {name}")
    version = re.search(r'^version:\s*"([^"]+)"\s*$', (repo / "SKILL.md").read_text(), re.MULTILINE)
    if not version or version.group(1) != lock["skill_version"]:
        raise ValueError("Upstream skill version mismatch")
    starter = re.search(r'^Starter set version:\s*(\d+)\s*$',
                        (repo / "references/starter-principles.md").read_text(), re.MULTILINE)
    if not starter or lock.get("starter_set_version") != int(starter.group(1)):
        raise ValueError("Upstream starter set version mismatch")
    return {"upstream_version": lock["skill_version"], "commit": lock["commit"],
            "files": len(sources), "all_files_byte_identical": True}


def expected_members(repo):
    repo = Path(repo).resolve()
    manifest = json.loads((repo / ".claude-plugin/plugin.json").read_text())
    unknown = set(manifest) - ALLOWED_KEYS
    if unknown:
        raise ValueError(f"Unsupported upload manifest keys: {sorted(unknown)}")
    if manifest.get("name") != PLUGIN:
        raise ValueError("Unexpected plugin identity")
    verify_upstream_skill(repo)
    manifest["skills"] = [f"./skills/{PLUGIN}"]
    members = {
        ".claude-plugin/plugin.json": ((json.dumps(manifest, indent=2) + "\n").encode(), 0o644),
        "README.md": ((repo / "DESKTOP-PLUGIN.md").read_bytes(), 0o644),
        "LICENSE": ((repo / "LICENSE").read_bytes(), 0o644),
        "upstream-skill.json": ((repo / "upstream-skill.json").read_bytes(), 0o644),
    }
    for item in sorted((repo / "hooks").rglob("*")):
        if item.is_symlink():
            raise ValueError(f"Symlink in source: {item}")
        if item.is_file() and not any(p in EXCLUDED for p in item.relative_to(repo).parts) and item.suffix != ".pyc":
            mode = 0o755 if item.stat().st_mode & 0o111 else 0o644
            members[item.relative_to(repo).as_posix()] = (item.read_bytes(), mode)
    for required in ["hooks/hooks.json", "hooks/session-start.sh", "hooks/session-start.py"]:
        if required not in members:
            raise ValueError(f"Missing startup integration: {required}")
    sources = [repo / "SKILL.md", repo / "LICENSE"]
    for folder in [repo / "references", repo / "scripts"]:
        for item in sorted(folder.rglob("*")):
            if item.is_symlink():
                raise ValueError(f"Symlink in source: {item}")
            if item.is_file() and not any(p in EXCLUDED for p in item.relative_to(repo).parts) and item.suffix != ".pyc":
                sources.append(item)
    for item in sources:
        if item.is_symlink() or not item.is_file():
            raise ValueError(f"Missing or linked source file: {item}")
        name = SKILL_PREFIX + item.relative_to(repo).as_posix()
        mode = 0o755 if item.stat().st_mode & 0o111 else 0o644
        members[name] = (item.read_bytes(), mode)
    return members


def verify(repo, archive):
    expected = expected_members(repo)
    for target in re.findall(r"\]\(([^)]+)\)", expected["README.md"][0].decode()):
        link = urlsplit(target.strip().strip("<>"))
        if not link.scheme and link.path and unquote(link.path) not in expected:
            raise ValueError(f"Unresolved upload README link: {target}")
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError("Archive/source membership mismatch")
        if bundle.testzip() is not None:
            raise ValueError("Archive integrity check failed")
        for name, (data, mode) in expected.items():
            entry = bundle.getinfo(name)
            if bundle.read(name) != data:
                raise ValueError(f"Archive/source content mismatch: {name}")
            actual_mode = entry.external_attr >> 16
            if stat.S_ISLNK(actual_mode) or actual_mode & 0o777 != mode:
                raise ValueError(f"Incorrect archive permissions: {name}")
    digest = hashlib.sha256(Path(archive).read_bytes()).hexdigest()
    checksum = Path(archive).with_suffix(".zip.sha256")
    if checksum.read_text() != f"{digest}  {Path(archive).name}\n":
        raise ValueError("Checksum does not match archive")
    return {"plugin": PLUGIN, "files": len(expected), "sha256": digest}


def build(repo, output=None):
    repo = Path(repo).resolve()
    output = Path(output).resolve() if output else repo / "dist"
    members = expected_members(repo)
    output.mkdir(parents=True, exist_ok=True)
    staging = output / "plugin"
    marker = output / ".task-observer-build.json"
    ownership = {"builder": "task-observer-desktop", "source": str(repo)}
    if staging.exists() and (staging.is_symlink() or not marker.is_file() or json.loads(marker.read_text()) != ownership):
        raise ValueError(f"Refusing to replace an unmanaged staging path: {staging}")
    with tempfile.TemporaryDirectory(prefix=".desktop-build-", dir=output) as temp:
        fresh = Path(temp) / "plugin"
        for name, (data, mode) in members.items():
            target = fresh / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(mode)
        subprocess.run([sys.executable, str(repo / "scripts/validate-skill-bundle.py"),
                        str(fresh / "skills" / PLUGIN)], check=True)
        archive = output / f"{PLUGIN}.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for name, (data, mode) in sorted(members.items()):
                entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = (stat.S_IFREG | mode) << 16
                entry.compress_type = zipfile.ZIP_DEFLATED
                bundle.writestr(entry, data)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n")
        result = verify(repo, archive)
        if staging.exists():
            shutil.rmtree(staging)
        fresh.rename(staging)
        marker.write_text(json.dumps(ownership) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--verify", action="store_true")
    action.add_argument("--check-upstream", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.check_upstream:
        result = verify_upstream_skill(root)
    else:
        result = verify(root, root / "dist/task-observer.zip") if args.verify else build(root)
    print(json.dumps(result, indent=2))
