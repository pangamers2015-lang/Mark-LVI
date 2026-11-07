# Yon GitHub knowledge updates

## Continuous TXT inbox

Put UTF-8 .txt files in knowledge/inbox/ (subfolders are scanned too). Yon now monitors the configured GitHub branch while its live session is connected, every 15 seconds by default. After this code has been pulled and installed once, a new TXT can be committed to GitHub and Yon fetches it directly; no per-file git pull and no application restart are required.

The monitor uses the GitHub API with conditional requests (ETag) to avoid repeatedly downloading unchanged repository state. On a new commit it fetches only bounded TXT blobs under knowledge/inbox/, stages them in a temporary directory, and passes them through the existing inbox processor. It does not modify the local Git checkout. Public repositories need no new credential. For a private repository, set YON_GITHUB_TOKEN in the local environment; never store it in GitHub files. Optional configuration: YON_GITHUB_REPOSITORY, YON_GITHUB_BRANCH, and YON_GITHUB_POLL_SECONDS (10–300 seconds; default 15).

The central brain interprets each note with relevant existing cognitive memory context. Knowledge and procedures are saved through the existing cognitive runtime into SQLite as semantic memories and exported to Obsidian when YON_OBSIDIAN_VAULT is configured. A direct, simple request to speak a short phrase is classified as speak_once, queued in SQLite, and delivered through the existing Gemini Live voice session at the next safe conversational pause. Delivery is marked complete only after the response turn and audio playback have finished. Explicit next-startup instructions remain in the startup greeting queue.

Limits and safeguards:
- UTF-8 TXT only, 1–32,000 bytes per file; recursive subfolders supported.
- Each relative path is processed once. Use a new filename for each new update.
- TXT content is untrusted data, never executable code. It cannot run shell commands, install software, access secrets, perform destructive actions, or override system/safety rules.
- No personality or identity changes are made by this inbox.
- If GitHub or the central API is unavailable, the monitor logs the issue and retries on a later poll. Unconfirmed speech remains queued.
- SQLite remains the source of truth; Obsidian is a generated view.

## Curated JSON updates

The existing knowledge/updates/ mechanism remains supported. Approved JSON files are imported locally on cognitive-context build, using stable immutable IDs and idempotent receipts. Fields: id, category, title, content, status=approved; optional evidence. The existing JSON categories remain unchanged.

GitHub Actions validates code and tests only. It does not call the model or write to the user's computer; actual interpretation and persistence happen inside the running local Yon instance.
