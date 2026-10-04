#!/usr/bin/env python3
"""生成 add-icons 的桌面快捷方式图标（icon-pack.ico）。

纯 Pillow 画，不依赖外部素材。深色圆角方块 + 几张彩色小卡片叠放，
一眼看出是「一包图标」。

    python make_shortcut_icon.py
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUT = Path(__file__).resolve().parent / "icon-pack.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]

BG = (32, 38, 52)        # 深蓝灰底
CARD = (255, 255, 255)
ACCENTS = [
    (94, 160, 255),      # 蓝
    (255, 148, 88),      # 橙
    (126, 217, 87),      # 绿
    (233, 90, 120),      # 红粉
]


def rounded(draw, box, r, fill):
    draw.rounded_rectangle(box, radius=r, fill=fill)


def render(px):
    S = px * 4# 超采样倍数，画完再缩
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 底：圆角方块
    m = int(S * 0.06)
    rounded(d, (m, m, S - m, S - m), int(S * 0.20), BG)

    # 四张错落的小卡片，每张内嵌一个彩色圆角块
    cw = int(S * 0.34)
    ch = int(S * 0.30)
    pos = [
        (int(S * 0.20), int(S * 0.20), 0),
        (int(S * 0.44), int(S * 0.17), 1),
        (int(S * 0.22), int(S * 0.50), 2),
        (int(S * 0.47), int(S * 0.47), 3),
    ]
    for (x, y, ai) in pos:
        rounded(d, (x, y, x + cw, y + ch), int(S * 0.055), CARD)
        pad = int(cw * 0.20)
        rounded(d, (x + pad, y + pad, x + cw - pad, y + ch - pad),
                int(S * 0.030), ACCENTS[ai])

    return img.resize((px, px), Image.LANCZOS)


def main():
    frames = [render(s) for s in SIZES]
    frames[-1].save(OUT, format="ICO",
                    sizes=[(s, s) for s in SIZES])
    # 顺手留一张 png 当参考图
    frames[-1].save(OUT.with_suffix(".png"))
    print(f"已生成 {OUT.name}  尺寸 {SIZES}")
    print(f"参考图 {OUT.with_suffix('.png').name}")


if __name__ == "__main__":
    main()