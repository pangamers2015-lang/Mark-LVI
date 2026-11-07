# Yon GitHub learning and knowledge updates

## TXT inbox

Put UTF-8 `.txt` files in `knowledge/inbox/` (subfolders are scanned too). After committing to `feature/behavioral-preferences`, pull that branch locally and start Yon.

At startup, `memory.github_inbox` reads new TXT files and sends their contents to the already-configured central brain through `core.gemini` using the existing local API configuration. No additional provider, API key, GitHub secret, package or local service is required for this path. The GitHub Actions workflow validates code and tests; it does not call the model or write to the user's computer.

The central brain classifies each note as knowledge, procedure, or a one-time next-startup instruction. Knowledge and procedures are saved through the existing cognitive runtime into SQLite as hypothesis-level semantic memories, with retrieval/relationship processing and Obsidian export when `YON_OBSIDIAN_VAULT` is configured. One-time startup instructions are separately queued in SQLite and included in the next startup greeting; they are marked delivered only after the greeting request is sent. Repeated startup scans do not duplicate processed files.

Limits and safeguards:
- UTF-8 TXT only, 1–32,000 bytes per file; recursive subfolders supported.
- Each relative file path is processed once. Use a new filename for a new instruction.
- TXT content is data to interpret, never executable code. The inbox cannot run shell commands, install software, access secrets, perform destructive actions, or override system/safety rules.
- The inbox does not create personality or identity changes. The supported categories are knowledge, procedure and one-time startup instruction.
- SQLite remains the source of truth. Obsidian is a generated view; it must be configured locally with `YON_OBSIDIAN_VAULT`.
- If the central API is unavailable or interpretation fails, the file is left unprocessed and the startup log reports the error. No success is claimed.

## Curated JSON updates

The existing `knowledge/updates/` mechanism remains supported. Approved JSON files are imported locally on cognitive-context build, using stable immutable IDs and idempotent receipts. Fields: id, category, title, content, status=approved; optional evidence. The existing JSON categories remain unchanged.

GitHub Actions runs isolated validation tests only. A green workflow does not mean local SQLite has been updated; local import is confirmed by the local processor and database write.
