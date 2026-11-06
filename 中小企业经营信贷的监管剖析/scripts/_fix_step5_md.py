# -*- coding: utf-8 -*-
"""修正第五步 md 的标题匹配，写入「输出怎么看 + 特征含义」说明。"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "汇报_中小企业经营信贷的监管剖析.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))
cells = nb["cells"]

NEW_MD = """#### 第五步：XGBoost 建模

- **使用数据**：`data/processed/firm_panel.csv` → `dm.build_panel()`（特征 = t 年财务指标；标签 = t+1 是否困境，严格前视）。
- **处理方式**：剔除关键特征缺失过半的样本 → XGBoost 训练 → ROC / AUC / KS → 特征重要度 Top12。

**输出怎么看（这就是"风险评估"）**：

- 模型给每家企业输出一个**违约概率**（0~1）——这就是风险评分；
- **AUC≈0.96、KS≈0.82**：衡量"风险排序准不准"。AUC=0.5 等于瞎猜，越接近 1 越能把高风险企业排到前面；
- **特征重要度**：哪个财务指标对"判定困境"贡献最大，就是贷前调查最该盯的指标。

**特征代码对照**（图/表里的缩写是什么意思）：

| 代码 | 指标含义 |
|---|---|
| ROEJQ | 加权 ROE：每 1 元净资产赚多少（盈利能力） |
| XSJLL | 销售净利率：每 1 元收入最后剩多少净利润 |
| XSMLL | 销售毛利率：扣除成本后每 1 元收入剩多少 |
| ZCFZL | 资产负债率：总负债 ÷ 总资产（杠杆，越高越危险） |
| INTSTCOVRATE | 利息保障倍数：利润够付几倍利息（<1 就危险） |
| ZZCJLL / ROIC | 总资产净利率 / 投入资本回报率（资产赚钱效率） |
| TOAZZL | 总资产周转率：资产一年转几圈（运营效率） |
| ocf_to_liab | 经营现金流 ÷ 总负债（现金回笼能否覆盖债务） |
| x3_ebit_ta | X3：息税前利润 ÷ 总资产（Altman 盈利因子） |
| x2_re_ta | X2：留存收益 ÷ 总资产（多年积累的利润家底） |
| x5_sales_ta | X5：营业收入 ÷ 总资产（资产创收效率） |
| TA_YOYRATIO_PK | 总资产同比增速（扩张速度） |
| 营收/净利同比 | 收入、利润的增长速度 |
"""

for c in cells:
    s = "".join(c.get("source", []))
    if c.get("cell_type") == "markdown" and s.strip().startswith("#### 第五步"):
        c["source"] = NEW_MD
        print("第五步 md 已更新（含输出解读 + 特征对照表）")
        break

nb["cells"] = cells
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("done")
