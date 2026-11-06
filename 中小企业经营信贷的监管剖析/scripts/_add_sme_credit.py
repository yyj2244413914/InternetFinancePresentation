# -*- coding: utf-8 -*-
"""3.3 补充：加回「只与中小企业信贷相关」的处罚分析 + 大模型从真实正文抽取。只动 3.3。"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "汇报_中小企业经营信贷的监管剖析.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))
cells = nb["cells"]

def src(c):
    return "".join(c.get("source", []))

def md(text):
    return {"cell_type": "markdown", "metadata": {"slideshow": {"slide_type": "subslide"}}, "source": text}

def code(text):
    return {"cell_type": "code", "metadata": {"slideshow": {"slide_type": "subslide"}},
            "source": text, "outputs": [], "execution_count": None}

# 找到「企业侧」那个 cell
idx_firm = next(i for i, c in enumerate(cells) if "# 企业侧：实时抓取" in src(c))
print("企业侧 cell:", idx_firm)

new_cells = [
    md("""#### 监管侧：只抓与「中小企业信贷」有关的处罚

被处罚主体必然是银行（监管处罚不会开给企业），所以关键在于**筛选条件**：
事由中**明确出现中小企业客群表述**——小微 / 普惠 / 中小企业 / 个体工商户 /
涉农 / 农户 / 经营贷 / 支农支小 / 创业担保贷 等——**且**与信贷相关。

这样得到的才是"因为给中小企业放贷而出的事"，而不是"银行的所有违规"。
"""),
    code('''sme_ev = da.sme_credit_events()
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
'''),
    md("""### 谁在为中小企业放贷时违规

注意这里的机构类型，回答的是**"哪一类放贷方在中小企业信贷上更容易出问题"**，
而不是"我们要研究这些银行"。研究对象仍是中小企业信贷这一业务本身。
"""),
    code('''g = (sme_ev.groupby("机构类型")
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
'''),
    md("""### 违规发生在中小企业信贷的哪个环节

看违规性质，判断风险落在"看清企业"还是"放款之后"。
"""),
    code('''vc = sme_ev["违规类型"].value_counts()
vc = vc[vc.index != "其他违规"]
fig, ax = plt.subplots(figsize=(9.6, 4.2))
ax.barh(vc.index[::-1], vc.values[::-1],
        color=[C_ACCENT if "贷" in i or "信贷" in i else C_MID for i in vc.index[::-1]], alpha=0.9)
ax.set_xlabel("处罚条数")
ax.set_title("中小企业信贷违规的环节分布", fontsize=13)
for i, v in enumerate(vc.values[::-1]):
    ax.text(v + 2, i, f"{v:,}", va="center", fontsize=9)
savefig(fig, "fig20_sme_violation"); plt.show()

display(Markdown(
    f"最高的是 **{vc.index[0]}（{vc.iloc[0]:,} 条，占 {vc.iloc[0]/vc.sum():.1%}）**，"
    f"其次是 **{vc.index[1]}（{vc.iloc[1]:,} 条）**。"))
'''),
    md("""### 中小企业信贷 vs 全部信贷处罚：结构差异

如果中小企业信贷的违规结构与"一般信贷处罚"不同，说明中小企业这一客群
确实有**独特的风险环节**，值得单独监管。
"""),
    code('''bev_credit = da.bank_events()
bev_credit = bev_credit[bev_credit["信贷相关"] == 1]
a = sme_ev["违规类型"].value_counts(normalize=True)
b = bev_credit["违规类型"].value_counts(normalize=True)
keys = [k for k in a.index if k != "其他违规"][:7]
cmp_df = pd.DataFrame({
    "中小企业信贷": [a.get(k, 0) for k in keys],
    "全部信贷处罚": [b.get(k, 0) for k in keys],
}, index=keys)
cmp_df["差异(百分点)"] = ((cmp_df["中小企业信贷"] - cmp_df["全部信贷处罚"]) * 100).round(1)
display(cmp_df.style.format({"中小企业信贷": "{:.1%}", "全部信贷处罚": "{:.1%}",
                             "差异(百分点)": "{:+.1f}"}))
fig, ax = plt.subplots(figsize=(10.5, 4.4))
x = np.arange(len(keys))
ax.bar(x - 0.2, cmp_df["中小企业信贷"] * 100, 0.4, label="中小企业信贷", color=C_ACCENT, alpha=0.9)
ax.bar(x + 0.2, cmp_df["全部信贷处罚"] * 100, 0.4, label="全部信贷处罚", color=C_MID, alpha=0.9)
ax.set_xticks(x); ax.set_xticklabels(keys, rotation=20, ha="right", fontsize=9)
ax.set_ylabel("占各自样本的比重（%）")
ax.set_title("结构差异：中小企业信贷更集中在哪些环节", fontsize=13)
ax.legend()
savefig(fig, "fig21_sme_vs_all"); plt.show()
'''),
    md("""### 一个只有中小企业信贷才有的违规：小微企业划型不准确

