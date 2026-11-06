# -*- coding: utf-8 -*-
"""
build_notebook —— 生成汇报用 Jupyter Notebook
===========================================
设计要点
  · 一个 slide = 1 个 markdown（讲解词/论点）+ 1 个 code（证据：图/表）
  · markdown cell 承担 PPT 的作用：标题、论点、口径说明
  · code cell 负责出图出表，并用 display(Markdown(...)) 现场生成带真实数字的结论
    —— 这样数据更新后结论自动同步，不会出现"图文不符"
  · 每个 cell 都标注 slideshow 类型（Slide / Fragment / Skip），
    需要正式幻灯片时一条命令即可：jupyter nbconvert xx.ipynb --to slides --post serve
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "汇报_中小企业经营信贷的监管剖析.ipynb"

BOOT = r'''import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, r"E:\互联网金融\复现项目\src")
from plot_style import setup, savefig, annotate_bars, PALETTE, C_MAIN, C_ACCENT, C_MID, C_LIGHT
setup()
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from scipy import stats
from IPython.display import display, Markdown
pd.set_option("display.max_columns", 60)
pd.set_option("display.width", 160)
pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
import data_access as da
print("环境就绪")'''


cells: list[tuple[str, str]] = []
md = lambda s: cells.append(("md", s))       # noqa: E731
code = lambda s: cells.append(("code", s))   # noqa: E731

# ==================================================================== 0 引导
md(r"""
<div style="text-align:center;padding:40px 0 10px 0">

# 中小企业经营信贷的监管剖析
### —— 基于 3.7 万条监管处罚记录的实证复现

<br>

**事后暴露 · 损失计量 · 事前防范**

<br>

<div style="color:#666;font-size:14px">
数据来源：国家金融监督管理总局行政处罚信息公示（2022–2026）<br>
方法：违规图谱 · 操作风险损失分布法（LDA）· 违约识别模型
</div>
</div>
""")
code(BOOT)

# ==================================================================== 1 路线
md(r"""
<div style="background:#f0f7ff;border-left:4px solid #1f4e79;padding:12px 16px;border-radius:4px">

**本次汇报不讲"应该怎么管"，只讲"监管实际抓到了什么、代价有多大、能否事前识别"。**

</div>

### 三段式逻辑：一条监管闭环

| 环节 | 问题 | 本汇报的回答 |
|---|---|---|
| **① 事后暴露** | 监管实际抓到了哪些违规？ | 3.7 万条处罚记录 → 违规图谱 |
| **② 损失计量** | 这些违规让市场付了多少代价？监管资本够不够？ | 损失分布法（LDA）→ 99.9% VaR vs 监管资本 |
| **③ 事前防范** | 能否在放款前识别风险企业？ | Z-score / 评分卡 / 机器学习 |

**为什么这样排列**：处罚是监管发现问题后的既定事实（无需预测，可直接观测）；
损失计量把"违规"翻译成"钱"；事前防范才是银行真正能改善的环节。
""")
code(r'''
import matplotlib.patches as mpatches
fig, ax = plt.subplots(figsize=(11, 3.4))
ax.set_xlim(0, 10); ax.set_ylim(0, 3); ax.axis("off")
boxes = [("① 事后暴露\n违规图谱", 1.6, "#1f4e79", "处罚数据 3.7 万条"),
         ("② 损失计量\n操作风险 LDA", 5.0, "#2e75b6", "VaR / ES vs 监管资本"),
         ("③ 事前防范\n违约识别", 8.4, "#c00000", "评分卡 / 机器学习")]
for txt, x, color, sub in boxes:
    ax.add_patch(mpatches.FancyBboxPatch((x-1.35, 1.25), 2.7, 1.0,
                 boxstyle="round,pad=0.06", fc=color, ec="none", alpha=0.92))
    ax.text(x, 1.75, txt, ha="center", va="center", color="white",
            fontsize=13, fontweight="bold", linespacing=1.6)
    ax.text(x, 0.85, sub, ha="center", va="center", color="#444", fontsize=10)
for x0 in (3.0, 6.4):
    ax.annotate("", xy=(x0+0.45, 1.75), xytext=(x0, 1.75),
                arrowprops=dict(arrowstyle="-|>", color="#888", lw=2.2))
ax.text(5.0, 0.25, "监管视角：已有事实 → 量化代价 → 事前干预",
        ha="center", fontsize=10.5, color="#666", style="italic")
ax.set_title("汇报路线：一条监管闭环", fontsize=15, pad=6)
savefig(fig, "fig00_roadmap"); plt.show()
''')

# ==================================================================== 2 数据来源
md(r"""
## 一、数据：监管处罚公示（自建数据库）

### 为什么用处罚数据
1. **公开可得**：国家金融监督管理总局按月公示行政处罚，是唯一覆盖全国、逐案可查的操作风险外部数据
2. **有金额**：每案披露罚款/没收金额，可直接作为"操作风险损失"的代理变量
3. **有事实**：披露违法违规事实，可做文本分析

### 数据抓取口径

| 项 | 内容 |
|---|---|
| 栏目 | 国家金融监督管理总局 → 政务信息 → 行政处罚 |
| 范围 | **总局机关** 661 期 + **派出机构** 29,198 期（2022-01 起） |
| 覆盖 | 省监管局 + 市监管分局 + 监管支局 |
| 原文 | 详情接口 `docClob` 字段（HTML 全文），无需解析 PDF |
| 合规 | 公开政府信息、限速抓取、仅学术用途 |

> 注：中小企业主要由**地市监管分局**监管，因此必须以"派出机构"为主样本。
> 只抓总局本级会得到 661 期、其中银行类仅 47 条 —— 会完全错失研究对象。
""")
code(r'''
src = pd.DataFrame([
    ("总局机关", 661, "2020–2026", "栏目 4113"),
    ("监管局本级（省级）", 32983, "含历史年份", "栏目 4114"),
    ("监管分局本级（地市）", 41894, "含历史年份", "栏目 4115"),
    ("已抓取并解析", len(da.events()), "2022–2026", "本期实际使用"),
], columns=["数据来源", "期数", "时间范围", "说明"])
display(src.style.hide(axis="index"))
display(Markdown(
    f"本期实际使用 **{da.events()['docId'].nunique():,} 期**公示，"
    f"解析出 **{len(da.events()):,} 条**处罚记录。"))
''')

# ==================================================================== 3 样本与质量
md(r"""
### 样本概况与数据质量

监管文本的自动化解析必须交代三件事：**格式是否统一、字段是否完整、错误如何控制**。

三类正文格式与处理方式：

| 格式 | 结构 | 占比 | 解析方式 |
|---|---|---|---|
| A 列表式汇总表 | 序号｜当事人｜违法事实｜处罚内容｜决定机关 | 多案一期 | 表头映射 + 合并单元格还原 |
| B 信息公开表 | 字段名—内容 键值对 | 一案一期 | 语义分槽（文号/日期/机关互斥） |
| C 处罚决定书 | 自由文本 | 少量 | 正则抽取当事人、事实、决定 |

**已修正的四类系统性错误**（不修则后续全部失真）：

1. `rowspan` 合并单元格导致整行错位 → 按网格还原，记录数 +39%
2. "作出决定机关"被关键词"决定"误判为处罚内容 → 机关全空
3. "罚没合计"与分项"罚款/没收"重复累加 → 金额虚高 10 倍
4. 当事人名带职务后缀（如"（时任…副行长）"）→ 机构名无法归集
""")
code(r'''
ev = da.events()
summ = da.sample_summary()
display(summ.style.hide(axis="index"))

q = pd.DataFrame({
    "质量指标": ["正文格式分布", "当事人可归类为机构", "有明确处罚金额",
                 "违法违规事实非空", "可归入具体违规类型", "机构层级可判定"],
    "数值": [
        " / ".join(f"{k}:{v:,}" for k, v in ev["_fmt"].value_counts().items()),
        f"{(ev['当事人类型']=='机构').mean():.1%}",
        f"{(ev['罚没合计万元']>0).mean():.1%}",
        f"{ev['违法违规事实'].notna().mean():.1%}",
        f"{(ev['违规类型']!='其他违规').mean():.1%}",
        f"{(ev['机构层级']!='未知').mean():.1%}",
    ]})
display(q.style.hide(axis="index"))
''')

# ==================================================================== 4 总览趋势
md(r"""
## 二、事后暴露：监管实际抓到了什么

### 处罚强度的时间趋势

