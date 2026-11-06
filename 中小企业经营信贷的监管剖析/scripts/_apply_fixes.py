# -*- coding: utf-8 -*-
"""按用户要求修 6 处：结论数字、重复标题、可视化一改名、第一部分改名、困境vs健康移位。"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "汇报_中小企业经营信贷的监管剖析.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))
cells = nb["cells"]

def src(c):
    return "".join(c.get("source", []))

log = []

# ---------- 1) 去重：每段只保留第一个标题 ----------
groups = [
    ("### 1.1 研究背景与意义", [3, 4, 5]),
    ("#### ① 贷前调查", [8, 9]),
    ("#### ④ 贷后管理", [12, 13, 14]),
    ("### 3.1 信贷风险评估方法", [16, 17, 18]),
    ("### 3.2 信贷风险度量模型", [19, 20, 21, 22]),
]
for prefix, idxs in groups:
    for i in idxs[1:]:
        s = src(cells[i])
        lines = s.splitlines()
        removed = False
        for j, ln in enumerate(lines):
            if ln.strip():
                if ln.strip().startswith(prefix):
                    del lines[j]
                    removed = True
                break
        if removed:
            cells[i]["source"] = "\n".join(lines).lstrip("\n")
            log.append(f"去重标题 [{i}] {prefix}")

# ---------- 2) 第一部分标题改名（cell 23）+ 删除重复空单元格（cell 24） ----------
for c in cells:
    s = src(c)
    if s.strip().startswith("### 3.3 大数据与人工智能时代"):
        c["source"] = s.replace(
            "#### 第一部分：基于大数据技术的数据挖掘",
            "#### 第一部分：基于大数据技术的数据采集与可视化")
        log.append("第一部分标题改名 -> 数据采集与可视化")

drop_idx = None
for i, c in enumerate(cells):
    s = src(c).strip()
    if s.startswith("#### 第一部分：基于大数据技术的数据挖掘") and len(s.splitlines()) <= 2:
        drop_idx = i
        break
if drop_idx is not None:
    del cells[drop_idx]
    log.append(f"删除重复的第一部分空标题 cell [{drop_idx}]")

# ---------- 3) 结果可视化一改名 ----------
for c in cells:
    s = src(c)
    if "结果可视化一：监管处罚的整体图谱" in s:
        c["source"] = s.replace("结果可视化一：监管处罚的整体图谱",
                                "结果可视化一：监管处罚图谱与中小企业画像")
        log.append("结果可视化一改名")

# ---------- 4) 结论数字与模型名对齐（0.90 -> 0.957 / GBDT -> XGBoost） ----------
for c in cells:
    s = src(c)
    orig = s
    s = s.replace("机器学习（GBDT）0.90", "机器学习（XGBoost）0.957")
    s = s.replace("Z′（AUC≈0.66）→ 评分卡（0.84）→ 机器学习（0.90）",
                  "Z′（AUC≈0.66）→ 评分卡（0.84）→ 机器学习（XGBoost，0.957）")
    if s != orig:
        c["source"] = s
        log.append("结论数字更新 0.90 -> 0.957")

# ---------- 5) 把「困境vs健康」挪到「三个模型」之后、评分卡之前 ----------
md_idx = None
for i, c in enumerate(cells):
    if src(c).strip().startswith("### 困境企业 vs 健康企业"):
        md_idx = i
        break
if md_idx is not None and md_idx + 1 < len(cells):
    pair = [cells[md_idx], cells[md_idx + 1]]
    del cells[md_idx:md_idx + 2]
    # 找到 zscore 那个 cell（含 zscore_label）
    zidx = None
    for i, c in enumerate(cells):
        if "zscore_label" in src(c):
            zidx = i
            break
    if zidx is not None:
        cells[zidx + 1:zidx + 1] = pair
        log.append(f"困境vs健康 移到 zscore cell [{zidx}] 之后")

nb["cells"] = cells
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"完成，总 cells = {len(cells)}")
for x in log:
    print(" ·", x)
