# -*- coding: utf-8 -*-
"""恢复前段被误删的重复标题行（3.1/3.2/1.1/①/④），不动 3.3。"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "汇报_中小企业经营信贷的监管剖析.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))
cells = nb["cells"]

def src(c):
    return "".join(c.get("source", []))

# 每组的“源 cell（保留了标题）” → 需要补回标题的 cell
groups = [
    (3, [4, 5]),      # 1.1 研究背景与意义
    (8, [9]),         # ① 贷前调查
    (12, [13, 14]),   # ④ 贷后管理
    (16, [17, 18]),   # 3.1 信贷风险评估方法
    (19, [20, 21, 22]),  # 3.2 信贷风险度量模型
]

for src_idx, targets in groups:
    header = src(cells[src_idx]).strip().splitlines()[0].strip()
    for t in targets:
        s = src(cells[t])
        if s.strip().startswith(header):
            continue  # 已经有标题，不重复
        cells[t]["source"] = header + "\n\n" + s.lstrip("\n")
        print(f"恢复标题 [{t}] <- {header[:30]}")

nb["cells"] = cells
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("done, cells =", len(cells))
