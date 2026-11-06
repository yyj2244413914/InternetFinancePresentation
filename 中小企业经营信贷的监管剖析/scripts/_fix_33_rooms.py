# -*- coding: utf-8 -*-
"""给 3.3 里新加的 3 个 markdown 格补 slide_type=subslide。"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "汇报_中小企业经营信贷的监管剖析.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))

targets = {
    "#### 第一部分：数据挖掘——只抓",
    "#### 样本构建与数据质量",
    "把镜头对准**中小企业自身**",
}
for c in nb["cells"]:
    s = "".join(c.get("source", [])).strip()
    if any(s.startswith(t) for t in targets) and c.get("cell_type") == "markdown":
        c.setdefault("metadata", {}).setdefault("slideshow", {})["slide_type"] = "subslide"
        print("已标注:", s.splitlines()[0][:40])

NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("done")
