# -*- coding: utf-8 -*-
"""在第四步（可视化）之后加回「困境 vs 健康」md + code。"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "汇报_中小企业经营信贷的监管剖析.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))
cells = nb["cells"]

def src(c):
    return "".join(c.get("source", []))

MD = """#### 困境 vs 健康：中小企业财务特征差在哪

把 679 家中小企业按下一年是否陷入困境分成两组，比较各财务指标的中位数，
并做 Mann-Whitney 检验——看"差"在**盈利与现金流**，而不是规模。
"""

CODE = '''# 困境 vs 健康：财务特征差在哪（企业侧）
sme = da.sme_profile()
g0 = sme[sme["distress"] == 0]
g1 = sme[sme["distress"] == 1]
items = [("ZCFZL", "资产负债率(%)"), ("LD", "流动比率"), ("XSJLL", "销售净利率(%)"),
         ("XSMLL", "销售毛利率(%)"), ("ROEJQ", "加权ROE(%)"),
         ("INTSTCOVRATE", "利息保障倍数"), ("TOAZZL", "总资产周转率"),
         ("ocf_to_liab", "经营现金流/总负债"), ("Z_score", "Altman Z′")]
rows = []
for col, cn in items:
    a, b = g0[col].dropna(), g1[col].dropna()
    if len(a) < 30 or len(b) < 30:
        continue
    p = stats.mannwhitneyu(a, b, alternative="two-sided").pvalue
    rows.append({"指标": cn, "健康组中位数": round(a.median(), 2),
                 "困境组中位数": round(b.median(), 2),
                 "差异": round(b.median() - a.median(), 2),
                 "p 值": f"{p:.2e}" if p < 1e-3 else f"{p:.3f}",
                 "是否显著": "***" if p < 0.01 else ("*" if p < 0.05 else "")})
cmp_tab = pd.DataFrame(rows)
display(cmp_tab.style.hide(axis="index"))

fig, ax = plt.subplots(figsize=(10, 4.4))
x = np.arange(len(cmp_tab))
ax.bar(x - 0.2, cmp_tab["健康组中位数"], 0.4, label="健康企业", color=C_MID, alpha=0.9)
ax.bar(x + 0.2, cmp_tab["困境组中位数"], 0.4, label="困境企业", color=C_ACCENT, alpha=0.9)
ax.set_xticks(x); ax.set_xticklabels(cmp_tab["指标"], rotation=22, ha="right", fontsize=9)
ax.set_ylabel("中位数")
ax.set_title("困境企业与健康企业的财务特征对比", fontsize=13)
ax.legend()
savefig(fig, "fig17_distress_compare"); plt.show()
'''

idx = next(i for i, c in enumerate(cells) if "fig18_sme_trend" in src(c))
md_cell = {"cell_type": "markdown", "metadata": {"slideshow": {"slide_type": "subslide"}}, "source": MD}
code_cell = {"cell_type": "code", "metadata": {"slideshow": {"slide_type": "subslide"}},
             "source": CODE, "outputs": [], "execution_count": None}
cells[idx + 1:idx + 1] = [md_cell, code_cell]
print(f"已插入「困境 vs 健康」到 [{idx+1}] md + [{idx+2}] code")

nb["cells"] = cells
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("done, cells =", len(cells))
