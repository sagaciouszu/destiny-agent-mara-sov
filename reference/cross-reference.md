# Mara Sov - Cross-Reference

> **Depends On:** INDEX.md
> **Token Estimate:** ~146 tokens

Map newly ingested transcripts to persona beats. Update this file when the
grimoire gains content that changes how Mara Sov should be played.

## New Transcripts to Persona Beats

| Transcript or activity | Beats |
|---|---|
| run `python3 lore/db/query.py activity <slug>` | record the scenes and lines worth using |

## Key Beats by Transcript

Use `python3 lore/db/query.py character "Mara Sov" --about <term>` to find
material, then `python3 lore/db/query.py verify "<line>" --speaker "Mara Sov" --exact`
to confirm every line before citing it. `--canon-only` excludes optional and
variant lines; it does not exclude captions.
