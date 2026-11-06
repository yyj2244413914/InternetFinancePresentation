# -*- coding: utf-8 -*-
"""
解析器验证：用已缓存的 661 期总局正文重跑，检查修 bug 后的效果
=============================================================
重点核对：
  1) 金额是否还会重复累加（罚没合计 vs 分项）
  2) 当事人是否拆出机构 / 个人
  3) 行业与机构类型分布是否合理
"""
import gzip
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from penalty_parser import (EVENT_COLUMNS, enrich_record,  # noqa: E402
                            parse_doc)

CLOB = ROOT / "data" / "raw" / "clob"
INTERIM = ROOT / "data" / "interim"


def main() -> int:
    index = json.loads((INTERIM / "doc_index.json").read_text(encoding="utf-8"))
    rows, missing = [], 0
    for meta in index:
        p = CLOB / f"{meta['docId']}.json.gz"
        if not p.exists():
            missing += 1
            continue
        with gzip.open(p, "rt", encoding="utf-8") as f:
            data = json.load(f)
        for r in parse_doc(meta["docId"], data, meta):
            rows.append(enrich_record(r))

    df = pd.DataFrame(rows)
    print(f"期数 {len(index)}  缺正文 {missing}  记录 {len(df)}")
    df = df[[c for c in EVENT_COLUMNS if c in df.columns]]
    out = ROOT / "data" / "processed" / "penalty_events_nfra.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"已存 {out}")

    print("\n" + "=" * 66)
    print("① 格式分布")
    print(df["_fmt"].value_counts().to_string())

    print("\n② 当事人类型")
    print(df["当事人类型"].value_counts().to_string())

    print("\n③ 行业分布")
    print(df["行业"].value_counts().to_string())

    print("\n④ 金额 Top10（核对是否还有重复累加）")
    t = df.nlargest(10, "罚没合计万元")
    for _, r in t.iterrows():
        print(f"  {int(r['年份'])} | {str(r['机构名称'])[:26]:<26} | "
              f"罚款{r['罚款万元']:>10,.0f} 没收{r['没收万元']:>10,.0f} "
              f"合计{r['罚没合计万元']:>10,.0f}")

    print("\n⑤ 金额统计（万元）")
    amt = df.loc[df["罚没合计万元"] > 0, "罚没合计万元"]
    print(f"  有金额记录 {len(amt)} 条")
    if len(amt):
        print(f"  合计 {amt.sum():,.0f} 万元 = {amt.sum()/10000:,.1f} 亿元")
        print(f"  中位数 {amt.median():,.1f}  均值 {amt.mean():,.1f}  "
              f"最大 {amt.max():,.1f}")

    print("\n⑥ 机构名称清洗效果（银行类）")
    print(df.loc[df["行业"] == "银行", "机构名称"].value_counts().head(15).to_string())

    print("\n⑦ 信贷相关 + 银行")
    b = df[(df["行业"] == "银行") & (df["信贷相关"] == 1)]
    print(f"  条数 {len(b)}")
    print(b["违规类型"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
