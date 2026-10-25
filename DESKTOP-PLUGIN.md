# Task Observer: Claude Desktop plugin

This compatibility fork is based on upstream **v3.8.0**, commit `ac00bed07526475a6679a3dc018e145f5e0a672f`. Its plugin version is **3.8.1** and its release tag is `desktop-v3.8.1`. This is a fork-maintained compatibility patch, not an upstream release or endorsement.

## Download and install

Download **task-observer.zip** from [the Desktop release](https://github.com/burak-tasci-parloa/one-skill-to-rule-them-all/releases/tag/desktop-v3.8.1). Import that ZIP through Claude Desktop's plugin import interface. Replace or disable a previous Task Observer upload so there is only one selected version. GitHub's automatic source archives and upstream's `.skill` asset are different distributions; use the named plugin ZIP for this route.

The archive has `.claude-plugin/plugin.json` at its root and one complete skill under `skills/task-observer/`. It includes the original references, helper scripts, author credit and CC BY 4.0 license. No hooks, MCP servers or automatic activation settings are added.

Installing the plugin does not establish that the observer runs in every session. Activation remains the upstream process documented in [USER-GUIDE.md](USER-GUIDE.md) and [references/environments.md](references/environments.md). This patch does not edit your CLAUDE.md, register schedules or choose an observation workspace. Static validation does not prove live Desktop import success.

## Changes from upstream

- Removed the unsupported top-level `$schema` property from the plugin manifest and the marketplace manifest
- Added a Desktop ZIP builder that declares `skills/task-observer` explicitly and keeps repository metadata outside the upload
- Advanced the plugin, skill and activation-template version markers to 3.8.1; the skill body and reference content are otherwise unchanged
- Pointed fork source metadata and the separate marketplace identity at this repository
- Added package regression checks and checksum generation

Eoghan Henn and the upstream contributors remain the authors of Task Observer. Copyright (c) 2026 Rebelytics. The [upstream project](https://github.com/rebelytics/one-skill-to-rule-them-all) and [CC BY 4.0 license](LICENSE) are retained in the distribution. Compatibility packaging changes were prepared by Burak Tasci.

## Build and verify

```sh
python3 scripts/validate-skill-bundle.py --repo-only .
python3 tools/build_desktop_plugin.py
python3 tools/build_desktop_plugin.py --verify
python3 -m unittest discover -s tests
```

The builder writes `dist/task-observer.zip`, its SHA256 checksum and an extracted `dist/plugin/` staging tree. It runs the upstream staged-skill validator before writing the archive. To perform the separate plugin manifest check when Claude Code is available:

```sh
claude plugin validate --strict --json dist/plugin
```

The upload manifest is derived from `.claude-plugin/plugin.json` with the explicit packaged skill path added. The verifier compares every archive member against those maintained inputs. Preserve this minimal patch when merging upstream changes; do not restore `$schema` to the upload manifest.
