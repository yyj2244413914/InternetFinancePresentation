# -*- coding: utf-8 -*-
"""校验放映版：页数、每页内容构成、是否零代码、图片是否内嵌"""
import nbformat
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
nb = nbformat.read(ROOT / "汇报_放映版.ipynb", as_version=4)

kinds = Counter()
print("页 | 类型 | 内容构成")
print("-" * 74)
for i, c in enumerate(nb.cells, 1):
    src = c.source
    if c.cell_type == "code":
        kinds["代码页(不应存在)"] += 1
        tag = "代码!"
    elif "data:image/png;base64," in src:
        kinds["图页"] += 1
        tag = "图"
    elif "<table" in src:
        kinds["表页"] += 1
        tag = "表"
    else:
        kinds["讲解页"] += 1
        tag = "讲解"
    has_img = "data:image/png;base64," in src
    has_tab = "<table" in src
    has_txt = len(src) > 60 and not has_img
    flags = []
    if has_txt:
        flags.append("文字")
    if has_img:
        flags.append("图")
    if has_tab:
        flags.append("表")
    if len(flags) > 1 and not ("文字" in flags and "图" not in flags and "表" not in flags):
        pass
    title = ""
    for line in src.splitlines():
        line = line.strip()
        if line.startswith("#"):
            title = line.lstrip("# ").strip()
            break
    if not title:
        title = "(图表页)" if (has_img or has_tab) else src.strip().splitlines()[0][:40]
    print(f"{i:>2} | {tag:<4} | {'+'.join(flags) or '-':<8} {title[:46]}")

print("-" * 74)
print("统计：", dict(kinds))
print("总页数：", len(nb.cells))

multi = []
for i, c in enumerate(nb.cells, 1):
    s = c.source
    if "data:image/png;base64," in s and "<table" in s:
        multi.append(i)
print("图+表混在一页的页码：", multi or "无 ✅")
