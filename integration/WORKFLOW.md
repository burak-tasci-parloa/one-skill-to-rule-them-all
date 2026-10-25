# Passive collection, original review, approved installation

This integration is the user-approved adaptation around the **unchanged** Task Observer v3.8.0 bundle. The bundle lives under `upstream/task-observer/` in an upload and at the repository root in source. Its original frontmatter is not registered for implicit live-session invocation. The plugin exposes explicit review/apply/status commands instead. Ordinary work has no Observer prerequisite, question, skill load, model call or completion gate.

## Boundaries

Preserve the original evidence, generalisability, triage, authoring, confidentiality and staging methodology. The user has authorized a custom installer to perform the previously manual install after a real, specific approval. Do not rewrite the upstream files to describe that adaptation. Review is an intentional user task; an optional starter offer belongs here, never in an unrelated work task. The original seven-day review offer is reported by status/context; no scheduled job or autonomous model analysis is installed.

Local capture records session/source pointers only. Harvest reads recorded Code conversations or explicitly requested Markdown/text/JSON artifacts. It omits thinking and synthetic instruction injections and performs best-effort token redaction. Evidence remains private; this is not a guarantee that arbitrary workplace text contains no secrets. Never publish evidence, transcripts, local paths, client details or review receipts to a skill repository. Published rules/examples must pass the original confidentiality checks.

Code's `CLAUDE_CONFIG_DIR` is respected. A normal discovery looks at recent (default seven-day) Code JSONL histories and hook-registered sources. An explicit `--source` restricts the batch to those sources. The byte budget is explicit, and pending bytes, malformed records and unreachable sources are recorded. No incomplete source is called a complete review. Increasing a byte budget is a scope/cost choice, not permission to omit the rest silently.

Hooks can be disabled by a harness. Autopilot's inspected read-only Claude transport deliberately disables hooks/plugins/session persistence. Do not alter that isolation. Review only its durable output artifacts when provided, and label missing inner execution data. Stop's async pointer capture is best-effort because headless Code teardown can cancel async work; discovery/backfill of persisted histories is the recovery path. No filesystem access means no claimed capture. Plan mode performs no capture writes.

## CLI and private files

Use `bash "<plugin root>/integration/observer.sh" <operation>`. `context` resolves the actual approved pool and original references. `status` reports capture and review states. Existing native setup checks and the original workspace creation command initialize `~/Developer/task-observer`; a cloud alias needs its real host-folder grant/registration. Never create a second pool under a container HOME.

`harvest [--source /absolute/file ...] [--days 7] [--max-bytes 400000]` creates or resumes a durable batch under `skill-observations/.plugin/batches/<24-hex-id>/`. Resume is restricted to the same explicit source set or default discovery scope; a demo never inherits an unfinished production batch. Read **all** of `evidence.json`, including `coverage`, before proposing findings. Cursor advancement means evidence is saved, not reviewed. Finish a batch before silently creating another in that scope. Use the original observation helper to write genuine findings to the common observation log; do not convert every source record to a finding.

Write `REVIEW.md` in the batch: source coverage, evidenced findings grouped by skill, hypotheses/decisions, selected changes, verification, and work left open. Also follow the original comprehensive review record procedure when performing that full review; the integration batch does not fabricate its timestamp. `finish --batch <id>` requires a nonempty batch REVIEW.md and closes collection work only; it does not install a plan or claim the comprehensive review happened.

## Source and install configuration

The agent prepares configuration; the user should not have to edit files or copy skills. Resolve physical paths, inspect source ownership/freshness and existing local changes. No automatic changes to third-party caches, synced plugin generations, volatile upstream copies or this pinned Observer bundle. Uncertain source ownership is a decision to resolve, not an inferred fact.

For an owned target, write a private JSON configuration and call `register-target --name <target> --config /absolute/config.json`. Example schema:

