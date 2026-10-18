"""Search the bundled copywriting examples with Python standard library."""
from pathlib import Path
import argparse
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

def read_records():
    with (ROOT / 'references' / 'corpus.jsonl').open(encoding='utf-8') as handle:
        return [json.loads(line) for line in handle if line.strip()]

def make_excerpt(text, terms, length):
    if not text or length == 0:
        return ''
    lower = text.casefold()
    hits = [lower.index(term) for term in terms if term in lower]
    start = max(0, min(hits)-80) if hits else 0
    end = min(len(text), start+length)
    return ('…' if start else '') + text[start:end] + ('…' if end<len(text) else '')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', nargs='?', default='', help='Space-separated keywords')
    parser.add_argument('--all-terms', action='store_true')
    parser.add_argument('--transcript', action='store_true')
    parser.add_argument('--scope', choices=('title', 'all'), default='title')
    parser.add_argument('--id', default='')
    parser.add_argument('--full-text', action='store_true')
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--excerpt-chars', type=int, default=600)
    parser.add_argument('--stats', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.limit <= 20 or not 0 <= args.excerpt_chars <= 4000:
        parser.error('limit must be 1..20; excerpt-chars must be 0..4000')
    if args.full_text and not args.id:
        parser.error('--full-text requires --id')
    if args.stats:
        print((ROOT/'references'/'corpus-stats.json').read_text(encoding='utf-8'))
        return
    terms = [term.casefold() for term in re.split(r'\s+', args.query.strip()) if term]
    matches = []
    for row in read_records():
        if args.id and row['id'] != args.id:
            continue
        if args.transcript and not row['transcript']:
            continue
        title = (row['title'] + ' ' + row['tags']).casefold()
        transcript = row['transcript'].casefold()
        text = title + (' ' + transcript if args.scope=='all' else '')
        hits = [term in text for term in terms]
        if terms and not (all(hits) if args.all_terms else any(hits)):
            continue
        score = sum(5*title.count(term) + (min(10, transcript.count(term)) if args.scope=='all' else 0) for term in terms)
        matches.append((score, row))
    matches.sort(key=lambda pair: (-pair[0], pair[1]['id']))
    output = []
    for score, row in matches[:args.limit]:
        item = {key:row[key] for key in ('id','source_file','record','title','tags','duration_raw','metrics',
                                        'author','published_date','video_url','same_title_records','same_transcript_records')}
        item['transcript_chars'] = len(row['transcript'])
        item['transcript_excerpt'] = make_excerpt(row['transcript'], terms, args.excerpt_chars)
        if args.full_text:
            item['transcript'] = row['transcript']
            item['raw_fields'] = row['raw_fields']
        output.append(item)
    print(json.dumps({'matched_records':len(matches),'returned_records':len(output),
                      'source_note':'Historical user-provided CSV; metrics do not prove current popularity or copy effectiveness.',
                      'results':output},ensure_ascii=False,indent=2))

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