看两件事：**罚单数量**（监管检查密度）与**罚没金额**（违规的经济代价）。
二者背离时，往往意味着监管从"以量处罚"转向"重点重罚"。
""")
code(r'''
ys = da.yearly_stats()
fig, ax1 = plt.subplots(figsize=(10, 4.6))
x = ys.index.astype(int)
ax1.bar(x, ys["事件数"], color=C_MID, alpha=0.85, width=0.55, label="处罚记录数（左轴）")
ax1.set_ylabel("处罚记录数（条）", color=C_MID)
ax1.tick_params(axis="y", labelcolor=C_MID)
annotate_bars(ax1, "{:,.0f}")
ax2 = ax1.twinx()
ax2.plot(x, ys["金额亿元"], color=C_ACCENT, marker="o", lw=2.4, label="罚没金额（右轴）")
ax2.set_ylabel("罚没金额（亿元）", color=C_ACCENT)
ax2.tick_params(axis="y", labelcolor=C_ACCENT)
ax2.grid(False)
for xi, yi in zip(x, ys["金额亿元"]):
    ax2.annotate(f"{yi:,.1f}", (xi, yi), textcoords="offset points",
                 xytext=(0, 9), ha="center", fontsize=9, color=C_ACCENT)
ax1.set_xticks(x); ax1.set_xticklabels([f"{i}年" for i in x])
ax1.set_title("处罚记录数与罚没金额：2022–2026", fontsize=14)
h1, l1 = ax1.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax1.legend(h1+h2, l1+l2, loc="upper left")
savefig(fig, "fig01_trend"); plt.show()

peak = ys["金额亿元"].idxmax()
display(Markdown(
    f"2022–2026 年共录得 **{len(ev):,} 条**处罚记录，罚没金额合计 "
    f"**{ev['罚没合计万元'].sum()/1e4:,.1f} 亿元**；"
    f"罚没金额峰值出现在 **{peak} 年（{ys.loc[peak,'金额亿元']:,.1f} 亿元）**。"))
''')

# ==================================================================== 5 机构结构
md(r"""
### 谁在被罚：机构的类型结构

这一页要回答一个容易被误导的问题：**"国有大行罚单最多" ≠ "国有大行违规最严重"**。

大行的分支网点遍布每个地市，每个分局都能独立开罚单；而一家村镇银行只有法人一个主体。
所以必须把「罚单数量」和「机构家数」分开看。
""")
code(r'''
bev = da.bank_events()
g = (bev.groupby("机构类型")
        .agg(罚单数=("docId", "size"), 机构家数=("机构名称", "nunique"),
             罚没万元=("罚没合计万元", "sum")))
g["单家机构罚单"] = (g["罚单数"] / g["机构家数"]).round(2)
g["罚没亿元"] = (g["罚没万元"] / 1e4).round(2)
g = g.sort_values("罚单数", ascending=True)
display(g.drop(columns=["罚没万元"]).style.format({"罚没亿元": "{:,.2f}"}))

fig, ax = plt.subplots(figsize=(10, 4.8))
colors = [C_ACCENT if ("农村" in i or "村镇" in i or "城商" in i or "民营" in i)
          else C_MAIN for i in g.index]
ax.barh(g.index, g["单家机构罚单"], color=colors, alpha=0.9)
ax.set_xlabel("单家机构平均罚单数（条）")
ax.set_title("按机构类型的处罚密度：红色为中小银行", fontsize=14)
for i, (idx, row) in enumerate(g.iterrows()):
    ax.text(row["单家机构罚单"] + 0.05, i, f"{row['单家机构罚单']:.2f}",
            va="center", fontsize=9.5)
savefig(fig, "fig02_institution"); plt.show()

small = g.loc[[i for i in g.index if ("农村" in i or "村镇" in i or "城商" in i or "民营" in i)]]
display(Markdown(
    f"中小银行（城商/农商/村镇/民营）合计 **{small['罚单数'].sum():,} 张**罚单，"
    f"涉及 **{small['机构家数'].sum():,} 家**机构，"
    f"罚没 **{small['罚没亿元'].sum():,.2f} 亿元**。"))
''')

# ==================================================================== 6 违规类型
md(r"""
### 违规类型的总体图谱

把 1.8 万余条非"其他"记录按违规性质归类。这张图是"监管关注点"的地形图 ——
**违规集中在哪一类，监管的检查资源就投向哪一类**。
""")
code(r'''
vc = bev["违规类型"].value_counts()
vc = vc[vc.index != "其他违规"].sort_values()
fig, ax = plt.subplots(figsize=(10, 5.2))
bars = ax.barh(vc.index, vc.values,
               color=[C_ACCENT if "贷" in i or "信贷" in i else C_MID for i in vc.index],
               alpha=0.9)
ax.set_xlabel("处罚记录数（条）")
ax.set_title("银行类违规性质分布（红色为信贷相关）", fontsize=14)
for i, v in enumerate(vc.values):
    ax.text(v + 20, i, f"{v:,}", va="center", fontsize=9.5)
savefig(fig, "fig03_violation_type"); plt.show()

credit_share = vc[[i for i in vc.index if ("贷" in i or "信贷" in i)]].sum() / vc.sum()
display(Markdown(
    f"信贷类违规（贷款三查、违规发放、资金挪用、掩盖不良、信贷管理）"
    f"合计占全部可归类处罚的 **{credit_share:.1%}**，"
    f"是银行处罚中最大的一块。"))
''')

# ==================================================================== 7 热力图（主图1）
md(r"""
### 主图①：机构类型 × 违规类型的结构性差异

同一个"信贷违规"，大行与中小银行的**成因并不相同**。数据给出的三个反差：

| 差异点 | 大型银行 | 中小银行/村镇银行 | 解读 |
|---|---|---|---|
| 贷款三查不到位 | 31%–34% | 26%–27% | 大行分支机构多、执行链条长，属**流程执行**问题 |
| 违规发放贷款 | 15%–16% | 17%（农村）/ **21%（村镇）** | 客户下沉，准入把关更容易出问题 |
| 掩盖不良（五级分类不实） | **1%–2%** | **4%（农村）/ 5%（村镇）** | 资产质量压力更大时的**报表修饰动机** |
| 关联交易与关系人 | **0%–1%** | **4%（农村）/ 5%（村镇）** | 公司治理薄弱，**关联方识别与授信约束失效** |

这张热力图是本汇报的第一个记忆点：**大行的问题在"执行"，中小银行的问题在"治理与质量"。**
""")
code(r'''
mat = da.violation_matrix("bank")
share = mat.div(mat.sum(axis=1), axis=0)          # 行内占比，消除规模差异

fig, ax = plt.subplots(figsize=(11.5, 4.6))
im = ax.imshow(share.values, cmap="Reds", aspect="auto", vmin=0,
               vmax=float(np.nanpercentile(share.values, 97)))
ax.set_xticks(range(share.shape[1]))
ax.set_xticklabels(share.columns, rotation=32, ha="right", fontsize=9.5)
ax.set_yticks(range(share.shape[0]))
ax.set_yticklabels(share.index, fontsize=10)
for i in range(share.shape[0]):
    for j in range(share.shape[1]):
        v = share.values[i, j]
        ax.text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=8.6,
                color="white" if v > np.nanpercentile(share.values, 75) else "#333")
ax.set_title("机构类型 × 违规类型（行内占比）", fontsize=14)
fig.colorbar(im, ax=ax, fraction=0.025, label="占该类型机构处罚的比重")
ax.grid(False)
savefig(fig, "fig04_heatmap"); plt.show()

# 大行 vs 中小银行：把差异最大的三项挑出来
grp = bev.assign(类别=np.where(bev["是否中小银行"] == 1, "中小银行", "大型/股份行"))
cmp_rows = {}
for col in ["贷款三查不到位", "违规发放贷款", "掩盖不良与五级分类", "关联交易与关系人",
            "信贷管理不到位"]:
    if col not in share.columns:
        continue
    cmp_rows[col] = {c: (grp.loc[grp["类别"] == c, "违规类型"] == col).mean()
                     for c in ["大型/股份行", "中小银行"]}
cmp = pd.DataFrame(cmp_rows).T
cmp["差异(中小-大行)"] = (cmp["中小银行"] - cmp["大型/股份行"])
display(cmp.style.format("{:.1%}").background_gradient(
    subset=["差异(中小-大行)"], cmap="RdBu_r", vmin=-0.05, vmax=0.05))
''')

# ==================================================================== 8 中小企业信贷聚焦
md(r"""
### 聚焦：中小企业信贷违规的特征

把范围收窄到 **信贷相关 + 中小银行**，看三个特征：

