# Background task completion notifications

Yon treats every action or plugin declared `NON_BLOCKING` as background work.
When it finishes, the result is persisted in the existing work journal and
placed in a single notification queue.

## Delivery behavior

- A task completion or failure is queued; it is not injected into the live
  conversation immediately.
- The dispatcher waits until the current live turn has completed, output audio
  has drained, the speaking tail has ended, and there has been a short quiet
  interval after the user's latest input.
- A new voice, typed, or remote user message takes priority and resets the
  safe-delivery window.
- Only one task result is delivered at a time. The next notification waits
  until Yon has finished speaking the previous one.
- The live model receives a compact internal handoff and turns it into a
  natural user-facing update. Provider prompts, session IDs, working
  directories, and internal tool conversations are not announced.
- Successful, failed, and interrupted tasks are all reported. FCC metadata is
  stripped from the user-facing result where possible.

## Reliability

Each task record has a `notification_status` field:

- `not_required`: task is still running.
- `pending`: completed result is waiting to be announced.
- `delivering`: Yon is currently announcing it.
- `delivered`: the announcement turn and its audio completed.

Pending announcements are retained in the existing `memory/work_journal.json`
and restored after reconnects. A task left in `delivering` after a restart is
returned to `pending`. Interrupted tasks recovered at startup also receive a
notice. If live delivery times out or fails, the notification remains pending
for a later safe opportunity.

The dispatcher is part of the existing live session task group. It does not
replace the microphone, Gemini Live, voice output, interface, FCC, Qwen, or
existing background task execution.
