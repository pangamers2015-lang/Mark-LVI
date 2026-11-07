# Yon learning inbox

Place one or more user-authored UTF-8 .txt files in this folder (subfolders are also scanned). Yon monitors the configured GitHub branch while its live session is connected, checking every 15 seconds by default. After this monitor code has been installed once, new or revised TXT files can be committed to GitHub and fetched directly by Yon; no per-file git pull or app restart is required.

The central brain reads files one at a time, retrieves relevant existing cognitive memories, interprets each note, and decides whether it contains useful new knowledge, a procedure, a one-time startup instruction, or a short speech request. Knowledge and procedures are stored as semantic memories in SQLite and synchronized to generated Obsidian notes when a vault is configured.

For genuinely new and relevant knowledge, the central brain can choose to notify the user. The notification is queued in SQLite and spoken through the existing live voice session at the next safe conversational pause. Trivial, duplicate, or uncertain information should not generate an announcement. The user can then ask Yon about the new knowledge; it should be recoverable through cognitive memory retrieval.

A direct, simple request to speak a short phrase is also queued and spoken. A clearly specified next-startup instruction remains queued for the next startup greeting.

If a TXT is edited at the same path, its new content is treated as a new revision and reprocessed. Unchanged revisions are skipped, so the same note is not learned or announced repeatedly. For multiple distinct notes, use multiple TXT files. Each revision is retained as a separate memory record; pending announcements from an older revision are superseded.

Limits: UTF-8 TXT only, 1–32,000 bytes per file. Files are data, never executable code. The inbox cannot run shell commands, install software, access secrets, or perform destructive actions. No new package or API key is required for the public repository. The default monitored branch is main. Optional settings: YON_GITHUB_REPOSITORY, YON_GITHUB_BRANCH, and YON_GITHUB_POLL_SECONDS (10–300 seconds).
