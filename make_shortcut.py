#!/usr/bin/env python3
"""创建桌面快捷方式（pywin32，不走受限的 COM 沙箱）。

    python make_shortcut.py

产物：桌面上的「添加图标.lnk」，双击即跑 add-icons.bat。
"""
from pathlib import Path

from win32com.client import Dispatch  # noqa: E402

ROOT = Path(__file__).resolve().parent
BAT = ROOT / "add-icons.bat"
ICO = ROOT / "icon-pack.ico"

# 桌面路径不能硬编码 Desktop —— 部分系统/配置下真实目录是 Documents\Desktop。
# win32com 有现成 API，优先用它；失败再退回逐个探测。
def desktop_dir() -> Path:
    try:
        import win32com.client.shell as shell
        return Path(shell.SHGetFolderPath(0, 0x10))     # 0x10 = CSIDL_DESKTOPDIRECTORY
    except Exception:
        for p in (Path.home() / "Desktop",
                  Path.home() / "OneDrive" / "Desktop",
                  Path.home() / "桌面"):
            if p.is_dir():
                return p
        raise SystemExit("[ERROR] 找不到桌面目录")


def main():
    if not BAT.is_file():
        raise SystemExit(f"[ERROR] 找不到 {BAT}")
    if not ICO.is_file():
        raise SystemExit(f"[ERROR] 找不到 {ICO}（先跑 make_shortcut_icon.py）")

    desk = desktop_dir()
    lnk = desk / "添加图标.lnk"

    ws = Dispatch("WScript.Shell")
    s = ws.CreateShortcut(str(lnk))
    s.Targetpath = str(BAT)
    s.WorkingDirectory = str(ROOT)
    s.IconLocation = str(ICO)
    s.Description = "Edit apps.txt then run: download + build + publish to GitHub"
    s.WindowStyle = 1                # SW_SHOWNORMAL
    s.Save()

    print(f"已创建桌面快捷方式：{lnk}")
    print(f"  指向  {BAT}")
    print(f"  图标  {ICO.name}")
    print(f"  大小  {lnk.stat().st_size} 字节")


if __name__ == "__main__":
    main()