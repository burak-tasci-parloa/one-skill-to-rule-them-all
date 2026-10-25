# Task Observer 3.8.4

**Original skill + small startup helper + approved installation helper.** All 15 upstream v3.8.0 files, pinned to `ac00bed07526475a6679a3dc018e145f5e0a672f`, retain their exact bytes and modes. The skill is visible under `skills/task-observer/` in the ZIP. There are no three extra commands or candidate 4/5 collection, batch, cursor, approval-receipt or demo subsystems.

## Install and use

Use `task-observer-3.8.4.zip` on each machine. In Claude Desktop, replace the previous Task Observer plugin, wait for security review to finish, enable it and start a new Cowork task with access to the local `~/Developer` folder. Cowork should show the original `task-observer` skill. Each machine has its own local observation pool; no cross-machine synchronization is configured.

In Claude Code, add the `burak-tasci-parloa/one-skill-to-rule-them-all` marketplace if needed and install `task-observer@one-skill-to-rule-them-all-desktop`. For an existing installation, run `claude plugin marketplace update one-skill-to-rule-them-all-desktop`, then `claude plugin update task-observer@one-skill-to-rule-them-all-desktop` and restart Code. If an earlier candidate remains installed as the same version 3.8.4, uninstall and reinstall it through Code's plugin manager after refreshing the marketplace. The fork's default branch contains this release. The skill's native qualified name is `/task-observer:task-observer`. The same ZIP also works with `claude --plugin-dir /absolute/task-observer-3.8.4.zip`; use one installation route to avoid duplicates.

Only SessionStart is registered. It locates the shared **~/Developer/task-observer** folder, reuses the original idempotent Workspace creation command, directly runs the unchanged session-start scan if writable, and requests the original skill for the remaining protocol. Missing folder access remains visible, while normal work continues. No CLAUDE.md change, extra settings hook or scheduler is required. No mandatory tool/Stop gate is installed. Skill invocation and adherence remain model decisions, not a guarantee made by this hook.

The same original skill handles observations, starter choices, scans, per-skill lookups, review offers and findings. Ask it naturally to review observations or explain status. Do not infer that the complete original protocol ran merely because the skill is listed or the startup helper returned.

## Shared storage and permissions

The startup helper directly calls the original `session-start-scan.sh`. Its complete output is delivered as data, and its checkpoint is written by the original script. Missing access, scan failure or plan mode does not claim success or block ordinary work. A request to preserve project files does not revoke separately approved Observer bookkeeping; an explicit prohibition on all writes is respected by the model.

Existing observations, principles, review dates and registration are preserved. A VM needs the real host folder grant and mapping; its HOME is never substituted for the user's pool. If first setup is needed through a granted VM alias, the agent uses `hooks/session-start.py --initialize <runtime-path> --host-workspace <actual-host-path>` based on folder grant metadata. Access must be granted by the user; installation cannot bypass that. Plan mode does not initialize storage.

Candidate 4/5 private `.plugin` data is not used or deleted by this package. It is left intact to avoid losing prior work. Hook-disabled/stateless harness runs may be missed; this package does not add retrospective transcript harvesting.

## Review and approved installation

The original skill's review already presents evidence and prepares staged updates. The explicit user-authorized addition is described in [INSTALL.md](integration/INSTALL.md): after showing the complete proposal and receiving a real question-card approval, use the source repository's existing checks/build and the small helper to apply the reviewed patch, synchronize owned physical copies and optionally commit/push. Release actions use the repo's existing process only when approved. Plugin caches are not patched. Deliver the resulting ZIP to the user for Desktop upload.

No private observations, transcripts or credentials belong in source or ZIPs. The helper does not implement a second approval system or a new recovery engine. On a failed operation, report the actual completed steps and inspect normal Git/filesystem state before proceeding. Never silently delete Git locks or bypass permissions.

## Verification

Development checks cover only original-file preservation/package layout, startup/bootstrap behavior and one disposable patch -> existing checks/build -> installed copy -> local Git push flow. The optional real Code probe uses a fake HOME and local fake model, not a paid model or user skills. It proves discovery and startup-context delivery, not actual model skill invocation or live review quality.

Candidate 8 passed live Cowork discovery, hook startup/scan/checkpoint, explicit original-skill invocation and user-approved starter-principle setup on 2026-10-25. Earlier absent-hook runs came from a disabled plugin; enabling it restored discovery and startup. The native Claude Code 2.1.310 probe passed discovery, shared-folder initialization and original scan/output delivery using a local fake model. The final package changes only release labels and documentation, preserving candidate 8 behavior.

Automatic model invocation of the remaining protocol, live review/application in the simplified adapter, and a real-model Code session have not been verified end to end. The package remains non-blocking. If a model skips the requested skill invocation, invoke `/task-observer:task-observer` explicitly. First-use starter choices and folder grants still require the user's answer; installing a plugin cannot supply that consent.

## Build

`python3 tools/build_desktop_plugin.py --check-upstream` checks the lock. `python3 tools/build_desktop_plugin.py` validates and packages the original skill and helpers. `python3 tools/build_desktop_plugin.py --verify` checks archive membership, bytes, modes and checksum. No dependencies, services or schedules are installed.