1. **金额小而频**：单笔金额小，但发生频次高 —— 正是中小企业信贷"短小频急"的镜像
2. **集中在贷前贷后**：调查不尽职、贷后管理不到位
3. **处罚金额的分布形态**：右偏重尾，为后续 LDA 建模提供依据
""")
code(r'''
sm = bev[(bev["是否中小银行"] == 1)]
sm_credit = sm[sm["信贷相关"] == 1]
big_credit = bev[(bev["机构类型"].isin(["国有大型银行", "股份制银行"])) & (bev["信贷相关"] == 1)]

fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
ax = axes[0]
amt = [sm_credit.loc[sm_credit["罚没合计万元"] > 0, "罚没合计万元"],
       big_credit.loc[big_credit["罚没合计万元"] > 0, "罚没合计万元"]]
bp = ax.boxplot(amt, vert=True, patch_artist=True, widths=0.55,
                showfliers=False, labels=["中小银行", "大行/股份行"])
for patch, c in zip(bp["boxes"], [C_ACCENT, C_MAIN]):
    patch.set_facecolor(c); patch.set_alpha(0.75)
ax.set_ylabel("单笔罚没金额（万元）")
ax.set_title("信贷类处罚金额对比（不含离群值）", fontsize=12.5)

ax = axes[1]
vc2 = sm_credit["违规类型"].value_counts().head(7).sort_values()
ax.barh(vc2.index, vc2.values, color=C_ACCENT, alpha=0.85)
ax.set_xlabel("处罚记录数")
ax.set_title("中小银行信贷违规的主要类型", fontsize=12.5)
for i, v in enumerate(vc2.values):
    ax.text(v + 3, i, f"{v:,}", va="center", fontsize=9)
savefig(fig, "fig05_sme_focus"); plt.show()

med_s = sm_credit.loc[sm_credit["罚没合计万元"] > 0, "罚没合计万元"].median()
med_b = big_credit.loc[big_credit["罚没合计万元"] > 0, "罚没合计万元"].median()
display(Markdown(
    f"中小银行信贷类处罚 **{len(sm_credit):,} 条**，金额中位数 **{med_s:,.1f} 万元**；"
    f"大行/股份行同口径中位数 **{med_b:,.1f} 万元**。"
    f"典型事由集中在 **{vc2.index[-1]}** 与 **{vc2.index[-2] if len(vc2)>1 else ''}**。"))
''')

# ==================================================================== 9 文本主题
md(r"""
### 违规事由的文本结构

处罚事由本身是规范化表述，用「、，；」切分后长度 4–20 字的片段即为一个违规要点。
用字符 n-gram TF-IDF + KMeans 把上万条事由聚成若干主题，看监管的**表述体系**。
""")
code(r'''
import text_analysis as ta
credit_txt = bev.loc[bev["违法违规事实"].notna(), "违法违规事实"].astype(str)
credit_txt = credit_txt[credit_txt.str.len() > 5]

top = ta.phrase_freq(bev, top=18)
display(top.to_frame().T.style.hide(axis="index"))

themes, labels, vec = ta.tfidf_kmeans(credit_txt.sample(min(6000, len(credit_txt)),
                                                        random_state=42), k=5)
display(themes.style.hide(axis="index"))

fig, ax = plt.subplots(figsize=(10, 4.6))
t2 = top.head(15).sort_values()
ax.barh(t2.index, t2.values, color=C_MID, alpha=0.88)
ax.set_xlabel("出现次数")
ax.set_title("银行处罚事由的高频表述 Top15", fontsize=13.5)
for i, v in enumerate(t2.values):
    ax.text(v + 3, i, f"{v:,}", va="center", fontsize=9)
savefig(fig, "fig06_phrases"); plt.show()
''')

# ==================================================================== 10 LDA 引入
md(r"""
## 三、损失计量：把"违规"翻译成"钱"

### 为什么可以用损失分布法（LDA）

巴塞尔协议的操作风险高级计量法，核心是把**年度损失**视为随机变量：

<div style="text-align:center;font-size:19px;margin:14px 0;font-family:Cambria,Georgia,serif"><i>L</i> = <b>Σ</b> <i>X<sub>i</sub></i>&nbsp;&nbsp;(i = 1, 2, …, <i>N</i>)</div>

- $N$：一年内损失事件的发生**次数**（频率分布）
- <i>X<sub>i</sub></i>：单次损失的**金额**（强度分布）

银行内部数据不可得，但**监管处罚金额**恰好是外部操作风险损失的可观测代理。
代价是：罚款只是真实损失的**下界**（不含声誉损失、拨备、整改成本），这一点必须写明。
""")
code(r'''
import lda_model as lm
qc = da.quarterly_counts("bank")
ac = da.annual_counts("bank")
freq = lm.fit_frequency(qc.values)

display(pd.DataFrame([
    ("完整季度数", freq["n"]),
    ("季度事件数均值 λ", round(freq["lam"], 1)),
    ("过离散度 (var-mean)/mean", round(freq["dispersion"], 2)),
    ("泊松 vs 负二项 LRT p 值", round(freq["lrt_p"], 4)),
    ("选定分布", freq["kind"]),
], columns=["频率分布检验", "结果"]).style.hide(axis="index"))

fig, ax = plt.subplots(figsize=(9.5, 4.2))
ax.plot(qc.index, qc.values, marker="o", color=C_MAIN, lw=2)
ax.set_title("银行类处罚事件的季度发生数（2022Q1–2025Q4）", fontsize=13.5)
ax.set_ylabel("事件数（件/季）")
ax.axhline(freq["lam"], color=C_ACCENT, ls="--", lw=1.6,
           label=f"均值 λ = {freq['lam']:.0f}")
ax.legend()
savefig(fig, "fig07_frequency"); plt.show()

display(Markdown(
    f"季度事件数均值 **{freq['lam']:.0f} 件**，过离散度 **{freq['dispersion']:.2f}**"
    f"（>1 表示方差大于均值）。LRT p 值 = **{freq['lrt_p']:.4f}**，"
    f"故采用 **{freq['kind']}** 分布刻画频率。"))
''')

# ==================================================================== 11 强度
md(r"""
### 单笔损失强度：对数正态拟合

罚款金额的典型特征是**右偏、重尾**：大量几万元的小额罚单，少量上亿元的大案。
这正是对数正态分布的形状。

拟合优度用 KS 检验（原假设：样本来自该分布）与 Anderson–Darling 检验（对尾部更敏感）。
""")
code(r'''
sev_s = da.severity_series("bank")
sev = lm.fit_severity(sev_s.values)

fig, ax = plt.subplots(figsize=(10, 4.6))
logs = np.log10(sev_s.values[sev_s.values > 0])
ax.hist(logs, bins=40, density=True, color=C_MID, alpha=0.65, label="实际分布")
xs = np.linspace(logs.min(), logs.max(), 400)
ax.plot(xs, (1/(np.sqrt(2*np.pi)*sev["sigma"]))*np.exp(-((xs*np.log(10)-sev["mu"])**2)/(2*sev["sigma"]**2))*np.log(10),
        color=C_ACCENT, lw=2.4, label="对数正态拟合")
ax.set_xlabel("单笔罚没金额（log10 万元）")
ax.set_ylabel("密度")
ax.set_title("处罚金额分布与对数正态拟合", fontsize=13.5)
ax.legend()
savefig(fig, "fig08_severity"); plt.show()

display(pd.DataFrame([
    ("样本量", f"{sev['n']:,}"),
    ("μ（对数均值）", f"{sev['mu']:.3f}"),
    ("σ（对数标准差）", f"{sev['sigma']:.3f}"),
    ("中位数（万元）", f"{sev['median']:,.1f}"),
    ("KS 统计量 / p 值", f"{sev['ks_stat']:.4f} / {sev['ks_p']:.4f}"),
    ("AD 统计量 / 5% 临界值", f"{sev['ad_stat']:.2f} / {sev['ad_crit_5pct']:.2f}"),
    ("最大单笔（万元）", f"{sev['max']:,.1f}"),
], columns=["强度分布参数", "取值"]).style.hide(axis="index"))
''')

# ==================================================================== 12 尾部
md(r"""
### 尾部风险：极值理论看"最坏的罚单"

对数正态对**极端尾部**往往低估。用极值理论的 POT 方法（Peaks Over Threshold）
对超过阈值的部分拟合广义帕累托分布（GPD），形状参数 ξ 决定尾部厚度：

- ξ > 0：厚尾（帕累托型），存在极端事件
- ξ ≈ 0：指数型衰减
- ξ < 0：有上界

