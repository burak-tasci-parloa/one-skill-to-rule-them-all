---
description: Show observer capture, pending review and coverage status without running an analysis or installing changes
disable-model-invocation: true
---

Run `bash "${CLAUDE_PLUGIN_ROOT}/integration/observer.sh" status`. Report the actual mode, last capture, pending batches and coverage limits. Capture means source registration, not a completed analysis or a new finding. No scheduler, model analysis, review, install or publication is authorized by this status command. If setup/access is incomplete, state that and continue normal work.
