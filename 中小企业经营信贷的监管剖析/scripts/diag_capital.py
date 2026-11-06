# -*- coding: utf-8 -*-
"""临时诊断：组合级资本对比与模型绩效（避免命令行引号问题）"""
import sys
sys.path.insert(0, r"E:\互联网金融\复现项目\src")
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import data_access as da
import default_model as dm
import lda_model as lm


def norm(s):
    return (str(s).replace("股份有限公司", "").replace("有限公司", "")
            .replace("股份", "").replace("中国", ""))


fin = da.bank_fin().dropna(subset=["gi_avg3"])
sme = fin[fin["bank_type"].isin(["城商行", "农商行"])].copy()
names = [norm(n) for n in sme["name"]]

ev = da.events().copy()
ev["_org"] = ev["机构名称"].astype(str).map(norm)
mask = ev["_org"].apply(lambda x: any(n and n in x for n in names))
matched = ev[mask]
print("匹配事件", len(matched), "涉及机构", matched["机构名称"].nunique(),
      "其中中小银行", int(matched["是否中小银行"].sum()))

q = pd.to_datetime(matched["发布日期"], errors="coerce")
qc = pd.Series(1, index=q[q.notna()]).resample("QE").sum().loc["2022-03-31":"2025-12-31"]
sev = matched["罚没合计万元"]
sev = sev[sev > 0]
f = lm.fit_frequency(qc.values)
s = lm.fit_severity(sev.values)
mc = lm.monte_carlo(f, s, n_sims=30000, periods_per_year=4, seed=42)

bia = sme["gi_avg3"].apply(lambda g: lm.capital_bia([g], 0.15))
sa = sme["gi_avg3"].apply(lambda g: lm.capital_sa_bis(g)[0])

print("季度数", len(qc), "季度均值", round(qc.mean(), 1), "强度样本", len(sev))
print("VaR99.9 亿元", round(mc["var"] / 1e4, 2), "均值 亿元", round(mc["mean"] / 1e4, 2))
print("家数", len(sme))
print("BIA 合计亿元", round(bia.sum(), 1), "SA 合计亿元", round(sa.sum(), 1))
print("VaR/BIA 比例", format(mc["var"] / 1e4 / bia.sum(), ".4%"))
print("VaR/SA 比例", format(mc["var"] / 1e4 / sa.sum(), ".4%"))
print("单家 BIA 中位数亿元", round(bia.median(), 2), " 单家 SA 中位数", round(sa.median(), 2))
print("单家年均罚没（万元）", round(matched["罚没合计万元"].sum() / 4 / len(sme), 1))
print("单家罚没 / 单家营收(gi_avg3亿元)", format(
    (matched["罚没合计万元"].sum() / 4 / len(sme) / 1e4) / sme["gi_avg3"].mean(), ".4%"))

print()
panel = dm.build_panel(da.firm_panel())
feat = [c for c in dm.FEATURES if c in panel.columns]
X = panel[feat].replace([np.inf, -np.inf], np.nan)
y = panel["distress"].astype(int)
sz = -panel["Z_score"].fillna(panel["Z_score"].median())
sc = dm.fit_scorecard(X, y)
gb = dm.fit_gbm(X, y)
print("样本", len(panel), "困境率", round(y.mean(), 4))
for nm, s_ in [("Altman Z", sz), ("评分卡", sc["proba"]), (gb["backend"], gb["proba"])]:
    print("  ", nm, "AUC", round(roc_auc_score(y, s_), 4),
          "KS", round(dm.ks_stat(y, s_), 4))
print("入模变量", len(sc["keep"]))
print("IV top5", [(dm.FEATURE_CN.get(k, k), round(v, 3))
                  for k, v in sc["iv"].head(5).items()])
imp, engine, _ = dm.shap_or_perm(gb["model"], X[gb["features"]], top=8)
print("重要性引擎", engine)
print("Top8", [(dm.FEATURE_CN.get(k, k), round(v, 4)) for k, v in imp.items()])

# 分年 AUC 稳定性（按年份分组 CV）
from sklearn.model_selection import GroupKFold
aucs = []
for tr, te in GroupKFold(n_splits=4).split(X, y, panel["year"]):
    m = dm.fit_gbm(X.iloc[tr], y.iloc[tr])["model"]
    p = m.predict_proba(X.iloc[te].fillna(0))[:, 1]
    if y.iloc[te].nunique() > 1:
        aucs.append(roc_auc_score(y.iloc[te], p))
print("分组CV AUC", [round(a, 3) for a in aucs], "均值", round(float(np.mean(aucs)), 4))