阈值的选取看**超阈值均值图（MR 图）**：曲线近似线性处即为合理阈值。
""")
code(r'''
mr_u, mr_y = lm.mean_residual_life(sev_s.values)
gpd = lm.fit_gpd(sev_s.values, threshold=float(mr_u[len(mr_u)//2]))

fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
ax = axes[0]
ax.plot(mr_u, mr_y, marker="o", ms=3.4, color=C_MAIN, lw=1.6)
if gpd:
    ax.axvline(gpd["threshold"], color=C_ACCENT, ls="--", lw=1.6,
               label=f"选定阈值 {gpd['threshold']:,.0f} 万元")
    ax.legend()
ax.set_xlabel("阈值 u（万元）"); ax.set_ylabel("平均超阈值 E[X-u|X>u]")
ax.set_title("超阈值均值图（选阈值）", fontsize=12.5)

ax = axes[1]
if gpd:
    excess = np.sort(sev_s.values[sev_s.values > gpd["threshold"]] - gpd["threshold"])
    ax.plot(excess, 1 - np.arange(1, len(excess)+1)/len(excess), "o",
            ms=3.4, color=C_MID, label="经验生存函数")
    fit = 1 - np.arange(1, len(excess)+1)/len(excess)
    from scipy.stats import genpareto
    ax.plot(excess, 1 - genpareto.cdf(excess, gpd["xi"], 0, gpd["beta"]),
            color=C_ACCENT, lw=2.2, label="GPD 拟合")
    ax.set_yscale("log")
    ax.set_xlabel("超阈值损失（万元）"); ax.set_ylabel("P(X > x)")
    ax.set_title(f"GPD 拟合（ξ={gpd['xi']:.2f}，尾指数 {gpd['tail_index']:.1f}）",
                 fontsize=12.5)
    ax.legend()
savefig(fig, "fig09_gpd"); plt.show()

if gpd:
    display(Markdown(
        f"阈值 **{gpd['threshold']:,.0f} 万元**，超阈值 **{gpd['n_exceed']} 笔**"
        f"（占 {gpd['excess_rate']:.1%}），形状参数 **ξ = {gpd['xi']:.3f}**、"
        f"尾指数 **{gpd['tail_index']:.2f}**；KS p 值 {gpd['ks_p']:.3f}。"
        f"ξ>0 说明存在厚尾极端损失，均值意义上的资本准备会低估极端情形。"))
''')

# ==================================================================== 13 蒙特卡洛（主图2）
md(r"""
### 主图②：年度损失分布与 99.9% VaR

把频率与强度组合，蒙特卡洛模拟 5 万次年度总损失：

- 频率：每季事件数 → 按 4 个季度合成年度事件数
- 强度：每次事件从对数正态分布抽样
- 年度损失 = 该年所有事件金额之和

取 **99.9% 分位**作为操作风险 VaR（与巴塞尔资本计量的置信水平一致），
并计算**期望尾部损失 ES**（越界部分的平均损失）。
""")
code(r'''
mc = lm.monte_carlo(freq, sev, n_sims=50000, periods_per_year=4, seed=42)
losses = mc["losses"]

fig, ax = plt.subplots(figsize=(10.5, 4.9))
ax.hist(losses/1e4, bins=90, color=C_MID, alpha=0.75)
ax.axvline(mc["var"]/1e4, color=C_ACCENT, lw=2.6,
           label=f"99.9% VaR = {mc['var']/1e4:,.1f} 亿元")
ax.axvline(mc["mean"]/1e4, color="#2e7d32", lw=2.0, ls="--",
           label=f"年度损失均值 = {mc['mean']/1e4:,.1f} 亿元")
ax.set_xlabel("年度操作风险损失（亿元）")
ax.set_ylabel("模拟频数")
ax.set_title("年度损失分布（5 万次蒙特卡洛模拟）", fontsize=14)
ax.legend(loc="upper right")
savefig(fig, "fig10_var"); plt.show()

display(pd.DataFrame([
    ("模拟次数", f"{mc['n_sims']:,}"),
    ("年度损失均值（亿元）", f"{mc['mean']/1e4:,.2f}"),
    ("年度损失中位数（亿元）", f"{mc['median']/1e4:,.2f}"),
    ("95% 分位（亿元）", f"{mc['p95']/1e4:,.2f}"),
    ("99.9% VaR（亿元）", f"{mc['var']/1e4:,.2f}"),
    ("99.9% ES（亿元）", f"{mc['es']/1e4:,.2f}"),
], columns=["蒙特卡洛结果（银行类）", "数值"]).style.hide(axis="index"))
''')

# ==================================================================== 14 资本对比（主图3）
md(r"""
### 主图③：监管资本够不够？—— 以及一个更锋利的替代指标

三种计量口径：

| 方法 | 公式 | 依据 |
|---|---|---|
| 基本指标法 BIA | <i>K</i> = α × <i>GI</i>，α = 15% | 巴塞尔 II（我国 2012 年试行办法） |
| 新标准法 SA | <i>K</i> = β(<i>BI</i>) × <i>BI</i>，β 分档 12%/15%/18% | 《商业银行资本管理办法》（2024 实施） |
| LDA 实测 | 99.9% VaR | 本节估计 |

**两个必须讲清的口径问题：**

1. **层级对齐**：资本要求针对**法人机构**，所以只能匹配"法人/总部"层级的处罚事件，
   分行网点罚单必须剔除（否则一家大行会被上千张网点罚单淹没）。
2. **对象对齐**：LDA 必须限定在与资本口径相同的机构集合上，
   不能把全市场损失除以机构家数（分母里混着大量网点）。

在资本对比之外，引入一个对监管更有操作性的替代指标：
**违规密度 = 单位营收的罚单数**。它不需要估计分布，且能区分个体差异。
""")
code(r'''
def _norm(s):
    """只去公司形式后缀，保留“中国/工商”等识别词（否则“中国银行”→“银行”会误匹配全部）。"""
    s = str(s)
    for x in ("股份有限公司", "有限责任公司", "有限公司", "股份", "集团"):
        s = s.replace(x, "")
    return s.strip()

fin = da.bank_fin().dropna(subset=["gi_avg3"]).copy()
fin["key"] = fin["name"].map(_norm)
ev = da.events().copy()
ev["_org"] = ev["机构名称"].astype(str).map(_norm)
legal = ev[ev["机构层级"] == "法人/总部"].copy()          # ← 只保留法人层级
keymap = dict(zip(fin["key"], zip(fin["name"], fin["bank_type"], fin["gi_avg3"])))

def _match(x):
    if not x:
        return None
    if x in keymap:
        return keymap[x]
    for k, v in keymap.items():
        if len(k) >= 4 and (x.startswith(k) or (k.startswith(x) and len(x) >= 4)):
            return v
    return None

legal["_hit"] = legal["_org"].apply(_match)
hit = legal[legal["_hit"].notna()].copy()
hit["bank_name"] = hit["_hit"].apply(lambda t: t[0])
hit["bank_type"] = hit["_hit"].apply(lambda t: t[1])
hit["gi"] = hit["_hit"].apply(lambda t: t[2])

dens = hit.groupby(["bank_name", "bank_type", "gi"]).size().reset_index(name="罚单数")
dens["密度"] = dens["罚单数"] / dens["gi"] * 100          # 每百亿营收罚单数

sme_d = dens[dens["bank_type"].isin(["城商行", "农商行"])]
big_d = dens[dens["bank_type"].isin(["国有大型银行", "股份制银行"])]

fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.6))
ax = axes[0]
order = ["国有大型银行", "股份制银行", "城商行"]
vals = [dens.loc[dens["bank_type"] == k, "密度"].median() for k in order]
ns = [int((dens["bank_type"] == k).sum()) for k in order]
ax.bar(order, vals, color=[C_MAIN, C_MID, C_ACCENT], alpha=0.9, width=0.55)
for i, (v, n) in enumerate(zip(vals, ns)):
    ax.text(i, v, f"{v:.2f}\n(n={n})", ha="center", va="bottom", fontsize=9.5)
ax.set_ylabel("每百亿营收罚单数（中位数）")
ax.set_title("违规密度：小型银行单位营收被罚更频繁", fontsize=12.5)

ax = axes[1]
ax.scatter(dens["gi"], dens["密度"], s=52, c=np.where(
    dens["bank_type"].isin(["城商行", "农商行"]), C_ACCENT, C_MAIN), alpha=0.8)
ax.set_xscale("log")
ax.set_xlabel("营业收入（亿元，对数）"); ax.set_ylabel("每百亿营收罚单数")
rho, pval = stats.spearmanr(dens["gi"], dens["密度"])
ax.set_title(f"规模 vs 违规密度：ρ={rho:.2f}（p={pval:.4f}）", fontsize=12.5)
savefig(fig, "fig11_density"); plt.show()

# —— 中小银行法人组合的独立 LDA
sm = hit[hit["bank_type"].isin(["城商行", "农商行"])]
_q = pd.to_datetime(sm["发布日期"], errors="coerce")
qc2 = pd.Series(1, index=_q[_q.notna()]).resample("QE").sum().loc["2022-03-31":"2025-12-31"]
sev2 = sm["罚没合计万元"]; sev2 = sev2[sev2 > 0]
sf = fin[fin["bank_type"].isin(["城商行", "农商行"])]
bia = sf["gi_avg3"].apply(lambda g: lm.capital_bia([g], 0.15))
sa = sf["gi_avg3"].apply(lambda g: lm.capital_sa_bis(g)[0])

mc2 = None
if len(qc2) >= 8 and len(sev2) >= 40:
    f2 = lm.fit_frequency(qc2.values); s2 = lm.fit_severity(sev2.values)
    mc2 = lm.monte_carlo(f2, s2, n_sims=30000, periods_per_year=4, seed=42)

uw = stats.mannwhitneyu(sme_d["密度"], big_d["密度"], alternative="greater")
rows = [
    ("匹配到的法人层级事件", f"{len(hit):,} 条 / {hit['bank_name'].nunique()} 家"),
    ("违规密度中位数：城商行", f"{sme_d['密度'].median():.2f} 张/百亿营收"),
    ("违规密度中位数：大行+股份行", f"{big_d['密度'].median():.2f} 张/百亿营收"),
    ("中小银行 > 大行的检验", f"Mann-Whitney p = {uw.pvalue:.4f}"),
    ("规模与密度相关性", f"Spearman ρ = {rho:.3f}（p={pval:.4f}）"),
    ("城商/农商资本合计 BIA", f"{bia.sum():,.1f} 亿元"),
    ("城商/农商资本合计 SA", f"{sa.sum():,.1f} 亿元"),
    ("单家年均罚没", f"{sm['罚没合计万元'].sum()/4/max(len(sf),1):,.0f} 万元"),
]
if mc2:
    rows += [("组合 99.9% VaR", f"{mc2['var']/1e4:,.2f} 亿元/年"),
             ("组合年度损失均值", f"{mc2['mean']/1e4:,.2f} 亿元/年"),
             ("VaR / BIA 资本", f"{mc2['var']/1e4/bia.sum():.3%}")]
display(pd.DataFrame(rows, columns=["监管资本 vs 实测损失（法人层级口径）", "数值"])
        .style.hide(axis="index"))
''')

md(r"""
<div style="background:#fff4f4;border-left:4px solid #c00000;padding:12px 16px;border-radius:4px">

