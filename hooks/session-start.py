#!/usr/bin/env python3
"""Deliver the upstream activation block; never create observations or edit settings."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile

RELATIVE_WORKSPACE = Path("Developer/task-observer")
PIN = Path("skill-observations/plugin-activation.json")
CONTEXT_LIMIT = 10000


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
                  "Invoke task-observer in the first batch and probe that folder through the device tools, or request the folder connection. Resolve [ABSOLUTE PATH] on the user's computer before running the template. Never expand the cloud container's HOME into a replacement workspace.",
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
    if pin is None:
        registration = "bash " + shlex.quote(str(plugin / "hooks/session-start.sh")) + " --register-workspace "
        if workspace is not None and system == "darwin":
            registration += shlex.quote(str(workspace))
        else:
            registration += "<resolved-runtime-root> --host-workspace <absolute-host-root>"
        intro += ["First setup: preserve existing pins/logs and inventory non-interactive consumers. Run the ORIGINAL Workspace creation and Session Start Protocol; do not fabricate a checkpoint or import starter principles silently.",
                  "After initialization, register the approved folder once: " + registration + ". Registration writes only skill-observations/plugin-activation.json. If the helper is remote from the device, use the original digest-matched staging procedure."]
    block = block.replace('"<skill directory>', '"' + shell_double(skill))
    block = block.replace("<skill directory>", str(skill)).replace("[PROJECTS ROOT]", projects)
    block = block.replace('[RUN OUTPUT PATHS, one per line, or "none"]',
                          "none configured by this plugin; for restricted runs use the caller's existing output destination")
    context = "\n\n".join(intro + [block])
    if len(context) > CONTEXT_LIMIT:
        raise ValueError("complete activation context exceeds the host's 10000-character limit; it was not truncated")
    return context


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register-workspace", type=Path)
    parser.add_argument("--host-workspace")
    args = parser.parse_args()
    plugin = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parent.parent))
    home = Path.home()
    try:
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
        context = activation_context(plugin, home, sys.platform, Path(event.get("cwd") or os.getcwd()),
                                     os.environ.get("TASK_OBSERVER_WORKSPACE"))
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}))
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        if args.register_workspace:
            print("Task Observer registration incomplete: " + str(exc), file=sys.stderr)
            return 1
        message = "Task Observer activation incomplete: " + str(exc)
        print(json.dumps({"systemMessage": message, "hookSpecificOutput": {
            "hookEventName": "SessionStart", "additionalContext": message + ". Do not claim the observer ran; report the setup gap and continue the user's task."}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
