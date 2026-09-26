# Pi extension

Almanac ships a native pi extension from this repo.
The extension is TypeScript, but lifecycle policy stays in Python core: pi calls a short-lived JSON adapter (`python3 -m almanac.pi_bridge`) for briefing, recall, and read-tool context.

For local testing:

```bash
pi -e ./extensions/almanac.ts
```

For package installation from a checkout:

```bash
pi install /path/to/almanac
```

The pi bridge does not start a long-lived MCP child process.
Automatic capture runs detached SessionEnd-style triage by default; explicit/manual captures can still be queued in local state for review and processed into curated notes manually.

Useful pi commands/tools:

- `/almanac` - open the TUI dashboard for status, readable queued-capture review cards, explicit capture selection, processing previews, live group-level processing progress, and retry controls for failed processing groups.
- `/almanac-status` or `almanac_status` - bridge/vault status, lifecycle feature state, queue count.
- `/almanac-queue` or `almanac_queue` - list queued pi capture candidates with deterministic excerpts and size metadata. Add `--include-generated-summaries`, pass `includeGeneratedSummaries: true`, or enable `queueSummaries` to opt in to cached model-generated review summaries.
- `/almanac-process` or `almanac_process` - process selected queued captures into curated durable notes. With no arguments the command shows a dry-run preview; use `/almanac` for interactive selection and confirmation.
- `almanac_capture` - manually write a durable note; pass `queue: true` to queue instead.

## Configuration

Pi bridge configuration can live in either `~/.config/almanac/pi-bridge.json`, project-local `.pi/settings.json`, or project `package.json`.
The bridge reads `almanac.piBridge` first, then `piBridge`, then top-level keys:

```json
{
  "almanac": {
    "piBridge": {
      "enabled": true,
      "briefing": true,
      "promptRecall": true,
      "toolContext": true,
      "autoCapture": true,
      "captureQueue": false,
      "processQueue": true,
      "processQueueOnSessionClose": false,
      "queueSummaries": false,
      "processQueueMaxCaptures": 3,
      "processQueueModel": "claude-sonnet-4-20250514",
      "maxInjectedChars": 4000,
      "maxToolContextPerSession": 5
    }
  }
}
```

Environment variables override file config:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ALMANAC_PI_ENABLED` | `true` | Enable/disable the extension lifecycle work. |
| `ALMANAC_PI_BRIEFING` | `true` | First-turn project briefing. |
| `ALMANAC_PI_PROMPT_RECALL` | `true` | Prompt recall before each agent turn. |
| `ALMANAC_PI_TOOL_CONTEXT` | `true` | Read-tool context injection. |
| `ALMANAC_PI_MAX_INJECTED_CHARS` | `4000` | Per-injection character cap. |
| `ALMANAC_PI_MAX_TOOL_CONTEXT_PER_SESSION` | `5` | Tool-context injection cap per pi session. |
| `ALMANAC_PI_AUTO_CAPTURE` | `true` | Run SessionEnd-style triage from the persisted Pi transcript on compaction/shutdown lifecycle events. |
| `ALMANAC_PI_CAPTURE_QUEUE` | `false` | Legacy/manual queue mode flag. Automatic capture does not append to the queue by default; use `almanac_capture(queue: true)` or `/almanac-process` for explicit queue review. |
| `ALMANAC_PI_PROCESS_QUEUE` | `true` | Enable manual queued-capture processing. |
| `ALMANAC_PI_PROCESS_QUEUE_ON_SESSION_CLOSE` | `false` | Reserved future automation route for processing a small batch on session close. |
| `ALMANAC_PI_QUEUE_SUMMARIES` | `false` | Opt in to model-generated queued-capture review summaries. Summaries are generated only for visible queue cards and cached under Pi state by capture content digest. |
| `ALMANAC_PI_PROCESS_QUEUE_MAX_CAPTURES` | `3` | Reserved future cap for session-close processing. |
| `ALMANAC_PI_PROCESS_QUEUE_MODEL` | `claude-sonnet-4-20250514` | Model for processor sessions; set config/env explicitly to override or `null` in config to use pi's default. |

## Automatic capture lifecycle

When automatic capture is enabled (the default), Pi no longer grows the review queue.
On `session_before_compact` or `session_shutdown`, the extension asks `python3 -m almanac.pi_bridge triage` to validate `ctx.sessionManager.getSessionFile()` and spawn the same detached `hooks/almanac-triage.py` pipeline used by Claude Code with `ALMANAC_AGENT=pi`.
Meaningful sessions get the normal triage outputs: a fleeting session line, a project session update, and structured atomic notes only when the shared substantial/new-insight gates pass.
Health records are written to the triage-health log for missing transcripts, disallowed paths, spawn failures, parse/LLM failures from the shared hook, and successful Pi triage spawn.

Manual queue review remains available for explicit captures (`almanac_capture` with `queue: true`, `/almanac-queue`, and `/almanac-process`).
Processing runs write progress under `${ALMANAC_PI_STATE_HOME:-${XDG_STATE_HOME:-~/.local/state}/almanac/pi}/processing/<run-id>/`, and the `/almanac` footer shows a compact active/failed/interrupted indicator while background processing is visible.
Failed processing groups keep their queue entries and can be retried directly from the TUI without reconstructing filters or selections.
When generated queue summaries are enabled, the bridge writes a digest-keyed cache at `${ALMANAC_PI_STATE_HOME:-${XDG_STATE_HOME:-~/.local/state}/almanac/pi}/queue/pi-capture-summaries.json`; changing a queued capture's title/body/metadata invalidates the cached summary while the default queue path remains deterministic excerpt-only.
The processor prompt receives deterministic existing-note deduplication context and instructs curators to store original project/cwd/branch/session metadata as note frontmatter via `almanac_capture`, not as prose boilerplate.

## Release smoke checklist

Before cutting a pi bridge release, the interactive smoke checklist has moved to [docs/history/releasing.md](history/releasing.md#pi-bridge-release-smoke-checklist).