**本汇报最锋利的一组结果：**

1. **违规密度随规模单调下降**：城商行中位数约 **1.4 张/百亿营收**，
   国有大行约 **0.1 张**，差距 10 倍以上；Spearman ρ ≈ −0.73（p<0.0001），
   中小银行显著高于大行（Mann-Whitney p<0.01）。
2. **资本计量对此完全"看不见"**：BIA/SA 只按营业收入的固定比例计提，
   营收越小、缴的资本越少，而这恰恰是违规密度最高的一档机构。
3. **罚款金额本身并不大**：组合 99.9% VaR 约 10 亿元，仅相当于 27 家城商/农商行
   操作风险资本合计的 1% 量级 —— 但极端值（σ≈1.9）说明真正致命的是少数大案。

</div>

**结论**：与其在"罚款金额"上做资本调整（金额太小、噪声太大），
不如把**违规密度与违规类型**作为差异化监管的抓手 —— 这是本汇报的政策落点。
""")



# ==================================================================== 15 小结
md(r"""
### 小结：从"违规"到"资本"

| 结论 | 证据 |
|---|---|
| 信贷类违规是银行处罚的主体 | 占比见上节 |
| 中小银行违规集中在贷前贷后 | 热力图行内占比 |
| 损失分布重尾，极端案值拉高 VaR | ξ > 0，VaR 远高于均值 |
| 监管资本以营收为基数，与实测损失不同步 | 两种口径对照 |

**政策含义**：以营业收入为基数的计量方法，对"业务规模小但违规密度高"的
中小银行并不敏感 —— 这是"监管资本"与"实际风险"之间的结构性错配。
""")
code(r'''
summary = pd.DataFrame([
    ("处罚记录总数", f"{len(ev):,}"),
    ("银行类记录", f"{len(bev):,}"),
    ("信贷相关记录", f"{int(bev['信贷相关'].sum()):,}"),
    ("罚没金额合计", f"{bev['罚没合计万元'].sum()/1e4:,.1f} 亿元"),
    ("99.9% VaR（银行类年度）", f"{mc['var']/1e4:,.1f} 亿元"),
    ("VaR / 年度均值", f"{mc['var']/max(mc['mean'],1e-9):.1f} 倍"),
], columns=["指标", "取值"])
display(summary.style.hide(axis="index"))
''')

# ==================================================================== 16 转向事前
md(r"""
## 四、事前防范：中小企业违约能否被识别

### 样本与标签

**样本**：新三板（含北交所）挂牌公司财务面板 —— 我国公开数据中"中小企业"最直接的口径。

**标签**（下一年度发生任一情形即为困境，y=1，**严格前视，只用 t+1 年信息**）：

1. 资不抵债：下一年资产负债率 ≥ 100%
2. 下一年亏损：下一年归母净利润 < 0

> ⚠️ **刻意不采用"连续两年亏损"**：该定义需要用到 t 年利润，
> 而 t 年利润同时是特征之一，会形成"特征—标签循环定义"，
> 把 AUC 人为推到 0.94 以上。修正后 AUC 回落到合理区间，这是必要的取舍。
>
> 同时须明确：这是**财务困境代理变量**，不是银行真实违约（银行微观信贷数据不可得）。
""")
code(r'''
import default_model as dm
panel = dm.build_panel(da.firm_panel())
feat = [c for c in dm.FEATURES if c in panel.columns]
X = panel[feat].replace([np.inf, -np.inf], np.nan)
y = panel["distress"].astype(int)

display(pd.DataFrame([
    ("公司家数", f"{panel['code'].nunique():,}"),
    ("公司-年观测", f"{len(panel):,}"),
    ("时间跨度", f"{int(panel['year'].min())}–{int(panel['year'].max())}"),
    ("困境样本占比", f"{y.mean():.1%}"),
    ("可用特征数", len(feat)),
], columns=["样本概况", "数值"]).style.hide(axis="index"))

display(panel.groupby("year")["distress"].agg(公司数="size", 困境数="sum",
                                              困境率="mean")
        .style.format({"困境率": "{:.1%}"}))
''')

# ==================================================================== 17 三个模型
md(r"""
### 三个模型：从"抄公式"到"机器学习"

**① Altman Z'（1968）**：直接套用原始系数，不重新估计。
这是"国外模型搬到中国还准不准"的检验——**基准线**。

<div style="text-align:center;font-size:19px;margin:14px 0;font-family:Cambria,Georgia,serif"><i>Z</i>′ = 1.2<i>X</i><sub>1</sub> + 1.4<i>X</i><sub>2</sub> + 3.3<i>X</i><sub>3</sub> + 0.6<i>X</i><sub>4</sub> + 1.0<i>X</i><sub>5</sub></div>

其中 <i>X</i><sub>4</sub> 用**账面权益/总负债**（Z′ 口径），而非市值，以避免前视偏差。

**② Logistic + WOE 评分卡**：分箱 → 计算 IV 筛选变量 → 逻辑回归 → 刻度转换（600 分，PDO=20）。
这是监管最容易接受的模型形态：单调、可解释、可落到分数。

**③ XGBoost / GBDT + 变量重要性**：性能上限，并检验机器学到的规律是否与专家经验一致。

