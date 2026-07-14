## What changed

Describe the user-visible behavior and why it belongs in IndexPilot’s focused review path.

## Evidence

- Tests run:
- Example report or command:
- Database reads/writes:

## Safety and compatibility

- [ ] The public review command remains read-only.
- [ ] Supplied SQL is parsed and rebuilt; it is never executed directly.
- [ ] JSON/Markdown reports do not retain raw workload SQL or secrets.
- [ ] Existing contracts, docs, and compatibility commands were updated when needed.
- [ ] Any database mutation has explicit opt-in, operator review, and rollback evidence.
