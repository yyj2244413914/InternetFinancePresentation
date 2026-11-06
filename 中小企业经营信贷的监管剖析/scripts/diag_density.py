# -*- coding: utf-8 -*-
"""诊断 v2：正确的机构名归并 + 法人层级口径的资本与密度对比"""
import sys
sys.path.insert(0, r"E:\互联网金融\复现项目\src")
import numpy as np
import pandas as pd
from scipy import stats

import data_access as da
import lda_model as lm


def norm(s):
    """只去掉公司形式后缀，保留“中国/工商”等识别词。"""
    s = str(s)
    for x in ("股份有限公司", "有限责任公司", "有限公司", "股份", "集团"):
        s = s.replace(x, "")
    return s.strip()


fin = da.bank_fin().dropna(subset=["gi_avg3"]).copy()
fin["key"] = fin["name"].map(norm)
ev = da.events().copy()
ev["_org"] = ev["机构名称"].astype(str).map(norm)

legal = ev[ev["机构层级"] == "法人/总部"].copy()
print("全部事件", len(ev), "| 法人层级事件", len(legal))

keymap = dict(zip(fin["key"], zip(fin["name"], fin["bank_type"], fin["gi_avg3"])))


def match_org(x):
    if not x:
        return None
    if x in keymap:
        return keymap[x]
    for k, v in keymap.items():
        if len(k) >= 4 and (x.startswith(k) or k.startswith(x) and len(x) >= 4):
            return v
    return None


legal["_hit"] = legal["_org"].apply(match_org)
hit = legal[legal["_hit"].notna()].copy()
hit["bank_name"] = hit["_hit"].apply(lambda t: t[0])
hit["bank_type"] = hit["_hit"].apply(lambda t: t[1])
hit["gi"] = hit["_hit"].apply(lambda t: t[2])
print("匹配到上市银行的法人层级事件", len(hit), "| 涉及", hit["bank_name"].nunique(), "家")
print(hit["bank_type"].value_counts().to_string())

dens = hit.groupby(["bank_name", "bank_type", "gi"]).size().reset_index(name="罚单数")
dens["密度"] = dens["罚单数"] / dens["gi"] * 100
print()
print("按类型的违规密度（每百亿营收罚单数）")
print(dens.groupby("bank_type")["密度"].agg(["count", "median", "mean", "max"])
      .round(2).to_string())
print()
print("密度 Top10")
print(dens.nlargest(10, "密度")[["bank_name", "bank_type", "gi", "罚单数", "密度"]]
      .round(2).to_string(index=False))
rho, p = stats.spearmanr(dens["gi"], dens["密度"])
print(f"\n规模 vs 密度 Spearman rho={rho:.3f} p={p:.4f}")

sme = dens[dens["bank_type"].isin(["城商行", "农商行"])]
big = dens[dens["bank_type"].isin(["国有大型银行", "股份制银行"])]
print(f"中小银行密度 中位数 {sme['密度'].median():.2f} 均值 {sme['密度'].mean():.2f} n={len(sme)}")
print(f"大行股份行 中位数 {big['密度'].median():.2f} 均值 {big['密度'].mean():.2f} n={len(big)}")
if len(sme) > 2 and len(big) > 2:
    print("Mann-Whitney p =", round(float(stats.mannwhitneyu(
        sme["密度"], big["密度"], alternative="greater").pvalue), 4))

# 中小银行法人组合 LDA
sm = hit[hit["bank_type"].isin(["城商行", "农商行"])]
q = pd.to_datetime(sm["发布日期"], errors="coerce")
qc = pd.Series(1, index=q[q.notna()]).resample("QE").sum().loc["2022-03-31":"2025-12-31"]
sev = sm["罚没合计万元"]
sev = sev[sev > 0]
print(f"\n中小银行法人事件 {len(sm)} 条 | 完整季度 {len(qc)} | 有金额 {len(sev)}")
sf = fin[fin["bank_type"].isin(["城商行", "农商行"])]
bia = sf["gi_avg3"].apply(lambda g: lm.capital_bia([g], 0.15))
sa = sf["gi_avg3"].apply(lambda g: lm.capital_sa_bis(g)[0])
print(f"城商/农商 {len(sf)} 家, BIA 合计 {bia.sum():.1f} 亿, SA 合计 {sa.sum():.1f} 亿")
print(f"单家年均罚没 {sm['罚没合计万元'].sum()/4/max(len(sf),1):.0f} 万元")
if len(qc) >= 8 and len(sev) >= 40:
    f = lm.fit_frequency(qc.values)
    s = lm.fit_severity(sev.values)
    mc = lm.monte_carlo(f, s, n_sims=30000, periods_per_year=4, seed=42)
    print(f"VaR99.9 {mc['var']/1e4:.2f} 亿元 | 均值 {mc['mean']/1e4:.2f} 亿元 "
          f"| VaR/BIA {mc['var']/1e4/bia.sum():.3%}")
    print(f"频率 {f['kind']} lam={f['lam']:.1f} 强度 mu={s['mu']:.2f} sigma={s['sigma']:.2f}")
