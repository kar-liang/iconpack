#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载 iOS / iPadOS / macOS App 的官方高清图标。

用法：
    python fetch_ios_icon.py 微信 支付宝 网易云音乐
    python fetch_ios_icon.py --id 414478124
    python fetch_ios_icon.py --list apps.txt
    python fetch_ios_icon.py --id 414478124 --size 512
    python fetch_ios_icon.py --out icons/apps

不用装任何东西，纯标准库。
图标直连 itunes.apple.com，国内可用，不需要代理。
"""

import argparse
import concurrent.futures
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOOKUP = "https://itunes.apple.com/lookup"
SEARCH = "https://itunes.apple.com/search"


def _bind_console_encoding():
    """让 print 走当前控制台代码页（cmd 里中文否则是乱码）。

    本机代码页 936（GBK），而 Python 3.6+ 在 Windows 上 stdout 默认 UTF-8。
    这个脚本会打印中文 app 名（元气壁纸/ 微信 / 哔哩哔哩…），不绑就全乱码。
    **不要用 chcp 65001** —— 跟 GBK 打架，bat 解析行结构会崩。
    """
    for stream in (sys.stdout, sys.stderr):
        if "utf-8" in (getattr(stream, "encoding", "") or "").lower():
            try:
                stream.reconfigure(encoding="gbk", errors="replace")
            except Exception:
                pass


_bind_console_encoding()

# mzstatic 的图片 URL 靠后缀控制尺寸与格式：
#   512x512bb.jpg  -> 512 jpg（bb = 加边框，不想要）
#   1024x1024w.png -> 1024 无损 png 原图（w = 原图，无缩放）
#   0x0bb.jpg      -> 会 400，别用
SIZE_MAP = {
    1024: "1024x1024w.png",
    512: "512x512.png",
    256: "256x256.png",
    180: "180x180.png",
    120: "120x120.png",
}


def http_get(url, timeout=30, retries=3):
    # 显式空字典 = 屏蔽环境变量代理（空参会继承，是个隐蔽坑）
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        urllib.request.ProxyHandler({}))
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (iconpack)"})
            with opener.open(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            if i < retries - 1:
                time.sleep(1.0 * (i + 1))
    raise last


def http_json(url, timeout=30):
    return json.loads(http_get(url, timeout).decode("utf-8"))


def legal(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name or "icon"


def short_name(track_name, query=""):
    """
    App 全名常带一堆副标题：
        「网易云音乐-数亿音乐畅听」「腾讯视频-沈腾携《现在就出发4》爆笑回归」
    直接当图标名太长也太难看（App 里列表会被截断）。
    原则：优先用你输入的查询词作为图标名。
    """
    name = track_name
    # 你查「元气壁纸」而全名是「元气桌面壁纸-超高清壁纸主题小组件」→
    #   结果应该是「元气壁纸」（你查的词），不是「元气桌面壁纸」（全名的前缀段）
    # 原则：**优先用你输入的查询词**。它是你的意图，比 App 全名可靠。
    if query and len(query.strip()) >= 2:
        return query.strip()
    # 没给查询词（比如用 --id 查的）才从全名里截
    for sep in ("-", "－", "—", "–", "·", "|", "：", ":"):
        if sep in name:
            head = name.split(sep, 1)[0].strip()
            if len(head) >= 2:
                return head
    return name


def best_artwork(rec):
    """挑一张可用的原图 URL。优先 1024 无损 png。"""
    for key in ("artworkUrl512", "artworkUrl100", "artworkUrl60"):
        u = rec.get(key)
        if not u:
            continue
        # 把 /512x512bb.jpg 之类换成 /1024x1024w.png
        base = u.rsplit("/", 1)[0]
        return base + "/1024x1024w.png", u
    return None, None


def norm_title(t):
    """把 App 名归一化：去掉所有标点/空格/括号内容，只留可比字符。"""
    return re.sub(r"[\s\-—–·|｜:：()（）\[\]【】《》<>、,，.。'\"“”‘’/\\!！?？~～+＋&]+",
                  "", t or "").lower()


def risky_peers(query, got, cands):
    """
    判定这次选择是否有歧义，返回 (硬告警候选, 参考候选)。

    只在**一种**情况算硬告警：选中的 App 归一化后压根不以查询词开头。
        元气壁纸 → 选中「元气桌面壁纸」   硬告警
        人人视频 → 选中「人人追剧」       硬告警（App 改名了，可能是你要的）
    「部落冲突（Clash of Clans）」「夸克-AI旗舰应用」这类只是带副标题 → 不告警。

    精确同名、只是同系列还有别的 App（知乎/知乎盐选版、QQ/QQ音乐）
    归为**参考**，一行带过。早期版本把这些也算告警，29 个 App 报了 11 个，
    真正要看的「元气壁纸」被埋在中间 —— 噪音会让真告警被忽略。
    """
    qn, gn = norm_title(query), norm_title(got)
    if not qn or not gn:
        return list(cands), []
    if gn == qn:
        # 精确命中，一票通过。同系列兄弟 App 只作参考。
        return [], list(cands)
    if gn.startswith(qn):
        # 带副标题的同一个 App，安全。
        return [], list(cands)
    return list(cands), []


def parse_list_file(path):
    """
    解析 apps.txt，每行支持四种写法：

        微信                      # 按名字搜（靠相关度，可能搜错）
        元气壁纸 = 6448843762      # 钉死 ID（**同名竞争时必须这么写**）
        卡通农场 = 506627515@us    # 钉死 ID **并指定区号**（国际版必须这么写）
        # 整行注释                 # 开头 # 的是注释

    返回 [(查询键, app_id 或 "", country 或 "")]；查询键就是最终的图标名。
    """
    out = []
    for ln in path.read_text(encoding="utf-8-sig").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        m = re.match(r"^(.*?)\s*[=＝]\s*(\d+)\s*(?:@\s*([a-zA-Z]{2}))?\s*$", ln)
        if m:
            nm = m.group(1).strip()
            if nm:
                out.append((nm, m.group(2), (m.group(3) or "").lower()))
        else:
            out.append((ln, "", ""))
    return out



def lookup_by_id(app_id, country="cn"):
    url = f"{LOOKUP}?id={urllib.parse.quote(str(app_id))}&country={country}&entity=software"
    d = http_json(url)
    return d.get("results", [])


def search_by_name(name, country="cn", limit=12):
    """
    limit 给足（默认 12）。
    实测教训：查「元气壁纸」时正确答案是
      [0] 元气桌面壁纸-超高清壁纸主题小组件   <- 另一个 App，排第一
      [1] 元气壁纸-海量超清壁纸下载         <- 用户要的，排第二
    只取前几条会拿错，而且光看图标名完全看不出来。
    """
    q = urllib.parse.quote(name)
    url = f"{SEARCH}?term={q}&country={country}&entity=software&limit={limit}"
    d = http_json(url)
    return d.get("results", [])


def pick_app(results, exact=None):
    """
    从搜索结果里挑最可能的那个。

    ⚠️ 关键：iTunes Search API 的 results **本身就是按相关度降序排的**，
    别自作聪明重排。之前我加了"名字最短优先"的评分，结果全错：
    支付宝→抖音、网易云音乐→QQ音乐、腾讯视频→优酷。

    ⚠️ 但 [0] 也不一定是你要的。「元气壁纸」查出来是：
      [0] 元气桌面壁纸-超高清壁纸主题小组件   <- 另一个 App
      [1] 元气壁纸-海量超清壁纸下载         <- 用户要的
    这种情况（查询词不是 [0] 的精确同名）必须警告并列出候选，
    否则你拿到的是别人的图标，而且光看图标名发现不了。
    """
    if not results:
        return None
    if exact:
        # 优先精确同名（可能不在 [0]）
        for r in results:
            if r.get("trackName", "").lower() == exact.lower():
                return r
        # 没有精确同名：返回 [0] 并带上候选，交给调用方警告
        return results[0]
    return results[0]


def save_icon(url, dest, size):
    suffix = SIZE_MAP.get(size, SIZE_MAP[1024])
    full = url.rsplit("/", 1)[0] + "/" + suffix
    body = http_get(full, timeout=40)
    if not body or len(body) < 200:
        raise RuntimeError("下载内容异常")
    dest.write_bytes(body)
    return len(body), suffix


def png_size(path):
    try:
        b = path.read_bytes()[:24]
        if b[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        import struct
        return struct.unpack(">II", b[16:24])
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="下载 iOS App 官方高清图标")
    ap.add_argument("names", nargs="*", help="App 名称（中文即可）")
    ap.add_argument("--id", action="append", default=[],
                    help="App Store ID（可多个），比名字准")
    ap.add_argument("--list", default="", help="从文本文件读名字，一行一个")
    ap.add_argument("--out", default="icons/apps", help="输出目录")
    ap.add_argument("--size", type=int, default=1024, choices=list(SIZE_MAP),
                    help="图标尺寸，默认 1024 原图")
    ap.add_argument("--country", default="cn", help="区号，默认 cn")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true", help="只查不下载")
    args = ap.parse_args()

    names = list(args.names)
    pinned = []       # (图标名, app_id, country) —— apps.txt 里用「名字 = id[@区号]」钉死的
    if args.list:
        p = Path(args.list)
        if not p.is_absolute():
            p = ROOT / args.list
        if not p.exists():
            print(f"找不到清单：{p}")
            return 1
        for row in parse_list_file(p):
            nm, aid, cc = (row + ("", ""))[:3] if len(row) == 2 else row
            if aid:
                pinned.append((nm, aid, cc))
            else:
                names.append(nm)

    if not names and not args.id and not pinned:
        print(__doc__)
        return 1

    outdir = Path(args.out)
    if not outdir.is_absolute():
        outdir = ROOT / outdir

    # ---- 先解析出所有目标 App
    print("查询中 …\n")
    targets = []   # (查询键, 记录)  查询键为空表示「用 App 全名」
    warnings = []  # 区号回退之类的小提示
    for nm, aid, cc in pinned:
        ctry = cc or args.country
        try:
            rs = lookup_by_id(aid, ctry)
            if not rs and not cc:
                # 钉了 ID 但当前区查不到 → 多半是「国际版在国内区下架」
                # （实测：Hay Day 国际版 id=506627515 在 cn 区查不到，搜 us 区才有）
                # 自动回退扫一圈常见区，比让用户手填区号省事。
                for alt in ("us", "sg", "hk", "jp", "de"):
                    try:
                        rs = lookup_by_id(aid, alt)
                    except Exception:
                        continue
                    if rs:
                        ctry = alt
                        warnings.append(f"{nm} (id={aid}) 在 {args.country} 区查不到，"
                                        f"已自动改用 {alt} 区")
                        break
            if not rs:
                print(f"  [跳过] {nm} (id={aid}, {ctry}) 查不到 —— "
                      f"App 可能在这个区下架，或 ID 写错了")
                continue
            targets.append((nm, rs[0]))
        except Exception as e:
            print(f"  [错误] {nm} id={aid}  {type(e).__name__}: {e}")
    for aid in args.id:
        try:
            rs = lookup_by_id(aid, args.country)
            if rs:
                targets.append((f"id:{aid}", rs[0]))
            else:
                print(f"  [跳过] id={aid} 查不到")
        except Exception as e:
            print(f"  [错误] id={aid}  {type(e).__name__}: {e}")

    hard, soft = [], []   # 硬告警 / 参考提示
    for nm in names:
        try:
            rs = search_by_name(nm, args.country)
            rec = pick_app(rs, exact=nm)
            if rec:
                targets.append((nm, rec))
                full = rec.get("trackName", "")
                # 只看「归一化后同样以查询词开头」的候选，其他都是噪音。
                # 必须按 trackId 排除选中的那条 —— 实测 115 会把「115」自己
                # 列进候选，打出 "115 -> 115、115管理"，看着像个 bug。
                qn = norm_title(nm)
                tid = rec.get("trackId")
                near = [r for r in rs[1:]
                        if r.get("trackName")
                        and r.get("trackId") != tid
                        and norm_title(r.get("trackName", "")).startswith(qn)]
                a, b = risky_peers(nm, full, near)
                if a:
                    hard.append((nm, full, a))
                elif b:
                    soft.append((nm, b))
            else:
                print(f"  [跳过] {nm} 搜不到")
        except Exception as e:
            print(f"  [错误] {nm}  {type(e).__name__}: {e}")

    if not targets:
        print("没解析到任何 App。")
        return 1

    print(f"{'查询':<22} {'App 名':<20} {'开发者':<20} 图标名")
    print("-" * 84)
    plan = []
    for key, rec in targets:
        art, _ = best_artwork(rec)
        if not art:
            print(f"  {key:<22} {rec.get('trackName','?')[:18]:<20} (无图标)")
            continue
        q = "" if key.startswith("id:") else key
        nm = legal(short_name(rec.get("trackName", "icon"), q))
        print(f"  {key:<22} {rec.get('trackName','?')[:18]:<20} "
              f"{rec.get('artistName','?')[:18]:<20} {nm}.png")
        plan.append((nm, art, rec))

    if warnings:
        print("ℹ️  " + "\nℹ️  ".join(warnings))
        print()

    if hard:
        print()
        print("=" * 84)
        print("❌  以下几项很可能下错了 App（选中的跟你的查询词不是一回事）")
        print("=" * 84)
        for q, got, near in hard:
            print(f"  你填的: {q}")
            print(f"  将下载: {got}")
            for r in near[:4]:
                print(f"     候选: {r.get('trackName')}  "
                      f"[{r.get('artistName','')[:18]}]  id={r.get('trackId')}")
            print()
        print("  改 apps.txt 那行，钉死 ID 即可（格式：名字 = 6448843762）：")
        print("    python fetch_ios_icon.py --id <上面的id> --out icons/apps")
        print("=" * 84)
        print()

    if soft:
        print("ℹ️  同系列还有这些 App（已经匹配对了，只是让你知道有别的版本）：")
        for q, cands in soft:
            names_ = "、".join(r.get("trackName", "")[:16] for r in cands[:4])
            print(f"     {q}  ->  {names_}")
        print()

    if args.dry_run:
        print("--dry-run，未下载。去掉这个参数就下。")
        return 0
    if not plan:
        return 1

    outdir.mkdir(parents=True, exist_ok=True)
    print(f"\n下载 {len(plan)} 个，尺寸 {args.size}，并发 {args.workers} …\n")

    ok, fail, skip = 0, [], 0
    manifest = []

    def work(item):
        nm, art, rec = item
        dest = outdir / f"{nm}.png"
        if dest.exists() and dest.stat().st_size > 0:
            return "skip", nm, rec, dest
        for attempt in range(2):
            try:
                nbytes, suffix = save_icon(art, dest, args.size)
                return "ok", nm, rec, dest
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                time.sleep(0.8)
        return "fail", nm, rec, err

    with concurrent.futures.ThreadPoolExecutor(args.workers) as ex:
        for res in ex.map(work, plan):
            status, nm, rec, extra = res
            if status == "ok":
                ok += 1
                size = png_size(extra)
                manifest.append({"name": nm, "file": f"{nm}.png",
                                 "bundleId": rec.get("bundleId"),
                                 "appId": rec.get("trackId"),
                                 "artist": rec.get("artistName"),
                                 "size": size})
                print(f"  [OK] {nm:<24} {size[0] if size else '?'}  "
                      f"{extra.stat().st_size/1024:.0f}KB")
            elif status == "skip":
                skip += 1
                size = png_size(extra)
                manifest.append({"name": nm, "file": f"{nm}.png",
                                 "bundleId": rec.get("bundleId"),
                                 "appId": rec.get("trackId"),
                                 "artist": rec.get("artistName"),
                                 "size": size})
                print(f"  [跳过] {nm:<22} 已存在")
            else:
                fail.append((nm, extra))
                print(f"  [失败] {nm:<22} {extra}")

    (outdir / "_ios_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n完成：成功 {ok}，跳过 {skip}，失败 {len(fail)}")
    print(f"目录：{outdir}")
    if fail:
        print("\n失败清单（重跑本脚本即可，已下载的会跳过）：")
        for nm, e in fail:
            print(f"  - {nm}: {e}")
    print("\n下一步：跑 build.bat 生成图标包。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
