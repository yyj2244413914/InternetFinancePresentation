# -*- coding: utf-8 -*-
"""
lda_model —— 操作风险损失分布法（LDA）核心模块
==============================================
对应汇报 A 线：把监管处罚当作「外部操作风险损失数据」，
用损失分布法估计年度损失分布，再与监管资本要求对比。

建模链条
  1. 频率分布  N ~ Poisson(λ)；若过离散（方差>均值）则改用负二项 NB(r,p)
  2. 强度分布  单笔罚没金额 ~ 对数正态 LN(μ,σ)；尾部另用极值理论 POT+GPD 刻画
  3. 蒙特卡洛  L = Σ_{i=1..N} X_i，重复 n_sims 次 → 99.9% VaR 与 ES
  4. 资本对照  基本指标法 K=α·GI、新标准法 K=β(BI)·BI  vs  LDA 得到的损失 VaR

口径说明（写论文必须交代）
  · 罚款≠真实损失：不含声誉损失、拨备、整改成本，故 LDA 结果是真实损失的下界
  · 监管处罚存在发现偏差：罚单密度反映监管关注度，不等于风险真实分布
"""
from __future__ import annotations

import numpy as np
from scipy import optimize, stats


# ------------------------------------------------------------------ 频率
def fit_frequency(counts) -> dict:
    """拟合事件计数分布。

    返回 dict：
      kind      Poisson / NegBin
      lam       Poisson 强度（事件数/期）
      r, p      负二项参数（过离散时给出）
      dispersion (var-mean)/mean，>1 提示过离散
      lrt_p     泊松 vs 负二项 的似然比检验 p 值
    """
    x = np.asarray(counts, dtype=float)
    n = len(x)
    mean, var = x.mean(), x.var(ddof=1) if n > 1 else 0.0
    dispersion = (var - mean) / mean if mean > 0 else np.nan

    ll_pois = np.sum(stats.poisson.logpmf(x, max(mean, 1e-9)))

    def nb_nll(theta):
        r, p = theta
        if r <= 0 or not (0 < p < 1):
            return 1e12
        return -np.sum(stats.nbinom.logpmf(x, r, p))

    # 负二项初值：矩估计 mean=r(1-p)/p, var=r(1-p)/p^2
    if var > mean and n > 2:
        p0 = min(max(mean / var, 0.01), 0.99)
        r0 = max(mean * p0 / (1 - p0), 0.1)
        res = optimize.minimize(nb_nll, x0=[r0, p0], method="Nelder-Mead",
                                options={"maxiter": 5000, "xatol": 1e-8})
        r_hat, p_hat = res.x
        ll_nb = -res.fun
        # 似然比检验：2*(ll_nb - ll_pois) ~ 0.5*chi2(1) + 0.5*chi2(0)
        lr = max(2 * (ll_nb - ll_pois), 0.0)
        lrt_p = 0.5 * stats.chi2.sf(lr, 1)
        kind = "NegBin" if (lrt_p < 0.10 and r_hat > 0) else "Poisson"
    else:
        r_hat = p_hat = np.nan
        lrt_p = np.nan
        kind = "Poisson"

    return {"kind": kind, "lam": float(mean),
            "nb_mean": float(r_hat * (1 - p_hat) / p_hat) if kind == "NegBin" else float(mean),
            "r": float(r_hat), "p": float(p_hat),
            "dispersion": float(dispersion), "lrt_p": float(lrt_p),
            "n": n, "total": int(x.sum())}


def sample_frequency(params: dict, size: int, rng: np.random.Generator) -> np.ndarray:
    if params["kind"] == "NegBin":
        mean = params["nb_mean"]
        var = mean / params["p"]
        p = mean / var
        r = mean * p / (1 - p)
        return rng.negative_binomial(max(r, 1e-6), min(max(p, 1e-6), 1 - 1e-9), size)
    return rng.poisson(max(params["lam"], 1e-9), size)


