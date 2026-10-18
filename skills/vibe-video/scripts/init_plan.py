"""Create editable planning templates in a new directory, without media or overwrites."""
from pathlib import Path
import argparse
import json
import sys

TEMPLATES = Path(__file__).resolve().parents[1] / 'assets' / 'templates'

def positive_number(value):
    parsed = float(value)
    if not 0 < parsed < float('inf'):
        raise argparse.ArgumentTypeError('must be a finite positive number')
    return parsed

def positive_integer(value):
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError('must be a positive integer')
    return parsed

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--title', required=True)
    parser.add_argument('--mode', choices=['original', 'replica', 'enhancement'], default='original')
    parser.add_argument('--duration', type=positive_number)
    parser.add_argument('--fps', type=positive_number)
    parser.add_argument('--width', type=positive_integer)
    parser.add_argument('--height', type=positive_integer)
    args = parser.parse_args(argv)
    if not args.title.strip():
        parser.error('title must contain text')
    if (args.width is None) != (args.height is None):
        parser.error('width and height must be supplied together')
    out = args.output.expanduser().resolve()
    if out.exists():
        parser.error('output already exists; choose a new planning directory')
    sources = sorted(TEMPLATES.glob('*.json')) + sorted(TEMPLATES.glob('*.md'))
    if not sources:
        parser.error('template files are missing')
    contents = {}
    for src in sources:
        content = src.read_text(encoding='utf-8')
        if src.suffix == '.json':
            data = json.loads(content)
            if src.name == 'creative-brief.json':
                data['title'] = args.title.strip()
                data['mode'] = args.mode
                data['spec'] = dict(duration_seconds=args.duration, fps=args.fps, width=args.width, height=args.height)
            elif src.name == 'storyboard.json':
                data['fps'] = args.fps
            elif src.name == 'cover-brief.json':
                data['title'] = args.title.strip()
            content = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
        contents[src.name] = content
    out.mkdir(parents=True, exist_ok=False)
    for name, content in contents.items():
        with (out / name).open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(content)
    print(json.dumps({'output': str(out), 'files': sorted(contents), 'media_created': False}, ensure_ascii=True))
    return 0

if __name__ == '__main__':
    sys.exit(main())
