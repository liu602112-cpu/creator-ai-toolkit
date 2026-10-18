#!/usr/bin/env python3
"""
直播切片包装：按分镜配置给剪映草稿加重点字、目录卡、对焦虚化、B-roll、章节条、音效，输出新草稿（原稿不动）。

用法：
  python3 jy_pack.py pack.json --dry-run     # 列出每个元素的出现时间，核对卡点
  python3 jy_pack.py pack.json               # 写成新草稿（先关剪映）

pack.json 见 ../references/pack-spec.md；完整例子 ../references/example-0926/pack.json。
时间写法（at / to）：
  12.5                 绝对秒
  "它会分为三个类型"     以这句字幕开头的那一行的起点
  "它会分为三个类型/三个" 这一行里「三个」开始说的时刻
  "…+0.3" / "…-0.25"   再加减秒数
  "end"                片尾
"""
import copy, json, os, subprocess, sys, uuid
from pathlib import Path

JD = Path(__file__).resolve().parents[2] / "jianying-draft/scripts"
sys.path.insert(0, str(JD))
import jy_runtime as R
from jy import decrypt_text, resolve  # noqa: E402
from jy_cut import write_draft, register  # noqa: E402

SKILL = Path(__file__).resolve().parent.parent
US, FPS = 1_000_000, 30
YELLOW = [1.0, 236 / 255, 138 / 255]            # FFEC8A 重点色
GRAD = [[1, 1, 1], [1.0, 243 / 255, 183 / 255]]  # FFFFFF → FFF3B7 重点字渐变
HOME = str(Path.home())


def find_font(name):
    override = os.environ.get("LIVE_CLIP_FONT_EN" if "Cherolina" in name else "LIVE_CLIP_FONT_CN")
    if override:
        path = Path(override).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"指定字体不存在：{path}")
        return path.as_posix()
    return R.font(name, "arial.ttf" if "Cherolina" in name else "simsun.ttc")


FONT_CN = find_font("猴尊宋体.ttf")
FONT_EN = find_font("Cherolina.otf")
SYS_FONT = R.font("SourceHanSansCN-Regular.otf", "msyh.ttc")
# 音效目录：环境变量 LIVE_CLIP_SFX > 喂鱼本机音效库 > skill 自带 assets/sfx
SFX_DIR = next((p for p in [Path(os.environ.get("LIVE_CLIP_SFX", "")).expanduser() if os.environ.get("LIVE_CLIP_SFX") else None,
                            SKILL / "assets/sfx"] if p and p.is_dir()), SKILL / "assets/sfx")
MISSING_SFX = set()
BLUR_TPL = {"effect_id": "7399495140399746304", "resource_id": "7399495140399746304", "name": "模糊",
            "type": "video_effect", "path": R.effect_path("7399495140399746304"),
            "value": 1.0, "category_id": "1111", "category_name": "画面特效", "source_platform": 1,
            "adjust_params": [{"name": "effects_adjust_blur", "value": 0.75, "default_value": 0.5}],
            "render_index": 11000, "request_id": ""}
KEEP_KINDS = {"speeds", "placeholder_infos", "canvases", "sound_channel_mappings", "material_colors", "vocal_separations"}


def nid():
    return str(uuid.uuid4()).upper()


def us(sec):
    return int(round(round(sec * FPS) * US / FPS))


def load(name):
    return json.loads(decrypt_text(resolve(name).read_text(encoding="utf-8-sig")))


def load_style(name):
    """重点字样式来源：本机有这个剪映草稿就用草稿，没有就用 skill 自带的 presets/keyword_style.json。"""
    try:
        return load(name)
    except (SystemExit, FileNotFoundError, OSError):
        txt = (SKILL / "presets/keyword_style.json").read_text(encoding="utf-8-sig")
        return R.adapt_paths(json.loads(txt))


