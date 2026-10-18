"""Search the bundled reference records without external dependencies."""
from pathlib import Path
import argparse
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

def load_records():
    with (ROOT / 'references' / 'corpus.jsonl').open(encoding='utf-8') as handle:
        return [json.loads(line) for line in handle if line.strip()]

def excerpt(text, terms, length):
    if not text or length <= 0:
        return ''
    positions = [text.casefold().find(term) for term in terms if term in text.casefold()]
    start = max(0, min(positions) - 90) if positions else 0
    end = min(len(text), start + length)
    return ('…' if start else '') + text[start:end] + ('…' if end < len(text) else '')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', nargs='?', default='', help='以空格分开的词；默认任一词匹配')
    parser.add_argument('--all-terms', action='store_true')
    parser.add_argument('--author', default='')
    parser.add_argument('--source', default='', help='S1到S5或文件名的一部分')
    parser.add_argument('--id', default='')
    parser.add_argument('--transcript', action='store_true', help='仅筛选已有逐字稿的记录')
    parser.add_argument('--scope', choices=['title', 'all'], default='title', help='默认标题/标签；all包含逐字稿')
    parser.add_argument('--sort', choices=['relevance', 'likes', 'comments', 'favorites', 'shares'], default='relevance')
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--excerpt-chars', type=int, default=700)
    parser.add_argument('--full-text', action='store_true', help='按ID深入阅读时输出完整逐字稿')
    parser.add_argument('--stats', action='store_true')
    args = parser.parse_args()
    if args.limit < 1 or args.excerpt_chars < 0:
        parser.error('limit须大于0，excerpt-chars须不小于0')
    if args.full_text and not args.id:
        parser.error('--full-text须同时指定--id，避免一次载入整个语料库')
    if args.stats:
        stats = json.loads((ROOT / 'references' / 'corpus-stats.json').read_text(encoding='utf-8'))
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return
    terms = [term.casefold() for term in re.split(r'\s+', args.query.strip()) if term]
    matches = []
    for record in load_records():
        if args.id and record['id'] != args.id:
            continue
        if args.author and args.author.casefold() not in record['author'].casefold():
            continue
        if args.source and not (record['id'].startswith(args.source + '-') or args.source in record['source_file']):
            continue
        if args.transcript and not record['transcript']:
            continue
        title = (record['title'] + ' ' + record['tags']).casefold()
        text = title + (' ' + record['transcript'].casefold() if args.scope == 'all' else '')
        hits = [term in text for term in terms]
        if terms and not (all(hits) if args.all_terms else any(hits)):
            continue
        score = sum(5 * title.count(term) + (record['transcript'].casefold().count(term) if args.scope == 'all' else 0) for term in terms)
        matches.append((score, record))
    if args.sort == 'relevance':
        matches.sort(key=lambda pair: (-pair[0], pair[1]['id']))
    else:
        matches.sort(key=lambda pair: (-(pair[1]['metrics'].get(args.sort) if pair[1]['metrics'].get(args.sort) is not None else -1), pair[1]['id']))
    results = []
    for score, record in matches[:args.limit]:
        out = {k: record[k] for k in ['id', 'source_file', 'record', 'title', 'title_quality', 'author', 'author_source', 'tags', 'metrics', 'published_raw', 'duration_raw', 'url', 'same_title_records']}
        out['transcript_chars'] = len(record['transcript'])
        out['transcript_excerpt'] = excerpt(record['transcript'], terms, args.excerpt_chars)
        if args.full_text:
            out['transcript'] = record['transcript']
        results.append(out)
    print(json.dumps({'matched_records': len(matches), 'returned_records': len(results), 'metric_note': '互动数是历史表格记录；排序只用于检索，不代表当前热度或选题优先级。', 'results': results}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
