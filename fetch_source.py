#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从社区图标库把 PNG 全部下到本地，供老大挑选。

用法：
    python fetch_source.py                       # 用内置的恩秀 Emby 图标库
    python fetch_source.py 其他.json              # 换别的源
    python fetch_source.py --proxy http://192.168.2.100:7890

设计要点：
  1. **按 URL 里的文件名保存**，不按 JSON 里的 name。
     恩秀库有 180 个重名（Emby 有 Emby-01/02/03…），
     按 name 存会互相覆盖 —— 那是社区展示名，不是唯一标识。
  2. 重名的自动加 -01/-02 后缀，跟社区习惯一致。
  3. 只用标准库 urllib，走系统/显式代理。
"""

import argparse
import concurrent.futures
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_SRC = "https://raw.githubusercontent.com/sooyaaabo/IconLibrary/main/Emby-Icon.json"
OUT = ROOT / "待挑选"


def http_get(url, proxy=None, timeout=40, retries=3):
    """
    注意 ProxyHandler 的坑：
      - ProxyHandler()      空参 = **自动继承环境变量**（http_proxy/https_proxy）
      - ProxyHandler({})    空字典 = 彻底忽略环境变量
    本机上 WorkBuddy 沙箱会注入一个 127.0.0.1:64851 的代理，它对普通
    HTTPS 请求会回 502。所以这里必须显式给字典，不能留空参。
    """
    if proxy:
        handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy})]
    else:
        # 显式空字典：屏蔽所有环境变量代理
        handlers = [urllib.request.ProxyHandler({})]
    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx), *handlers)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 iconpack-fetch"})
            with opener.open(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            if attempt < retries - 1:
                import time
                time.sleep(1.2 * (attempt + 1))
    raise last


def safe_name(raw, used):
    """把 URL 文件名弄成合法且不重复的本地文件名。"""
    name = urllib.parse.unquote(raw)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    if not name.lower().endswith(".png"):
        name += ".png"
    if name not in used:
        used.add(name)
        return name
    stem, ext = os.path.splitext(name)
    n = 1
    while f"{stem}-{n:02d}{ext}" in used:
        n += 1
    fixed = f"{stem}-{n:02d}{ext}"
    used.add(fixed)
    return fixed


def pick_proxy(explicit="", probe_url=DEFAULT_SRC):
    """
    决定用哪个代理。显式指定 > 自动探测。
    自动探测顺序：直连 -> 常见内网代理端口。
    直连能通（境外可访问）就不用折腾代理。
    """
    if explicit:
        return explicit, "命令行指定"
    candidates = [
        ("", "直连"),
        ("http://192.168.2.100:7890", "NAS 旁路由 192.168.2.100:7890"),
        ("http://127.0.0.1:7890", "本机 127.0.0.1:7890"),
    ]
    for proxy, label in candidates:
        try:
            http_get(probe_url, proxy, timeout=12, retries=1)
            return proxy, label
        except Exception:
            continue
    return "", "全部候选都失败，勉强用直连"


def main():
    ap = argparse.ArgumentParser(description="下载社区图标库到本地挑选")
    ap.add_argument("source", nargs="?", default=DEFAULT_SRC, help="图标库 JSON 地址")
    ap.add_argument("--proxy", default="", help="如 http://192.168.2.100:7890（留空=自动探测）")
    ap.add_argument("--out", default=str(OUT), help="输出目录")
    ap.add_argument("--workers", type=int, default=8, help="并发数")
    ap.add_argument("--limit", type=int, default=0, help="只下前 N 个（调试用）")
    args = ap.parse_args()

    src = args.source
    # 允许直接传本地 json 文件名
    if not re.match(r"^https?://", src, re.I):
        p = Path(src)
        if not p.is_absolute():
            p = ROOT / src
        if not p.exists():
            print(f"找不到清单文件：{p}")
            return 1
        src = p.as_uri()
    print(f"拉取清单：{src}")
    if args.proxy:
        proxy, how = args.proxy, "命令行指定"
    elif re.match(r"^https?://", src, re.I):
        # 只有远程清单才需要代理探测；本地 file:// 探测没意义
        proxy, how = pick_proxy("")
    else:
        proxy, how = "", "本地清单，无需代理"
    print(f"代理：{how}" + (f"  ->  {proxy}" if proxy else "  ->  无"))
    raw = http_get(src, proxy or None)
    data = json.loads(raw.decode("utf-8"))
    icons = data.get("icons", [])
    print(f"源：{data.get('name','?')}  共 {len(icons)} 个图标")
    if args.limit:
        icons = icons[:args.limit]

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    # 关键：URL -> 落盘文件名的**持久映射**。
    # 没有它的话，重跑时 used 里已有同名文件，同一张图会被迫改名成
    # X-01.png / X-02.png …越堆越多（实测堆到 742 个垃圾文件）。
    prev = {}
    prev_idx = outdir / "_index.json"
    if prev_idx.exists():
        try:
            for it in json.loads(prev_idx.read_text(encoding="utf-8")).get("icons", []):
                if it.get("url") and it.get("file"):
                    prev[it["url"]] = it["file"]
        except Exception:
            prev = {}

    used = set()
    jobs, mapping = [], []
    for it in icons:
        url = it["url"]
        raw = url.rsplit("/", 1)[-1]
        if url in prev and (outdir / prev[url]).exists():
            fname = prev[url]          # 上次就是这么存的，沿用
        else:
            fname = safe_name(raw, used)
        used.add(fname)
        jobs.append((url, outdir / fname))
        mapping.append({"name": it["name"], "file": fname, "url": url})

    print(f"开始下载，并发 {args.workers} …\n")
    ok = fail = skip = 0
    errors = []

    # 图片下载失败的兜底代理链：先试当前选中的，再依次降级。
    # 清单可能是本地 file://（探测不出代理），所以必须留完整候选链。
    CANDS = ["", "http://192.168.2.100:7890", "http://127.0.0.1:7890"]
    FALLBACK = ([proxy] if proxy else []) + [p for p in CANDS if p != (proxy or "")]

    def work(job):
        url, path = job
        if path.exists() and path.stat().st_size > 0:
            return "skip", url, ""
        last = ""
        for cand in FALLBACK:
            try:
                body = http_get(url, cand or None, timeout=25, retries=1)
                if not body:
                    last = "空响应"
                    continue
                path.write_bytes(body)
                return "ok", url, ""
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
        return "fail", url, last

    with concurrent.futures.ThreadPoolExecutor(args.workers) as ex:
        for i, (status, url, msg) in enumerate(
                ex.map(work, jobs), 1):
            if status == "ok":
                ok += 1
            elif status == "skip":
                skip += 1
            else:
                fail += 1
                errors.append((url, msg))
            if i % 50 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)}  成功 {ok}  跳过 {skip}  失败 {fail}")

    (outdir / "_index.json").write_text(
        json.dumps({"source": src, "pack": data.get("name", ""),
                    "count": len(mapping), "icons": mapping},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n完成：成功 {ok}，跳过 {skip}，失败 {fail}")
    print(f"目录：{outdir}")
    if errors:
        print("\n失败清单：")
        for u, m in errors[:20]:
            print(f"  - {u.rsplit('/',1)[-1]}  {m}")
        if len(errors) > 20:
            print(f"  …… 还有 {len(errors)-20} 条")
        print("\n重跑本脚本即可，已下载的会自动跳过。")
    print("\n下一步：打开 挑选.html 点选你要的图标。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