class Pack:
    def __init__(self, spec, spec_dir):
        self.spec, self.dir = spec, spec_dir
        self.assets = (spec_dir / spec.get("assets", ".")).resolve()
        self.src = resolve(spec["source"]).parent
        self.d = load(spec["source"])
        global FPS
        FPS = float(self.d.get("fps") or 30)
        self.ref = load_style(spec.get("style_draft", "重点字"))
        self.M = self.d["materials"]
        self.lookup = {m["id"]: (k, m) for k, v in self.M.items() if isinstance(v, list) for m in v if isinstance(m, dict) and "id" in m}
        self.main = [t for t in self.d["tracks"] if t["type"] == "video"][0]
        self.subs = [t for t in self.d["tracks"] if t["type"] == "text"]
        self.T_BLUR, self.T_SCRIM, self.T_VIG = self.track("video", 2), self.track("video", 2), self.track("video", 2)
        self.T_KW, self.T_EN, self.T_INDEX = self.track("text"), self.track("text"), self.track("text")
        self.P_BROLL, self.P_CARD, self.P_SFX = [], [], []
        self.windows = []          # 虚化窗口，最后统一合并
        ref_lookup = {m["id"]: m for v in self.ref["materials"].values() if isinstance(v, list) for m in v if isinstance(m, dict) and "id" in m}
        segs = [s for t in self.ref["tracks"] if t["type"] == "text" for s in t.get("segments", [])]
        self.REF_CN, self.REF_EN = [ref_lookup[s["material_id"]] for s in segs[:2]]
        self.REF_ANIM = {s["material_id"]: ref_lookup[s["extra_material_refs"][0]] for s in segs[:2]}
        self.TPL_TSEG = sorted(self.subs[0]["segments"], key=lambda s: s["target_timerange"].get("start", 0))[0]
        self.TPL_VSEG = self.main["segments"][0]

    # ------------------------------------------------------------ 基础
    def track(self, kind, flag=None):
        t = {"id": nid(), "type": kind, "is_default_name": True, "segments": []}
        if flag is not None:
            t["flag"] = flag
        return t

    def add_mat(self, kind, m):
        self.M.setdefault(kind, []).append(m)
        self.lookup[m["id"]] = (kind, m)
        return m["id"]

    def clone_mat(self, mid):
        kind, m = self.lookup[mid]
        c = copy.deepcopy(m)
        c["id"] = nid()
        return self.add_mat(kind, c)

    @staticmethod
    def span(seg):
        a = seg["target_timerange"].get("start", 0)
        return a, a + seg["target_timerange"]["duration"]

    def put(self, where, seg, kind, flag=None):
        if isinstance(where, dict):
            where["segments"].append(seg)
            return
        a, b = self.span(seg)
        for t in where:
            if all(self.span(x)[1] <= a or self.span(x)[0] >= b for x in t["segments"]):
                t["segments"].append(seg)
                return
        t = self.track(kind, flag)
        t["segments"].append(seg)
        where.append(t)

    @staticmethod
    def kf(prop, pts):
        out = {"id": nid(), "material_id": "", "property_type": prop, "keyframe_list": []}
        for t, v in pts:
            k = {"id": nid(), "left_control": {"x": 0.0, "y": 0.0}, "right_control": {"x": 0.0, "y": 0.0}, "values": [v]}
            if t > 0:
                k["time_offset"] = us(t)
            out["keyframe_list"].append(k)
        return out

    @staticmethod
    def fade(dur, fin, fout, peak=1.0):
        pts = [(0, 0.0 if fin else peak)]
        if fin:
            pts.append((fin, peak))
        if fout:
            pts.append((dur - fout, peak))
        pts.append((dur, 0.0 if fout else peak))
        return pts

    # ------------------------------------------------------------ 时间
    def sub_text(self, s):
        return json.loads(self.lookup[s["material_id"]][1]["content"])["text"]

    def T(self, expr):
        if isinstance(expr, (int, float)):
            return float(expr)
        e, off = expr, 0.0
        for sign in ("+", "-"):
            if sign in e[1:]:
                i = e.rindex(sign)
                try:
                    off = float(e[i:])
                    e = e[:i]
                except ValueError:
                    pass
                break
        if e == "end":
            return self.TOTAL + off
        line, word = (e.split("/", 1) + [None])[:2]
        for s in sorted((s for t in self.subs for s in t["segments"]), key=lambda s: s["target_timerange"].get("start", 0)):
            if self.sub_text(s).startswith(line):
                st = s["target_timerange"].get("start", 0) / US
                if not word:
                    return st + off
                w = self.lookup[s["material_id"]][1].get("words") or {}
                full = "".join(w.get("text", []))
                idx = full.find(word)
                if idx < 0:
                    sys.exit(f"「{word}」不在字幕「{full}」里")
                pos = 0
                for t0, tx in zip(w["start_time"], w["text"]):
                    if pos + len(tx) > idx:
                        return st + t0 / 1000 + off
                    pos += len(tx)
                return st + off
        sys.exit(f"找不到以「{line}」开头的字幕")

    # ------------------------------------------------------------ A-roll 运镜
    def camera(self):
        cam = {"punch": 0.08, "push": 0.035, **self.spec.get("camera", {})}
        tail = self.spec.get("tail", 0)
        if tail:
            lv = self.main["segments"][-1]
            lv["target_timerange"]["duration"] += us(tail)
            lv["source_timerange"]["duration"] += us(tail)
            self.d["duration"] += us(tail)
            for t in self.subs:
                last = max(t["segments"], key=lambda s: s["target_timerange"].get("start", 0))
                last["target_timerange"]["duration"] = self.d["duration"] - last["target_timerange"].get("start", 0)
        self.TOTAL = self.d["duration"] / US
        scale = 1.0
        for i, s in enumerate(self.main["segments"]):
            dur = s["target_timerange"]["duration"] / US
            if i and dur >= 1.0:
                scale = 1.0 + cam["punch"] if scale == 1.0 else 1.0
            s["clip"]["scale"] = {"x": scale, "y": scale}
            s["common_keyframes"] = [self.kf("KFTypeScaleX", [(0, scale), (dur, scale + cam["push"] * min(dur, 4) / 4)])]

    def aroll_scale_at(self, t):
        for s in self.main["segments"]:
            a = s["target_timerange"].get("start", 0) / US
            dur = s["target_timerange"]["duration"] / US
            if a <= t <= a + dur:
                v0, v1 = (k["values"][0] for k in s["common_keyframes"][0]["keyframe_list"][:2])
                return v0 + (v1 - v0) * (t - a) / dur
        return 1.0

    # ------------------------------------------------------------ 图片
    def asset(self, name):
        for p in (self.assets / name, SKILL / "assets" / name):
            if p.exists():
                return p
        sys.exit(f"找不到素材 {name}（在 {self.assets} 和 skill assets 里都没有）")

    def photo(self, where, fname, t0, t1, alpha=None, scale_pts=None, pos_pts=None):
        from PIL import Image
        path = self.asset(fname)
        w, h = Image.open(path).size
        mat = {"id": nid(), "type": "photo", "duration": 10800000000, "path": str(path), "has_audio": False, "width": w, "height": h,
               "material_name": fname, "crop": {}, "stable": {"time_range": {}}, "matting": {"path": ""}, "source": 0,
               "video_algorithm": {"path": ""}}
        self.add_mat("videos", mat)
        s = copy.deepcopy(self.TPL_VSEG)
        s["id"] = nid()
        s["material_id"] = mat["id"]
        s["extra_material_refs"] = [self.clone_mat(r) for r in self.TPL_VSEG["extra_material_refs"] if self.lookup[r][0] in KEEP_KINDS]
        s["target_timerange"] = {"start": us(t0), "duration": us(t1) - us(t0)}
        s["source_timerange"] = {"start": 0, "duration": us(t1) - us(t0)}
        s["clip"] = {"scale": {"x": 1.0, "y": 1.0}, "transform": {"x": 0.0, "y": 0.0}, "flip": {}}
        s.pop("volume", None)
        s["common_keyframes"] = []
        if alpha:
            s["common_keyframes"].append(self.kf("KFTypeAlpha", alpha))
        if scale_pts:
            s["clip"]["scale"] = {"x": scale_pts[0][1], "y": scale_pts[0][1]}
            s["common_keyframes"].append(self.kf("KFTypeScaleX", scale_pts))
        if pos_pts:
            s["common_keyframes"].append(self.kf("KFTypePositionY", pos_pts))
        self.put(where, s, "video", 2)
        return s

    def broll(self, img, t0, t1, enter=True, leave=True):
        """对焦转场：进 1.15→1.0 + 淡入；在场匀速慢推；出 = 缩成卡片上飘 + 淡出。"""
        dur = t1 - t0
        sp = [(0, 1.15 if enter else 1.02)] + ([(0.45, 1.02)] if enter else [])
        sp += [(dur - 0.4, 1.06), (dur, 0.45)] if leave else [(dur, 1.06)]
        pos = [(0, 0.0), (dur - 0.4, 0.0), (dur, 0.9)] if leave else None
        self.photo(self.P_BROLL, img, t0, t1, alpha=self.fade(dur, 0.25 if enter else 0, 0.4 if leave else 0), scale_pts=sp, pos_pts=pos)

    # ------------------------------------------------------------ 对焦虚化（A-roll 虚化副本 + 压暗）
    def defocus(self, t0, t1, fin=0.3, fout=0.35):
        for s in self.main["segments"]:
            a = s["target_timerange"].get("start", 0) / US
            b = a + s["target_timerange"]["duration"] / US
            lo, hi = max(a, t0), min(b, t1)
            if hi - lo < 1 / FPS:
                continue
            c = copy.deepcopy(s)
            c["id"] = nid()
            c["material_id"] = self.clone_mat(s["material_id"])
            c["extra_material_refs"] = [self.clone_mat(r) for r in s["extra_material_refs"]]
            if BLUR_TPL["path"]:
                bl = {**copy.deepcopy(BLUR_TPL), "id": nid()}
                c["extra_material_refs"].append(self.add_mat("video_effects", bl))
            else:
                print("提示：本机未缓存模糊特效，仅保留对焦压暗；首次使用需在剪映验证视觉效果。", file=sys.stderr)
                continue
            c["target_timerange"] = {"start": us(lo), "duration": us(hi) - us(lo)}
            sp = s.get("speed") or 1.0  # 变速片段：源文件上的偏移和时长都要乘倍速
            c["source_timerange"] = {"start": s["source_timerange"].get("start", 0) + round(us(lo - a) * sp),
                                     "duration": round((us(hi) - us(lo)) * sp)}
            c["volume"], c["last_nonzero_volume"] = 0.0, 1.0
            dur = (us(hi) - us(lo)) / US
            s0, s1 = self.aroll_scale_at(lo) + 0.05, self.aroll_scale_at(hi) + 0.07
            c["clip"]["scale"] = {"x": s0, "y": s0}
            c["common_keyframes"] = [self.kf("KFTypeScaleX", [(0, s0), (dur, s1)]),
                                     self.kf("KFTypeAlpha", self.fade(dur, fin if abs(lo - t0) < 1e-3 else 0, fout if abs(hi - t1) < 1e-3 else 0))]
            self.T_BLUR["segments"].append(c)
        self.photo(self.T_SCRIM, "scrim.png", t0, t1, alpha=self.fade(t1 - t0, fin, fout))

    # ------------------------------------------------------------ 文字
    def text(self, where, t0, t1, runs, x=0.0, y=0.0, scale=1.0, tpl=None, anim=0.7, push=0.04, fade_out=0.2):
        tpl = tpl or self.REF_CN
        m = copy.deepcopy(tpl)
        m["id"] = nid()
        styles, pos = [], 0
        for txt, fill, size, font in runs:
            st = copy.deepcopy(json.loads(tpl["content"])["styles"][0])
            st.update(range=[pos, pos + len(txt)], fill=fill, size=size, font={"path": font, "id": ""})
            styles.append(st)
            pos += len(txt)
        m["content"] = json.dumps({"styles": styles, "text": "".join(r[0] for r in runs)}, ensure_ascii=False, separators=(",", ":"))
        m.pop("base_content", None)
        m["font_path"] = runs[0][3]
        self.add_mat("texts", m)
        an = copy.deepcopy(self.REF_ANIM[tpl["id"]])
        an["id"] = nid()
        an["animations"][0]["duration"] = us(anim)
        self.add_mat("material_animations", an)
        s = copy.deepcopy(self.TPL_TSEG)
        s["id"] = nid()
        s["material_id"] = m["id"]
        s["extra_material_refs"] = [an["id"]]
        dur = t1 - t0
        s["target_timerange"] = {"start": us(t0), "duration": us(t1) - us(t0)}
        s["clip"] = {"scale": {"x": scale, "y": scale}, "transform": {"x": x, "y": y}, "flip": {}}
        s["common_keyframes"] = [self.kf("KFTypeScaleX", [(0, scale), (dur, scale * (1 + push))])]
        if fade_out:
            s["common_keyframes"].append(self.kf("KFTypeGlobalAlpha", [(0, 1.0), (dur - fade_out, 1.0), (dur, 0.0)]))
        self.put(where, s, "text")
        return s

    @staticmethod
    def solid(rgb, alpha=1.0):
        f = {"content": {"solid": {"color": rgb}, "render_type": "solid"}}
        if alpha < 1:
            f["alpha"] = alpha
        return f

    @staticmethod
    def grad():
        return {"content": {"gradient": {"mode": "all", "angle": 0, "percent": [0, 1], "alpha": [1, 1], "color": GRAD}, "render_type": "gradient"}}

    def cn(self, txt, accent=False, size=15):
        return (txt, self.solid(YELLOW) if accent else self.grad(), size, FONT_CN)

    # ------------------------------------------------------------ 音效
    def sfx(self, t, name, gain=0.35):
        f = SFX_DIR / name
        if not f.exists():
            if name not in MISSING_SFX:
                MISSING_SFX.add(name)
                print(f"⚠ 音效不存在，跳过：{f}", file=sys.stderr)
            return
        dur = float(subprocess.run([R.tool("ffprobe"), "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                   capture_output=True, encoding="utf-8", errors="replace", check=True).stdout.strip())
        dur = min(dur, 2.5, self.TOTAL - t)
        if dur <= 0.05:
            return
        mat = {"id": nid(), "type": "extract_music", "name": name, "duration": us(dur), "path": str(f),
               "resource_id": "", "similiar_music_info": {}, "tts_benefit_info": {"benefit_type": "none"}}
        self.add_mat("audios", mat)
        refs = [self.clone_mat(r) for r in self.TPL_VSEG["extra_material_refs"]
                if self.lookup[r][0] in ("speeds", "placeholder_infos", "sound_channel_mappings", "vocal_separations")]
        s = {"id": nid(), "source_timerange": {"start": 0, "duration": us(dur)}, "target_timerange": {"start": us(max(t, 0)), "duration": us(dur)},
             "render_timerange": {}, "volume": gain, "last_nonzero_volume": gain, "material_id": mat["id"], "extra_material_refs": refs,
             "enable_lut": False, "enable_adjust": False, "enable_hsl": False, "visible": True, "track_render_index": 0,
             "responsive_layout": {}, "enable_adjust_mask": False, "source": "segmentsourcenormal"}
        self.put(self.P_SFX, s, "audio")

    # ------------------------------------------------------------ 分镜元素
    def b_keyword(self, b, t0, t1):
        zh, y = b["zh"], b.get("y", -0.33)
        n = sum(0.55 if c.isascii() else 1 for c in zh)
        sc = b.get("scale", 2.1 * min(1.0, 4 / max(n, 1)))
        self.text(self.T_KW, t0, t1, [self.cn(zh, b.get("accent"))], y=y, scale=sc)
        if b.get("en"):
            half = 0.105 * sc * n
            self.text(self.T_EN, t0 + 0.15, t1, [(b["en"], self.solid(YELLOW), 15, FONT_EN)],
                      x=min(0.55, half * 0.8), y=y - 0.08, scale=1.0, tpl=self.REF_EN, anim=0.5)
        if b.get("sfx", "一次呼.wav"):
            self.sfx(t0 - 0.05, b.get("sfx", "一次呼.wav"), 0.35)

    def b_menu(self, b, t0, t1):
        items, hl, dim = b["items"], set(b.get("highlight", [])), set(b.get("dim", []))
        ys = b.get("ys") or [0.34 - 0.24 * i for i in range(len(items))]
        for i, (nm, y) in enumerate(zip(items, ys)):
            a = 0.35 if i in dim else 1.0
            body = self.solid(YELLOW) if i in hl else (self.solid([1, 1, 1], a) if a < 1 else self.grad())
            self.text(self.P_CARD, t0 + i * 0.18, t1, [(f"0{i+1} ", self.solid(YELLOW, a), 15, FONT_CN), (nm, body, 15, FONT_CN)],
                      y=y, scale=b.get("scale", 1.25), push=0.03)
            if b.get("sfx", True):
                self.sfx(t0 + i * 0.18, f"手机UI阳性0{i % 3 + 1}.mp3", 0.3)

    def b_cards(self, b, t0, t1):
        """逐条卡住台词出现的标签：items=[{at, zh, prefix?, accent?, sfx?}]；arrows=true 时条目之间画 ↓（做链路）。"""
        items = b["items"]
        ys = b.get("ys") or [0.3 - 0.26 * i for i in range(len(items))]
        for k, (it, y) in enumerate(zip(items, ys)):
            ti = self.T(it["at"]) if "at" in it else t0 + k * 0.2
            runs = ([(it["prefix"], self.solid(YELLOW), 15, FONT_CN)] if it.get("prefix") else []) + [self.cn(it["zh"], it.get("accent"))]
            self.text(self.P_CARD, ti, t1, runs, y=y, scale=b.get("scale", 1.25), push=0.03)
            if b.get("arrows") and k:
                self.text(self.P_CARD, ti - 0.1, t1, [("↓", self.solid([1, 1, 1], 0.6), 15, SYS_FONT)], y=(ys[k - 1] + y) / 2,
                          scale=0.6, push=0.0, anim=0.3)
            snd = it.get("sfx", b.get("sfx", "任务游戏界面点击型.wav"))
            if snd:
                self.sfx(ti - 0.03, snd, 0.3)

    def b_index(self, b, t0, t1):
        labels = self.spec["sections"]
        runs = []
        for i, lab in enumerate(labels):
            fill = self.solid(YELLOW) if i == b["active"] else self.solid([1, 1, 1], 0.45)
            runs.append((f"0{i+1} {lab}" + ("   " if i < len(labels) - 1 else ""), fill, 15, FONT_CN))
        self.text(self.T_INDEX, t0, t1, runs, y=b.get("y", 0.84), scale=b.get("scale", 0.5), anim=0.4, push=0.0, fade_out=0.15)

    def b_broll(self, b, t0, t1):
        self.broll(b["img"], t0, t1, b.get("enter", True), b.get("leave", True))
        if b.get("sfx", "Whoosh.mp3"):
            self.sfx(t0 - 0.05, b.get("sfx", "Whoosh.mp3"), 0.4)
        if b.get("leave", True) and b.get("sfx_out", "快吹.wav"):
            self.sfx(t1 - 0.4, b.get("sfx_out", "快吹.wav"), 0.35)

    def b_caption(self, b, t0, t1):
        self.text(self.P_CARD, t0, t1, [(b["text"], self.solid([1, 1, 1]), b.get("size", 8), SYS_FONT)],
                  y=b.get("y", -0.38), scale=b.get("scale", 1.0), push=0.0, fade_out=0 if b.get("to") == "end" else 0.2)

    def b_sfx(self, b, t0, t1):
        self.sfx(t0, b["name"], b.get("gain", 0.35))

    def b_defocus(self, b, t0, t1):
        self.windows.append((t0, t1))

    # ------------------------------------------------------------ 组装
    def build(self):
        self.camera()
        rows = []
        for b in self.spec["beats"]:
            t0 = self.T(b["at"])
            t1 = self.T(b.get("to", "end"))
            getattr(self, "b_" + b["do"])(b, t0, t1)
            if b.get("defocus"):
                pad = b.get("defocus") if isinstance(b.get("defocus"), list) else [0.25, 0.1]
                self.windows.append((t0 - pad[0], t1 + pad[1]))
            rows.append((t0, t1, b["do"], b.get("zh") or b.get("img") or b.get("text") or ",".join(b.get("items", []) if isinstance(b.get("items", [None])[0], str) else [i["zh"] for i in b.get("items", [])])))
        # 合并重叠/相邻（<0.3s）的虚化窗口，避免同轨冲突和闪一下
        merged = []
        for a, b_ in sorted(self.windows):
            if merged and a <= merged[-1][1] + 0.3:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b_))
            else:
                merged.append((a, b_))
        for a, b_ in merged:
            self.defocus(max(0, a), min(self.TOTAL, b_), fout=0 if b_ >= self.TOTAL - 0.05 else 0.35)
        if self.spec.get("vignette", True):
            self.photo(self.T_VIG, "vignette.png", 0, self.TOTAL)

        V = [self.main, self.T_BLUR] + self.P_BROLL + [self.T_SCRIM, self.T_VIG]
        others = [t for t in self.d["tracks"] if t["type"] not in ("text", "video")]
        self.d["tracks"] = V + [self.T_KW, self.T_EN] + self.P_CARD + [self.T_INDEX] + self.subs + others + self.P_SFX
        self.d["tracks"] = [t for t in self.d["tracks"] if t["segments"] or t in (self.main, *self.subs)]
        ri = 14000
        for t in self.d["tracks"]:
            t["segments"].sort(key=lambda s: s["target_timerange"].get("start", 0))
            if t["type"] == "text":
                for s in t["segments"]:
                    s["render_index"] = ri
                ri += 1
        for k, t in enumerate(v for v in self.d["tracks"] if v["type"] == "video"):
            for s in t["segments"]:
                s["track_render_index"] = k
                if k:
                    s["render_index"] = k
        # 关键帧：钳到片段内、递增、去重
        for t in self.d["tracks"]:
            for sg in t["segments"]:
                D = sg["target_timerange"]["duration"]
                for k in sg.get("common_keyframes", []):
                    out, last = [], -1
                    for x in k["keyframe_list"]:
                        off = max(min(max(x.pop("time_offset", 0), 0), D), last)
                        if out and off == last:
                            out[-1] = x
                        else:
                            out.append(x)
                        if off > 0:
                            x["time_offset"] = off
                        last = off
                    k["keyframe_list"] = out
        for t in self.d["tracks"]:
            for p, q in zip(t["segments"], t["segments"][1:]):
                if q["target_timerange"].get("start", 0) < self.span(p)[1]:
                    sys.exit(f"轨道 {t['type']} 在 {q['target_timerange']['start'] / US:.2f}s 重叠")
        return rows, merged


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sp = Path(sys.argv[1]).resolve()
    spec = json.loads(sp.read_text(encoding="utf-8-sig"))
    pk = Pack(spec, sp.parent)
    rows, merged = pk.build()
    if "--dry-run" in sys.argv:
        for t0, t1, kind, what in sorted(rows):
            warn = "  ⚠ 停留不到 1.4s" if kind == "keyword" and t1 - t0 < 1.4 else ""
            print(f"{t0:6.2f}-{t1:6.2f}  {kind:8s} {what}{warn}")
        print("虚化窗口：", ", ".join(f"{a:.2f}-{b:.2f}" for a, b in merged))
        print(f"时长 {pk.TOTAL:.2f}s · 轨道 {len(pk.d['tracks'])} 条")
        return
    out = spec["output"]
    R.safe_child(pk.src.parent, out)
    if (pk.src.parent / out).exists():
        sys.exit(f"已存在草稿「{out}」，换个 output 名，或先在剪映里删掉它")
    raw = resolve(str(pk.src)).read_text(encoding="utf-8-sig")
    dst, draft_id, meta = write_draft(pk.src, pk.d, out, raw)
    register(pk.src.parent, [(pk.src.name, dst, draft_id, meta)])
    print("✅", dst, f"{pk.TOTAL:.2f}s")


if __name__ == "__main__":
    main()
