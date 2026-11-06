# -*- coding: utf-8 -*-
"""3.3 重构为五步：①东财爬取 ②NFRA爬取 ③大模型NLP ④数据可视化 ⑤只用XGBoost，各配 md。
   只动 3.3（cell 23 之后到「四、结论」之前）；四、结论里结论一改为 XGBoost 口径。"""
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

# 复用现有「企业侧」东财代码
firm_idx = next(i for i, c in enumerate(cells) if "datacenter.eastmoney" in src(c))
FIRM_CODE = src(cells[firm_idx])

MD1 = """#### 第一步：爬取东方财富——中小企业财务面板

接口 `datacenter.eastmoney.com`（F10 主要财务指标，`RPT_F10_FINANCE_MAINFINADATA`）。
抓取新三板（含北交所）**679 家**中小企业的财务数据：营收、净利润、资产负债率、ROE、流动比率等。

> 演示实时抓 5 家；全量面板在本地 `data/processed/firm_panel.csv`（4,060 企业-年）。
"""

NFRA_CODE = '''# 第二步：爬取 NFRA——监管处罚公示（被限流时回退本地缓存）
import json, time, urllib.request

_UA_NFRA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

def _get_nfra(url, timeout=25):
    req = urllib.request.Request(url, headers={**_UA_NFRA, "Referer": "http://www.nfra.gov.cn/"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8-sig", "ignore"))

def crawl_page(page, page_size=10):
    d = _get_nfra("http://www.nfra.gov.cn/cbircweb/DocInfo/SelectDocByItemIdAndChild"
                  f"?itemId=4293&pageSize={page_size}&pageIndex={page}")
    out = []
    for r in d["data"]["rows"]:
        try:
            detail = _get_nfra("http://www.nfra.gov.cn/cbircweb/DocInfo/SelectByDocId"
                               f"?docId={r['docId']}")["data"]
        except Exception:
            detail = {}
        out.append({"docId": r["docId"],
                    "标题": r.get("docTitle") or r.get("docSubtitle") or "",
                    "日期": str(r.get("publishDate") or "")[:10],
                    "正文": detail.get("docClob") or ""})
    return out

try:
    _rows = crawl_page(1, page_size=10)
    _nfra_ok = True
    display(Markdown(f"NFRA 第 1 页抓到 **{len(_rows)} 条**处罚公示"))
    display(pd.DataFrame(_rows)[["docId", "标题", "日期"]])
except Exception as e:
    _nfra_ok = False
    _ev = da.events()
    _rows = [{"docId": r.docId, "标题": r["标题"], "日期": r["发布日期"],
              "正文": str(r["违法违规事实"])}
             for r in _ev.sample(10, random_state=7).itertuples()]
    display(Markdown(f"⚠️ NFRA 接口被 WAF 限流（`{type(e).__name__}`），改用本地缓存 "
                     f"`events_all.csv` 抽 10 条继续。"))
    display(pd.DataFrame(_rows)[["docId", "标题", "日期"]])
'''

MD2 = """#### 第二步：爬取 NFRA——监管处罚公示

接口 `www.nfra.gov.cn/cbircweb/...`（目录 `SelectDocByItemIdAndChild` + 详情 `SelectByDocId`）。
累计抓取 **29,859 期**（总局 661 + 派出 29,198），解析出 **37,236 条**处罚记录。

> ⚠️ 该接口可能被 WAF 限流（403）；代码已做回退，失败自动用本地缓存。
"""

LLM_CODE = '''# 第三步：丢给大模型做自然语言处理——逐条判断「是否与中小企业信贷有关」
import json, time, urllib.request
try:
    from llm_config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
except ImportError:
    import os
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"
    DEEPSEEK_MODEL = "deepseek-chat"

def _ask_sme(title, text):
    prompt = (
        "下面是金融监管的一条处罚公示。请判断它是否与**中小企业信贷**直接相关"
        "（涉及小微/普惠/个体工商户/经营贷/涉农等客群，且与信贷业务有关）。"
        '只输出 JSON：{"有关": true 或 false, "理由": "一句话"}\\n\\n'
        f"标题：{title}\\n正文：{str(text)[:1000]}"
    )
    payload = {"model": DEEPSEEK_MODEL,
               "messages": [{"role": "system", "content": "你是金融监管文本判断助手，只输出严格 JSON。"},
                            {"role": "user", "content": prompt}],
               "temperature": 0, "max_tokens": 200, "stream": False}
    req = urllib.request.Request(f"{DEEPSEEK_BASE_URL}/chat/completions",
                                 data=json.dumps(payload).encode("utf-8"),
                                 headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read().decode("utf-8"))
    ans = resp["choices"][0]["message"]["content"]
    import re
    m = re.search(r"\\{.*\\}", ans, re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}

_picked = []
t0 = time.time()
for r in _rows:
    rec = _ask_sme(r["标题"], r["正文"])
    r.update(rec)
    if rec.get("有关"):
        _picked.append(r)

_sme_df = pd.DataFrame(_picked)
if len(_sme_df):
    _sme_df[["docId", "标题", "日期", "理由"]].to_csv(
        "data/processed/llm_sme_selected.csv", index=False, encoding="utf-8-sig")
display(Markdown(f"大模型逐条判断：**{len(_picked)} / {len(_rows)}** 条与中小企业信贷有关，"
                 f"已落本地 `data/processed/llm_sme_selected.csv`（耗时 {time.time()-t0:.1f}s）"))
if len(_sme_df):
    display(_sme_df[["docId", "标题", "理由"]])
else:
    display(Markdown("本批未命中（中小企业信贷只占全部约 2%）；全量口径用关键词筛出的 745 条，见下一步。"))
'''

