# Yon shared workspace

This folder is synchronized in both directions between the local Yon installation
and the configured GitHub branch.

Create folders and place UTF-8 `.txt` or `.md` files here. Yon checks for
changes about once per minute while its live session is connected. A subfolder
such as `Oi Chat/` is represented on GitHub as soon as it contains an eligible
text file.

Safety rules:
- Only `.txt` and `.md` files up to 256 KB are synchronized.
- Hidden paths, symlinks, binary files, credentials, configuration, and files
  outside this folder are excluded.
- Deletions are not propagated.
- Conflicting edits are reported and neither side is overwritten.
- Uploads require a fine-grained GitHub token with Contents: Read and write.