> 分箱时强制每箱最小样本量（≥40），否则小样本会让 IV 虚高到 4 以上，变量筛选失真。
""")
code(r'''
import matplotlib.pyplot as plt
fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))

ax = axes[0]
zlab = dm.zscore_label(panel["Z_score"])
tab = pd.crosstab(zlab, y, normalize="index")
tab.plot(kind="bar", stacked=True, ax=ax, color=["#8faadc", C_ACCENT], width=0.55)
ax.set_title("Altman Z' 分区的实际困境率", fontsize=12.5)
ax.set_xlabel("Z' 判别区间"); ax.set_ylabel("占比"); ax.legend(["非困境", "困境"])
ax.tick_params(axis="x", rotation=0)

ax = axes[1]
sub = panel.dropna(subset=["Z_score", "distress"])
ax.hist(sub.loc[sub.distress == 0, "Z_score"].clip(-5, 20), bins=60,
        alpha=0.6, color="#8faadc", label="非困境", density=True)
ax.hist(sub.loc[sub.distress == 1, "Z_score"].clip(-5, 20), bins=60,
        alpha=0.65, color=C_ACCENT, label="困境", density=True)
ax.axvline(1.23, color="#333", ls="--", lw=1.4); ax.axvline(2.9, color="#333", ls="--", lw=1.4)
ax.set_title("Z' 在各组的分布（虚线为经典阈值）", fontsize=12.5)
ax.set_xlabel("Z' 值"); ax.legend()
savefig(fig, "fig12_zscore"); plt.show()

display(tab.style.format("{:.1%}"))
''')

# ==================================================================== 18 模型对比
md(r"""
### 模型绩效对比

评价指标取 AUC 与 KS —— 信贷风控的行业标准。
**注意**：交叉验证按年份分组（GroupKFold），禁止随机拆分，
否则同一年度样本同时进训练与测试，会严重高估绩效。

三个模型构成一条清晰的阶梯：
**抄公式（Z'）→ 可解释统计模型（评分卡）→ 机器学习（GBDT/XGBoost）**，
每一步的提升幅度，就是"方法升级"的真实价值。
""")
code(r'''
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_curve, roc_auc_score

mask = X.notna().sum(axis=1) > len(feat) * 0.5
Xm, ym, gm = X[mask], y[mask], panel.loc[mask, "year"]

# ① Z' 基准（取负号：Z 越低越危险）
s_z = -panel.loc[mask, "Z_score"].fillna(panel["Z_score"].median())
# ② 评分卡
sc = dm.fit_scorecard(Xm, ym)
s_sc = sc["proba"]
# ③ 机器学习
gb = dm.fit_gbm(Xm, ym)
s_gb = gb["proba"]
feat_gb = gb["features"]

res = []
for name, s in [("Altman Z'（原始系数）", s_z), ("SVM", None)]:
    pass
for name, s in [("Altman Z'（原始系数）", s_z),
                ("Logistic + WOE 评分卡", s_sc),
                (f"{gb['backend']}", s_gb)]:
    res.append({"模型": name, "AUC": roc_auc_score(ym, s),
                "KS": dm.ks_stat(ym, s)})
perf = pd.DataFrame(res).sort_values("AUC", ascending=False)
display(perf.style.format({"AUC": "{:.4f}", "KS": "{:.4f}"}).hide(axis="index"))

fig, ax = plt.subplots(figsize=(8.6, 5.6))
for name, s, c in [("Altman Z'", s_z, "#8faadc"),
                   ("评分卡", s_sc, C_MID),
                   (gb["backend"], s_gb, C_ACCENT)]:
    fpr, tpr, _, _ = dm.ks_curve(ym, s)
    ax.plot(fpr, tpr, lw=2.2, color=c,
            label=f"{name}  AUC={roc_auc_score(ym, s):.3f}  KS={dm.ks_stat(ym, s):.3f}")
ax.plot([0, 1], [0, 1], ls=":", color="#999")
ax.set_xlabel("假正例率 FPR"); ax.set_ylabel("真正例率 TPR")
ax.set_title("ROC 曲线：三个模型的违约识别能力", fontsize=13.5)
ax.legend(loc="lower right")
savefig(fig, "fig13_roc"); plt.show()
''')

# ==================================================================== 19 评分卡
md(r"""
### 评分卡：把模型变成能落地的分数

监管与业务都更接受"分数"而非"概率"。用 IV 筛选变量，WOE 编码后逻辑回归，
再按 600 分基准、PDO=20 换算：

<div style="text-align:center;font-size:19px;margin:14px 0;font-family:Cambria,Georgia,serif"><i>Score</i> = <i>A</i> − <i>B</i> · ln[ <i>p</i> / (1 − <i>p</i>) ]</div>

- PDO=20：坏好比每翻一倍，分数下降 20 分
- IV > 0.1 为强预测力，0.02–0.1 为弱预测力
""")
code(r'''
iv = sc["iv"].head(15)
display(pd.DataFrame({"变量": [dm.FEATURE_CN.get(k, k) for k in iv.index],
                      "IV": iv.values})
        .style.format({"IV": "{:.4f}"}).hide(axis="index"))

fig, ax = plt.subplots(figsize=(10, 4.6))
labels = [dm.FEATURE_CN.get(k, k) for k in iv.index][::-1]
ax.barh(labels, iv.values[::-1],
        color=[C_ACCENT if v > 0.1 else C_MID for v in iv.values[::-1]], alpha=0.9)
ax.axvline(0.1, color="#333", ls="--", lw=1.3)
ax.set_xlabel("IV 值（虚线 0.1 为强预测力阈）")
ax.set_title("评分卡变量筛选：IV 排序", fontsize=13.5)
for i, v in enumerate(iv.values[::-1]):
    ax.text(v + 0.004, i, f"{v:.3f}", va="center", fontsize=9)
savefig(fig, "fig14_iv"); plt.show()

score = pd.Series(sc["score"])
display(Markdown(
    f"最终入模变量 **{len(sc['keep'])} 个**，最强变量为 "
    f"**{dm.FEATURE_CN.get(iv.index[0], iv.index[0])}（IV={iv.iloc[0]:.3f}）**。"
    f"评分分布：中位数 **{score.median():.0f} 分**，"
    f"10%–90% 分位 **{score.quantile(.1):.0f}–{score.quantile(.9):.0f} 分**。"))
''')

# ==================================================================== 20 SHAP
md(r"""
### 可解释性：模型学到了什么，监管能否接受

机器学习模型进银行，**可解释性是合规硬门槛**（《商业银行模型风险管理指引》）。
用 SHAP（环境缺失时自动退化为置换重要度）看每个变量对违约判断的贡献大小，
再与信贷专家经验对照：

- 若模型主要依赖"盈利能力、流动性、偿债能力" → 与专家逻辑一致，**可接受**
- 若主要依赖某个不稳定会计科目 → 需警惕过拟合

**这一步是 B 线能否写进汇报的关键**：否则就只是"跑了个模型"。
""")
code(r'''
imp, engine, shap_vals = dm.shap_or_perm(gb["model"], Xm[feat_gb], top=14)
labels = [dm.FEATURE_CN.get(k, k) for k in imp.index][::-1]

fig, ax = plt.subplots(figsize=(9.8, 4.8))
ax.barh(labels, imp.values[::-1], color=C_MAIN, alpha=0.88)
ax.set_xlabel(f"平均绝对贡献（{engine}）")
ax.set_title(f"变量重要性（{engine}）：模型在依赖什么", fontsize=13.5)
for i, v in enumerate(imp.values[::-1]):
    ax.text(v, i, f" {v:.4f}", va="center", fontsize=8.8)
savefig(fig, "fig15_shap"); plt.show()

display(pd.DataFrame({"变量": labels[::-1], "重要性": imp.values[::-1]})
        .style.format({"重要性": "{:.5f}"}).hide(axis="index"))
''')

# ============================================ 20 SME 需求侧：中小企业本身
md(r"""
## 五、把镜头对准中小企业本身（需求侧证据）

前面用的是监管处罚数据，被处罚主体必然是银行。但**本汇报的研究对象是中小企业**，
所以先把镜头对准企业这一侧：它们的规模、盈利能力、债务水平、经营困境发生率。

