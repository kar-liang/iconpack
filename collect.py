#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把挑选出来的图标收进 icons/，并按社区显示名重命名。

用法：
    python collect.py                    # 读 待挑选/已选.txt
    python collect.py --list 另一个.txt

为什么要重命名：
    社区库文件名和显示名经常不一致，比如文件是 DIYEmby-01.png、显示名是「Emby」。
    App 是按图标名精确匹配的，所以按**显示名**命名才好用。
    同名多图会自动加 -02/-03 后缀。

自动做的事：
    1. 复制到 icons/emby/ （想换目录用 --dest）
    2. 用显示名重命名，非法字符替换掉
    3. 打印一份「你的节点叫什么名字」的对照表，方便你去 App 里对号入座

不写 aliases.txt：同名变体（X-02/X-03）由 build.py 的 fold_variants() 自动折叠成别名。
要加**手写**别名（抹平大小写差异等）就自己往 aliases.txt 里加。
"""

import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def legal(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name or "icon"


def main():
    ap = argparse.ArgumentParser(description="把选中的图标收进 icons/")
    ap.add_argument("--list", default="待挑选/已选.txt", help="已选文件名清单")
    ap.add_argument("--src", default="待挑选", help="图标源目录")
    ap.add_argument("--dest", default="icons/emby", help="目标子目录")
    args = ap.parse_args()

    def p(x):
        q = Path(x)
        return q if q.is_absolute() else ROOT / q

    listfile, srcdir, destdir = p(args.list), p(args.src), p(args.dest)

    if not listfile.exists():
        print(f"找不到清单：{listfile}")
        print("先在 挑选.html 里点「导出选中」。")
        return 1
    if not srcdir.exists():
        print(f"找不到源目录：{srcdir}")
        return 1

    picked = [ln.strip() for ln in
              listfile.read_text(encoding="utf-8-sig").splitlines()
              if ln.strip() and not ln.strip().startswith("#")]
    if not picked:
        print("清单是空的。")
        return 1

    meta = {}
    idx = srcdir / "_index.json"
    if idx.exists():
        meta = json.loads(idx.read_text(encoding="utf-8"))
    by_file = {it.get("file"): it.get("name", "")
               for it in meta.get("icons", [])}

    destdir.mkdir(parents=True, exist_ok=True)

    # 重跑时先清掉「上一轮由本脚本生成的」文件，否则会无限叠加成
    # Emby-02 / Emby-03 / Emby-04… 靠 .collected 清单精确回溯，不误伤你手放的图。
    stamp = destdir / ".collected"
    if stamp.exists():
        for old in stamp.read_text(encoding="utf-8").splitlines():
            old = old.strip()
            if not old:
                continue
            f = destdir / old
            if f.is_file():
                f.unlink()
        print(f"清理上一轮 {len(stamp.read_text(encoding='utf-8').splitlines())} 个文件")

    used = {q.name for q in destdir.glob("*.png")}
    buckets = defaultdict(list)   # 显示名 -> [落盘文件名]
    copied, missing, renamed = [], [], 0

    for fname in picked:
        src = srcdir / fname
        if not src.exists():
            missing.append(fname)
            continue
        label = legal(by_file.get(fname) or Path(fname).stem)

        # 目标名冲突就加后缀；同名多图正是社区区分变体的方式
        target = f"{label}.png"
        if target in used:
            n = 2
            while f"{label}-{n:02d}.png" in used:
                n += 1
            target = f"{label}-{n:02d}.png"
        used.add(target)

        shutil.copy2(src, destdir / target)
        if target != fname:
            renamed += 1
        copied.append(target)
        buckets[label].append(target)

    # 记下本轮产物，供下次重跑时清理
    (destdir / ".collected").write_text(
        "\n".join(copied) + "\n", encoding="utf-8")

    # 别名**不写进 aliases.txt** —— build.py 的 fold_variants() 会在扫描阶段
    # 自动把 X-02/X-03 折叠成 X 的别名。早期版本在这里写自动段，结果：
    # 变体被折叠掉后 aliases.txt 里留着指向不存在图标的僵尸别名，白报一堆警。
    # 要给图标加**手写**别名（大小写差异等），自己往 aliases.txt 里加。

    print(f"收进 {destdir}：{len(copied)} 个"
          + (f"（{renamed} 个按社区显示名改了文件名）" if renamed else ""))
    if missing:
        print(f"跳过 {len(missing)} 个（源文件不存在）")
    variants = sum(len(f) - 1 for f in buckets.values() if len(f) > 1)
    if variants:
        print(f"同名变体 {variants} 个 —— build.py 会自动折叠成正式名的别名，不用管")

    print("\n下面这张表拿去 App 里对号入座 —— App 按图标名精确匹配：")
    print(f"{'图标名':<24} 文件")
    print("-" * 56)
    for label, files in sorted(buckets.items()):
        show = files[0] if len(files) == 1 else f"{files[0]} 等{len(files)}个"
        print(f"{label:<24} {show}")

    print("\n下一步：")
    print(f"  1. 检查一下 {destdir} 里的图（不够大的会告警）")
    print("  2. 跑 build.bat 生成图标包")
    return 0


if __name__ == "__main__":
    sys.exit(main())
