"""Count text explicitly; optionally estimate reading time at a supplied rate."""
from pathlib import Path
import argparse
import json
import math
import re
import sys

def measure(text, cpm=None):
    compact = re.sub(r'\s', '', text)
    out = {'characters_including_whitespace':len(text),
           'characters_without_whitespace':len(compact),
           'cjk_characters':len(re.findall(r'[\u3400-\u4dbf\u4e00-\u9fff]',text)),
           'latin_word_tokens':len(re.findall(r'[A-Za-z]+(?:[\x27-][A-Za-z]+)*',text)),
           'number_tokens':len(re.findall(r'\d+(?:\.\d+)?',text)),
           'count_note':'Non-whitespace count includes punctuation, digits and Latin characters; CJK count is separate.'}
    if cpm is not None:
        out.update({'supplied_characters_per_minute':cpm,
                    'estimated_seconds':round(len(compact)*60/cpm,1),
                    'timing_note':'Rough estimate using the supplied non-whitespace-character rate; pauses, demos and number pronunciation are not measured.'})
    return out

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file',help='UTF-8 text file, or - to read stdin')
    parser.add_argument('--cpm',type=float,help='User-calibrated non-whitespace characters per minute')
    args=parser.parse_args()
    if args.cpm is not None and (not math.isfinite(args.cpm) or args.cpm<=0):
        parser.error('cpm must be finite and positive')
    if args.file=='-' and hasattr(sys.stdin,'reconfigure'):
        sys.stdin.reconfigure(encoding='utf-8')
    text=sys.stdin.read() if args.file=='-' else Path(args.file).read_text(encoding='utf-8-sig')
    print(json.dumps(measure(text,args.cpm),ensure_ascii=False,indent=2))

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