**数据**：新三板（含北交所）挂牌公司财务面板——我国公开数据中"中小企业"最直接的口径。
**标签**：下一年度发生「资不抵债」或「亏损」即为经营困境。
""")
code(r'''
sme = da.sme_profile()
print(f"中小企业面板：{sme['code'].nunique():,} 家 × {len(sme):,} 个企业-年"
      f"（{int(sme['year'].min())}–{int(sme['year'].max())}）")

asset_yi = (sme["TOTAL_ASSETS_PK"] / 1e8).clip(0, 500)
rev_yi = (sme["TOTALOPERATEREVE"] / 1e8).clip(0, 200)
fig, axes = plt.subplots(1, 3, figsize=(13, 3.9))

axes[0].hist(asset_yi.dropna(), bins=40, color=C_MID, alpha=0.85)
axes[0].set_xlabel("总资产（亿元）"); axes[0].set_ylabel("企业-年数")
axes[0].set_title("规模：绝大多数在 50 亿元以下", fontsize=11.5)

axes[1].hist(rev_yi.dropna(), bins=40, color=C_MAIN, alpha=0.85)
axes[1].set_xlabel("营业收入（亿元）")
axes[1].set_title("收入：长尾分布，小企业为主", fontsize=11.5)

d = sme.groupby("year")["distress"].mean()
axes[2].bar(d.index.astype(str), d.values * 100, color=C_ACCENT, alpha=0.85)
axes[2].set_ylabel("经营困境率（%）")
axes[2].set_title("下一年陷入困境的比例", fontsize=11.5)
for x, v in zip(axes[2].get_xticklabels(), d.values):
    axes[2].text(x.get_text(), v * 100, f"{v:.0%}", ha="center", va="bottom",
                 fontsize=9)
savefig(fig, "fig16_sme_profile"); plt.show()

display(pd.DataFrame([
    ("企业数量", f"{sme['code'].nunique():,} 家"),
    ("企业-年观测", f"{len(sme):,}"),
    ("总资产中位数", f"{sme['TOTAL_ASSETS_PK'].median()/1e8:,.2f} 亿元"),
    ("营业收入中位数", f"{sme['TOTALOPERATEREVE'].median()/1e8:,.2f} 亿元"),
    ("资产负债率中位数", f"{sme['ZCFZL'].median():.1f}%"),
    ("经营困境率（下一年）", f"{sme['distress'].mean():.1%}"),
], columns=["中小企业画像（需求侧）", "取值"]).style.hide(axis="index"))
''')

md(r"""
### 困境企业 vs 健康企业：财务特征到底差在哪

这是把原文所说"中小企业抗风险能力弱、财务不稳定"落到数据上：
按下一年是否陷入困境分组，比较各财务指标的中位数，并做 Mann-Whitney 检验。
""")
code(r'''
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
''')

# ============================================ 21 SME 供给侧：专项处罚子样本
md(r"""
## 六、监管处罚里的「中小企业信贷」（供给侧证据）

### 口径：怎样从 3.7 万条处罚里切出"因中小企业信贷而出的事"

被处罚主体必然是银行（监管处罚不会开给企业），所以关键在于**筛选条件**：
事由中**明确出现中小企业客群表述** —— 小微 / 普惠 / 中小企业 / 个体工商户 /
涉农 / 农户 / 经营贷 / 支农支小 / 创业担保贷 等 —— **且**与信贷相关。

这样得到的就是"因为给中小企业放贷而出的事"，而不是"银行的所有违规"。
""")
code(r'''
sme_ev = da.sme_credit_events()
all_ev = da.events()
print(f"全部处罚事件      {len(all_ev):,} 条")
print(f"★ 中小企业信贷专项 {len(sme_ev):,} 条（占全部 {len(sme_ev)/len(all_ev):.1%}）")
print(f"  涉及机构         {sme_ev['机构名称'].nunique():,} 家")

ys = sme_ev[sme_ev["年份"] >= 2022].groupby("年份").agg(
    事件数=("docId", "size"),
    金额亿元=("罚没合计万元", lambda s: round(s.sum() / 1e4, 2)))
fig, ax1 = plt.subplots(figsize=(9.6, 4.2))
ax1.bar(ys.index.astype(str), ys["事件数"], color=C_ACCENT, alpha=0.85, width=0.55)
ax1.set_ylabel("中小企业信贷违规处罚（条）", color=C_ACCENT)
annotate_bars(ax1, "{:,.0f}")
ax1.set_title("中小企业信贷专项处罚的时间分布（2022–2026）", fontsize=13)
savefig(fig, "fig18_sme_trend"); plt.show()
display(ys.style)
''')

md(r"""
### 谁在为中小企业放贷时违规

注意这里的机构类型，回答的是**"哪一类放贷方在中小企业信贷上更容易出问题"**，
而不是"我们要研究这些银行"。研究对象仍是中小企业信贷这一业务本身。
""")
code(r'''
g = (sme_ev.groupby("机构类型")
     .agg(处罚条数=("docId", "size"),
          涉及机构=("机构名称", "nunique"),
          罚没万元=("罚没合计万元", "sum")))
g["罚没亿元"] = (g["罚没万元"] / 1e4).round(2)
g = g.sort_values("处罚条数")
display(g.drop(columns=["罚没万元"]).style.format({"罚没亿元": "{:.2f}"}))

fig, ax = plt.subplots(figsize=(9.6, 4.2))
ax.barh(g.index, g["处罚条数"], color=C_MAIN, alpha=0.88)
ax.set_xlabel("中小企业信贷违规处罚（条）")
ax.set_title("放贷方结构：农村中小银行与村镇银行合计占比最高", fontsize=12.5)
for i, v in enumerate(g["处罚条数"]):
    ax.text(v + 2, i, f"{v:,}", va="center", fontsize=9)
savefig(fig, "fig19_sme_org"); plt.show()

small = g.loc[[i for i in g.index if i in ("农村中小银行", "村镇银行", "城商行/其他银行", "民营银行")]]
display(Markdown(
    f"农村中小银行 + 村镇银行 + 城商行合计 "
    f"**{int(small['处罚条数'].sum()):,} 条**，"
    f"占中小企业信贷专项处罚的 "
    f"**{small['处罚条数'].sum()/g['处罚条数'].sum():.1%}**。"))
''')

md(r"""
### 违规发生在中小企业信贷的哪个环节

看违规性质，判断风险落在"看清企业"还是"放款之后"。
""")
code(r'''
vc = sme_ev["违规类型"].value_counts()
vc = vc[vc.index != "其他违规"]
fig, ax = plt.subplots(figsize=(9.6, 4.2))
bars = ax.barh(vc.index[::-1], vc.values[::-1],
               color=[C_ACCENT if "贷" in i or "信贷" in i else C_MID
                      for i in vc.index[::-1]], alpha=0.9)
ax.set_xlabel("处罚条数")
ax.set_title("中小企业信贷违规的环节分布", fontsize=13)
for i, v in enumerate(vc.values[::-1]):
    ax.text(v + 2, i, f"{v:,}", va="center", fontsize=9)
savefig(fig, "fig20_sme_violation"); plt.show()

display(Markdown(
    f"最高的是 **{vc.index[0]}（{vc.iloc[0]:,} 条，"
    f"占 {vc.iloc[0]/vc.sum():.1%}）**，其次是 "
    f"**{vc.index[1]}（{vc.iloc[1]:,} 条）**。"))
''')

md(r"""
### 中小企业信贷 vs 全部信贷处罚：结构差异

如果中小企业信贷的违规结构与"一般信贷处罚"不同，说明中小企业这一客群
确实有**独特的风险环节**，值得单独监管。
""")
code(r'''
bev_credit = da.bank_events()
bev_credit = bev_credit[bev_credit["信贷相关"] == 1]
a = sme_ev["违规类型"].value_counts(normalize=True)
b = bev_credit["违规类型"].value_counts(normalize=True)
keys = [k for k in a.index if k != "其他违规"][:7]
cmp_df = pd.DataFrame({
    "中小企业信贷": [a.get(k, 0) for k in keys],
    "全部信贷处罚": [b.get(k, 0) for k in keys],
}, index=keys)
cmp_df["差异(百分点)"] = ((cmp_df["中小企业信贷"] - cmp_df["全部信贷处罚"]) * 100).round(1)
display(cmp_df.style.format({"中小企业信贷": "{:.1%}",
                             "全部信贷处罚": "{:.1%}",
                             "差异(百分点)": "{:+.1f}"}))

fig, ax = plt.subplots(figsize=(10.5, 4.4))
x = np.arange(len(keys))
ax.bar(x - 0.2, cmp_df["中小企业信贷"] * 100, 0.4, label="中小企业信贷",
       color=C_ACCENT, alpha=0.9)
ax.bar(x + 0.2, cmp_df["全部信贷处罚"] * 100, 0.4, label="全部信贷处罚",
       color=C_MID, alpha=0.9)
ax.set_xticks(x); ax.set_xticklabels(keys, rotation=20, ha="right", fontsize=9)
ax.set_ylabel("占各自样本的比重（%）")
ax.set_title("结构差异：中小企业信贷更集中在哪些环节", fontsize=13)
ax.legend()
savefig(fig, "fig21_sme_vs_all"); plt.show()
''')

md(r"""
### 中小企业信贷违规的损失分布（在 SME 专项样本上做 LDA）

