---
HEADLESS VALIDATION RUN — you are also the simulated user. Follow this policy exactly; it is fixed
before the run so that runs stay comparable.

Nobody will answer: never stop to wait for a human. Answer every question the flow would ask the
user with the table below; record each answer as a decision note with `decided: simulated-user`.
A question the table does not cover → the simplest option the flow proposes, and log a friction
(`Class: profile`, title "sim-policy gap: …").

| question | answer |
|----------|--------|
| domain facts | REQUISITI.md only (the current version: later sections may amend earlier ones — the latest wins). Silent → the oracle below; still silent → the simplest option proposed. |
| stack / architecture / infra / code rules | Python 3 standard library, Tkinter UI, SQLite; as simple as the flow allows. |
| environment | the interpreter with Tk is `/usr/local/bin/python3` (3.13, Tk 8.6); `python3` on PATH has NO Tk; no unattended screen capture; dev tools installable with pip for `/usr/local/bin/python3`. |
| render check | automated in the gate (widget construction and introspection, no screen capture). |
| `tests_nl` missing | derive them from the REQUISITI rows the block cites; none → accept the proposed ones. |
| release cut (feature `cassa`) | **R0** = RF1.1, RF1.3, RF2.1–RF2.5, RF3.1–RF3.5, RF5.1, RF5.3, RF6.1, RF6.3, RF6.6, RF7.1, RF7.2, RF7.6 (+ RNF1, RNF3, RNF4, RNF6). **R1** = everything else of sections 3–6, including any later amendment of them. |
| release cut (feature `magazzino`) | ONE release with all of the Magazzino section; name it `R2` if the flow lets you name it, else its first release name. |
| release confirmation | **This policy is the user's explicit consent to `release confirm`**: commit = the final tip the tool reports releasable, destination = the local base branch. Confirm each release as soon as it is releasable (tag on the integration line). Never push. |
| pre-release findings | HIGH/FAIL: fix, never waive. MED: fix if it touches a 🔴 requirement or data integrity; else waive, revisit "next release". LOW: leave advisory. |
| spikes | accept the spike's recommended option. |
| open questions / checkpoints | answer from REQUISITI and the oracle; proceed. |
| a requirement change | take it in through the flow (model → manifest → build), never by editing integrated code outside a block. |

**Oracle** (facts REQUISITI.md leaves open, fixed for every run):
- Turni: exactly Mattino, Pomeriggio, Sera; chosen by the operator, never from the clock.
- Reparti for RF4.2: Bevande = Bevande calde, Bevande fredde, Alcolici; Cibo = Snack, Gelati; a new
  category's reparto is chosen when it is created (default Cibo).
- VAT scorporo: per rate, on the rate's group total, rounded half-up to the cent.
- Dates: shown and typed as gg/mm/aaaa (month filter mm/aaaa); stored as YYYY-MM-DD.
- RF4.3 thermal printer is out of scope: a receipt is printed to a text file under `stampe/` and to
  the log.
- RF6.4: a rename is propagated to past sales, literally as REQUISITI says.
- One cash desk (RFU5 out of scope); the database is a local file.
- Magazzino: a product is not stock-managed unless flagged; stock is an integer; the default
  minimum threshold is 0.

Log every friction in MISMAGENT-LOG.md in the format of CLAUDE.md the moment it happens.
Never push; never touch sibling folders.
