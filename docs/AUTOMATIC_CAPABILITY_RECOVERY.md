# Automatic Capability Recovery

## Purpose

When the user requests a real operation and Yon lacks a required technical capability,
Yon should investigate how to gain that capability instead of stopping at "I cannot".
This mechanism is deliberately separate from ordinary question answering.

## Trigger paths

1. **Explicit tool failure:** `main.py` checks foreground and background tool results.
   Only explicit missing-capability signals (unknown tool, unsupported operation/platform,
   or an unavailable registered action) start the recovery workflow automatically.
2. **No suitable tool exists:** the central model is instructed in `core/prompt.txt`
   to call the `capability_recovery` action with the task and precise limitation.

Permission denials, missing files, invalid credentials, quota/rate limits, timeouts,
network failures and other transient errors are not treated as missing capabilities.

## Research and approval lifecycle

- `actions/capability_recovery.py` sanitizes task context, redacts credentials and
  local user-profile paths, checks for an existing proposal and rejected approaches,
  then asks FCC Cloud for research only.
- FCC must not modify files, install packages, execute downloaded code or inspect
  unrelated/private user data during research.
- A concise proposal is created with sources, approach, risks, dependencies and tests.
- The proposal is presented to the user. No sandbox is created until explicit approval.
- After sandbox approval, FCC works only in the isolated proposal workspace and its
  own virtual environment.
- A successful sandbox test requires a separate approval before production integration.
- Production integration is separately tested and recorded as verified only with evidence.

## Rejection and repetition control

Rejecting a proposal erases its detailed implementation notes and retains a narrow
topic + rejected-approach filter. Active proposals are reused rather than duplicated.
The user's underlying goal is never marked irrelevant merely because one approach
was rejected.

## Privacy and UI

Model-to-model prompts and FCC's intermediate conversation stay internal. The user
sees only task progress and the resulting update note. Sensitive argument keys are
redacted, and absolute paths under the user's Windows profile are not sent to FCC.

## Validation

Run:

```powershell
python -m pytest tests/test_capability_recovery.py tests/test_capability_development.py -v
python -m py_compile main.py actions/capability_recovery.py actions/capability_development.py
```

These checks validate classification and code syntax. A runtime test in the actual Yon
application is still required to confirm the full automatic path with FCC Cloud.
