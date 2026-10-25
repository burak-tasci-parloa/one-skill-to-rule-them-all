# Task Observer 3.8.4, candidate 8

**Original skill + small startup helper + approved installation helper.** All 15 upstream v3.8.0 files, pinned to `ac00bed07526475a6679a3dc018e145f5e0a672f`, retain their exact bytes and modes. The skill is visible under `skills/task-observer/` in the ZIP. There are no three extra commands or candidate 4/5 collection, batch, cursor, approval-receipt or demo subsystems.

## Install and use

Replace the previous Task Observer plugin with this ZIP and start a new session. Cowork should show the original `task-observer` skill. Claude Code uses its native qualified name, `/task-observer:task-observer`. For an exact Code test, disable an older active copy and launch `claude --plugin-dir /absolute/task-observer-3.8.4-candidate-8.zip`. The fork's default branch may be older; an unpinned marketplace install is not proof of this candidate.

Only SessionStart is registered. It locates the shared **~/Developer/task-observer** folder, reuses the original idempotent Workspace creation command, directly runs the unchanged session-start scan if writable, and requests the original skill for the remaining protocol. Missing folder access remains visible, while normal work continues. No CLAUDE.md change, extra settings hook or scheduler is required. No mandatory tool/Stop gate is installed. Skill invocation and adherence remain model decisions, not a guarantee made by this hook.

The same original skill handles observations, starter choices, scans, per-skill lookups, review offers and findings. Ask it naturally to review observations or explain status. Do not infer that the complete original protocol ran merely because the skill is listed or the startup helper returned.

## Shared storage and permissions

Candidate 8 adds only a direct call to the original `session-start-scan.sh` in the existing startup helper. Its complete output is delivered as data, and its checkpoint is written by the original script. Missing access, scan failure or plan mode does not claim success or block ordinary work. Hook registration and installer behavior are unchanged. A request to preserve project files does not revoke separately approved Observer bookkeeping; an explicit prohibition on all writes is respected by the model.

Existing observations, principles, review dates and registration are preserved. A VM needs the real host folder grant and mapping; its HOME is never substituted for the user's pool. If first setup is needed through a granted VM alias, the agent uses `hooks/session-start.py --initialize <runtime-path> --host-workspace <actual-host-path>` based on folder grant metadata. Access must be granted by the user; installation cannot bypass that. Plan mode does not initialize storage.

Candidate 4/5 private `.plugin` data is not used or deleted by this package. It is left intact to avoid losing prior work. Hook-disabled/stateless harness runs may be missed; this candidate does not add retrospective transcript harvesting.

## Review and approved installation

The original skill's review already presents evidence and prepares staged updates. The explicit user-authorized addition is described in [INSTALL.md](integration/INSTALL.md): after showing the complete proposal and receiving a real question-card approval, use the source repository's existing checks/build and the small helper to apply the reviewed patch, synchronize owned physical copies and optionally commit/push. Release actions use the repo's existing process only when approved. Plugin caches are not patched. Deliver the resulting ZIP to the user for Desktop upload.

No private observations, transcripts or credentials belong in source or ZIPs. The helper does not implement a second approval system or a new recovery engine. On a failed operation, report the actual completed steps and inspect normal Git/filesystem state before proceeding. Never silently delete Git locks or bypass permissions.

## Narrow acceptance checks

Development checks cover only original-file preservation/package layout, startup/bootstrap behavior and one disposable patch -> existing checks/build -> installed copy -> local Git push flow. The optional real Code probe uses a fake HOME and local fake model, not a paid model or user skills. It proves discovery and startup-context delivery, not actual model skill invocation or live review quality.

After upload, use this normal prompt in both hosts: **Read this folder without changing project files and explain its purpose in three sentences.** Confirm the original skill is available and invoked. The startup scan now runs inside the hook, so it need not appear as a separate model tool call: verify the fresh `session-start scan` line in `skill-observations/checkpoints.log` and its delivered output. Skill invocation and the remaining protocol are separate live checks. Then ask it to review an isolated example in a disposable skill repo, present its diff and apply only after your approval. Follow [INSTALL.md](integration/INSTALL.md) for fixture isolation; synthetic corrections must not enter the production observations. Existing candidate-4 demo completion is evidence for that earlier adapter, not proof of this restored original flow. Final release remains pending both hosts' live acceptance.

## Build

`python3 tools/build_desktop_plugin.py --check-upstream` checks the lock. `python3 tools/build_desktop_plugin.py` validates and packages the original skill and helpers. `python3 tools/build_desktop_plugin.py --verify` checks archive membership, bytes, modes and checksum. No dependencies, services or schedules are installed.
