"""Archive original visual references, separately by publishing platform."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1] / "assets" / "reference-library"
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".bmp", ".tif", ".tiff"}


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def atomic_json(path, value):
    descriptor, temporary = tempfile.mkstemp(prefix="metadata-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def add(args):
    source = Path(args.image).resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in EXTENSIONS or source.stat().st_size == 0:
        raise ValueError("Provide an existing, nonempty raster image file.")
    checksum = digest(source)
    folder = ROOT / args.platform / checksum[:16]
    folder.mkdir(parents=True, exist_ok=True)
    record = folder / "metadata.json"
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if record.exists():
        data = json.loads(record.read_text(encoding="utf-8"))
        if data["sha256"] != checksum:
            raise ValueError("Reference ID collision; existing original was preserved.")
        original = folder / data["original_file"]
        if original.parent.resolve() != folder.resolve() or digest(original) != checksum:
            raise ValueError("Stored original failed integrity verification.")
    else:
        original = folder / ("original" + source.suffix.lower())
        existing = list(folder.glob("original.*"))
        if existing:
            if len(existing) != 1 or digest(existing[0]) != checksum:
                raise ValueError("Unindexed original exists; refusing to overwrite it.")
            original = existing[0]
        else:
            # Exclusive creation prevents overwriting an existing reference.
            with source.open("rb") as src, original.open("xb") as dst:
                shutil.copyfileobj(src, dst)
        if digest(original) != checksum:
            raise ValueError("Archive copy failed hash verification.")
        data = {
            "schema_version": 1, "id": checksum[:16], "platform": args.platform,
            "title": args.title, "sha256": checksum, "original_file": original.name,
            "first_received_at": stamp, "origins": [], "tags": [], "notes": [], "imports": []
        }
    for key, values in (("tags", args.tag), ("origins", [args.origin])):
        data.setdefault(key, [])
        for value in values:
            if value not in data[key]:
                data[key].append(value)
    if args.note and args.note not in data.setdefault("notes", []):
        data["notes"].append(args.note)
    data["updated_at"] = stamp
    data["imports"].append({"at": stamp, "filename": source.name, "origin": args.origin, "title": args.title})
    atomic_json(record, data)
    return {"id": data["id"], "platform": args.platform, "original": str(original), "sha256": checksum}


def listing(args):
    result = []
    for path in sorted((ROOT / args.platform).glob("*/metadata.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        result.append({key: data.get(key) for key in ("id", "title", "origins", "tags", "notes", "first_received_at")})
        result[-1]["original"] = str(path.parent / data["original_file"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("add", "list"):
        sub = commands.add_parser(command)
        sub.add_argument("--platform", choices=("xiaohongshu", "wechat"), required=True)
        if command == "add":
            sub.add_argument("--image", required=True)
            sub.add_argument("--title", required=True)
            sub.add_argument("--origin", choices=("user-reference", "generated-example"), required=True)
            sub.add_argument("--tag", action="append", default=[])
            sub.add_argument("--note", default="")
    args = parser.parse_args()
    print(json.dumps(add(args) if args.command == "add" else listing(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
