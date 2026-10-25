# Task Observer 3.8.3: Cowork and Claude Code

This compatibility fork is based on upstream **v3.8.0**, commit `ac00bed07526475a6679a3dc018e145f5e0a672f`. It preserves Eoghan Henn / Rebelytics' observer methodology and adds the packaging and startup integration described here. It is not an upstream release or endorsement. Each build has a separate validation record: static validation is not evidence of live activation.

## Install once from Cowork

Use the named **task-observer.zip** provided with the candidate build or the [fork's releases](https://github.com/burak-tasci-parloa/one-skill-to-rule-them-all/releases). Check that its manifest version is **3.8.3**. In Claude Desktop, open Customize > Plugins > Add > Upload plugin and upload this ZIP. GitHub's automatic source archives and the upstream `.skill` bundle are different distributions.

Start a new Cowork task. With the same Claude account, start Claude Code again so the account plugin syncs; account sync requires Claude Code 2.1.273 or later. `/reload-plugins` can reload a plugin that has already synced. Keep only one active Task Observer: replace/disable an older account upload and disable a separate, older CLI installation before the live check. Do not add another physical skill copy under `~/.claude/skills`.

The source manifest explicitly declares the root skill. The upload places that same complete skill under `skills/task-observer/`. Both include its references and five original helper scripts. `hooks/hooks.json` is discovered automatically while the plugin is enabled; no second hook entry in user settings or edit to a shared `CLAUDE.md` is needed. A `CLAUDE.md` placed in a plugin's root would not provide startup activation.

## What runs automatically

Only **SessionStart** is registered: startup, resume, clear, compact and fork. Its command requires Bash and Python 3, already used by upstream helpers; it installs no dependencies and contacts no network service. A missing interpreter or invalid setup produces an explicit activation-incomplete diagnostic.

The hook resolves the skill inside either distribution, reads the original activation block directly from `references/environments.md`, substitutes the resolved paths, and adds it to the session context with the open-observation count and last-review date. The full block remains intact, including per-skill lookups, controller/subagent boundaries, observation creation and post-task closure. It is not replaced by a short startup reminder. Output over the host's 10,000-character limit is rejected explicitly, never silently shortened.

The hook itself does **not** create observations, checkpoints or review timestamps. Claude must invoke the skill and execute its original Session Start Protocol. Successful hook output proves only that context was delivered, not that the model followed it.

The first protocol run creates the workspace with the original procedure, checks existing pins/logs and non-interactive consumers, and offers the original starter-principles choice. It must not silently import them. After initialization, it records the shared-folder registration using the integration helper; this writes only private metadata at `skill-observations/plugin-activation.json`, without editing instructions, settings, skills or schedules.

The command supplied in startup context is:

```sh
bash "<installed-plugin-root>/hooks/session-start.sh" --register-workspace "<resolved-runtime-root>"
```

For a mounted Cowork alias, also pass `--host-workspace "<absolute-path-on-the-user-computer>"`. Run registration on the filesystem holding the persistent folder. If the helper is only in the cloud container, follow the upstream digest-matched staging procedure rather than treating a cloud-only path as a device path.

## One persistent pool

The approved user-scope workspace is **`~/Developer/task-observer` on the user's computer**. It holds `skill-observations/` and `skill-updates/` and is outside the plugin installation/data cache, so replacing or uninstalling the plugin does not delete the observations. No personal observation content or registration is included in this repository or ZIP.

On macOS, the hook resolves the preferred path from the user's home directory. Cowork can expose the same folder through a different runtime alias. A reachable registration identifies a candidate alias; the Session Start Protocol must verify its host-folder mapping before writes. A registration is data, not proof of a mount. Multiple conflicting registrations require reconciliation, not automatic consolidation.

In an unconnected or cloud session, the hook does not expand the container's home directory into a second pool. It supplies setup instructions and the original block, with unresolved paths clearly marked for resolution through the device tools or folder connection. An unavailable folder is never reported as a clean backlog of zero. A folder grant may be needed once or when the session has no connection. When the device is unavailable, retain the original handoff/report-back behavior; do not claim persistent logging succeeded.

`TASK_OBSERVER_WORKSPACE` remains an explicit absolute-path override, compatible with upstream helper usage. Do not use it to point into a skill directory, plugin cache, worktree or disposable session storage. Configure the same physical pool in both hosts, then verify it through actual reads/writes across them.

## Review and optional enforcement

The original review offer is unchanged: when OPEN observations exist and the last review is `never` or at least seven days old, offer a review once and continue the user's task unless they opt in. A hook's summary does not replace the protocol's review-record checks. No weekly job, cron entry or scheduled task is created.

Stop, observation-creation and skill-writing gates remain examples in the original reference; none are installed. Changes to live skills still require the original review/staging and human-installation process. No startup hook applies skill improvements automatically.

The original [user guide](https://github.com/rebelytics/one-skill-to-rule-them-all/blob/v3.8.0/USER-GUIDE.md) and [environment reference](https://github.com/rebelytics/one-skill-to-rule-them-all/blob/v3.8.0/references/environments.md) describe the full methodology. This fork corrects only the environment reference's outdated Cowork hook-support statements and template version. Current Anthropic documentation lists plugin-bundled hooks for both Cowork and Claude Code.

## Verify in both hosts

1. Confirm one `task-observer` skill is discoverable from the source and upload, including in Cowork's `/` menu.
2. Open a **fresh Cowork task** with ordinary work that names neither the observer nor the log. Verify the skill invocation and actual protocol execution, not just its listing or a manually requested call.
3. Open a **fresh Claude Code session** with unrelated ordinary work and collect the same evidence.
4. Confirm each host reads the same physical workspace and sees the other host's genuine startup checkpoint. A matching copied registration alone is insufficient.
5. Check resume/compaction startup context as well. A failed or unreachable setup must remain visibly incomplete.

Candidate ZIP delivery precedes these live checks. Publish the final 3.8.3 GitHub release only after both hosts pass. Do not describe a manifest check, helper unit test or manual invocation as a live activation test.

## Build and verify

```sh
python3 scripts/validate-skill-bundle.py --repo-only .
python3 tools/build_desktop_plugin.py
python3 tools/build_desktop_plugin.py --verify
python3 -m unittest discover -s tests
claude plugin validate --strict --json .claude-plugin/plugin.json
claude plugin validate --strict --json dist/plugin
```

The build writes `dist/task-observer.zip`, its SHA256 checksum and an extracted `dist/plugin/`. Archive verification checks membership, every file's bytes and permissions, manifest compatibility, documentation links and complete startup integration. The original five helper scripts remain unchanged; the core skill changes only its version header.

Eoghan Henn and upstream contributors remain the authors. Copyright (c) 2026 Rebelytics. The [original project](https://github.com/rebelytics/one-skill-to-rule-them-all/) and [CC BY 4.0 license](LICENSE) are retained. Fork compatibility changes are maintained by Burak Tasci.
