#!/bin/bash
# Conversation smoke: confirm the database has lines for this speaker.
# Usage: bash tests/conversation-test.sh
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$HERE")"
LORE="${LORE:-$REPO/lore}"
DB="$LORE/db/grimoire.db"
SPEAKER="Mara Sov"

[ -f "$DB" ] || { echo "FAIL: database not found at $DB - run ./setup.sh"; exit 1; }

python3 - "$DB" "$SPEAKER" "$REPO/persona.json" <<'PY'
import json, sqlite3, sys
db, speaker, persona_path = sys.argv[1], sys.argv[2], sys.argv[3]
conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
try:
    count = conn.execute(
        'SELECT COUNT(*) FROM transcript_lines WHERE speaker LIKE ? AND is_stage_dir=0',
        (f'%{speaker}%',)).fetchone()[0]
finally:
    conn.close()
print(f'speaker lines for {speaker}: {count}')
if not count:
    try:
        status = json.load(open(persona_path, encoding='utf-8')).get('status') or ''
    except (OSError, json.JSONDecodeError):
        status = ''
    if status == 'skeleton':
        print('note: skeleton persona; no lines expected until sourcing')
    else:
        print(f'FAIL: no transcript lines for {speaker} after sourcing ({status or "unknown"} persona)')
        sys.exit(1)
PY
