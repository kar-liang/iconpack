#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图标包生成器 —— 产出一份 JSON，同时喂给 Loon / SenPlayer / Quantumult X / Fileball / Yamby / Hills。

用法（最常见）：
    python build.py                      # 交互式：会问你要托管地址
    python build.py --base https://raw.githubusercontent.com/你/仓库/main
    python build.py --base http://192.168.2.144:8899 --name "我的图标包"

设计要点：
  1. 图标放 icons/ 目录里，文件名就是图标名（不带扩展名）。
  2. 输出统一走 {name, description, icons:[{name,url}]}，这几个 App 都吃这个结构。
  3. URL 里的路径段做百分号编码 —— 中文、空格、括号不编码的话部分 App 会拉不到图。
  4. 纯标准库，不用装任何东西。
"""

import argparse
import datetime
import html
import json
import re
import struct
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ICONS_DIR = ROOT / "icons"
DIST = ROOT / "dist"

IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

# App 侧显示尺寸：Loon 策略列表按 60pt 左右渲染，TV 端媒体库卡片能到 150pt+
MIN_SIZE = 108
RECOMMENDED_SIZE = 256


# ---------------------------------------------------------------- 图片尺寸读取
def _png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def _gif_size(path):
    with open(path, "rb") as f:
        head = f.read(10)
    if len(head) < 10 or head[:6] not in (b"GIF87a", b"GIF89a"):
        return None
    return struct.unpack("<HH", head[6:10])


def _jpeg_size(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:2] != b"\xff\xd8":
        return None
    i, n = 2, len(data)
    sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
           0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while i < n - 1:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if i + 4 > n:
            break
        seglen = struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker in sof:
            if i + 9 <= n:
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            break
        i += 2 + seglen
    return None


def _webp_size(path):
    with open(path, "rb") as f:
        data = f.read(30)
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8X":
        return (int.from_bytes(data[24:27], "little") + 1,
                int.from_bytes(data[27:30], "little") + 1)
    if chunk == b"VP8 ":
        return (int.from_bytes(data[26:28], "little") & 0x3FFF,
                int.from_bytes(data[28:30], "little") & 0x3FFF)
    if chunk == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
    return None


def image_size(path):
    ext = path.suffix.lower()
    fn = {".png": _png_size, ".gif": _gif_size,
          ".jpg": _jpeg_size, ".jpeg": _jpeg_size, ".webp": _webp_size}.get(ext)
    if not fn:
        return None
    try:
        return fn(path)
    except Exception:
        return None


# ---------------------------------------------------------------- 别名
def load_aliases(path):
    """
    每行： 正式名 = 别名1, 别名2, 别名3
    用来抹平大小写 / 空格差异 —— App 里是按名字精确匹配的，
    你节点叫「Emby」而图标叫「emby」时就匹配不上，很烦。
    """
    mapping = {}
    if not path.exists():
        return mapping
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        canon, _, rest = line.partition("=")
        canon = canon.strip()
        for alias in rest.split(","):
            alias = alias.strip()
            if alias and alias != canon:
                mapping[alias] = canon
    return mapping


def slug(name):
    """规整成小写、去空格，用于查重（不改变实际图标名）。"""
    return re.sub(r"\s+", "", name).lower()


VARIANT_RE = re.compile(r"^(?P<stem>.+?)-(?P<num>0[2-9]|\d{2,})$")


def fold_variants(icons):
    """
    把「X-02 / X-03」这类**同名变体**折叠成 X 的别名，而不是当成独立图标。

    为什么必须折叠：App 是按图标名**精确匹配**的。你手机上的 App 叫「Emby」，
    图标包里却只有「Emby-02」这种名字 → 永远匹配不上，等于白放。
    社区库里 718 个图标有 180 个重名（同一 App 的不同清晰度/版本），
    下载工具为了不覆盖才加了 -02 后缀，但那些后缀名在 App 侧毫无意义。

    返回 (保留的图标, 自动别名 dict)。
    只有当 X.png 本身存在时才折叠 —— 否则 -02 才是唯一那张，得留着。
    """
    stems = {slug(i["name"]) for i in icons}
    kept, auto = [], {}
    for it in icons:
        m = VARIANT_RE.match(it["name"])
        if m and slug(m.group("stem")) in stems:
            auto[it["name"]] = m.group("stem")
        else:
            kept.append(it)
    return kept, auto


# ---------------------------------------------------------------- 扫描
def scan_icons(root, prefix_folder=False):
    found, problems = [], []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in IMG_EXTS:
            continue
        if p.name.startswith((".", "_")):
            continue
        rel = p.relative_to(root).as_posix()
        stem = p.stem
        if prefix_folder:
            parts = p.relative_to(root).parts
            if len(parts) > 1:
                stem = f"{parts[-2]}-{stem}"
        found.append({"path": p, "rel": rel, "name": stem})

    by_key = {}
    for item in found:
        by_key.setdefault(slug(item["name"]), []).append(item)
    for key, group in by_key.items():
        if len(group) > 1:
            problems.append("重名：" + " / ".join(g["rel"] for g in group))
            for g in group[1:]:
                found.remove(g)
    return found, problems


# ---------------------------------------------------------------- HTML 产出
SENPLAYER_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>导入 SenPlayer 图标包</title>
<style>
 body{{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;
      text-align:center;padding:48px 20px;background:#f6f6f8;color:#1c1c1e}}
 h3{{margin:0 0 8px;font-size:17px}}
 p{{color:#8a8a8e;font-size:14px;margin:6px 0}}
 .btn{{display:inline-block;margin-top:22px;padding:12px 22px;background:#0a84ff;color:#fff;
       text-decoration:none;border-radius:10px;font-size:16px}}
 code{{background:#ececf0;padding:2px 6px;border-radius:4px;font-size:12px;word-break:break-all}}
</style>
</head>
<body>
<h3>正在唤醒 SenPlayer…</h3>
<p>弹窗里选「打开」</p>
<p>没反应就用下面的手动按钮（SenPlayer 需 6.0.6 或更高）</p>
<div id="wrap"><a class="btn" id="btn" href="#">手动一键导入</a></div>
<p style="margin-top:28px">图标包地址<br><code>{url}</code></p>
<script>
 (function(){{
  var u = new URLSearchParams(location.search).get('iconset') || {json_url};
  var scheme = "senplayer://importicon?iconset=" + encodeURIComponent(u);
  var a = document.getElementById('btn'); a.href = scheme;
  location.href = scheme;
  setTimeout(function(){{
    if (document.getElementById('wrap')) document.getElementById('wrap').style.opacity = 1;
  }}, 3000);
 }})();
</script>
</body>
</html>
"""

