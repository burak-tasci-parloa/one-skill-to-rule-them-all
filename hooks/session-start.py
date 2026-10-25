#!/usr/bin/env python3
"""Initialize approved storage and deliver activation; never invent observations."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile

RELATIVE_WORKSPACE = Path("Developer/task-observer")
PIN = Path("skill-observations/plugin-activation.json")
CONTEXT_LIMIT = 10000
WORKSPACE_ITEMS = ["skill-observations/observation-log", "skill-observations/observation-log/archive",
                   "skill-updates", "skill-observations/cross-cutting-principles.md",
                   "skill-observations/last-review-date.txt"]


def skill_directory(plugin):
    candidates = [p for p in [plugin, plugin / "skills/task-observer"]
                  if (p / "SKILL.md").is_file()]
    if len(candidates) != 1:
        raise ValueError("expected exactly one complete task-observer skill")
    skill = candidates[0]
    for rel in ["references/environments.md", "references/observation-log.md",
                "scripts/new-observation.sh", "scripts/session-start-scan.sh",
                "scripts/skill-load.sh"]:
        if not (skill / rel).is_file():
            raise ValueError("incomplete skill bundle: missing " + rel)
    return skill


def read_pin(workspace):
    pin = json.loads((workspace / PIN).read_text())
    if not isinstance(pin, dict) or not isinstance(pin.get("host_workspace"), str):
        raise ValueError("invalid workspace registration object")
    host = Path(pin.get("host_workspace", ""))
    if (pin.get("format") != 1 or pin.get("scope") != "user"
            or pin.get("relative_workspace") != RELATIVE_WORKSPACE.as_posix()
            or not host.is_absolute() or host.parts[-2:] != RELATIVE_WORKSPACE.parts
            or any(c in str(host) for c in "\x00\r\n")):
        raise ValueError("invalid workspace registration; reconcile it before writing")
    return pin


def persistent_path(path, plugin, home, registered=False):
    if not path.is_absolute() or any(c in str(path) for c in "\x00\r\n"):
        raise ValueError("workspace must be an absolute path without control characters")
    resolved = path.resolve()
    if resolved == plugin.resolve() or plugin.resolve() in resolved.parents:
        raise ValueError("the plugin installation is not persistent observation storage")
    forbidden = ["/worktrees/", "/scratch-workspaces/", "/scratch-", "/plugins/cache/",
                 "/plugins/synced/", "/.claude/skills/", "/.agents/skills/"]
    if any(part in str(resolved) + "/" for part in forbidden):
        raise ValueError("an ephemeral checkout or skill directory cannot be the workspace")
    # A verified registration identifies a persistent folder mounted under a
    # session-specific alias. Unregistered /sessions paths are never adopted.
    temporary = ("/sessions/", "/tmp/", "/private/tmp/", "/private/var/folders/",
                 str(Path(tempfile.gettempdir()).resolve()) + "/")
    if (str(resolved).startswith(temporary)
            and home.resolve() not in resolved.parents and not registered):
        raise ValueError("unregistered temporary/session storage is not the shared workspace")
    return resolved


def resolve_workspace(plugin, home, system, cwd, override=None, mounts=None):
    if override:
        path = Path(override).expanduser()
        pin = read_pin(path) if (path / PIN).exists() else None
        path = persistent_path(path, plugin, home, registered=pin is not None)
        return path, pin
    if system == "darwin":
        path = persistent_path(home / RELATIVE_WORKSPACE, plugin, home)
        pin = read_pin(path) if (path / PIN).exists() else None
        if pin and Path(pin["host_workspace"]).resolve() != path:
            raise ValueError("workspace registration names a different host root; reconcile first")
        return path, pin
    # Cowork may expose the selected folder through an alias instead of the
    # Mac's path. A directory name alone is insufficient evidence of identity.
    candidates = [cwd] + list(cwd.parents)
    if mounts is None:
        candidates += list(Path("/sessions").glob("*/mnt/*"))[:200]
        if Path("/mnt").is_dir():
            candidates += list(Path("/mnt").iterdir())[:200]
    else:
        candidates += list(mounts)
    # A first-run grant may expose Developer rather than its newly created child.
    candidates += [path / "task-observer" for path in list(candidates)]
    found = {}
    for path in candidates:
        try:
            if (path / PIN).is_file():
                pin = read_pin(path)
                resolved = persistent_path(path, plugin, home, registered=True)
                found[resolved] = pin
        except OSError:
            continue
    if len(found) > 1:
        raise ValueError("several registered workspace folders are reachable; reconcile before writing")
    return next(iter(found.items())) if found else (None, None)


def register_workspace(workspace, plugin, home, host_workspace=None):
    host = Path(host_workspace) if host_workspace else workspace
    if (not host.is_absolute() or host.parts[-2:] != RELATIVE_WORKSPACE.parts
            or any(c in str(host) for c in "\x00\r\n")):
        raise ValueError("host workspace must be the approved absolute ~/Developer/task-observer path")
    workspace = persistent_path(workspace, plugin, home, registered=host_workspace is not None)
    for rel in ["skill-observations/observation-log", "skill-updates",
                "skill-observations/cross-cutting-principles.md",
                "skill-observations/last-review-date.txt"]:
        if not (workspace / rel).exists():
            raise ValueError("run the original Workspace creation procedure first: missing " + rel)
    data = {"format": 1, "scope": "user", "relative_workspace": RELATIVE_WORKSPACE.as_posix(),
            "host_workspace": str(host)}
    target = workspace / PIN
    if target.exists():
        if read_pin(workspace) != data:
            raise ValueError("existing registration differs; it was not overwritten")
    else:
        fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(json.dumps(data, indent=2) + "\n")
    return target


def setup_conflicts(workspace, home, cwd):
    """Bounded preflight: do not silently fork an existing or configured log."""
    candidates = {home / name for name in [".claude", ".agents", ".codex"]}
    candidates.update([cwd] + list(cwd.parents))
    for pattern in ["*/skill-observations", "*/memory/skill-observations"]:
        candidates.update(p.parent for p in (home / "Developer").glob(pattern))
    candidates.update(p.parent for p in (home / ".claude/projects").glob("*/skill-observations"))
    candidates.update(p.parent for p in (home / ".claude/projects").glob("*/memory/skill-observations"))
    conflicts = {str(p.resolve()) for p in candidates
                 if (p / "skill-observations").exists() and p.resolve() != workspace}
    instructions = {home / ".claude/CLAUDE.md", home / ".codex/AGENTS.md", home / ".agents/AGENTS.md"}
    for parent in [cwd] + list(cwd.parents):
        instructions.update(parent / name for name in ["CLAUDE.md", "AGENTS.md"])
    for source in instructions:
        if not source.is_file():
            continue
        for line in source.read_text().splitlines():
            for match in re.finditer(r"(?:~/|/(?:Users|home)/)[^\n`\"'<>]*?/(?:skill-observations|task-observer)(?=[/\s`\"'<>)\],.:;]|$)", line):
                if any(part in match.group() for part in ["/.agents/skills/", "/.claude/skills/", "/plugins/"]):
                    continue  # A skill installation path is not an observation-store pin.
                path = Path(match.group().replace("~/", str(home) + "/", 1))
                root = path.parent if path.name == "skill-observations" else path
                if root.resolve() != workspace:
                    conflicts.add(str(root))
    for source in [home / ".claude/settings.json", cwd / ".claude/settings.json", cwd / ".claude/settings.local.json"]:
        if source.is_file():
            hooks = json.loads(source.read_text()).get("hooks", {})
            if "task-observer" in json.dumps(hooks):
                conflicts.add("inspect existing observer hooks in " + str(source))
    return sorted(conflicts)


def initialize_workspace(workspace, plugin, home, cwd, host_workspace=None):
    """Run the original setup command, then register; never run the observer scan."""
    import fcntl  # Setup runs on macOS or the Linux Cowork filesystem.
    skill = skill_directory(plugin)
    workspace = persistent_path(workspace, plugin, home, registered=host_workspace is not None)
    host = Path(host_workspace) if host_workspace else workspace
    if (not host.is_absolute() or host.parts[-2:] != RELATIVE_WORKSPACE.parts
            or any(c in str(host) for c in "\x00\r\n")):
        raise ValueError("initialization needs the approved absolute host workspace")
    # A cloud mount needs an explicit, verified host mapping from the folder grant.
    if host_workspace is None and workspace != (home / RELATIVE_WORKSPACE).resolve():
        raise ValueError("initialize only the approved home-relative workspace or a verified host-folder alias")
    for rel in [".", "skill-observations", "skill-updates", "skill-observations/observation-log",
                "skill-observations/observation-log/archive", "skill-observations/cross-cutting-principles.md",
                "skill-observations/last-review-date.txt", "skill-observations/checkpoints.log",
                ".setup.lock", PIN.as_posix()]:
        if (workspace / rel).is_symlink():
            raise ValueError("setup will not write through a symlink: " + str(workspace / rel))
    for index, rel in enumerate(WORKSPACE_ITEMS):
        item = workspace / rel
        if item.exists() and not (item.is_dir() if index < 3 else item.is_file()):
            raise ValueError("workspace item has an unexpected file type: " + str(item))
    if (workspace / "skill-observations/log.md").exists():
        raise ValueError("legacy or split log.md; use the original migration before setup")
    if (workspace / "skill-observations/MOVED.md").exists():
        raise ValueError("workspace has a MOVED.md pointer; reconcile before setup")
    if (workspace / PIN).exists():
        if Path(read_pin(workspace)["host_workspace"]) != host:
            raise ValueError("existing registration names a different host root")
        if workspace_complete(workspace):
            return False
    conflicts = setup_conflicts(workspace, home, cwd)
    if conflicts:
        raise ValueError("setup paused; reconcile other observer stores/pins first: " + "; ".join(conflicts))
    text = (skill / "references/observation-log.md").read_text()
    command = text.split("### Workspace creation\n", 1)[1].split("```bash\n", 1)[1].split("\n```", 1)[0]
    command = command.replace("[ABSOLUTE PATH]", shell_double(workspace))
    workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(str(workspace / ".setup.lock"), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        # Another new session may have completed setup while this one waited.
        if (workspace / PIN).exists() and workspace_complete(workspace):
            if Path(read_pin(workspace)["host_workspace"]) != host:
                raise ValueError("existing registration names a different host root")
            return False
        result = subprocess.run(["bash", "-e", "-c", command], cwd=str(cwd),
                                text=True, capture_output=True, timeout=5)
        if result.returncode:
            raise ValueError("original Workspace creation failed: " + (result.stderr or result.stdout).strip())
        (workspace / "skill-updates").mkdir(exist_ok=True)
        register_workspace(workspace, plugin, home, str(host))
    return True


def workspace_complete(workspace):
    return all((workspace / rel).is_dir() if index < 3 else (workspace / rel).is_file()
               for index, rel in enumerate(WORKSPACE_ITEMS))


def review_state(workspace, today):
    directory = workspace / "skill-observations"
    log = directory / "observation-log"
    if not log.is_dir():
        return "Observation storage is not initialized/reachable; this is NOT a verified empty log."
    count = 0
    for path in log.glob("*.md"):
        # Stop at the closing delimiter; do not read observation bodies.
        with path.open(encoding="utf-8-sig") as stream:
            if stream.readline().strip() != "---":
                raise ValueError("observation header is unreadable/invalid: " + path.name)
            is_open = False
            for line in stream:
                if line.strip() == "---":
                    break
                is_open |= re.fullmatch(r"status:\s*[\"']?open[\"']?\s*", line.strip()) is not None
            else:
                raise ValueError("observation header is incomplete: " + path.name)
        count += is_open
    last_file = directory / "last-review-date.txt"
    last = last_file.read_text().strip() if last_file.is_file() else "never"
    due = last == "never"
    if not due:
        try:
            due = (today - dt.date.fromisoformat(last)).days >= 7
        except ValueError:
            raise ValueError("last-review-date.txt is not a date or 'never'")
    message = "{} OPEN observations in {}; last review: {}.".format(count, directory, last)
    if count and due:
        message += " Offer the original review once, then continue the user's task unless they opt in."
    return message


def shell_double(path):
    return str(path).replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")


def activation_context(plugin, home, system, cwd, override=None, mounts=None, today=None):
    skill = skill_directory(plugin)
    text = (skill / "references/environments.md").read_text()
    block = text.split("### The activation block", 1)[1].split("```text\n", 1)[1].split("\n```", 1)[0]
    workspace, pin = resolve_workspace(plugin, home, system, cwd, override, mounts)
    intro = ["Task Observer plugin startup: this is the equivalent activation configuration; no CLAUDE.md edit or second settings hook is required.",
             "This plugin registers only SessionStart. It configures no Stop/write gates or scheduled job."]
    if workspace is None:
        intro += ["The user's ONE persistent workspace is ~/Developer/task-observer ON THEIR COMPUTER. Its runtime path is unresolved, not an empty log.",
                  "Invoke task-observer in the first batch and request its folder access now: grant Developer if task-observer does not exist yet, then initialize that child. Use grant metadata to verify the host mapping. Do not silently skip setup or ask for an installation prompt. Resolve [ABSOLUTE PATH] on the user's computer; never use the cloud HOME.",
                  "Use the original environment-mapping/bridged-script procedure; if access is unavailable, report that and use the original handoff/report-back mode."]
        projects = "[resolve the user's computer's Developer directory]"
    else:
        intro += ["Resolved runtime workspace: " + str(workspace)]
        if pin:
            intro += ["Registered host workspace: " + pin["host_workspace"] + ". Verify the host-folder mapping before writes; registration is configuration, not proof of a mount. A verified /sessions mount alias reaches persistent storage, not a second pool."]
        intro += [review_state(workspace, today or dt.date.today())]
        projects = str(Path(pin["host_workspace"]).parent if pin else (home / "Developer"))
        block = block.replace('"[ABSOLUTE PATH]', '"' + shell_double(workspace))
        block = block.replace("[ABSOLUTE PATH]", str(workspace))
    if pin is None or (workspace is not None and not workspace_complete(workspace)):
        registration = "bash " + shlex.quote(str(plugin / "hooks/session-start.sh")) + " --initialize-workspace "
        if workspace is not None and system == "darwin":
            registration += shlex.quote(str(workspace))
        else:
            registration += "<resolved-runtime-root> --host-workspace <absolute-host-root>"
        intro += ["First setup is part of this plugin. Preserve existing pins/logs and inventory non-interactive consumers. After verifying device mapping, run: " + registration + ". It runs ORIGINAL Workspace creation and registration. Run against the granted mount; for device-only access, digest-match the COMPLETE helper bundle before staging. Then run Session Start; no fabricated scan/checkpoint or silent starter import.",
                  "A restriction on changing PROJECT files does not prohibit the approved observer storage. If the user prohibits ALL writes or permission is missing, ask for the specific setup access once; respect a decline and report setup incomplete. Never bypass a read-only boundary or silently claim activation."]
    block = block.replace('"<skill directory>', '"' + shell_double(skill))
    block = block.replace("<skill directory>", str(skill)).replace("[PROJECTS ROOT]", projects)
    block = block.replace('[RUN OUTPUT PATHS, one per line, or "none"]',
                          "none configured by this plugin; for restricted runs use the caller's existing output destination")
    context = "\n\n".join(intro + [block])
    if len(context) > CONTEXT_LIMIT:
        raise ValueError("complete activation context exceeds the host's 10000-character limit; it was not truncated")
    return context


def startup_context(plugin, home, system, cwd, override=None, permission_mode=None):
    workspace, pin = resolve_workspace(plugin, home, system, cwd, override)
    if system == "darwin" and permission_mode != "plan" and workspace is not None:
        initialize_workspace(workspace, plugin, home, cwd)
    context = activation_context(plugin, home, system, cwd, override)
    pending = workspace is None or not (workspace / PIN).exists() or not workspace_complete(workspace)
    if permission_mode == "plan":
        context = "Plan mode: do not initialize or write observer storage. Report setup pending if needed.\n\n" + context
    if len(context) > CONTEXT_LIMIT:
        raise ValueError("complete activation context exceeds the host's 10000-character limit; it was not truncated")
    output = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
    if pending:
        output["systemMessage"] = "Task Observer setup is pending. The plugin must request any missing folder access and complete setup; no manual installation prompt is required."
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--register-workspace", type=Path)
    action.add_argument("--initialize-workspace", type=Path)
    parser.add_argument("--host-workspace")
    args = parser.parse_args()
    plugin = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parent.parent))
    home = Path.home()
    try:
        if args.initialize_workspace:
            if sys.platform != "darwin" and not args.host_workspace:
                raise ValueError("cloud setup needs a verified --host-workspace mapping; never use the cloud HOME")
            changed = initialize_workspace(args.initialize_workspace, plugin, home, Path.cwd(), args.host_workspace)
            print(("Initialized" if changed else "Verified existing") + " persistent workspace: " + str(args.initialize_workspace))
            return 0
        if args.register_workspace:
            target = register_workspace(args.register_workspace, plugin, home, args.host_workspace)
            print("Registered persistent workspace: " + str(target))
            return 0
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
        if not isinstance(event, dict):
            raise ValueError("hook input must be a JSON object")
        if event.get("agent_id"):
            return 0  # The controller observes; delegated workers do not repeat startup.
        output = startup_context(plugin, home, sys.platform, Path(event.get("cwd") or os.getcwd()),
                                 os.environ.get("TASK_OBSERVER_WORKSPACE"), event.get("permission_mode"))
        print(json.dumps(output))
    except (OSError, ValueError, KeyError, IndexError, TypeError, subprocess.TimeoutExpired) as exc:
        if args.register_workspace or args.initialize_workspace:
            print("Task Observer setup incomplete: " + str(exc), file=sys.stderr)
            return 1
        message = "Task Observer activation incomplete: " + str(exc)
        print(json.dumps({"systemMessage": message, "hookSpecificOutput": {
            "hookEventName": "SessionStart", "additionalContext": message + ". Do not claim the observer ran or create a replacement store. Request the missing folder access or reconcile the named conflict; respect a decline and continue the user's task."}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
