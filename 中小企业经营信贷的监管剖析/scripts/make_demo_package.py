# -*- coding: utf-8 -*-
"""一键生成最小演示包：slides.html + slides_assets + README，放到上级目录。"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT.parent / "中小企业信贷汇报_演示版"

if DEST.exists():
    shutil.rmtree(DEST)
DEST.mkdir(parents=True, exist_ok=True)

files = ["汇报_中小企业经营信贷的监管剖析.slides.html", "README_放映说明.md"]
for f in files:
    src = ROOT / f
    if src.exists():
        shutil.copy2(src, DEST / f)
        print(f"  copy: {f}")
shutil.copytree(ROOT / "slides_assets", DEST / "slides_assets")
print("  copy: slides_assets/ (6 files)")

print(f"\n演示包已生成: {DEST}")
print("  拷走这个文件夹即可放映（双击 slides.html）")
