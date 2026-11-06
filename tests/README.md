# Tests

> **Token Estimate:** ~448 tokens

Run the full gate first:

```bash
bash tests/master-audit.sh
```

| Test | Purpose |
|---|---|
| `master-audit.sh` | every local and shared gate |
| `connection-test.sh` | grimoire database, query interface, lore/seal, MCP |
| `module-test.sh` | required modules and no placeholders |
| `quote-verify.sh` | every quoted line is canon |
| `conversation-test.sh` | database has canon lines for this speaker (gated post-sourcing) |
| `multiturn-test.sh` | generated `multiturn.json` arc |
| `scenario-simulator.sh` | generated `scenarios.json` cases |
| `voice-consistency.sh` | forbidden terms outside verified canon |
| `voice-scorer.py` | statistical voice score (`--gate`: canon accepted, slang rejected) |
| `sample-conversation-test.py` | recorded conversation passes the scorer (skips while empty) |
| `persona-freshness.py` | `persona.json` counts match the live database |
| `golden-voice-test.sh` | locked voice snapshots |
| `memory-test.py` | per-user memory isolation |
| `suites.json` + `run-suites.sh` | manifest copy of the audit (same names, commands, tiers) |

Voice scoring methodology: the scorer loads this speaker's canonical lines
from `lore/db/grimoire.db` (stage directions excluded) and scores vocabulary
overlap, bigram/trigram phrasing, signature markers, sentence cadence,
character 3-grams, signature phrases and brevity, minus a forbidden-term
penalty read from `persona.json` (terms are derived by `source-persona.py`
only when absent from the speaker's canon). PASS at 55+ of a clamped 100;
exit 0 pass, 1 fail, 2 database missing, SKIP+0 before sourcing.
`golden-voice.json` cases assert a binary verdict per seeded line; the
Voice Scorer suite runs `--gate` so canon must score PASS and known slang
must score FAIL.