# ------------------------------------------------------------------ 强度
def fit_severity(amounts, positive_only: bool = True) -> dict:
    """对数正态拟合 + 拟合优度检验。金额单位：万元。"""
    x = np.asarray(amounts, dtype=float)
    if positive_only:
        x = x[x > 0]
    if len(x) < 5:
        return {}
    logs = np.log(x)
    mu, sigma = logs.mean(), logs.std(ddof=1)
    ks = stats.kstest(x, "lognorm", args=(sigma, 0, np.exp(mu)))
    # 正态性检验（对数尺度）
    ad = stats.anderson(logs, dist="norm")
    return {"n": int(len(x)), "mu": float(mu), "sigma": float(sigma),
            "median": float(np.exp(mu)),
            "mean": float(np.exp(mu + sigma ** 2 / 2)),
            "ks_stat": float(ks.statistic), "ks_p": float(ks.pvalue),
            "ad_stat": float(ad.statistic),
            "ad_crit_5pct": float(ad.critical_values[2]),
            "max": float(x.max()), "total": float(x.sum())}


def sample_severity(params: dict, size: int, rng: np.random.Generator) -> np.ndarray:
    return rng.lognormal(params["mu"], params["sigma"], size)


# ------------------------------------------------------------------ 极值
def hill_estimator(x, k: int | None = None) -> dict:
    """Hill 估计尾指数（金额降序前 k 个）。"""
    xs = np.sort(np.asarray(x, dtype=float))[::-1]
    if len(xs) < 20:
        return {}
    k = k or max(10, int(len(xs) * 0.10))
    k = min(k, len(xs) - 1)
    xi = np.mean(np.log(xs[:k]) - np.log(xs[k]))
    se = xi / np.sqrt(k - 1)
    return {"k": k, "threshold": float(xs[k]), "xi": float(xi),
            "alpha": float(1 / xi) if xi > 0 else np.inf,
            "se": float(se)}


def mean_residual_life(x, u_grid=None) -> tuple[np.ndarray, np.ndarray]:
    """超阈值均值图：MR(u) 与 u 近似线性处即合理阈值。"""
    xs = np.sort(np.asarray(x, dtype=float))
    if u_grid is None:
        u_grid = np.quantile(xs, np.linspace(0.50, 0.97, 40))
    u_out, mr = [], []
    for u in u_grid:
        excess = xs[xs > u] - u
        if len(excess) >= 15:
            u_out.append(u)
            mr.append(excess.mean())
    return np.array(u_out), np.array(mr)


def fit_gpd(amounts, threshold: float | None = None) -> dict:
    """POT：对超阈值部分拟合广义帕累托分布。"""
    x = np.asarray(amounts, dtype=float)
    x = x[x > 0]
    if len(x) < 50:
        return {}
    u = threshold if threshold is not None else float(np.quantile(x, 0.90))
    excess = x[x > u] - u
    if len(excess) < 20:
        return {}
    try:
        xi, loc, beta = stats.genpareto.fit(excess, floc=0)
    except Exception:                                  # noqa: BLE001
        return {}
    ks = stats.kstest(excess, "genpareto", args=(xi, 0, beta))
    return {"threshold": float(u), "n_exceed": int(len(excess)),
            "excess_rate": float(len(excess) / len(x)),
            "xi": float(xi), "beta": float(beta),
            "ks_stat": float(ks.statistic), "ks_p": float(ks.pvalue),
            "tail_index": float(1 / xi) if xi > 0 else np.inf}


# ------------------------------------------------------------------ 蒙特卡洛
def monte_carlo(freq: dict, sev: dict, n_sims: int = 50_000,
                periods_per_year: float = 1.0, seed: int = 42,
                confidence: float = 0.999) -> dict:
    """模拟年度损失分布，返回 VaR / ES 及分位点。

    periods_per_year：频率参数所对应的期数换算成年，如按季度计数则传 4。
    """
    rng = np.random.default_rng(seed)
    lam_scale = periods_per_year
    total = np.empty(n_sims)
    for i in range(n_sims):
        if freq["kind"] == "NegBin":
            mean = freq["nb_mean"] * lam_scale
            var_per = freq["nb_mean"] / freq["p"]
            p = mean / (var_per * lam_scale)
            r = mean * p / (1 - p)
            n = rng.negative_binomial(max(r, 1e-6), min(max(p, 1e-6), 1 - 1e-9))
        else:
            n = rng.poisson(max(freq["lam"] * lam_scale, 1e-9))
        if n:
            total[i] = rng.lognormal(sev["mu"], sev["sigma"], n).sum()
        else:
            total[i] = 0.0
    var = float(np.quantile(total, confidence))
    tail = total[total >= var]
    es = float(tail.mean()) if len(tail) else var
    return {"n_sims": n_sims, "confidence": confidence,
            "var": var, "es": es,
            "mean": float(total.mean()), "median": float(np.median(total)),
            "p95": float(np.quantile(total, 0.95)),
            "p999": var, "max": float(total.max()),
            "losses": total}


