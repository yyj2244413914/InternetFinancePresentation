# -*- coding: utf-8 -*-
"""
default_model —— 中小企业违约识别模型（B 线）
============================================
样本：新三板/北交所挂牌公司财务面板（firm_panel.csv）
标签：下一年度发生「资不抵债 / 连续亏损 / ST」→ 1

模型阶梯（对应汇报 S14–S16）
  ① Altman Z'（账面权益口径，直接套原始系数，不重新估计）
  ② Logistic + WOE/IV 评分卡（自建分箱，刻度 600/PDO=20）
  ③ XGBoost（若未安装则退化为 sklearn GradientBoosting）
  ④ 可解释性：SHAP（若未安装则用 permutation importance）

防泄漏约定
  · 特征取 t 年，标签取 t+1 年
  · 交叉验证按「年份」分组（GroupKFold），禁止随机拆分
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import GroupKFold

RANDOM_STATE = 42

FEATURES = [
    "ZCFZL", "LD", "SD", "XJLLB", "XSMLL", "XSJLL", "ROEJQ", "ROIC", "ZZCJLL",
    "INTSTCOVRATE", "TOAZZL", "YSZKZZL", "CHZZL",
    "TOTALOPERATEREVETZ", "PARENTNETPROFITTZ", "OI_YOYRATIO_PK", "TA_YOYRATIO_PK",
    "log_assets", "ocf_to_liab", "x1_wc_ta", "x2_re_ta", "x3_ebit_ta",
    "x4_equity_tl", "x5_sales_ta",
]
FEATURE_CN = {
    "ZCFZL": "资产负债率", "LD": "流动比率", "SD": "速动比率", "XJLLB": "现金流量比率",
    "XSMLL": "销售毛利率", "XSJLL": "销售净利率", "ROEJQ": "加权ROE", "ROIC": "投入资本回报率",
    "ZZCJLL": "总资产净利率", "INTSTCOVRATE": "利息保障倍数", "TOAZZL": "总资产周转率",
    "YSZKZZL": "应收账款周转率", "CHZZL": "存货周转率",
    "TOTALOPERATEREVETZ": "营收同比增速", "PARENTNETPROFITTZ": "净利同比增速",
    "OI_YOYRATIO_PK": "营收同比(快照)", "TA_YOYRATIO_PK": "总资产同比",
    "log_assets": "总资产对数", "ocf_to_liab": "经营现金流/总负债",
    "x1_wc_ta": "X1 营运资金/总资产", "x2_re_ta": "X2 留存收益/总资产",
    "x3_ebit_ta": "X3 EBIT/总资产", "x4_equity_tl": "X4 账面权益/总负债",
    "x5_sales_ta": "X5 营业收入/总资产",
}


# ---------------------------------------------------------------- 特征工程
def build_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """构造 Z' 五变量 + 派生财务特征，并生成下一年标签。"""
    df = panel.copy()
    ta = df["TOTAL_ASSETS_PK"].replace(0, np.nan)
    tl = df["LIABILITY"].replace(0, np.nan)

    ca = df["CA_TA"] / 100 * ta                      # 流动资产
    cl = df["CL_TL"] / 100 * tl                      # 流动负债
    df["x1_wc_ta"] = (ca - cl) / ta
    df["x2_re_ta"] = (df["MGWFPLR"].fillna(0) * df["TOTAL_SHARE"]) / ta
    df["x3_ebit_ta"] = (df["PER_EBIT"].fillna(0) * df["TOTAL_SHARE"]) / ta
    df["x4_equity_tl"] = df["TOTAL_EQUITY_PK"] / tl
    df["x5_sales_ta"] = df["TOTALOPERATEREVE"] / ta
    df["log_assets"] = np.log(ta.clip(lower=1))
    df["ocf_to_liab"] = df["NETCASH_OPERATE_PK"] / tl

    # Altman Z'（账面权益口径，避免使用当期市值造成前视偏差）
    df["Z_score"] = (1.2 * df["x1_wc_ta"] + 1.4 * df["x2_re_ta"]
                     + 3.3 * df["x3_ebit_ta"] + 0.6 * df["x4_equity_tl"]
                     + 1.0 * df["x5_sales_ta"])

    # 下一年标签（严格前视：只用 t+1 年信息，避免与 t 年特征循环定义）
    df = df.sort_values(["code", "year"])
    nxt = df.groupby("code")[["ZCFZL", "PARENTNETPROFIT"]].shift(-1)
    nxt.columns = ["next_zcfzl", "next_profit"]
    df = pd.concat([df, nxt], axis=1)
    df["flag_debt"] = (df["next_zcfzl"] >= 100).astype(int)      # 下一年资不抵债
    df["flag_loss"] = (df["next_profit"] < 0).astype(int)        # 下一年亏损
    # 标签只取 t+1 年状态：'连续两年亏损'会把 t 年利润拖进标签，
    # 而 t 年利润同时是特征，造成循环定义，故不予采用。
    df["distress"] = ((df["flag_debt"] + df["flag_loss"]) > 0).astype(int)
    # 没有下一年数据的样本不能当负样本，直接剔除
    df = df[df["next_zcfzl"].notna() & df["next_profit"].notna()]
    return df.reset_index(drop=True)


