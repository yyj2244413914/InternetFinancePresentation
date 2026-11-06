# -*- coding: utf-8 -*-
"""3.3 大修：删掉银行处罚分析（违规趋势/违规类型/SME专项/文本/大模型政策），
   只保留「企业侧数据挖掘 → 中小企业画像 → 特征工程/XGBoost/SHAP」。只动 3.3。"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "汇报_中小企业经营信贷的监管剖析.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))
cells = nb["cells"]

def src(c):
    return "".join(c.get("source", []))

def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text}

# 确认几个关键 cell 的当前位置
assert src(cells[23]).strip().startswith("### 3.3"), src(cells[23])[:40]
assert "企业侧" in src(cells[25]), src(cells[25])[:40]
assert "中小企业自身画像" in src(cells[43]), src(cells[43])[:40]
assert "sme = da.sme_profile()" in src(cells[45]), src(cells[45])[:40]
assert "第二部分" in src(cells[57]), src(cells[57])[:40]

INTRO = """#### 第一部分：数据挖掘——只抓"能用于违约识别"的有效数据

本示例只服务一个目标：**识别中小企业会不会违约**。所以数据挖掘只抓企业侧数据，
**不讨论银行处罚**（处罚对象是银行，不是中小企业）。

| 数据 | 来源 | 规模 | 用途 |
|---|---|---|---|
| 中小企业财务面板 | 东方财富 `datacenter`（实时抓取） | 679 家 × 约 6 年 | 特征：资产负债率、ROE、流动比率… |
| 违约标签 | 由面板构造（t+1 严格前视） | — | 标签：下一年资不抵债 / 亏损 |
| 数据质量 | 缺失率、覆盖年份 | — | 筛选可用样本 |
"""

QUALITY = """#### 样本构建与数据质量

- **样本**：新三板（含北交所）挂牌公司财务面板——我国公开数据中"中小企业"最直接的口径。
- **标签**：下一年度发生「资不抵债（资产负债率 ≥ 100%）」或「亏损（归母净利润 < 0）」即为困境（y=1）；
  **严格前视，只用 t+1 年信息**，避免特征—标签循环定义。
- **可用样本**：剔除关键特征缺失的观测后进入建模。
"""

PROFILE_DESC = """把镜头对准**中小企业自身**：它们的规模、盈利能力、债务水平、经营困境发生率。

**数据**：新三板（含北交所）挂牌公司财务面板——我国公开数据中"中小企业"最直接的口径。
**标签**：下一年度发生「资不抵债」或「亏损」即为经营困境。
"""

# 新的 3.3 = [3.3 header] + 数据挖掘说明 + 企业侧 + 数据质量 + 企业画像 + 第二部分及结论
new_33 = [
    cells[23],          # ### 3.3 ...
    md(INTRO),          # 第一部分：数据挖掘（只抓有效数据）
    cells[25],          # 企业侧：实时抓取中小企业财务面板
    md(QUALITY),        # 样本构建与数据质量
    cells[43],          # ### 中小企业自身画像
    md(PROFILE_DESC),   # 更新后的说明（去掉"前面用的是监管处罚数据"）
    cells[45],          # sme = da.sme_profile()
] + cells[57:73]        # #### 第二部分 + 样本/模型/评分卡/SHAP + 评估结论

new_cells = cells[:23] + new_33 + cells[73:]
nb["cells"] = new_cells
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"3.3 重构完成：{len(cells)} -> {len(new_cells)} cells")
print("保留的 3.3 结构：")
for i, c in enumerate(new_cells[23:len(new_cells) - 5], start=23):
    s = "".join(c.get("source", [])).strip()
    print(" ", i, c["cell_type"], "|", (s.splitlines()[0][:55] if s else "(empty)"))
