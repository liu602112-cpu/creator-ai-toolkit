"""Archive original visual references, separately by publishing platform."""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlsplit

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
    source_info = {"source_url": args.source_url, "creator": args.creator,
                   "license": args.license, "license_url": args.license_url,
                   "usage": args.usage, "dimensions": args.dimensions}
    if args.origin == "web-reference" and not args.source_url:
        raise ValueError("A web reference needs its source page URL.")
    if args.usage == "licensed-photo" and not all((args.source_url, args.license, args.license_url, args.creator)):
        raise ValueError("Licensed photos need source, creator and license details.")
    for key in ("source_url", "license_url"):
        if source_info[key] and urlsplit(source_info[key]).scheme not in ("https", "http"):
            raise ValueError("Source and license URLs must use http or https.")
    source = Path(args.image).resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in EXTENSIONS or source.stat().st_size == 0:
        raise ValueError("Provide an existing, nonempty raster image file.")
    checksum = digest(source)
    folder = args.root / args.platform / checksum[:16]
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
            "schema_version": 2, "id": checksum[:16], "platform": args.platform,
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
    data.setdefault("sources", [])
    if source_info not in data["sources"]:
        data["sources"].append(source_info)
    data["imports"].append({"at": stamp, "filename": source.name, "origin": args.origin, "title": args.title, **source_info})
    atomic_json(record, data)
    return {"id": data["id"], "platform": args.platform, "original": str(original), "sha256": checksum}


def listing(args):
    result = []
    base = args.root / args.platform if args.platform else args.root
    pattern = "*/metadata.json" if args.platform else "*/*/metadata.json"
    for path in sorted(base.glob(pattern)):
        data = json.loads(path.read_text(encoding="utf-8"))
        if any(tag not in data.get("tags", []) for tag in getattr(args, "tag", [])):
            continue
        result.append({key: data.get(key) for key in ("id", "platform", "title", "origins", "tags", "notes", "sources", "sha256", "first_received_at")})
        if Path(data["original_file"]).name != data["original_file"]:
            raise ValueError("Invalid archive filename.")
        result[-1]["original"] = str(path.parent / data["original_file"])
    return result


def verify(args):
    records = listing(args)
    failures = []
    for data in records:
        original = Path(data["original"])
        if not original.is_file() or digest(original) != data["sha256"]:
            failures.append(data["platform"] + "/" + data["id"])
    if failures:
        raise ValueError("Image integrity failures: " + ", ".join(failures))
    return {"verified": len(records), "failures": []}


