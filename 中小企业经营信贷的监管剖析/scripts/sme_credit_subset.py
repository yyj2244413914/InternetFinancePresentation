# -*- coding: utf-8 -*-
"""
sme_credit_subset —— 从处罚事件里切出「中小企业信贷」专项子样本
=============================================================
目的：把研究对象从"银行"拉回到"中小企业信贷"本身。

做法：在违法违规事实/处罚内容里检索明确指向中小企业客群的表述
      小微 / 普惠 / 中小企业 / 个体工商户 / 民营企业 / 涉农 / 农户 / 首贷
      再与「信贷相关」取交集，得到"专门因为给中小企业放贷而出的事"。

输出：
  data/processed/sme_credit_events.csv
  控制台打印规模、机构分布、违规类型、金额、年度趋势、典型事由
"""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

SME_KEYS = ["小微", "普惠", "中小企业", "个体工商户", "民营企业", "涉农",
            "农户", "首贷", "无还本续贷", "支农支小", "涉农贷款", "小微贷",
            # 中小企业信贷在处罚文书里的其他常见表述
            "经营贷", "个人经营", "小企业", "微型企业", "小微企", "支小",
            "支农", "创业担保贷", "助业贷", "民营企", "家庭农场",
            "农民专业合作社", "涉农信贷", "普惠型", "两增两控"]
CREDIT_KEYS = ["贷款", "授信", "信贷", "贷前", "贷中", "贷后", "受托支付",
               "挪用", "三查", "担保", "抵押", "票据", "贴现", "融资"]


def main() -> int:
    df = pd.read_csv(PROCESSED / "events_all.csv", low_memory=False)
    df["年份"] = pd.to_numeric(df["年份"], errors="coerce").astype("Int64")
    df["罚没合计万元"] = pd.to_numeric(df["罚没合计万元"], errors="coerce").fillna(0)
    text = (df["违法违规事实"].fillna("") + df["处罚内容"].fillna("")
            + df["标题"].fillna(""))

    df["sme_kw"] = text.apply(lambda t: int(any(k in str(t) for k in SME_KEYS)))
    df["credit_kw"] = text.apply(lambda t: int(any(k in str(t) for k in CREDIT_KEYS)))
    sub = df[(df["sme_kw"] == 1) & (df["credit_kw"] == 1)].copy()

    print(f"全部事件 {len(df):,} 条")
    print(f"  含中小企业客群关键词     {int(df['sme_kw'].sum()):,} 条")
    print(f"  含信贷关键词             {int(df['credit_kw'].sum()):,} 条")
    print(f"  ★ 中小企业信贷专项子样本  {len(sub):,} 条 "
          f"（占全部 {len(sub)/len(df):.1%}）")

    print(f"\n机构类型分布：")
    print(sub["机构类型"].value_counts().head(8).to_string())
    print(f"\n行业分布：")
    print(sub["行业"].value_counts().to_string())
    print(f"\n违规类型分布：")
    print(sub["违规类型"].value_counts().head(10).to_string())
    print(f"\n年度分布（2022 起）：")
    print(sub.loc[sub["年份"] >= 2022, "年份"].value_counts().sort_index().to_string())
    print(f"\n金额：有金额 {int((sub['罚没合计万元']>0).sum()):,} 条，"
          f"合计 {sub['罚没合计万元'].sum()/1e4:,.2f} 亿元，"
          f"中位数 {sub.loc[sub['罚没合计万元']>0,'罚没合计万元'].median():,.1f} 万元")

    print("\n高频事由片段（前 15）：")
    from collections import Counter
    cnt = Counter()
    for t in sub["违法违规事实"].dropna().astype(str):
        for seg in re.split(r"[、，,；;。]", t):
            seg = re.sub(r"\s+", "", seg)
            if 4 <= len(seg) <= 22:
                cnt[seg] += 1
    for k, v in cnt.most_common(15):
        print(f"   {v:>4}  {k}")

    out = PROCESSED / "sme_credit_events.csv"
    sub.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n已存 {out}  ({len(sub):,} 行)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
