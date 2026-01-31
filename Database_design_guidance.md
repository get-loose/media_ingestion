# db.py Design Guidance (Intent Only)

db.py responsibilities:
- Own database connections
- Hide SQLite specifics from the rest of the code
- Provide explicit, small functions (no magic)

Design principles:
- One connection per process
- Explicit transactions
- No global state beyond connection management
- No business logic in db.py
- Schema creation handled explicitly (not implicitly on import)

Future-proofing:
- Avoid hard-coding table names outside db.py
- Keep SQL centralized
- Prepare for possible migration to another DB backend
  without rewriting application logic
