# CLAUDE.md

## Golden rule — do not look at the past
Work ONLY in this folder. Do not read, search or inspect sibling folders. The only domain source is
`REQUISITI.md`. Missing information → ask the user; never guess.

## Environment
The interpreter with Tk is `/usr/local/bin/python3` (3.13, Tk 8.6); `python3` on PATH has no Tk.
No screen capture: test the UI in-process (build the real windows, find widgets, invoke them).

## How we work
- Understand the requirement, agree concrete examples with the user when a rule is unclear.
- Tests first: each requirement you implement gets automated tests; the whole suite stays green.
- Small steps; one commit per working feature, with a clear message.
- Keep the code clean and simple; refactor as you go.
- When a release the user asked for is complete and tested, tell the user and wait for the
  confirmation; create the release tag only when the user confirms. Never push.
- Write the application's texts in Italian.