def zscore_label(z: pd.Series) -> pd.Series:
    """Altman 判别区间：Z' > 2.9 安全，1.23–2.9 灰色，< 1.23 困境。"""
    return pd.cut(z, bins=[-np.inf, 1.23, 2.9, np.inf],
                  labels=["困境区", "灰色区", "安全区"])


# ---------------------------------------------------------------- 评估指标
def ks_stat(y_true, y_score) -> float:
    fpr, tpr, _ = roc_curve(y_true, y_score)
    return float(np.max(tpr - fpr))


def evaluate(y_true, y_score, names=("AUC", "KS")) -> dict:
    return {names[0]: float(roc_auc_score(y_true, y_score)),
            names[1]: ks_stat(y_true, y_score)}


def ks_curve(y_true, y_score):
    fpr, tpr, thr = roc_curve(y_true, y_score)
    ks_idx = int(np.argmax(tpr - fpr))
    return fpr, tpr, thr, ks_idx


# ---------------------------------------------------------------- WOE / IV 评分卡
def _bin_edges(s: pd.Series, q: int = 5, min_count: int = 40) -> np.ndarray:
    """分箱边界：在保证每箱样本量的前提下做等频分箱，避免小样本导致 IV 虚高。"""
    v = s.dropna()
    if v.empty:
        return np.array([-np.inf, 0, np.inf])
    n = len(v)
    qq = max(2, min(q, n // max(min_count, 1)))
    edges = np.unique(v.quantile(np.linspace(0, 1, qq + 1)).values)
    if len(edges) < 3:
        med = float(v.median())
        edges = np.array([-np.inf, med, np.inf]) if v.max() > med else np.array(
            [-np.inf, np.inf])
    edges[0], edges[-1] = -np.inf, np.inf
    return np.unique(edges)


def woe_iv(x: pd.Series, y: pd.Series, q: int = 5) -> tuple[pd.DataFrame, float, np.ndarray]:
    edges = _bin_edges(x, q)
    bins = pd.cut(x, bins=edges, duplicates="drop")
    d = pd.DataFrame({"bin": bins, "y": y.values})
    g = d.groupby("bin", observed=True)["y"].agg(["count", "sum"])
    g["bad"] = g["sum"].clip(lower=0.5)
    g["good"] = (g["count"] - g["sum"]).clip(lower=0.5)
    tot_bad, tot_good = g["bad"].sum(), g["good"].sum()
    g["bad_rate"] = g["sum"] / g["count"]
    g["woe"] = np.log((g["bad"] / tot_bad) / (g["good"] / tot_good))
    g["iv_part"] = (g["bad"] / tot_bad - g["good"] / tot_good) * g["woe"]
    return g[["count", "bad_rate", "woe", "iv_part"]], float(g["iv_part"].sum()), edges


def fit_scorecard(X: pd.DataFrame, y: pd.Series, q: int = 5,
                  min_iv: float = 0.02):
    """WOE 编码 + 逻辑回归 + 刻度转换（600 分基准，PDO=20）。"""
    from sklearn.linear_model import LogisticRegression

    tables, ivs, edges_map = {}, {}, {}
    for c in X.columns:
        tab, iv, edges = woe_iv(X[c], y, q)
        tables[c], ivs[c], edges_map[c] = tab, iv, edges
    keep = [c for c, v in ivs.items() if v >= min_iv] or list(X.columns)

    Xw = pd.DataFrame(index=X.index)
    for c in keep:
        cut = pd.cut(X[c], bins=edges_map[c], duplicates="drop")
        Xw[c] = cut.map(tables[c]["woe"]).astype(float)

    lr = LogisticRegression(max_iter=2000, class_weight="balanced",
                            random_state=RANDOM_STATE)
    ok = Xw.notna().all(axis=1)
    lr.fit(Xw[ok], y[ok])

    # 刻度：Score = A - B*ln(odds_bad)
    B = 20 / np.log(2)
    A = 600 + B * np.log(20)                          # 基准坏好比 20:1 → 600 分
    score = A - B * np.log(np.clip(
        lr.predict_proba(Xw.fillna(0))[:, 1] / np.clip(1 - lr.predict_proba(Xw.fillna(0))[:, 1], 1e-9, 1),
        1e-9, 1e9))
    return {"model": lr, "woe_tables": tables, "iv": pd.Series(ivs).sort_values(ascending=False),
            "edges": edges_map, "keep": keep, "Xw": Xw, "score": score,
            "coef": pd.Series(lr.coef_[0], index=keep), "A": A, "B": B,
            "proba": lr.predict_proba(Xw.fillna(0))[:, 1]}


# ---------------------------------------------------------------- 机器学习
def fit_gbm(X: pd.DataFrame, y: pd.Series, X_test=None, y_test=None):
    """优先 XGBoost，缺失则退化为 sklearn GradientBoosting。"""
    ok = X.notna().all(axis=1)
    X_, y_ = X[ok], y[ok]
    try:
        from xgboost import XGBClassifier
        model = XGBClassifier(
            n_estimators=350, max_depth=4, learning_rate=0.05,
            subsample=0.85, colsample_bytree=0.85,
            scale_pos_weight=max((y_ == 0).sum() / max((y_ == 1).sum(), 1), 1),
            eval_metric="auc", random_state=RANDOM_STATE, n_jobs=4)
        backend = "XGBoost"
    except ImportError:
        from sklearn.ensemble import GradientBoostingClassifier
        model = GradientBoostingClassifier(random_state=RANDOM_STATE)
        backend = "sklearn-GBDT"
    model.fit(X_, y_)
    proba = model.predict_proba(X.fillna(0))[:, 1]
    return {"model": model, "proba": proba, "backend": backend, "features": list(X.columns)}


def shap_or_perm(model, X: pd.DataFrame, top: int = 15):
    """SHAP 优先，缺失则用置换重要度。"""
    Xf = X.fillna(0)
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        sv = explainer.shap_values(Xf)
        vals = sv[1] if isinstance(sv, list) else sv
        imp = pd.Series(np.abs(vals).mean(axis=0), index=Xf.columns).sort_values(ascending=False)
        return imp.head(top), "SHAP", vals
    except Exception:                                # noqa: BLE001
        from sklearn.inspection import permutation_importance
        r = permutation_importance(model, Xf, np.zeros(len(Xf)),
                                   n_repeats=3, random_state=RANDOM_STATE)
        imp = pd.Series(r.importances_mean, index=Xf.columns).sort_values(ascending=False)
        return imp.head(top), "permutation", None


def group_cv_auc(make_model, X: pd.DataFrame, y: pd.Series, groups: pd.Series,
                 n_splits: int = 4) -> tuple[float, list[float]]:
    """按年份分组的交叉验证 AUC（避免时序泄漏）。"""
    aucs = []
    gkf = GroupKFold(n_splits=n_splits)
    for tr, te in gkf.split(X, y, groups):
        m = make_model()
        Xtr, ytr = X.iloc[tr].fillna(0), y.iloc[tr]
        Xte, yte = X.iloc[te].fillna(0), y.iloc[te]
        if yte.nunique() < 2:
            continue
        m.fit(Xtr, ytr) if hasattr(m, "fit") else None
        if hasattr(m, "predict_proba"):
            aucs.append(roc_auc_score(yte, m.predict_proba(Xte)[:, 1]))
    return float(np.mean(aucs)) if aucs else float("nan"), aucs
