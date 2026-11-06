# -*- coding: utf-8 -*-
"""预演自检：检查 notebook 的分页结构、输出完整性、离线可用性

用途：正式汇报前跑一次，30 秒内确认"能不能顺利放完"。
"""
import collections
import re
import sys
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "汇报_中小企业经营信贷的监管剖析.ipynb"
ANA = NB
SLIDES = ROOT / "汇报_中小企业经营信贷的监管剖析.slides.html"
HTML = ROOT / "汇报_中小企业经营信贷的监管剖析.html"
ASSETS = ROOT / "slides_assets"


def main() -> int:
    ok = True
    nb = nbformat.read(NB, as_version=4)

    print("=" * 66)
    print("1. 单元格与分页")
    print("=" * 66)
    types = collections.Counter(
        c.metadata.get("slideshow", {}).get("slide_type", "(未标注)") for c in nb.cells)
    for k, v in sorted(types.items()):
        print(f"   {k:<10} {v} 个")
    n_frag = types.get("fragment", 0)
    if n_frag:
        print(f"   ⚠️ 仍有 {n_frag} 个 fragment —— 会出现淡入白闪，建议改为 slide")
        ok = False
    else:
        print("   ✅ 无 fragment：一次翻页 = 一整页，不会闪跳")
    pages = sum(1 for c in nb.cells if c.cell_type in ("markdown", "code"))
    print(f"   放映总页数：{pages} 页")

    print()
    print("=" * 66)
    print("2. 执行结果完整性")
    print("=" * 66)
    errs = [(i, o.get("ename"), o.get("evalue"))
            for i, c in enumerate(nb.cells) if c.cell_type == "code"
            for o in c.get("outputs", []) if o.get("output_type") == "error"]
    if errs:
        ok = False
        print(f"   ❌ {len(errs)} 个 cell 报错")
        for e in errs[:5]:
            print("      cell", e[0], e[1], str(e[2])[:80])
    else:
        print("   ✅ 全部 cell 执行通过，无报错")

    n_img = sum(1 for c in nb.cells if "data:image/png;base64," in c.source)
    n_tab = sum(1 for c in nb.cells if "<table" in c.source)
    n_code_cell = sum(1 for c in nb.cells if c.cell_type == "code")
    n_codeblock = sum(1 for c in nb.cells
                      if c.cell_type == "markdown" and "```python" in c.source)
    n_md = sum(1 for c in nb.cells if c.cell_type == "markdown")
    print(f"   页型构成：markdown 页 {n_md}  真实代码 cell {n_code_cell}"
          f"（其中独立代码页 {n_codeblock} 个 markdown 代码块）")
    # 代码 cell 与结果分页的实现方式：CSS 隐藏代码 cell 的输入区
    html_slides = ROOT / (NB.stem + ".slides.html")
    hides = False
    if html_slides.exists():
        txt = html_slides.read_text(encoding="utf-8", errors="ignore")
        hides = "jp-CodeCell .jp-InputArea" in txt
    if n_code_cell and hides:
        print(f"   ✅ {n_code_cell} 个代码 cell 的输入区在放映时已隐藏 → 代码页/结果页分页成立")
    elif n_code_cell:
        print("   ⚠️ 存在代码 cell 但未检测到隐藏规则，放映时会出现代码+结果同页")
        ok = False
    else:
        print("   ✅ 无代码 cell（纯 markdown 放映稿）")
    empty = [i for i, c in enumerate(nb.cells)
             if c.cell_type == "code" and not c.get("outputs")]
    if empty:
        print(f"   ⚠️ 无任何输出的代码 cell：{empty}")
    else:
        print("   ✅ 每个证据 cell 都有输出（不会出现空白页）")

    print()
    print("=" * 66)
    print("3. 离线放映检查")
    print("=" * 66)
    for f in (SLIDES, HTML):
        if not f.exists():
            print(f"   ❌ 缺少 {f.name}（先跑 make_offline_html.py）")
            ok = False
            continue
        txt = f.read_text(encoding="utf-8", errors="ignore")
        left = len(re.findall(r'<(?:script[^>]*src|link[^>]*href)="https?://', txt))
        sec = txt.count("<section")
        flag = "✅ 无外链，可离线" if left == 0 else f"⚠️ 仍有 {left} 处外链"
        extra = f"，{sec} 页" if sec else ""
        print(f"   {f.name}: {flag}{extra}")
        if left:
            ok = False
    need = ["reveal.css", "reveal-simple.css", "jquery.min.js", "require.min.js"]
    miss = [n for n in need if not (ASSETS / n).exists()]
    if miss:
        print(f"   ❌ slides_assets 缺少：{miss}")
        ok = False
    else:
        print(f"   ✅ slides_assets 齐全（{len(need)} 个文件）")

    print()
    print("=" * 66)
    print("结论：" + ("✅ 可以正式放映" if ok else "⚠️ 有项目需要先修"))
    print("=" * 66)
    print("放映前 30 秒操作：")
    print("  · Jupyter 路线：打开 notebook → 左侧栏 Rise Slides → Present")
    print("  · 浏览器路线：双击 slides.html → 用鼠标控制条或 ←/→ 翻页")
    print("  · 讲解页与证据页交替：第 1 页讲解、第 2 页出图，依此类推")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
