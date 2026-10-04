#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 待挑选/ 里的图标做成一个可点选的网页挑选器。

用法：
    python picker.py                    # 生成 挑选.html 并打开
    python picker.py --dir 待挑选

产出：
    挑选.html      浏览器打开，勾选 / 全选 / 按名字筛 / 实时显示已选数量
    已选.txt       勾完点「导出」，把选中的文件名写到这里
    已选/          勾完点「导出选中」，把选中的 PNG 复制到这里，可直接喂给 build.py
"""

import argparse
import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ · 挑选图标</title>
<style>
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;
     margin:0;background:#f2f2f7;color:#1c1c1e}
header{position:sticky;top:0;z-index:10;background:rgba(255,255,255,.94);
       backdrop-filter:saturate(180%) blur(20px);border-bottom:1px solid #e3e3e8;padding:14px 20px}
h1{margin:0 0 10px;font-size:17px;font-weight:600}
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
input[type=search]{flex:1;min-width:160px;padding:8px 12px;border:1px solid #d3d3d8;border-radius:9px;
     font-size:14px;background:#fff}
button{padding:8px 14px;border:1px solid #d3d3d8;border-radius:9px;background:#fff;
     font-size:13px;cursor:pointer;color:#1c1c1e}
button:hover{background:#f0f0f5}
button.p{background:#0a84ff;border-color:#0a84ff;color:#fff;font-weight:500}
button.p:hover{background:#0070e0}
#cnt{font-size:13px;color:#8a8a8e;margin-left:auto;white-space:nowrap}
#cnt b{color:#0a84ff;font-size:15px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(104px,1fr));gap:12px;padding:18px 20px 60px}
.c{background:#fff;border-radius:12px;padding:10px 6px;text-align:center;cursor:pointer;
   border:2px solid transparent;position:relative;user-select:none}
.c:hover{background:#fafafa}
.c.on{border-color:#0a84ff;background:#f0f7ff}
.c img{width:52px;height:52px;object-fit:contain;display:block;margin:0 auto}
.n{font-size:10.5px;color:#3a3a3c;margin-top:7px;word-break:break-all;line-height:1.25;
   max-height:2.5em;overflow:hidden}
.c.on .n{color:#0a84ff;font-weight:600}
.badge{position:absolute;top:6px;right:6px;width:17px;height:17px;border-radius:50%;
   background:#0a84ff;color:#fff;font-size:11px;line-height:17px;display:none}
.c.on .badge{display:block}
.hide{display:none!important}
#toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:rgba(28,28,30,.92);
   color:#fff;padding:11px 20px;border-radius:10px;font-size:13.5px;opacity:0;transition:.25s;pointer-events:none;z-index:99}
#toast.on{opacity:1}
</style>
</head>
<body>
<header>
  <h1>__TITLE__<span style="font-weight:400;color:#8a8a8e;font-size:13px"> · 共 __COUNT__ 个</span></h1>
  <div class="bar">
    <input type="search" id="q" placeholder="按名字筛选，例如 emby / 115 / 腾讯">
    <button onclick="pick('all')">全选可见</button>
    <button onclick="pick('none')">清空</button>
    <button onclick="pick('invert')">反选可见</button>
    <button class="p" onclick="exp()">导出选中 (__N__)</button>
  </div>
  <div class="bar" style="margin-top:8px">
    <span id="cnt">已选 <b>0</b></span>
  </div>
</header>
<div class="grid" id="g"></div>
<div id="toast"></div>
<script>
const DATA = __DATA__;
const g = document.getElementById('g');
const sel = new Set();

DATA.forEach((d, i) => {
  const el = document.createElement('div');
  el.className = 'c';
  el.dataset.n = d.n.toLowerCase();
  el.dataset.f = d.f;
  el.innerHTML = '<span class="badge">✓</span><img loading="lazy" src="'+d.f+'" alt="'+d.n+'">'+
                 '<div class="n" title="'+d.f+'">'+d.n+'</div>';
  el.onclick = () => {
    if (sel.has(d.f)) { sel.delete(d.f); el.classList.remove('on'); }
    else { sel.add(d.f); el.classList.add('on'); }
    upd();
  };
  el.onerror = () => { el.style.opacity = .25; };
  g.appendChild(el);
});

function upd(){
  document.getElementById('cnt').innerHTML = '已选 <b>'+sel.size+'</b>';
  const b = document.querySelector('button.p');
  b.textContent = '导出选中 ('+sel.size+')';
}

document.getElementById('q').oninput = e => {
  const v = e.target.value.trim().toLowerCase();
  document.querySelectorAll('.c').forEach(el => {
    el.classList.toggle('hide', v && !el.dataset.n.includes(v));
  });
};

function pick(mode){
  document.querySelectorAll('.c:not(.hide)').forEach(el => {
    const on = !el.classList.contains('on');
    if (mode === 'all') el.classList.add('on');
    else if (mode === 'none') el.classList.remove('on');
    else if (mode === 'invert') el.classList.toggle('on', on);
    el.classList.contains('on') ? sel.add(el.dataset.f) : sel.delete(el.dataset.f);
  });
  upd();
}

function toast(m){
  const t = document.getElementById('toast');
  t.textContent = m; t.classList.add('on');
  setTimeout(() => t.classList.remove('on'), 2200);
}

function exp(){
  if (!sel.size) { toast('还没选任何图标'); return; }
  const names = [...sel].sort();
  // 已选.txt
  const blob = new Blob([names.join('\n')+'\n'], {type:'text/plain'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = '已选.txt'; a.click();
  // 存 localStorage，供 collect.py 读取
  try { localStorage.setItem('__KEY__', JSON.stringify(names)); } catch(e){}
  toast('已导出 已选.txt（' + names.length + ' 个），另存到浏览器本地');
}
upd();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="生成图标挑选页")
    ap.add_argument("--dir", default="待挑选", help="图标目录")
    ap.add_argument("--title", default="恩秀 Emby 图标库", help="页面标题")
    ap.add_argument("--out", default="挑选.html", help="输出 HTML")
    ap.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    args = ap.parse_args()

    src = Path(args.dir)
    if not src.is_absolute():
        src = ROOT / src
    if not src.exists():
        print(f"找不到目录：{src}")
        print("先跑 fetch_source.py 把图下下来。")
        return 1

    idx = src / "_index.json"
    meta = {}
    if idx.exists():
        meta = json.loads(idx.read_text(encoding="utf-8"))

    files = sorted(p.name for p in src.glob("*.png"))
    if not files:
        print(f"{src} 里没有 PNG。")
        return 1

    # 优先用 _index.json 里的社区显示名，缺失则用文件名
    by_file = {}
    for it in meta.get("icons", []):
        by_file[it.get("file")] = it.get("name") or it.get("file")

    data = []
    for f in files:
        data.append({
            "f": html.escape(f, quote=True),
            "n": html.escape(by_file.get(f, Path(f).stem)),
        })

    page = (HTML
            .replace("__TITLE__", html.escape(args.title))
            .replace("__COUNT__", str(len(data)))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__KEY__", "iconpack_sel_" + str(abs(hash(args.dir)) % 10**8))
            .replace("__N__", "0"))

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.write_text(page, encoding="utf-8")

    print(f"共 {len(data)} 个图标")
    print(f"挑选页：{out}")
    print()
    print("用法：")
    print("  1. 浏览器打开上面的挑选页")
    print("  2. 勾选 / 筛选 / 全选")
    print("  3. 点「导出选中」得到 已选.txt")
    print("  4. 回到本目录跑：python collect.py")
    print("     （把选中的 PNG 复制到 icons/ 并自动改好文件名）")
    if not args.no_open:
        import webbrowser
        webbrowser.open(out.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