# ------------------------------------------------------------------ 监管资本
def capital_bia(gi_list, alpha: float = 0.15) -> float:
    """基本指标法：K = α × 近三年平均总收入（单位与输入一致）。"""
    g = [x for x in gi_list if x and x > 0]
    if not g:
        return float("nan")
    return alpha * float(np.mean(g))


def capital_sa_bis(bi: float) -> tuple[float, float]:
    """新标准法（《商业银行资本管理办法》2024 实施）：按业务指标 BI 分档。

    BI ≤ 100 亿元           → 12%
    100 亿 < BI ≤ 300 亿元  → 15%
    BI > 300 亿元           → 18%
    单位：亿元 → 返回 (资本要求亿元, 适用系数)
    """
    if bi <= 100:
        beta = 0.12
    elif bi <= 300:
        beta = 0.15
    else:
        beta = 0.18
    return beta * bi, beta


def capital_standardised_old(gi_by_line: dict) -> float:
    """旧标准法（巴塞尔 II / 2012 试行办法）：八条业务线 β 加权。

    gi_by_line: {业务线: 该线营业收入}，业务线名称必须是下列之一。
    """
    betas = {"公司金融": 0.18, "交易和销售": 0.18, "零售银行": 0.12,
             "商业银行": 0.15, "支付和清算": 0.18, "代理服务": 0.15,
             "资产管理": 0.12, "零售经纪": 0.12}
    return sum(betas.get(k, 0.15) * v for k, v in gi_by_line.items())


def summary_table(freq: dict, sev: dict, mc: dict, gpd: dict | None = None) -> list[tuple]:
    """把关键参数整理成可直接 display 的行。"""
    rows = [
        ("频率分布类型", freq.get("kind", "-"),
         "过离散检验 (var-mean)/mean", f"{freq.get('dispersion', float('nan')):.2f}"),
        ("泊松 vs 负二项 LRT p 值", f"{freq.get('lrt_p', float('nan')):.4f}", "", ""),
        ("期均事件数 λ", f"{freq.get('lam', float('nan')):.2f}", "", ""),
        ("强度分布", "对数正态", "μ (对数均值)", f"{sev.get('mu', float('nan')):.3f}"),
        ("", "", "σ (对数标准差)", f"{sev.get('sigma', float('nan')):.3f}"),
        ("", "", "KS 检验 p 值", f"{sev.get('ks_p', float('nan')):.4f}"),
        ("", "", "AD 统计量 / 5% 临界值",
         f"{sev.get('ad_stat', float('nan')):.2f} / {sev.get('ad_crit_5pct', float('nan')):.2f}"),
        ("蒙特卡洛", f"{mc.get('n_sims', 0):,} 次", "年度损失均值（万元）",
         f"{mc.get('mean', float('nan')):,.0f}"),
        ("", "", "99.9% VaR（万元）", f"{mc.get('var', float('nan')):,.0f}"),
        ("", "", "99.9% ES（万元）", f"{mc.get('es', float('nan')):,.0f}"),
    ]
    if gpd:
        rows += [
            ("极值理论 POT", f"阈值 P{gpd.get('threshold', 0):,.0f} 万元",
             "超阈值次数 / 比例",
             f"{gpd.get('n_exceed', 0)} / {gpd.get('excess_rate', 0):.1%}"),
            ("", "", "形状参数 ξ", f"{gpd.get('xi', float('nan')):.3f}"),
            ("", "", "尾指数 1/ξ", f"{gpd.get('tail_index', float('nan')):.2f}"),
        ]
    return rows