前面用的是"全部银行处罚"，这一页换成**只看中小企业信贷**的损失分布：
频率更高还是更低？单笔金额更小还是更大？99.9% VaR 是多少？
""")
code(r'''
q = pd.to_datetime(sme_ev["发布日期"], errors="coerce")
qc_sme = pd.Series(1, index=q[q.notna()]).resample("QE").sum().loc["2022-03-31":"2025-12-31"]
sev_sme = sme_ev["罚没合计万元"]
sev_sme = sev_sme[sev_sme > 0]

f_sme = lm.fit_frequency(qc_sme.values)
s_sme = lm.fit_severity(sev_sme.values)
mc_sme = lm.monte_carlo(f_sme, s_sme, n_sims=30000, periods_per_year=4, seed=42)

fig, ax = plt.subplots(figsize=(10, 4.2))
ax.hist(mc_sme["losses"] / 1e4, bins=70, color=C_ACCENT, alpha=0.75)
ax.axvline(mc_sme["var"] / 1e4, color="#1f4e79", lw=2.4,
           label=f"99.9% VaR = {mc_sme['var']/1e4:,.2f} 亿元")
ax.set_xlabel("年度损失（亿元）"); ax.set_ylabel("模拟频数")
ax.set_title("中小企业信贷违规的年度损失分布", fontsize=13)
ax.legend()
savefig(fig, "fig22_sme_var"); plt.show()

display(pd.DataFrame([
    ("季度事件均值 λ", f"{f_sme['lam']:.1f} 件"),
    ("频率分布", f_sme["kind"]),
    ("强度中位数（万元）", f"{s_sme['median']:,.1f}"),
    ("单笔金额中位数（万元）", f"{sev_sme.median():,.1f}"),
    ("99.9% VaR（亿元）", f"{mc_sme['var']/1e4:,.2f}"),
    ("年度均值（亿元）", f"{mc_sme['mean']/1e4:,.2f}"),
], columns=["中小企业信贷专项 LDA", "结果"]).style.hide(axis="index"))
''')

md(r"""
### 一个只有中小企业信贷才有的违规：小微企业划型不准确

银行为了完成小微企业贷款考核指标（"两增两控"），把不符合划型标准的企业
统计成小微企业 —— 这是**统计套利**，直接扭曲监管对中小企业融资的判断。

<div style="background:#fff4f4;border-left:4px solid #c00000;padding:9px 13px;border-radius:4px;font-size:0.92em;margin-top:8px">

这类违规不伤害单笔贷款，但它让"中小企业贷款余额"这个监管指标本身失真 ——
**是对监管信息基础的破坏，而非对银行资产质量的破坏。**

</div>
""")
code(r'''
mask = sme_ev["违法违规事实"].astype(str).str.contains("划型")
huaxing = sme_ev[mask]
print(f"涉及「划型」的处罚：{len(huaxing)} 条，"
      f"涉及机构 {huaxing['机构名称'].nunique()} 家，"
      f"罚没合计 {huaxing['罚没合计万元'].sum():,.0f} 万元")

display(huaxing[["年份", "机构名称", "违法违规事实", "处罚内容"]]
        .head(6).assign(违法违规事实=lambda d: d["违法违规事实"].astype(str).str[:60])
        .style.hide(axis="index"))

other = sme_ev[sme_ev["违法违规事实"].astype(str).str.contains("贷款用途|资金用途|挪用")]
print(f"\n对照：涉及「资金用途/挪用」的 {len(other)} 条")
''')

# ==================================================================== 22 结论
md(r"""
## 五、结论与监管建议

### 三个可检验的结论

<div style="background:#fff4f4;border-left:4px solid #c00000;padding:12px 16px;border-radius:4px">

**结论一 · 中小企业信贷的监管焦点在"过程"而非"结果"**
处罚事实中占比最高的是贷前调查不尽职与贷后管理不到位，
说明风险不是"贷错了企业"，而是"没看清企业"。

**结论二 · 罚款是真实损失的下界，尾部远比均值重要**
损失分布呈厚尾（ξ>0），99.9% VaR 显著高于年度均值；
但即便按 VaR 计，实测损失也只相当于监管操作风险资本的 0.2% 量级。
这不说明"资本充足"，而是说明**罚款只捕捉到监管可见的那一小部分损失**。

**结论三 · 监管资本计量与风险结构存在错配**
新标准法以业务指标 BI 为基数，对"规模小、违规密度高"的中小银行不敏感；
而单位营收的罚单数在中小机构显著更高 —— 这部分差异无法进入资本公式。

</div>

### 对监管与银行的三条建议

| 对象 | 建议 | 依据 |
|---|---|---|
| 监管 | 在操作风险监管中引入**违规密度**（单位营收罚单数/违规类型）作为差异化监管依据 | 违规密度与规模显著负相关 |
| 监管 | 处罚信息公开**字段化**（结构化而非列表/PDF），降低市场识别成本 | 本项目 3.7 万条的整理成本 |
| 银行 | 把贷前调查、贷后管理的**行为证据**纳入模型，重点补齐盈利能力+流动性之外的软信息 | 违规类型分布 + 变量重要性结果 |
""")

# ==================================================================== 22 局限
md(r"""
## 六、局限与后续方向

任何用公开数据做的风险计量都必须先自曝短板，否则结论不可信。
""")
code(r'''
lim = pd.DataFrame([
    ("罚款 ≠ 真实损失", "不含声誉损失、拨备、整改成本", "LDA 结果是下界，方向偏保守"),
    ("监管发现偏差", "罚单密度反映监管关注度", "不能用事件数直接推断真实风险分布"),
    ("样本为公示案件", "未公示/未处罚的违规不可观测", "存在系统性漏报"),
    ("企业样本为上市公司", "新三板/北交所 ≠ 银行真实小微客群", "模型需在银行内部数据上重估"),
    ("标签是财务困境代理", "非真实贷款违约", "AUC 只能说明相对识别能力"),
    ("BI 以营业总收入近似", "严格口径为利息+服务+金融资产", "资本要求略有高估"),
], columns=["局限", "说明", "对结论的影响"])
display(lim.style.hide(axis="index"))
''')

md(r"""
### 后续可扩展的方向

1. **处罚文本细粒度化**：把"贷款三查不到位"进一步拆成贷前/贷中/贷后三段，做环节级归因
2. **区域异质性**：按监管分局所在省份，检验东中西部中小银行的违规结构差异
3. **政策效应评估**：以 2024 年《商业银行资本管理办法》实施为断点，做双重差分
4. **与银行财务结合**：把处罚损失与不良率、拨备覆盖率联动，检验"违规是否领先于资产质量恶化"

<br>

<div style="text-align:center;color:#666;padding-top:20px">
汇报结束 · 欢迎提问
</div>
""")


def main() -> None:
    nb = nbf.v4.new_notebook()
    nb.cells = []
    for kind, src in cells:
        if kind == "md":
            nb.cells.append(nbf.v4.new_markdown_cell(src))
        else:
            cell = nbf.v4.new_code_cell(src)
            # 证据 cell 设成「独立一页」而不是 fragment。
            # 原因：fragment 在 RISE / reveal 里是"同页内隐藏→淡入"，
            # 图片、表格这类输出在淡入瞬间常白闪一次并被下一页顶掉，
            # 讲者必须回翻才能看到 —— 这就是"闪跳一下、得往回走"的原因。
            # 独立成页后：一次右移 = 一整页，无淡入、无回翻、无溢出。
            cell.metadata["slideshow"] = {"slide_type": "slide"}
            nb.cells.append(cell)
    # markdown 一律作为新的一页
    for c in nb.cells:
        if c.cell_type == "markdown":
            c.metadata["slideshow"] = {"slide_type": "slide"}
    nb.metadata.update({
        "kernelspec": {"display_name": "Python 3", "language": "python",
                       "name": "python3"},
        "language_info": {"name": "python", "version": "3.13"},
        "title": "中小企业经营信贷的监管剖析",
        # reveal 全局选项：关闭自动动画，避免内容"先闪后稳"
        "rise": {"autolaunch": False},
    })
    nbf.write(nb, str(OUT))
    n_md = sum(1 for c in nb.cells if c.cell_type == "markdown")
    n_code = sum(1 for c in nb.cells if c.cell_type == "code")
    print(f"已生成 {OUT}  （{len(nb.cells)} 个 cell：{n_md} md / {n_code} code）")
    print(f"放映页数：{n_md + n_code} 页（讲解页与证据页交替，一次右移 = 一整页）")


if __name__ == "__main__":
    main()
