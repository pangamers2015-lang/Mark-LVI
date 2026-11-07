# Yon GitHub knowledge updates

## Continuous TXT inbox

Put UTF-8 .txt files in knowledge/inbox/ (subfolders are scanned too). Yon now monitors the configured GitHub branch while its live session is connected, every 15 seconds by default. After this code has been pulled and installed once, a new TXT can be committed to GitHub and Yon fetches it directly; no per-file git pull and no application restart are required.

The monitor uses the GitHub API with conditional requests (ETag) to avoid repeatedly downloading unchanged repository state. On a new commit it fetches only bounded TXT blobs under knowledge/inbox/, stages them in a temporary directory, and passes them through the existing inbox processor. It does not modify the local Git checkout. A fine-grained personal access token is recommended even for a public repository to raise the unauthenticated API rate limit; grant access only to Mark-LVI with Contents: Read-only. Set YON_GITHUB_TOKEN in the local environment; never store it in GitHub files. When GitHub returns HTTP 403/429, Yon respects Retry-After or X-RateLimit-Reset and pauses polling instead of repeatedly hitting the API. Optional configuration: YON_GITHUB_REPOSITORY, YON_GITHUB_BRANCH (default main), and YON_GITHUB_POLL_SECONDS (10–300 seconds; default 15).

The central brain reads files one at a time and interprets each note with relevant existing cognitive memory context. It judges whether the content is genuinely new and relevant, then saves knowledge and procedures through the existing cognitive runtime into SQLite as semantic memories and exports them to Obsidian when YON_OBSIDIAN_VAULT is configured. For important new knowledge, it may set notify_user=true and provide a concise notification; that message is queued in the existing live-speech queue and spoken at the next safe conversational pause. Routine, duplicate, or uncertain information should not trigger an announcement. The user can ask about the discovery later; the stored semantic memory is available to the existing retrieval system. A direct, simple request to speak a short phrase is classified as speak_once, queued in SQLite, and delivered through the existing Gemini Live voice session at the next safe conversational pause. Delivery is marked complete only after the response turn and audio playback have finished. Explicit next-startup instructions remain in the startup greeting queue.

Limits and safeguards:
- UTF-8 TXT only, 1–32,000 bytes per file; recursive subfolders supported.
- Each relative path is tracked by content hash: unchanged content is skipped, while an edited file at the same path is reprocessed as a new revision. Use multiple TXT files for separate notes; old pending announcements are superseded when a file is revised.
- TXT content is untrusted data, never executable code. It cannot run shell commands, install software, access secrets, perform destructive actions, or override system/safety rules.
- No personality or identity changes are made by this inbox.
- If GitHub or the central API is unavailable, the monitor logs the issue and retries on a later poll. Unconfirmed speech remains queued.
- SQLite remains the source of truth; Obsidian is a generated view. The cognitive database uses WAL mode, a shared in-process lock, and a 30-second busy timeout. Inbox revision handling performs cognitive-memory writes before receipt/directive writes on its separate connection, avoiding nested write transactions against the same database. No database is deleted or recreated.

## Curated JSON updates

The existing knowledge/updates/ mechanism remains supported. Approved JSON files are imported locally on cognitive-context build, using stable immutable IDs and idempotent receipts. Fields: id, category, title, content, status=approved; optional evidence. The existing JSON categories remain unchanged.

GitHub Actions validates code and tests only. It does not call the model or write to the user's computer; actual interpretation and persistence happen inside the running local Yon instance.
