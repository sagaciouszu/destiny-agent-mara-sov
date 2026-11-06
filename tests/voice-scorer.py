#!/usr/bin/env python3
"""Statistical voice scorer for a generated Mara Sov agent.

Scores a candidate line against canonical Mara Sov dialogue from the grimoire
database. Components (self-calibrating from the corpus):
    vocabulary overlap /20, bigram+trigram phrasing /10, signature markers /25,
    sentence cadence /15, char-3-gram overlap /15, signature phrases /15,
    brevity /5, consistency bonus /5, forbidden-term penalty /-25.
PASS when the clamped total is >= 55.

Usage:
    python3 voice-scorer.py "<candidate line>"
    python3 voice-scorer.py --gate      # audit mode: canon accepts, slang rejects

Exit codes: 0 pass, 1 fail (or no usable corpus), 2 database missing.
When the persona has not been sourced yet (no canonical lines for this
speaker), both modes SKIP with exit 0 so the blank-shell audit stays green.
"""
import json
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SPEAKER = "Mara Sov"

STOPWORDS = frozenset("""
a an and are as at be but by for from has have he her his i if in is it its me my
no not of on or our she so that the their them they this to too up was we were
what when who will with you your
""".split())

GATE_NEGATIVES = (
    'nah kid yeah heh bro punk snitch reckoner cue ball motes wager',
    'As an AI language model, I cannot help you with that request.',
)


def db_path():
    env = os.environ.get('GRIMOIRE_DB')
    if env:
        return env
    lore = os.environ.get('LORE') or os.path.join(REPO, 'lore')
    return os.path.join(lore, 'db', 'grimoire.db')


def corpus():
    path = db_path()
    if not os.path.exists(path):
        print(f'database not found; run ./setup.sh (expected {path})')
        sys.exit(2)
    conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        rows = conn.execute(
            'SELECT line FROM transcript_lines '
            'WHERE speaker = ? AND is_stage_dir = 0', (SPEAKER,)).fetchall()
    finally:
        conn.close()
    return [' '.join((r[0] or '').split()) for r in rows if (r[0] or '').strip()]