def gallery(args):
    verify(args)
    records = listing(args)
    names = {"photos": "照片素材", "xiaohongshu": "小红书版式", "wechat": "公众号版式"}
    cards = []
    for d in records:
        e = html.escape
        relative = Path(d["original"]).relative_to(args.root).as_posix()
        tags = " · ".join(d.get("tags") or [])
        notes = "\n".join(d.get("notes") or [])
        sources = []
        for src in d.get("sources") or []:
            links = []
            for key, label in (("source_url", "来源网页"), ("license_url", src.get("license") or "许可")):
                url = src.get(key) or ""
                if urlsplit(url).scheme in ("https", "http"):
                    links.append(f'<a href="{e(url, quote=True)}" target="_blank" rel="noreferrer">{e(label)}</a>')
            sources.append(f'<p>{e(src.get("creator") or "未提供作者")} · {e(src.get("dimensions") or "尺寸未登记")}<br>{" · ".join(links)}<br>{e(src.get("usage") or "reference-only")}</p>')
        search = e(" ".join([d["title"], tags, notes, d["id"]]), quote=True)
        cards.append(f'''<article data-platform="{e(d['platform'])}" data-search="{search}">
<a class="image" href="{e(relative)}" target="_blank"><img src="{e(relative)}" alt="{e(d['title'], quote=True)}" loading="lazy"></a>
<div class="body"><span class="eyebrow">{names[d['platform']]}</span><h2>{e(d['title'])}</h2><p class="tags">{e(tags)}</p>
<details><summary>构图、出处与使用说明</summary><p class="notes">{e(notes)}</p>{''.join(sources)}<small>ID {e(d['id'])}</small></details></div></article>''')
    options = ''.join(f'<option value="{key}">{name}（{sum(x["platform"] == key for x in records)}）</option>' for key, name in names.items())
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>健身参考图库</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f4ee;color:#20251f;font:16px/1.65 "Microsoft YaHei",sans-serif}main{max-width:1180px;padding:52px 28px 70px;margin:auto}header{border-bottom:1px solid #cdd4c4;padding-bottom:26px;margin-bottom:28px}.eyebrow{font-size:12px;color:#587444;letter-spacing:1px}h1{font-size:42px;letter-spacing:-2px;line-height:1.2;margin:10px 0 18px}header p{max-width:700px;color:#65715e;margin:10px 0}.controls{display:flex;gap:12px;margin:26px 0 12px;flex-wrap:wrap}input,select{font:inherit;border:1px solid #bdc8b4;border-radius:7px;padding:10px;background:#fff;color:#20251f}input{flex:1;min-width:180px}#count{font-size:14px;color:#687760}section{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px}article{background:white;border:1px solid #e0e4d8;border-radius:12px;overflow:hidden}article[hidden]{display:none}.image{display:block;background:#e9ece3;height:255px;padding:12px}.image img{height:100%;width:100%;object-fit:contain;display:block}.body{padding:20px}h2{font-size:20px;line-height:1.4;margin:7px 0 10px}.tags{font-size:13px;color:#65715e}.notes{white-space:pre-line}details{font-size:13px;overflow-wrap:anywhere}summary{cursor:pointer;color:#426733}details p{margin:14px 0}a{color:#426733}footer{margin-top:35px;font-size:13px;color:#65715e}@media(max-width:800px){section{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:520px){main{padding:30px 18px}h1{font-size:34px}section{grid-template-columns:1fr}.image{height:270px}input,select{width:100%}}
</style><main><header><div class="eyebrow">FITNESS / VISUAL LIBRARY</div><h1>健身参考图库</h1><p>按选题找到适合的照片与版式。保留图片出处，持续加入你的新参考。</p><p>照片素材用于构图与场景参考。平台版式尚未入库时显示 0；不会把照片计作排版案例。</p><div class="controls"><input id="query" aria-label="搜索图库" placeholder="搜索跑步、力量、居家、饮食…"><select id="platform" aria-label="按用途筛选"><option value="">全部用途</option>OPTIONS</select></div><div id="count" role="status"></div></header><section>CARDS</section><footer>个人编辑参考库 · 图片按各自许可使用，素材人物不代表研究对象、疗效案例或品牌代言。点击图片查看保存文件，展开说明查看出处。</footer></main><script>
const query=document.querySelector('#query'),platform=document.querySelector('#platform'),cards=[...document.querySelectorAll('article')];function filter(){let n=0;const q=query.value.trim().toLowerCase();cards.forEach(c=>{const show=(!platform.value||c.dataset.platform===platform.value)&&c.dataset.search.toLowerCase().includes(q);c.hidden=!show;if(show)n++});document.querySelector('#count').textContent=`显示 ${n} / ${cards.length} 张`;};query.addEventListener('input',filter);platform.addEventListener('change',filter);filter();</script></html>'''.replace('OPTIONS', options).replace('CARDS', ''.join(cards))
    args.root.mkdir(parents=True, exist_ok=True)
    target = args.root / "index.html"
    target.write_text(page, encoding="utf-8")
    return {"gallery": str(target), "items": len(records)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("add", "list", "verify", "gallery"):
        sub = commands.add_parser(command)
        sub.add_argument("--platform", choices=("photos", "xiaohongshu", "wechat"), required=command == "add")
        sub.add_argument("--tag", action="append", default=[])
        if command == "add":
            sub.add_argument("--image", required=True)
            sub.add_argument("--title", required=True)
            sub.add_argument("--origin", choices=("user-reference", "web-reference", "generated-example"), required=True)
            sub.add_argument("--source-url", default="")
            sub.add_argument("--creator", default="")
            sub.add_argument("--license", default="")
            sub.add_argument("--license-url", default="")
            sub.add_argument("--usage", choices=("reference-only", "licensed-photo", "own-generated"), default="reference-only")
            sub.add_argument("--dimensions", default="")
            sub.add_argument("--note", default="")
    args = parser.parse_args()
    args.root = args.root.resolve()
    print(json.dumps({"add": add, "list": listing, "verify": verify, "gallery": gallery}[args.command](args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
