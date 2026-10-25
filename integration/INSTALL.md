# Approved installation extension

The original Task Observer remains responsible for observation, review, evidence, authoring, staging and validation. Its 15 files are unchanged. Use this reference only when review leads to an installation; ordinary work does not load or run an installer.

The user has explicitly requested automatic installation of approved changes to their own skills, including canonical source updates, existing installation copies, Git publication and applicable plugin ZIPs. This is an external extension to the original staging-only delivery policy, not a claim that upstream installs live files. No separate review/apply/status commands, transcript collector, batch/cursor store, approval receipts or scheduler are installed.

## Review and approve

Follow the original review. Inspect the real owned source repo, physical installation symlinks and existing validation/build instructions. Read staged files and show their complete diff, affected paths, checks, publication destination and any version/release decision. Do not edit foreign-maintained skills or plugin caches. Unclear ownership or release choices need user input.

Ask one real AskUserQuestion card for the specific proposed update; allow approval, revision or deferral. Only an actual explicit answer authorizes the corresponding install. This helper does not prove approval or add a second permission system. Existing host permission controls still apply. If AskUserQuestion is unavailable, explain that and leave installation pending.

## Apply using existing tools

After approval, prepare a Git patch and a temporary plan outside the target repo. Do not create a target registry or new workflow database. The helper is `python3 <plugin-root>/integration/install.py <absolute-plan.json>`:

```json
{
  "ownership": "user",
  "repo": "/absolute/owned/source",
  "patch": "/absolute/reviewed.patch",
  "paths": ["skills/example", ".claude-plugin/plugin.json", "README.md"],
  "checks": [["python3", "tools/validate.py"]],
  "build": [["python3", "tools/build.py"]],
  "artifacts": ["dist/plugin.zip"],
  "installs": [{"source": "skills/example", "destination": "/absolute/existing/skill-copy"}],
  "publish": {"remote": "origin", "branch": "main", "message": "Update approved skill guidance"}
}
```

Use the repository's actual tools, not the example commands. Omit publishing when not approved. A symlink resolving to source needs no copy. Plugin changes require its real source manifests/version and full existing build, not just a loose SKILL.md. If a release is approved, use the repository's existing release process after verifying the push; do not invent another publisher. Never publish private observations or review records. Give the resulting ZIP to the user for Claude Desktop upload; filesystem changes cannot prove the Desktop plugin was updated.

The helper requires a clean source, checks that the reviewed patch applies, runs the existing checks/build, verifies artifacts and installation copies, and commits/pushes only when requested. It creates no persistent control state. If a step fails, inspect Git and actual files, report which actions completed, then resolve only the concrete failure using normal tools and the existing approval scope. Do not blindly rerun a partially applied patch, delete Git locks, discard work or bypass a host refusal. A changed proposal requires fresh approval.

For an isolated acceptance test, use a disposable skill repo, physical copy and local bare remote under a temporary directory. Record one synthetic correction, ask the original skill to review it and show the diff, then approve installation. Keep all synthetic observations and principles out of the production pool. No special demo command or permanent demo subsystem is needed.