```json
{
  "ownership": "user",
  "repo": "/absolute/owned/source-repo",
  "skill_dir": "skills/example-skill",
  "installs": ["/absolute/existing/skill-install"],
  "checks": [["python3", "tools/validate.py"]],
  "build": [["python3", "tools/package.py"]],
  "artifacts": ["dist/example-plugin.zip"],
  "publish": {"remote": "origin", "branch": "review-branch"}
}
```

`checks` and `build` are argv arrays with repository working directory; their exact commands are part of the approved plan. Do not introduce dependencies or unconstrained shell strings. `publish: {}` means no commit/push. An optional release under `publish.release` has explicit `repo`, `tag`, `title`, `notes` and `draft`; it is never inferred. Show all publishing destinations and version choices before approval. The installer requires a clean target repo and exact current HEAD. Reconcile dirty/stale work without discarding it. One target per repository per plan avoids interleaved commits; combine a related update under one target, or use separate reviewed batches.

Source and existing physical install destinations are synchronized; a symlink resolving to source needs no second copy. Do not add duplicate discovery entries. The agent stages the FULL independent skill directory (never a symlink to live), validates it using the original authoring procedure, and stages additional source files such as README/version manifests when needed. Stage the repository's existing build tools too if they need a reviewed change; configuration must not assume a build updates a plugin version by itself.

Write `changes.json` as a list:

```json
[
  {
    "target": "example",
    "staged": "/absolute/batch/staged/example",
    "repo_files": {"README.md": "/absolute/batch/staged-repo/README.md"}
  }
]
```

All staged files must be inside this batch. `freeze --batch <id> --changes /absolute/changes.json` snapshots source/install bytes, modes, HEAD, staged files, selected extra source files, checks/builds and publication options. It writes `PLAN.diff`, `plan.json`, `plan-summary.json` and returns the plan SHA256. Present the complete diff and execution summary. If the user selects a subset or anything changes, regenerate and show the new plan. No editing staged files after approval.

## One approval, automated mechanics

The apply command asks a real card with header **Observer**, question exactly `Approve observer plan <64-hex-hash>?`, and option **Apply this plan** (other options: Keep staged; Revise selection). Only the actual successful AskUserQuestion PostToolUse response can record this integration approval. A model-written receipt, CLI boolean, historical transcript or unrelated answer is not approval. Do not simulate a hook from the assistant. The receipt is a workflow guard, not a tamper-proof boundary against a process with access to the user's files.

`apply --batch <id> --plan-hash <hash>` checks that receipt and freshness before live changes. It saves preimages, updates source and approved extra source files, executes the specified checks/build, verifies ZIP paths exist, then synchronizes and reads back installations. A verification failure restores owned source/install preimages. Generated build outputs outside the approved paths are not blindly cleaned. An interrupted write leaves rollback data and a pending receipt requiring reconciliation, not silent success.

`recover --batch <id> --plan-hash <hash>` restores an interrupted local attempt only when every affected member still matches its approved pre/post image. It refuses independent edits, retains previous rollback data, and never reverts a completed/published install. After recovery, the original plan can be retried if its freshness checks still pass; changed checks or code need a new plan/approval. A changed Git remote URL also invalidates the original approval. Repo scripts/builds may not silently modify unapproved source paths.

For live acceptance, `/task-observer:review demo` creates an isolated synthetic conversation, owned source repository, physical install copy and local bare remote under the private demos directory. Only that explicit source is harvested. Its findings stay in the private batch; no synthetic correction enters the production observation log or principles. The model still has to infer the change, show the complete diff and obtain the real apply card. The demo never publishes to GitHub or adds an installed discovery entry.

With publishing configured, commit only the selected source paths, push the exact commit without force, verify the remote branch, and optionally create/upload the explicitly approved release. Existing mismatched releases/assets are not overwritten. A local install, a local commit, a verified push and a verified release are separate states. Publication failure leaves a resumable local-applied receipt; re-running this exact batch resumes publication rather than applying twice. Do not reset a published commit to pretend rollback. Artifacts can be given directly to the user even while remote publication remains pending, with that distinction stated.

No user skill source is changed during plugin development tests. The candidate's final GitHub release remains outside this installer and requires the separately agreed live acceptance in both hosts.
