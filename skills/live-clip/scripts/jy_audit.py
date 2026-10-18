#!/usr/bin/env python3
"""
只读体检：字幕是不是个人预设、声道配置对不对、响度到没到目标。不写任何文件。

用法：
  python3 jy_audit.py <草稿名或目录> [...] [--target -13]

第 0 步判断入口时跑。精剪脚本写入时会自动套这三样；但从包装（第 4 步）进来、
或者草稿是这套规则之前剪的，就可能没套上，jy_pack 会原样照搬。
修法（都改在我们生成的新草稿上，用户改过的原稿不动）：
  字幕  python3 ~/.codex/skills/jianying-draft/scripts/jy_style.py <新草稿>
  声道 + 音量  python3 ~/.codex/skills/jianying-draft/scripts/jy_loud.py <新草稿>
"""
import argparse, json, math, sys
from pathlib import Path

JD = Path(__file__).resolve().parents[2] / "jianying-draft/scripts"
sys.path.insert(0, str(JD))
import jy_runtime as R
from jy import decrypt_text, resolve  # noqa: E402
from jy_style import load_preset  # noqa: E402
import jy_loud as L  # noqa: E402

TOL = 1.5                                                  # 响度离目标这么多 dB 以内算达标


def essentials(m):
    """字幕真正影响观感的几项。剪映自己存的和我们模板写的结构详略不同，只比这些。"""
    st = (json.loads(m["content"]).get("styles") or [{}])[0]
    fill = st.get("fill", {}).get("content", {}).get("solid", {}).get("color")
    sh = st.get("shadows") or []
    sh_col = sh[0].get("content", {}).get("solid", {}).get("color") if sh else None
    r = lambda x: [round(v, 2) for v in x] if isinstance(x, list) else x
    return {
        "字体": Path(st.get("font", {}).get("path", "")).name,
        "字号": round(float(st.get("size", 0)), 1),
        "加粗": bool(st.get("bold")),
        "字色": r(fill),
        "阴影": r(sh_col) if sh else None,
        "底框": (round(m.get("background_alpha") or 0, 2), m.get("background_color")) if m.get("background_style") else None,
    }


def audit_subs(info, preset):
    """返回 (字幕条数, 不符合预设的条数, 第一处差异)。"""
    want = essentials({**preset["fields"], "content": json.dumps({"styles": [preset["style"]]})})
    subs = [m for m in info["materials"].get("texts", []) if m.get("type") == "subtitle"]
    bad, first = 0, None
    for m in subs:
        got = essentials(m)
        diff = [f"{k} {got[k]}≠{want[k]}" for k in want if got[k] != want[k]]
        if diff:
            bad += 1
            first = first or diff[:3]
    return len(subs), bad, first


def audit_audio(info, target):
    if L.is_compound(info):
        return "主轨已是复合片段，响度没法直接量，请在剪映里看电平（冒红尖儿）"
    idx = L.mat_index(info)
    segs = L.main_video_track(info)["segments"]
    cur_map = {idx[r][1].get("audio_channel_mapping") or 0 for s in segs for r in s.get("extra_material_refs", [])
               if idx.get(r, ("",))[0] == "sound_channel_mappings"} or {0}
    want, l, r = L.pick_mapping(info)
    names = {0: "不动", 1: "左填充至右", 2: "右填充至左"}
    ch_ok = cur_map == {want}
    raw, _ = L.measure(info, want)
    if raw is None:
        return "量不出响度（找不到源素材？）"
    vols = sorted({round(20 * math.log10(max(s.get("volume", 1.0), 1e-6)), 1) for s in segs})
    now = raw + vols[len(vols) // 2]
    lr = f"左{l:.1f}/右{r:.1f} dB" if r is not None else "单声道"
    out = [f"声道 {lr}，应为「{names[want]}」，现在「{'/'.join(names.get(x, str(x)) for x in sorted(cur_map))}」 {'✅' if ch_ok else '❌'}",
           f"音量 片段增益 {'/'.join(f'{v:+.1f}' for v in vols)} dB → 约 {now:.1f} LUFS（目标 {target}）"
           + (" ✅" if abs(now - target) <= TOL else f" ❌ 差 {target - now:+.1f} dB")]
    return "；".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drafts", nargs="+")
    ap.add_argument("--target", type=float, default=L.TARGET)
    a = ap.parse_args()
    preset = load_preset()
    for name in a.drafts:
        info = json.loads(decrypt_text(resolve(name).read_text(encoding="utf-8-sig")))
        n, bad, first = audit_subs(info, preset)
        print(f"# {resolve(name).parent.name}")
        print(f"  字幕 {n} 条，" + ("全部是个人预设 ✅" if not bad else f"{bad} 条不符合预设 ❌（如 {', '.join(first)}）"))
        print("  " + audit_audio(info, a.target))


if __name__ == "__main__":
    main()