银行为了完成小微企业贷款考核指标（"两增两控"），把不符合划型标准的企业统计成小微——
这是**统计套利**，直接扭曲监管对中小企业融资的判断。
"""),
    code('''mask = sme_ev["违法违规事实"].astype(str).str.contains("划型")
huaxing = sme_ev[mask]
print(f"涉及「划型」的处罚：{len(huaxing)} 条，涉及机构 {huaxing['机构名称'].nunique()} 家，"
      f"罚没合计 {huaxing['罚没合计万元'].sum():,.0f} 万元")
display(huaxing[["年份", "机构名称", "违法违规事实", "处罚内容"]]
        .head(6).assign(违法违规事实=lambda d: d["违法违规事实"].astype(str).str[:60])
        .style.hide(axis="index"))
'''),
    md("""### 大模型：从真实处罚正文里抽取字段（有效数据）

不是让模型"编"政策，而是把**一条真实的处罚正文**喂给它，让模型只做**结构化抽取**——
输出能逐条对照原文，才算有效数据。
"""),
    code('''import json, time, urllib.request
try:
    from llm_config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
except ImportError:
    import os
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"
    DEEPSEEK_MODEL = "deepseek-chat"

_sample = sme_ev[sme_ev["违法违规事实"].astype(str).str.len() > 30].iloc[0]
_text = str(_sample["违法违规事实"])[:1200]

prompt = (
    "下面是一条真实的金融监管处罚事实（针对银行给中小企业放贷）。"
    "请抽取结构化字段，只输出 JSON，不要解释：\\n"
    '{"违规环节":"贷前调查/贷款审批/贷款发放/贷后管理 之一",'
    '"违规类型":"一句话",'
    '"中小企业客群":true 或 false}\\n\\n'
    f"文本：{_text}"
)

payload = {
    "model": DEEPSEEK_MODEL,
    "messages": [
        {"role": "system", "content": "你是金融监管文本抽取助手，只输出严格 JSON。"},
        {"role": "user", "content": prompt},
    ],
    "temperature": 0,
    "max_tokens": 300,
    "stream": False,
}

try:
    t0 = time.time()
    req = urllib.request.Request(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read().decode("utf-8"))
    ans = resp["choices"][0]["message"]["content"]
    import re
    m = re.search(r"\\{.*\\}", ans, re.S)
    rec = json.loads(m.group(0)) if m else {}
    display(Markdown(f"**大模型抽取**（{resp.get('model', DEEPSEEK_MODEL)}，{time.time()-t0:.2f}s）"))
    display(pd.DataFrame([rec]))
    display(Markdown(f"> 原文（节选）：{_text[:180]}…"))
except Exception as e:
    display(Markdown(f"⚠️ 大模型接口不可达（`{type(e).__name__}`），本步跳过。"))
'''),
]

# 插到「企业侧」之后
cells[idx_firm + 1:idx_firm + 1] = new_cells

# 更新第一部分说明表
for c in cells:
    s = src(c)
    if s.startswith("#### 第一部分：数据挖掘"):
        c["source"] = """#### 第一部分：数据挖掘

本示例服务一个目标：**识别中小企业信贷风险**。数据只取与中小企业直接相关的部分：

| 数据 | 来源 | 规模 | 用途 |
|---|---|---|---|
| 中小企业财务面板 | 东方财富 `datacenter`（实时） | 679 家 × 约 6 年 | 企业侧特征 |
| 中小企业信贷处罚 | 金融监管总局（筛选后） | **745 条**（占全部 2.0%） | 监管侧证据：只留"因中小企业信贷而出的事" |
| 违约标签 | 由面板构造（t+1 严格前视） | — | 建模标签 |
| 大模型抽取 | DeepSeek（从真实处罚正文） | 1 条演示 | 结构化字段（可核对） |
"""
        print("第一部分说明表已更新")
        break

nb["cells"] = cells
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("done, cells =", len(cells))