MD3 = """#### 第三步：丢给大模型做自然语言处理

把处罚正文交给 DeepSeek，逐条判断"是否与中小企业信贷有关"，**只把有关的落本地**。

> 大模型只做"从真实文本抽取/判断"，输出可逐条对照原文——是可验证的 NLP，不是凭空生成。
"""

VIS_CODE = '''# 第四步：数据可视化——中小企业信贷专项（745 条）
sme_ev = da.sme_credit_events()
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

vc = sme_ev["违规类型"].value_counts()
vc = vc[vc.index != "其他违规"]
fig, ax = plt.subplots(figsize=(9.6, 4.2))
ax.barh(vc.index[::-1], vc.values[::-1],
        color=[C_ACCENT if "贷" in i or "信贷" in i else C_MID for i in vc.index[::-1]], alpha=0.9)
ax.set_xlabel("处罚条数")
ax.set_title("中小企业信贷违规集中在哪个环节", fontsize=13)
for i, v in enumerate(vc.values[::-1]):
    ax.text(v + 2, i, f"{v:,}", va="center", fontsize=9)
savefig(fig, "fig20_sme_violation"); plt.show()

display(Markdown(f"中小企业信贷专项共 **{len(sme_ev):,} 条**（占全部处罚 2.0%），"
                 f"最高的是 **{vc.index[0]}（{vc.iloc[0]:,} 条）**。"))
'''

MD4 = """#### 第四步：数据可视化

用筛出的 **745 条中小企业信贷专项处罚**画两件事：
1. **时间趋势**：监管对中小企业信贷的关注变化；
2. **环节分布**：风险落在"看清企业"还是"放款之后"。
"""

XGB_CODE = '''# 第五步：只用 XGBoost 建模——中小企业违约识别
import default_model as dm
from sklearn.metrics import roc_auc_score

panel = dm.build_panel(da.firm_panel())
feat = [c for c in dm.FEATURES if c in panel.columns]
X = panel[feat].replace([np.inf, -np.inf], np.nan)
y = panel["distress"].astype(int)
mask = X.notna().sum(axis=1) > len(feat) * 0.5
Xm, ym = X[mask], y[mask]

gb = dm.fit_gbm(Xm, ym)
s_gb = gb["proba"]
display(Markdown(f"样本 **{len(Xm):,}** 条；**{gb['backend']}** AUC **{roc_auc_score(ym, s_gb):.4f}**，"
                 f"KS **{dm.ks_stat(ym, s_gb):.4f}**"))

fig, ax = plt.subplots(figsize=(7.5, 5.2))
fpr, tpr, _, _ = dm.ks_curve(ym, s_gb)
ax.plot(fpr, tpr, lw=2.4, color=C_ACCENT,
        label=f"{gb['backend']}  AUC={roc_auc_score(ym, s_gb):.3f}  KS={dm.ks_stat(ym, s_gb):.3f}")
ax.plot([0, 1], [0, 1], ls=":", color="#999")
ax.set_xlabel("假正例率 FPR"); ax.set_ylabel("真正例率 TPR")
ax.set_title("XGBoost 违约识别 ROC", fontsize=13)
ax.legend(loc="lower right")
savefig(fig, "fig13_roc"); plt.show()

imp = pd.Series(gb["model"].feature_importances_, index=gb["features"]).sort_values(ascending=False)
top = imp.head(12)[::-1]
labels = [dm.FEATURE_CN.get(k, k) for k in top.index]
fig, ax = plt.subplots(figsize=(9, 4.6))
ax.barh(labels, top.values, color=C_MAIN, alpha=0.88)
ax.set_title("XGBoost 特征重要度 Top12", fontsize=13)
for i, v in enumerate(top.values):
    ax.text(v, i, f" {v:.4f}", va="center", fontsize=8.8)
savefig(fig, "fig15_imp"); plt.show()
'''

MD5 = """#### 第五步：只用 XGBoost 建模

特征 = 中小企业财务指标（t 年）；标签 = 下一年是否困境（t+1 **严格前视**，防循环定义）。
**只用一个 XGBoost**：训练 → ROC/AUC → 特征重要度，不再堆多个模型。
"""

MD_CONC = """#### 评估结论

XGBoost 在 679 家中小企业财务面板上，用 t 年特征预测 t+1 年困境：
**AUC≈0.96**，最重要的特征集中在**盈利能力与偿债能力**（ROE、销售净利率、资产负债率…），
与信贷专家"中小企业风险源于盈利与现金流脆弱"的判断一致。
"""

new_33 = [
    cells[23],
    md(MD1), code(FIRM_CODE),
    md(MD2), code(NFRA_CODE),
    md(MD3), code(LLM_CODE),
    md(MD4), code(VIS_CODE),
    md(MD5), code(XGB_CODE),
    md(MD_CONC),
]

# 保留「四、结论」及之后，但结论一改成 XGBoost 口径
tail = cells[62:]
for c in tail:
    s = src(c)
    if "Z′（AUC≈0.66）→ 评分卡（0.84）→ 机器学习（XGBoost，0.957）" in s:
        c["source"] = s.replace(
            "Z′（AUC≈0.66）→ 评分卡（0.84）→ 机器学习（XGBoost，0.957）",
            "XGBoost 单模型 AUC≈0.96")
        print("核心结论回顾已改 XGBoost 口径")

nb["cells"] = cells[:23] + new_33 + tail
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("done, cells =", len(nb["cells"]))
