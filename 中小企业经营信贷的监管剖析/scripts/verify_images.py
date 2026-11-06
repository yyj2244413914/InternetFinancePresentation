# -*- coding: utf-8 -*-
"""验证 html 里图片的引用方式与可达性

nbconvert 导出 HTML 时可能把 markdown 里的本地图片重新内嵌成 base64，
本脚本把实际情况查清楚：是相对路径还是 base64、张数对不对、能否加载。
"""
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "汇报_放映版.slides.html"
PORT = 8767


def main() -> int:
    txt = HTML.read_text(encoding="utf-8", errors="ignore")
    rel = sorted(set(re.findall(r'src="(汇报材料/[^"]+)"', txt)))
    b64 = len(re.findall(r'data:image/(?:png|jpeg);base64', txt))
    imgs = len(re.findall(r"<img\b", txt))
    print(f"文件: {HTML.name}  {len(txt)/1024/1024:.2f} MB")
    print(f"  <img> 标签          : {imgs}")
    print(f"  相对路径引用        : {len(rel)} 种")
    print(f"  base64 内嵌         : {b64} 处")
    if rel:
        for r in rel[:6]:
            print(f"     {r}")
    # 目录里实际有多少张
    mat = ROOT / "汇报材料"
    files = sorted(p.name for p in mat.glob("*") if p.suffix.lower() in
                   (".png", ".jpg", ".jpeg"))
    print(f"  汇报材料 文件夹      : {len(files)} 张")
    miss = [f for f in files if f"汇报材料/{f}" not in rel] if rel else []
    if rel and miss:
        print(f"  ⚠️ 未被引用的图      : {len(miss)} 张 {miss[:5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
