# -*- coding: utf-8 -*-
"""第五步：md 里解释 XGBoost 输出怎么读 + 特征含义；code 里加一张「代码→含义」表。"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "汇报_中小企业经营信贷的监管剖析.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))
cells = nb["cells"]

def src(c):
    return "".join(c.get("source", []))

NEW_MD = """#### 第五步：只用 XGBoost 建模

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

MEANING_BLOCK = '''

FEAT_MEANING = {
    "ROEJQ": "加权ROE：每1元净资产赚多少", "XSJLL": "销售净利率：收入里剩多少净利润",
    "XSMLL": "销售毛利率：扣除成本后剩多少", "ZCFZL": "资产负债率：负债/总资产（杠杆）",
    "INTSTCOVRATE": "利息保障倍数：利润够付几倍利息", "ZZCJLL": "总资产净利率：资产赚钱效率",
    "ROIC": "投入资本回报率", "TOAZZL": "总资产周转率：资产一年转几圈",
    "ocf_to_liab": "经营现金流/总负债", "XJLLB": "现金流量比率",
    "x3_ebit_ta": "X3：息税前利润/总资产", "x2_re_ta": "X2：留存收益/总资产",
    "x5_sales_ta": "X5：营业收入/总资产", "x1_wc_ta": "X1：营运资金/总资产",
    "x4_equity_tl": "X4：账面权益/总负债", "TA_YOYRATIO_PK": "总资产同比增速",
    "TOTALOPERATEREVETZ": "营收同比增速", "PARENTNETPROFITTZ": "净利同比增速",
    "YSZKZZL": "应收账款周转率", "CHZZL": "存货周转率", "log_assets": "总资产对数（规模）",
}

imp_tab = pd.DataFrame({
    "代码": top.index,
    "指标含义": [FEAT_MEANING.get(k, dm.FEATURE_CN.get(k, k)) for k in top.index],
    "重要度": top.values,
}).sort_values("重要度", ascending=False)
display(imp_tab.style.format({"重要度": "{:.4f}"}).hide(axis="index"))
'''

for c in cells:
    s = src(c)
    if s.strip().startswith("#### 第五步：只用 XGBoost 建模"):
        c["source"] = NEW_MD
        print("第五步 md 已更新")
    if "fig15_imp" in s:
        # 在 savefig(fig, "fig15_imp") 那行之后加含义表
        c["source"] = s.replace('savefig(fig, "fig15_imp"); plt.show()',
                                'savefig(fig, "fig15_imp"); plt.show()' + MEANING_BLOCK)
        print("第五步 code 已加含义表")

nb["cells"] = cells
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("done")