def tokens(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def ngrams(items, n):
    return [tuple(items[i:i + n]) for i in range(len(items) - n + 1)]


def normalize(text):
    return ' ' + re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip() + ' '


def forbidden_terms():
    path = os.path.join(REPO, 'persona.json')
    try:
        data = json.load(open(path, encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    terms = data.get('forbidden_terms') or []
    return [t for t in terms if isinstance(t, str) and t.strip()]


def load_profile(lines):
    """Corpus statistics: vocab, n-grams, markers, phrases, cadence center."""
    vocab, bigrams, trigrams = set(), set(), set()
    marker_counts, phrase_counts, sent_lens = {}, {}, []
    for line in lines:
        toks = tokens(line)
        vocab.update(toks)
        bigrams.update(ngrams(toks, 2))
        trigrams.update(ngrams(toks, 3))
        for t in toks:
            if len(t) > 2 and t not in STOPWORDS:
                marker_counts[t] = marker_counts.get(t, 0) + 1
        for tri in ngrams(toks, 3):
            if any(w in STOPWORDS or len(w) < 3 for w in tri):
                continue
            key = ' '.join(tri)
            phrase_counts[key] = phrase_counts.get(key, 0) + 1
        sent_lens.extend(len(tokens(s)) for s in re.split(r'[.!?]+', line) if s.strip())
    markers = [w for w, _ in sorted(marker_counts.items(),
                                     key=lambda kv: (-kv[1], kv[0]))[:40]]
    phrases = [p for p, c in sorted(phrase_counts.items(),
                                    key=lambda kv: (-kv[1], kv[0]))
               if c >= 2][:12]
    avg_sent = (sum(sent_lens) / len(sent_lens)) if sent_lens else 6.0
    return {'vocab': vocab, 'bigrams': bigrams,
            'trigrams': trigrams, 'markers': set(markers), 'phrases': phrases,
            'avg_sent': avg_sent}


def score(candidate, profile):
    details = {}
    toks = tokens(candidate)
    n = len(toks)
    if n < 8:
        print(f'Total Score: 0.0/100 (FAIL) - too short to score ({n} tokens)')
        return 0.0, details

    # 1. Vocabulary overlap (/20)
    vocab = profile['vocab']
    ratio = (sum(1 for t in toks if t in vocab) / n) if n else 0.0
    details['vocab'] = round(min(20.0, ratio * 20), 1)

    # 2. N-gram phrasing (/10)
    bi = ngrams(toks, 2)
    tri = ngrams(toks, 3)
    bi_rate = (sum(1 for g in bi if g in profile['bigrams']) / len(bi)) if bi else 0.0
    tri_rate = (sum(1 for g in tri if g in profile['trigrams']) / len(tri)) if tri else 0.0
    details['ngram'] = round(min(10.0, bi_rate * 6 + tri_rate * 6), 1)

    # 3. Signature markers (/25)
    found = [t for t in set(toks) if t in profile['markers']]
    details['markers'] = round(min(25.0, len(found) * 4), 1)

    # 4. Sentence cadence (/15) against the corpus average
    sentences = [s for s in re.split(r'[.!?]+', candidate) if s.strip()]
    avg = n / max(1, len(sentences))
    center = profile['avg_sent']
    delta = abs(avg - center)
    cadence = 15 if delta <= 2 else 12 if delta <= 4 else 8 if delta <= 6 else 5
    details['cadence'] = float(cadence)

    # 5. Char 3-gram overlap (/15): token character fragments vs corpus vocab
    frags = {t[i:i + 3] for t in toks for i in range(max(0, len(t) - 2))}
    pool_frags = {t[i:i + 3] for t in vocab for i in range(max(0, len(t) - 2))}
    overlap = len(frags & pool_frags) / len(frags) if frags else 0.0
    details['char3'] = round(min(15.0, overlap * 15), 1)

    # 6. Signature phrases (/15)
    lowered = normalize(candidate)
    phrase_hits = sum(1 for p in profile['phrases'] if ' ' + p + ' ' in lowered)
    details['phrases'] = round(min(15.0, phrase_hits * 3), 1)

    # 7. Brevity (/5)
    details['brevity'] = 5.0 if n <= 25 else 3.0 if n <= 40 else 1.0

    # 8. Consistency bonus (/5)
    bonus = 0.0
    if n > 30 and phrase_hits >= 3 and len(found) >= 4:
        bonus = 5.0
    elif n > 20 and phrase_hits >= 2 and len(found) >= 3:
        bonus = 3.0
    details['consistency'] = bonus

    total = (details['vocab'] + details['ngram'] + details['markers']
             + details['cadence'] + details['char3'] + details['phrases']
             + details['brevity'] + details['consistency'])

    # 9. Forbidden-term penalty (/25)
    forbidden = forbidden_terms()
    hits = set()
    for term in forbidden:
        needle = term.lower()
        if ' ' in needle or "'" in needle:
            if needle in candidate.lower().replace('\u2019', "'"):
                hits.add(term)
        elif needle in toks:
            hits.add(term)
    penalty = min(25.0, len(hits) * 8.0)
    details['penalty'] = -penalty
    details['forbidden_found'] = sorted(hits)
    total = max(0.0, min(100.0, total - penalty))
    return round(total, 1), details


def report(total, details, corpus_lines):
    verdict = 'PASS' if total >= 55 else 'FAIL'
    print(f'=== {SPEAKER.upper()} STATISTICAL VOICE SCORER ===')
    print(f'Corpus size: {corpus_lines} canonical lines')
    print(f'Total Score: {total}/100 ({verdict})')
    print(f"  Vocabulary overlap : {details.get('vocab', 0)}/20")
    print(f"  N-gram phrasing    : {details.get('ngram', 0)}/10")
    print(f"  Signature markers  : {details.get('markers', 0)}/25"
          + (f" ({', '.join(details.get('forbidden_found', []))})"
             if details.get('forbidden_found') else ''))
    print(f"  Sentence cadence   : {details.get('cadence', 0)}/15")
    print(f"  Char n-gram        : {details.get('char3', 0)}/15")
    print(f"  Signature phrases  : {details.get('phrases', 0)}/15")
    print(f"  Brevity bonus      : {details.get('brevity', 0)}/5")
    if details.get('penalty'):
        print(f"  Forbidden penalty  : {details['penalty']}/25")
    return verdict == 'PASS'


def gate(profile, lines):
    """Audit mode: evenly spaced canon lines must pass; known slang must fail."""
    candidates = [l for l in lines if len(tokens(l)) >= 10]
    if len(candidates) >= 5:
        step = max(1, len(candidates) // 5)
        sample = [candidates[i] for i in range(0, len(candidates), step)][:5]
    else:
        sample = candidates
    ok = 0
    for text in sample:
        total, _ = score(text, profile)
        ok += total >= 55
    negatives_ok = True
    for text in GATE_NEGATIVES:
        total, _ = score(text, profile)
        if total >= 55:
            negatives_ok = False
    passed = negatives_ok and ok == len(sample) and bool(sample)
    print(f'gate: {ok}/{len(sample)} canon lines accepted, '
          f'negatives {"rejected" if negatives_ok else "ACCEPTED"}')
    print(f'Total Score: {"100.0" if passed else "0.0"}/100 '
          f'({"PASS" if passed else "FAIL"})')
    return passed


def main():
    args = sys.argv[1:]
    lines = corpus()
    if not lines:
        print('SKIP: no canonical lines for this speaker yet')
        return 0
    profile = load_profile(lines)
    if args and args[0] == '--gate':
        return 0 if gate(profile, lines) else 1
    if not args:
        print('usage: voice-scorer.py "<candidate>" | --gate', file=sys.stderr)
        return 2
    total, details = score(' '.join(args[0].split()), profile)
    passed = report(total, details, len(lines))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
