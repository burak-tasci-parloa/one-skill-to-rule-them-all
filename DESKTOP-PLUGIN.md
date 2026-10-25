# Task Observer plugin 3.8.4, candidate 3: Cowork and Claude Code

This compatibility fork is based on upstream **v3.8.0**, commit `ac00bed07526475a6679a3dc018e145f5e0a672f`. The upstream skill is preserved byte-for-byte at **3.8.0**, including its version, activation template, every reference and all five helper scripts. Only the separate plugin/installer layer is versioned **3.8.4**. Candidate 3 keeps that complete separation and also executes the original startup scan in the installer, after live candidate-2 testing showed that the model loaded the skill but skipped the scan. It is not an upstream release or endorsement. Each build has a separate validation record: static validation is not evidence of live activation.

## Install once from Cowork

Use the named **task-observer.zip** provided with the candidate build or the [fork's releases](https://github.com/burak-tasci-parloa/one-skill-to-rule-them-all/releases). Check that its plugin manifest version is **3.8.4**. The skill correctly reports **3.8.0**; these are separate versions. In Claude Desktop, open Customize > Plugins > Add > Upload plugin and upload this ZIP. GitHub's automatic source archives and the upstream `.skill` bundle are different distributions.

Start a new Cowork task. With the same Claude account, start Claude Code again so the account plugin syncs; account sync requires Claude Code 2.1.273 or later. `/reload-plugins` can reload a plugin that has already synced. Keep only one active Task Observer: replace/disable an older account upload and disable a separate, older CLI installation before the live check. Do not add another physical skill copy under `~/.claude/skills`.

The source manifest explicitly declares the root skill. The upload places that same complete skill under `skills/task-observer/`. Both include its references and five original helper scripts. `hooks/hooks.json` is discovered automatically while the plugin is enabled; no second hook entry in user settings or edit to a shared `CLAUDE.md` is needed. A `CLAUDE.md` placed in a plugin's root would not provide startup activation.

## What runs automatically

Only **SessionStart** is registered: startup, resume, clear, compact and fork. Its command requires Bash and Python 3, already used by upstream helpers; it installs no dependencies and contacts no network service. A missing interpreter or invalid setup produces an explicit activation-incomplete diagnostic.

The hook resolves the skill inside either distribution, reads the original activation block directly from `references/environments.md`, and substitutes its runtime paths in memory. The full block remains intact, including per-skill lookups, controller/subagent boundaries, observation creation and post-task closure. The installer also executes the unchanged `scripts/session-start-scan.sh` and captures its complete output. Nothing is silently shortened to fit the host's 10,000-character context limit: when activation plus scan output is too large, the full payload is saved as a private file under `skill-observations/.plugin/startup-scans/`, and the hook directs the model to read that entire file in its first batch with the Skill invocation. A pointer means full result delivery is still pending until the file is read.

On native macOS, the hook now initializes the approved storage itself before the model runs. It executes the exact Workspace creation command extracted from `references/observation-log.md`, creates the staging directory, and records the host-folder registration. The original command writes its genuine setup checkpoint and initializes the review date to `never`. It then runs the original scan script, which writes its own genuine scan checkpoint and returns the frontmatter, active-principle headings and findings. A nonzero exit, stderr diagnostic or missing final scan record is reported as incomplete; a setup checkpoint alone never counts as a scan. The installer writes no observations, completed review date or starter-principles decision. Native initialization and scan no longer depend on the model choosing to execute them.

Setup is idempotent and protected by a workspace-local lock: concurrent first sessions create one pool and one setup trace. Existing core files and observations are preserved. A preflight checks nearby existing stores, instruction-file pins and configured observer hooks; a conflicting root, legacy/split log, redirect marker or unsafe file type pauses setup for reconciliation. This bounded preflight does not replace the original protocol's broader pin/consumer inventory. Plan mode does not initialize storage. No instruction file, global settings, extra hook or schedule is edited.

In Cowork, the plugin requests the required host-folder access itself when the persistent pool is not reachable. If the child folder does not exist, grant the user's `Developer` parent and let the bundled helper create `task-observer` beneath the verified mount. The user should not need to type a setup prompt or run the helper manually. A project-only read-only restriction does not prohibit the separately approved observer storage; a ban on all writes, missing permission or a decline is respected and reported as incomplete setup. The hook emits a visible pending-setup notice so skipped initialization is not mistaken for success.

For a verified mount or device-side setup, the single command supplied in startup context initializes storage, runs the original scan and delivers its output:

```sh
bash "<installed-plugin-root>/hooks/session-start.sh" --start-workspace "<resolved-runtime-root>"
```

For a mounted Cowork alias, also pass `--host-workspace "<absolute-path-on-the-user-computer>"`, verified from the folder grant. Run the bundled helper against that persistent mount. With device-only tools, stage the complete integration bundle (including its skill and references) with the original digest checks before running on the device; the Python wrapper alone is not a standalone installer. The earlier `--initialize-workspace` (setup only) and `--register-workspace` operations remain available for their original purposes.

The model must still invoke the unchanged skill and do its per-skill body lookup in that same tool batch; a startup frontmatter scan does not satisfy that lookup. The installer explicitly cues a due starter-set reconciliation as its own interactive question, preserves the original review offer and optional history backfill, and leaves staged-work reconciliation and actual observation/closure behavior to the original skill. No user choice is fabricated or imported automatically. Only SessionStart remains enabled: this package does not add Stop or per-tool enforcement gates and does not claim that it can force every later model action. Removing/replacing the plugin leaves the external pool intact.

## One persistent pool

The approved user-scope workspace is **`~/Developer/task-observer` on the user's computer**. It holds `skill-observations/` and `skill-updates/` and is outside the plugin installation/data cache, so replacing or uninstalling the plugin does not delete the observations. No personal observation content or registration is included in this repository or ZIP.

On macOS, the hook resolves the preferred path from the user's home directory. Cowork can expose the same folder through a different runtime alias. A reachable registration identifies a candidate alias; the Session Start Protocol must verify its host-folder mapping before writes. A registration is data, not proof of a mount. Multiple conflicting registrations require reconciliation, not automatic consolidation.

In an unconnected or cloud session, the hook does not expand the container's home directory into a second pool. It supplies the original block and explicit access/setup instructions, with unresolved paths clearly marked. Subsequent sessions can discover the registered child through a grant to its parent. An unavailable folder is never reported as a clean backlog of zero. The installer's filesystem access does not itself grant model tools access to the pool: a folder grant may be needed for per-skill lookups, full-output reads or observation writes. It may be needed once per machine or when a session has no connection. When the device is unavailable, retain the original handoff/report-back behavior; do not claim persistent logging succeeded.

Use the same ZIP on another Mac: the native default derives from that user's home directory, and Cowork resolves its own granted alias. No username or machine path is baked into the bundle. Each machine has its own local pool unless the user separately arranges synchronization; this plugin installs none.

`TASK_OBSERVER_WORKSPACE` remains an explicit absolute-path override, compatible with upstream helper usage. Do not use it to point into a skill directory, plugin cache, worktree or disposable session storage. Configure the same physical pool in both hosts, then verify it through actual reads/writes across them.

## Review and optional enforcement

The original review offer is unchanged: when OPEN observations exist and the last review is `never` or at least seven days old, offer a review once and continue the user's task unless they opt in. The installer checks the local review date, unfinished review marker and missing dated review directory; it still does not run a review or accept an offer for the user. No weekly job, cron entry or scheduled task is created.

Stop, observation-creation and skill-writing gates remain examples in the original reference; none are installed. Changes to live skills still require the original review/staging and human-installation process. No startup hook applies skill improvements automatically.

The original [user guide](https://github.com/rebelytics/one-skill-to-rule-them-all/blob/v3.8.0/USER-GUIDE.md) and [environment reference](https://github.com/rebelytics/one-skill-to-rule-them-all/blob/v3.8.0/references/environments.md) describe the full methodology. Those upstream files are untouched, including their historical statements that Cowork has no hooks. The separate startup integration supplies the current compatibility note: plugin-bundled SessionStart hooks are supported in Cowork and Claude Code. It reads the original activation template and substitutes only its runtime placeholders in memory; it never rewrites the skill or references.

## Verify in both hosts

1. Confirm one `task-observer` skill is discoverable from the source and upload, including in Cowork's `/` menu.
2. Test a **fresh Cowork task** before any setup prompt: confirm the plugin requests missing folder access and initializes the granted persistent pool. Then verify actual skill invocation, the original scan checkpoint, complete output delivery and remaining model protocol steps on ordinary work. A project-read-only task must not cause a silent skip; an explicit all-writes denial must be honored.
3. Open a **fresh Claude Code session** with unrelated ordinary work: verify automatic native storage initialization, actual original-script scan execution and remaining model protocol steps. Confirm the loaded plugin version is 3.8.4 and the unchanged skill version is 3.8.0, rather than inferring them from a menu entry.
4. Confirm each host reads the same physical workspace and sees the other host's genuine startup checkpoint. A matching copied registration alone is insufficient.
5. Check resume/compaction startup context as well. A failed or unreachable setup must remain visibly incomplete.

Candidate ZIP delivery precedes these live checks. Publish the final 3.8.4 GitHub release only after both hosts pass. Do not describe a manifest check, helper unit test or manual invocation as a live activation test.

## Build and verify

```sh
python3 tools/build_desktop_plugin.py --check-upstream
python3 tools/build_desktop_plugin.py
python3 tools/build_desktop_plugin.py --verify
python3 -m unittest discover -s tests
claude plugin validate --strict --json .claude-plugin/plugin.json
claude plugin validate --strict --json dist/plugin
```

The build writes `dist/task-observer.zip`, its SHA256 checksum and an extracted `dist/plugin/`. Archive verification checks membership, every file's bytes and permissions, manifest compatibility, documentation links and complete startup integration. The included [upstream lock](upstream-skill.json) pins all 15 upstream skill files to their original commit, SHA256 and permissions. The builder refuses changed, missing or added upstream skill files. The ZIP and installation/bootstrap tests verify that the skill remains byte-identical. Upstream's repository-wide version-equality check is intentionally not used for this wrapper, because plugin 3.8.4 and skill 3.8.0 are independently versioned; its original skill validator still runs on the staged, unmodified skill.

Eoghan Henn and upstream contributors remain the authors. Copyright (c) 2026 Rebelytics. The [original project](https://github.com/rebelytics/one-skill-to-rule-them-all/) and [CC BY 4.0 license](LICENSE) are retained. Fork compatibility changes are maintained by Burak Tasci.
