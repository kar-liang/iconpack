#!/usr/bin/env python3
"""一键发布：读 iconpack.conf.json -> build -> git 提交推送 -> 打印订阅链接。

add-icons.bat 只调这个脚本。bat 必须是纯 ASCII（本机代码页 936），
所以所有中文配置都放在 iconpack.conf.json 里由本脚本读取。

用法：
    python publish.py            # build + 提交 + 推送
    python publish.py --check    # 只校验，不推送（看线上和本地是否一致）
    python publish.py --no-push  # 只 build，不推
"""
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONF = ROOT / "iconpack.conf.json"
PY = sys.executable


def load_conf():
    if not CONF.is_file():
        sys.exit(f"[ERROR] 找不到配置文件：{CONF}")
    try:
        return json.loads(CONF.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        sys.exit(f"[ERROR] iconpack.conf.json 格式错了（第 {e.lineno} 行）：{e.msg}")


def run(cmd, **kw):
    """跑一条命令，打印它，失败抛 CalledProcessError。"""
    printable = " ".join(str(c) for c in cmd)
    print(f"\n$ {printable}\n")
    return subprocess.run([str(c) for c in cmd], cwd=ROOT, **kw)


def build(conf):
    """跑 build.py，--strict 让重名等告警直接失败。"""
    cmd = [
        PY, ROOT / "build.py",
        "--base", conf["base_url"],
        "--name", conf.get("pack_name", "我的图标包"),
        "--strict",
    ]
    if conf.get("pack_description"):
        cmd += ["--description", conf["pack_description"]]
    return run(cmd).returncode


def git(*args):
    return run(["git", *args], capture_output=True, text=True)


def has_staged_changes():
    r = git("diff", "--cached", "--quiet")
    # returncode 0 = 没变化，1 = 有变化
    return r.returncode != 0


def publish(conf):
    branch = conf.get("branch", "master")
    repo = conf.get("repo", "kar-liang/iconpack")

    print("\n" + "=" * 60)
    print("  提交并推送")
    print("=" * 60)

    git("add", "-A")
    if not has_staged_changes():
        print("\n没有文件变化，跳过推送（本地包已是最新）。")
        return 0

    r = git("commit", "-q", "-m", "update icons")
    if r.returncode != 0:
        print("[ERROR] git commit 失败：\n" + (r.stderr or r.stdout))
        return 1

    print(f"\n$ git push origin {branch}\n")
    r = run(["git", "push", "origin", branch], capture_output=True, text=True)
    if r.returncode != 0:
        print("[ERROR] git push 失败：\n" + (r.stderr or r.stdout))
        print("文件都在本地，没丢。常见原因：没登录 —— 跑  gh auth login")
        return 1

    print(f"\n已推送到 https://github.com/{repo} 的 {branch} 分支。")
    return 0


def verify(conf):
    """联网核对：线上的 icons.json 引用到的文件是不是都在仓库里。"""
    repo = conf.get("repo", "kar-liang/iconpack")
    branch = conf.get("branch", "master")
    marker = conf["base_url"].split("/master/")[-1].strip("/") + "/"

    print("\n" + "=" * 60)
    print("  联网核对线上")
    print("=" * 60)

    api = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(urllib.request.Request(api, headers={
                "User-Agent": "iconpack-verify"}), timeout=30) as resp:
            tree = json.load(resp)
    except Exception as e:
        print(f"[WARN] 拿不到线上文件树（{e}）—— 跳过联网核对。")
        print("       常见原因：没网/ 被墙 / 仓库是私有的。")
        return None

    remote = {t["path"] for t in tree.get("tree", [])
              if t["path"].startswith("icons/") and t["path"].endswith(".png")}
    if not remote:
        print("[WARN] 线上没扫到 icons/ 下的 PNG，跳过核对。")
        return None

    local_json = ROOT / "dist" / "icons.json"
    if not local_json.is_file():
        print("[ERROR] 本地 dist/icons.json 不存在，先 build。")
        return 1
    entries = json.loads(local_json.read_text(encoding="utf-8"))["icons"]

    missing = []
    for it in entries:
        if marker not in it["url"]:
            continue
        rel = "icons/" + urllib.parse.unquote(it["url"].split(marker, 1)[1])
        if rel not in remote:
            missing.append((it["name"], rel))

    print(f"\n本地 {len(entries)} 条 | 线上 icons/ 下 {len(remote)} 个 PNG")
    if missing:
        print(f"\n[FAIL] 有 {len(missing)} 条在线上找不到对应文件：")
        for n, r in missing:
            print(f"  - {n}  ->  {r}")
        print("\n这通常是 CDN 缓存没刷新，等几分钟再验；")
        print("若持续存在，检查 base_url 末尾有没有 /icons 这一层。")
        return 1
    print("\n[OK] 全部对得上，零缺失。")
    return 0


def show_links(conf):
    repo = conf.get("repo", "kar-liang/iconpack")
    branch = conf.get("branch", "master")
    raw = f"https://raw.githubusercontent.com/{repo}/{branch}"
    print("\n" + "=" * 60)
    print("  订阅 / 导入链接")
    print("=" * 60)
    print(f"\n  Loon        {raw}/dist/loon-import.html")
    print(f"  SenPlayer   {raw}/dist/senplayer-import.html")
    print(f"  图标包本体  {raw}/dist/icons.json\n")


def main():
    conf = load_conf()

    print("=" * 60)
    print("  图标包一键发布")
    print("=" * 60)
    print(f"\n  包名  {conf.get('pack_name')}")
    print(f"  地址  {conf['base_url']}")

    if "--check" in sys.argv:
        return verify(conf) or 0

    rc = build(conf)
    if rc != 0:
        print("\n" + "=" * 60)
        print("  build 失败 —— 没有推送任何东西")
        print("=" * 60)
        print("\n最常见原因是重名：两个图标同名会直接报错。")
        print("看上面输出里点名的那两个文件，把其中一个改名再跑一次。")
        return rc

    if "--no-push" in sys.argv:
        print("\n已按要求跳过推送。")
        show_links(conf)
        return 0

    rc = publish(conf)
    if rc != 0:
        return rc

    verify(conf)
    show_links(conf)
    print("  手机上重新导入一次 Loon / SenPlayer 就能看到新图标。\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())