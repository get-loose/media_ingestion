# Session Carry-Over

Next focus: Worker A – token-based media unit grouping.

- Move away from fuzzy-first clustering for media units.
- Design a folder-local, token-based core derivation:
  - Tokenize stems on separators.
  - Derive per-media-unit cores from shared token prefixes.
  - Attach assets based on token-prefix similarity.
- Use this to:
  - Group files into media units per folder.
  - Surface decorations per unit and per folder (for later interpretation).
- Keep Worker A read-only in PRE-PROJECT (no DB writes, no processed_flag changes).
