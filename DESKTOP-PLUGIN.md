# Task Observer 3.8.4, candidate 5

This fork preserves **all 15 upstream v3.8.0 files byte-for-byte**, pinned to commit `ac00bed07526475a6679a3dc018e145f5e0a672f`. Plugin/installer version 3.8.4 is independent of that skill version. Candidate 5 renames candidate 4's three commands to include `task-observer-`; collection, review, approval and installation behavior are unchanged. It is a candidate, not a verified final release or upstream endorsement.

## Install and test

Upload the supplied candidate-5 plugin ZIP through Claude Desktop Customize > Plugins. Replace the older Task Observer upload; do not keep two active copies or add another skill symlink. Start a new task/session. With the same account, let the upload sync to Claude Code, then restart or reload plugins. For an isolated Code test, the supported `claude --plugin-dir /absolute/candidate-5.zip` loads that exact ZIP for the session; disable the older Task Observer copy first. The fork's default branch may still hold an older release: do not install an unpinned marketplace source as proof of this candidate.

The commands are:

- `/task-observer-status`: capture, coverage and pending review/install status. No analysis/model call is launched by the helper.
- `/task-observer-review`: harvest recorded evidence, use the original methodology, prepare findings and an independent staged diff. No live installation.
- `/task-observer-apply <batch>`: show the exact plan, ask one real approval card, then automate source/install checks, configured Git publication and ZIP/release outputs.

These are the Cowork command labels. Claude Code adds its plugin namespace: `/task-observer:task-observer-status`, `/task-observer:task-observer-review` and `/task-observer:task-observer-apply`. The old generic `apply`, `review` and `status` command files are removed. Existing batches, approvals and the shared pool are preserved.

A review may use several model turns because it is a requested analysis task. No model runs per tool call or in an automatically scheduled background review. No scheduler is installed.

## What changes in ordinary work

SessionStart initializes/verifies the approved pool and registers a transcript pointer. UserPromptSubmit refreshes the pointer; it never saves a duplicate raw prompt. Stop has an asynchronous best-effort pointer capture. PostToolUse matches only AskUserQuestion to record a genuine explicit apply decision. **There is no PreToolUse gate, Stop gate, enforced startup Skill invocation, injected activation block or mandatory question in ordinary work.** Tiny local pointer writes have bounded overhead; this is not a zero-latency promise. A capture failure/timeout cannot deny ordinary tools. Plan mode performs no capture writes.

The original skill is packaged under `upstream/task-observer/`, outside automatic discovery. Its original broad trigger therefore cannot pull the live-session protocol back into ordinary work. The three commands load the original method as a reference only during explicit review; they do not falsely claim an old startup protocol passed. Source also has explicit `skills: []`, so a root SKILL.md is not implicitly exposed. The build validates original bytes and the staged pure skill independently.

## Storage, privacy and coverage

The same approved user-local pool remains **~/Developer/task-observer**. Existing observations/principles/review dates are preserved. Registration derives the current user's home on macOS; an actual granted alias/registration is needed in a cloud/VM environment. Neither a copied pin nor container HOME creates a replacement pool. Missing storage is reported as incomplete, never zero observations. Installing/removing this plugin leaves the pool intact.

Private integration data is under `skill-observations/.plugin/`: source pointers, cursors, evidence batches, targets, frozen plans and apply receipts. The repository/ZIP includes none of that data. Full thinking is omitted. Token redaction is best effort; private evidence must not be published. Review uses the original confidentiality and staging procedure.

Harvest discovers recent Code histories, honors CLAUDE_CONFIG_DIR, or reads explicitly selected JSONL/Markdown/text/JSON artifacts. It records exact consumed byte ranges, pending bytes and source errors and resumes unfinished batches. A completed capture is **not** a semantic finding or completed review. Stateless/hook-disabled inner calls are not fully observed. In the inspected Autopilot read-only transport, hooks/plugins and session persistence are intentionally disabled: preserve that isolation and use only its available artifacts, with partial coverage disclosed. Async Stop capture can be canceled at `claude -p` teardown; persisted-history discovery is the recovery path. No raw transcript is uploaded anywhere by the collector.

## Review and apply

The upstream review already groups findings by skill, distinguishes facts/judgment calls and prepares validated staged copies. The user-approved adapter adds the mechanical installation step after the exact diff is shown. Its schema, commands and recovery behavior are in [WORKFLOW.md](integration/WORKFLOW.md). The agent prepares configuration and staging; the user should not need to copy files or edit manifests.

Only explicitly confirmed owned canonical Git targets can be installed. Resolve symlinks, preserve unrelated edits, check current source/upstream freshness and use the repository's own validation/build tools. Never patch a plugin cache or overwrite this pinned Observer bundle. A new version/tag or unknown source route is a decision, not an inferred default. Configured checks/build commands and commit/push/release destinations are part of the frozen plan.

A real AskUserQuestion approval is bound to that plan's SHA256. An absent/canceled/unknown answer, altered staged bytes, changed source/installation or changed target configuration leaves apply pending. The installer saves preimages, verifies builds/ZIPs and installations, and records local install, commit, remote push and optional release separately. Failed checks restore source/install files. Interrupted local installs have a guarded `recover` operation; publication failure is resumed without applying twice. No release asset is overwritten silently. This is a workflow guard, not a security sandbox against a process that can edit the user's own files.

## Candidate acceptance

Development checks use temporary homes, synthetic conversations and temporary owned Git repositories only. They exercise capture -> evidence -> reviewed diff -> real-event-shaped approval receipt -> source/install -> ZIP -> local test remote, plus refusal/rollback/resume paths. **Synthetic fixtures do not verify model judgment or live host hook delivery.**

After upload, first give ordinary work without naming Observer and confirm it completes without its questions/gates. Then run status and review on a safe recorded example. Confirm actual findings, full diff, a genuine question-card approval and a controlled test-target install. Verify both hosts load candidate 5 and exercise the actual AskUserQuestion response shape before relying on automatic apply. Final GitHub 3.8.4 release remains withheld until the agreed live checks pass.

For the isolated live test, run `/task-observer-status`, then `/task-observer-review demo`. The latter creates a synthetic conversation, disposable skill source, installation copy and local Git remote under the private demo directory. It must show the correction, evidence, full diff and returned batch ID without changing real skills or production observations. Run `/task-observer-apply <returned-batch-id>` and choose **Apply this plan** on the actual approval card. Confirm the reported source, installation, ZIP and local-remote commit checks pass. If the card does not appear or its host event is unsupported, leave apply pending and report the exact output; do not manufacture an approval receipt. Repeat in the other host.

## Build

Run `python3 tools/build_desktop_plugin.py --check-upstream`, `python3 tools/build_desktop_plugin.py`, `python3 tools/build_desktop_plugin.py --verify`, and the Python unittest suite. The archive contains only the original pure skill, custom commands/integration/hooks, public docs/license and lock. Reproducible ZIP bytes, permissions, membership and original content are verified. No compiler, service, network dependency or schedule is installed by the package.
