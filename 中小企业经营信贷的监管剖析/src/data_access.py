# -*- coding: utf-8 -*-
"""
data_access —— 统一的取数入口（notebook 只调这里，不写重复代码）
=============================================================
所有函数带 @lru_cache，汇报时重复调用不重复读盘，保证「点一下就出结果」。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
INTERIM = ROOT / "data" / "interim"

# 中小银行口径：城商行 / 农村中小银行 / 村镇银行 / 民营银行
SME_BANK_TYPES = ["城商行/其他银行", "农村中小银行", "村镇银行", "民营银行"]
LARGE_BANK_TYPES = ["国有大型银行", "股份制银行", "政策性银行"]


@lru_cache(maxsize=1)
def events() -> pd.DataFrame:
    """处罚事件总表（一行 = 一个被处罚当事人的一次处罚）。"""
    df = pd.read_csv(PROCESSED / "events_all.csv", low_memory=False)
    df["年份"] = pd.to_numeric(df["年份"], errors="coerce").astype("Int64")
    df["罚没合计万元"] = pd.to_numeric(df["罚没合计万元"], errors="coerce").fillna(0)
    df["信贷相关"] = pd.to_numeric(df["信贷相关"], errors="coerce").fillna(0).astype(int)
    # 机构层级：总行 / 分行 / 支行 / 其他
    name = df["机构名称"].fillna("")
    layer = np.select(
        [name.str.contains("支行|分理处|营业部|储蓄所"),
         name.str.contains("分行|分公司|支公司|中心支公司"),
         name.str.contains("银行|信用社|联社|公司")],
        ["支行/网点", "分行/省级", "法人/总部"], default="未知")
    df["机构层级"] = layer
    df["是否中小银行"] = df["机构类型"].isin(SME_BANK_TYPES).astype(int)
    return df


@lru_cache(maxsize=1)
def bank_events() -> pd.DataFrame:
    """只看银行的处罚事件。"""
    df = events()
    return df[df["行业"] == "银行"].copy()


@lru_cache(maxsize=1)
def credit_events() -> pd.DataFrame:
    """信贷相关事件（含银行）。"""
    df = events()
    return df[df["信贷相关"] == 1].copy()


# ---------------------------------------------------------------- 中小企业口径
# 中小企业客群在处罚文书里的常见表述（用于切出「中小企业信贷」专项子样本）
SME_KEYS = ("小微", "普惠", "中小企业", "个体工商户", "民营企业", "涉农",
            "农户", "首贷", "无还本续贷", "支农支小", "涉农贷款", "小微贷",
            "经营贷", "个人经营", "小企业", "微型企业", "小微企", "支小",
            "支农", "创业担保贷", "助业贷", "民营企", "家庭农场",
            "农民专业合作社", "涉农信贷", "普惠型", "两增两控")
CREDIT_KEYS_ALL = ("贷款", "授信", "信贷", "贷前", "贷中", "贷后", "受托支付",
                   "挪用", "三查", "担保", "抵押", "票据", "贴现", "融资")


@lru_cache(maxsize=1)
def sme_credit_events() -> pd.DataFrame:
    """★ 中小企业信贷专项子样本

    口径：违法违规事实/处罚内容/标题中**明确出现中小企业客群表述**
    （小微、普惠、个体工商户、涉农、经营贷…）**且**与信贷相关的事由。

    这是把研究对象从「银行」拉回「中小企业信贷」的关键切片：
    被处罚主体仍是银行（监管处罚无法绕过这一层），
    但筛选条件锁定的是"因为给中小企业放贷而出的事"。
    """
    df = events().copy()
    text = (df["违法违规事实"].fillna("") + df["处罚内容"].fillna("")
            + df["标题"].fillna("")).astype(str)
    sme = text.apply(lambda t: int(any(k in t for k in SME_KEYS)))
    cre = text.apply(lambda t: int(any(k in t for k in CREDIT_KEYS_ALL)))
    out = df[(sme == 1) & (cre == 1)].copy()
    out["sme_kw"] = 1
    return out


@lru_cache(maxsize=1)
def sme_profile() -> pd.DataFrame:
    """中小企业本身的画像：企业面板 + 下一年困境标签（需求侧证据）。"""
    import sys as _sys
    p = str(ROOT / "src")
    if p not in _sys.path:
        _sys.path.insert(0, p)
    import default_model as dm
    return dm.build_panel(firm_panel())


@lru_cache(maxsize=1)
def bank_fin() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "bank_fin.csv")


@lru_cache(maxsize=1)
def firm_panel() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED / "firm_panel.csv", low_memory=False)
    num_cols = [c for c in df.columns
                if c not in ("SECURITY_CODE", "SECURITY_NAME_ABBR", "REPORT_DATE",
                             "REPORT_TYPE", "code", "name")]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def sample_summary() -> pd.DataFrame:
    """汇报 S3 用的样本概况表。"""
    ev = events()
    bank = ev[ev["行业"] == "银行"]
    rows = [
        ("处罚公示期数（2022–2026）", f"{ev['docId'].nunique():,} 期"),
        ("解析出的处罚记录", f"{len(ev):,} 条"),
        ("其中：银行类", f"{len(bank):,} 条"),
        ("其中：中小银行（城商/农商/村镇/民营）", f"{bank['是否中小银行'].sum():,} 条"),
        ("其中：信贷相关", f"{int(ev['信贷相关'].sum()):,} 条"),
        ("涉及机构家数（去重）", f"{ev['机构名称'].nunique():,} 家"),
        ("处罚金额合计", f"{ev['罚没合计万元'].sum()/1e4:,.1f} 亿元"),
        ("样本区间", f"{int(ev['年份'].min())}–{int(ev['年份'].max())}"),
    ]
    return pd.DataFrame(rows, columns=["指标", "数值"])


def violation_matrix(scope: str = "bank") -> pd.DataFrame:
    """机构类型 × 违规类型 计数矩阵（热力图用）。"""
    df = bank_events() if scope == "bank" else events()
    order_v = ["贷款三查不到位", "信贷管理不到位", "违规发放贷款", "贷款资金挪用",
               "掩盖不良与五级分类", "内控与员工行为", "违规经营与指标不实",
               "收费与销售行为", "数据报送与统计", "同业理财与票据", "关联交易与关系人",
               "其他违规"]
    order_i = ["国有大型银行", "股份制银行", "城商行/其他银行",
               "农村中小银行", "村镇银行", "民营银行", "政策性银行"]
    mat = (df.groupby(["机构类型", "违规类型"]).size()
           .unstack(fill_value=0)
           .reindex(index=[i for i in order_i if i in set(df["机构类型"])],
                    columns=[v for v in order_v if v in set(df["违规类型"])])
           ).fillna(0).astype(int)
    return mat


def yearly_stats() -> pd.DataFrame:
    """按年统计：事件数、涉事机构数、处罚金额（亿元）。"""
    df = events()
    out = df.groupby("年份").agg(
        事件数=("docId", "size"),
        涉及机构=("机构名称", "nunique"),
        金额亿元=("罚没合计万元", lambda s: round(s.sum() / 1e4, 2)),
    )
    return out.loc[out.index >= 2022]


def avg_penalty_by_type() -> pd.DataFrame:
    """各机构类型的单笔罚款均值与中位数（万元）。"""
    b = bank_events()
    b = b[b["罚没合计万元"] > 0]
    out = (b.groupby("机构类型")["罚没合计万元"]
           .agg(样本数="size", 均值="mean", 中位数="median", 合计="sum")
           .round(2).sort_values("均值", ascending=False))
    return out


def severity_series(scope: str = "bank", positive_only: bool = True) -> pd.Series:
    """单笔罚没金额序列（万元），供 LDA 强度分布使用。"""
    df = bank_events() if scope == "bank" else events()
    s = df["罚没合计万元"]
    if positive_only:
        s = s[s > 0]
    return s


def quarterly_counts(scope: str = "bank") -> pd.Series:
    """按季度的事件计数序列，供 LDA 频率分布使用。"""
    df = bank_events() if scope == "bank" else events()
    d = pd.to_datetime(df["发布日期"], errors="coerce")
    ok = d.notna()
    s = (pd.Series(1, index=d[ok])
         .resample("QE").sum()
         .loc["2022-03-31":"2025-12-31"])          # 只保留完整季度
    return s[s.index <= pd.Timestamp("2025-12-31")]


def annual_counts(scope: str = "bank") -> pd.Series:
    df = bank_events() if scope == "bank" else events()
    d = pd.to_datetime(df["发布日期"], errors="coerce")
    s = pd.Series(1, index=d[d.notna()]).resample("YE").sum()
    return s.loc["2022":"2025"]