LOON_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>导入 Loon 图标包</title>
<style>
 body{{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;
      text-align:center;padding:48px 20px;background:#f6f6f8;color:#1c1c1e}}
 h3{{margin:0 0 8px;font-size:17px}}
 p{{color:#8a8a8e;font-size:14px;margin:6px 0}}
 .btn{{display:inline-block;margin-top:22px;padding:12px 22px;background:#0a84ff;color:#fff;
       text-decoration:none;border-radius:10px;font-size:16px}}
 code{{background:#ececf0;padding:2px 6px;border-radius:4px;font-size:12px;word-break:break-all}}
</style>
</head>
<body>
<h3>导入 Loon 图标包</h3>
<p>点下面按钮，会自动跳到 Loon 并完成导入</p>
<a class="btn" id="btn" href="{loon_url}">一键导入到 Loon</a>
<p style="margin-top:28px">图标包地址<br><code>{url}</code></p>
<p style="margin-top:6px">若想手动：Loon 里长按策略组/订阅 → 图标 → 右上角 + → 粘贴同一地址</p>
</body>
</html>
"""


def build_preview(entries, pack_name, base):
    cards = []
    for e in entries:
        cards.append(
            '<figure class="c"><img src="{url}" alt="{name}" loading="lazy">'
            '<figcaption>{name}</figcaption></figure>'.format(
                url=urllib.parse.quote(e["url"], safe=":/?&=%#"),
                name=html.escape(e["name"]))
        )
    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · 预览</title>
<style>
 body{{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;
      margin:0;padding:28px;background:#f6f6f8;color:#1c1c1e}}
 h1{{font-size:20px;margin:0 0 4px}}
 .meta{{color:#8a8a8e;font-size:13px;margin-bottom:22px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:16px}}
 .c{{margin:0;background:#fff;border-radius:12px;padding:12px 8px;text-align:center}}
 .c img{{width:56px;height:56px;object-fit:contain}}
 figcaption{{font-size:11px;color:#3a3a3c;margin-top:8px;word-break:break-all;line-height:1.3}}
 .bad{{outline:2px solid #ff3b30}}
</style></head><body>
<h1>{title}</h1>
<div class="meta">共 {count} 个图标 · 底图源 {base}</div>
<div class="grid">
{cards}
</div>
</body></html>
""".format(title=pack_name, count=len(entries), base=base, cards="".join(cards))


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser(description="生成 Loon / SenPlayer 通用图标包")
    ap.add_argument("--base", help="图标包的公网访问前缀，例如 https://raw.githubusercontent.com/你/仓库/main")
    ap.add_argument("--name", default="我的图标包", help="图标包显示名")
    ap.add_argument("--description", default="", help="图标包描述")
    ap.add_argument("--prefix-folder", action="store_true", help="图标名带上子目录前缀，避免重名")
    ap.add_argument("--strict", action="store_true", help="有告警就退出，不生成")
    args = ap.parse_args()

    if not ICONS_DIR.exists():
        print(f"找不到图标目录：{ICONS_DIR}")
        print("建一个，把 png 丢进去再跑。")
        return 1

    icons, dup_problems = scan_icons(ICONS_DIR, args.prefix_folder)
    if not icons:
        print(f"{ICONS_DIR} 里没有找到图片。")
        return 1
    # 同名变体（X-02/X-03）折叠成 X 的别名，否则这些名字在 App 侧匹配不到任何东西
    icons, auto_aliases = fold_variants(icons)

    base = (args.base or "").strip().rstrip("/")
    if not base:
        print()
        print("没有指定 --base，图标包得有个公网地址手机才拉得到。选一个：")
        print("  1) GitHub 仓库  → https://raw.githubusercontent.com/<用户名>/<仓库>/main")
        print("  2) 自己的 NAS    → http://192.168.2.144:<端口>（需配 Lucky/反代）")
        print("  3) Cloudflare R2 → https://<桶>.r2.dev")
        try:
            base = input("粘贴前缀（回车用示例 https://example.com/icons）: ").strip()
        except (EOFError, KeyboardInterrupt):
            return 1
        base = base or "https://example.com/icons"

    warnings = list(dup_problems)
    entries = []
    for it in icons:
        size = image_size(it["path"])
        if size is None:
            warnings.append(f"读不出尺寸（可能文件损坏）：{it['rel']}")
        else:
            w, h = size
            if w != h:
                warnings.append(f"非正方形 {w}x{h}：{it['rel']}")
            if min(w, h) < MIN_SIZE:
                warnings.append(f"太小 {w}x{h}（<{MIN_SIZE}，TV 端会糊）：{it['rel']}")
            elif min(w, h) < RECOMMENDED_SIZE:
                warnings.append(f"偏小 {w}x{h}（建议 ≥{RECOMMENDED_SIZE}）：{it['rel']}")
        # 路径段逐个百分号编码，斜杠保留
        quoted = "/".join(urllib.parse.quote(seg, safe="")
                          for seg in it["rel"].split("/"))
        entries.append({"name": it["name"], "url": f"{base}/{quoted}",
                        "_rel": it["rel"], "_size": size})

    aliases = load_aliases(ROOT / "aliases.txt")
    # 手工写的 aliases.txt 优先，自动折叠的同名变体只作补充
    for k, v in auto_aliases.items():
        aliases.setdefault(k, v)
    by_name = {e["name"]: e for e in entries}
    # 大小写/空格不敏感索引 —— 手工写的 aliases.txt 常把 Plex 写成 plex
    loose = {slug(k): k for k in by_name}
    for alias, canon in aliases.items():
        target = canon if canon in by_name else loose.get(slug(canon))
        if target:
            if target != canon:
                warnings.append(f"别名「{alias}」的正式名 {canon} 不存在，已按 {target} 处理")
            entries.append({"name": alias, "url": by_name[target]["url"],
                            "_rel": by_name[target]["_rel"], "_alias_of": target})
        else:
            warnings.append(f"别名指向不存在的图标：{alias} → {canon}"
                            f"（有 icons/{canon}.png 吗？）")

    # 排序：先原始图标后别名，各按名字
    entries.sort(key=lambda e: (1 if "_alias_of" in e else 0,
                                e["name"].lower()))

    # App 按图标名**精确匹配**，同名两条会打架（选到哪条不确定）→ 强制去重。
    # 同名时保留第一条（排序后原始图标优先），后续的改叫 -02/-03 并告警。
    final, seen = [], {}
    for e in entries:
        key = e["name"]
        if key not in seen:
            seen[key] = e
            final.append(e)
            continue
        stem, n = key, 2
        while f"{stem}-{n:02d}" in seen:
            n += 1
        renamed = f"{stem}-{n:02d}"
        seen[renamed] = e
        e = dict(e, name=renamed)
        final.append(e)
        warnings.append(f"图标名重复，已改名：{key} -> {renamed}")
    entries = final

    today = datetime.date.today().strftime("%y%m%d")
    desc = args.description or f"自建图标包 · {today}"

    DIST.mkdir(exist_ok=True)
    payload = {
        "name": f"{args.name} {today}",
        "description": desc,
        "icons": [{"name": e["name"], "url": e["url"]} for e in entries],
    }
    json_path = DIST / "icons.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")

    primary = [e for e in entries if "_alias_of" not in e]
    (DIST / "preview.html").write_text(
        build_preview(primary, payload["name"], base), encoding="utf-8")
    (DIST / "senplayer-import.html").write_text(
        SENPLAYER_HTML.format(url=base + "/icons.json",
                              json_url=json.dumps(base + "/icons.json")),
        encoding="utf-8")
    (DIST / "loon-import.html").write_text(
        LOON_HTML.format(url=base + "/icons.json",
                         loon_url="https://www.nsloon.com/openloon/import?iconset="
                                  + urllib.parse.quote(base + "/icons.json", safe="")),
        encoding="utf-8")
    (DIST / "manifest.txt").write_text(
        "\n".join(f"{e['name']}\t{e['_rel']}\t{e['_size']}" for e in primary)
        + "\n", encoding="utf-8")

    real = len(primary)
    print()
    print(f"图标 {real} 个" + (f"，别名 {len(entries) - real} 个" if len(entries) > real else ""))
    print(f"输出：{json_path}")
    print(f"      {DIST / 'loon-import.html'}")
    print(f"      {DIST / 'senplayer-import.html'}")
    print(f"      {DIST / 'preview.html'}")
    if warnings:
        print(f"\n告警 {len(warnings)} 条：")
        for w in warnings[:40]:
            print("  - " + w)
        if len(warnings) > 40:
            print(f"  …… 还有 {len(warnings) - 40} 条")
    if dup_problems and args.strict:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
