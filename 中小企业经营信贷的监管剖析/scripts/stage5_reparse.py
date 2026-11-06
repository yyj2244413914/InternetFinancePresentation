# -*- coding: utf-8 -*-
"""
Stage 5：用当前解析器重新解析全部已缓存正文 → 统一事件表
========================================================
为什么需要这一步：抓取脚本产出的是「当时代码版本」的解析结果。
原文已 gzip 缓存，改动解析规则后只需重跑本脚本，无需重新爬取。

输入：data/raw/clob/*.json.gz（总局机关）
      data/raw/branch_clob/*.json.gz（派出机构）
输出：data/processed/events_all.csv
      data/processed/diagnostics.txt（其他违规的高频表述，用于迭代规则）
"""
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from penalty_parser import (EVENT_COLUMNS, enrich_record,  # noqa: E402
                            html_tables, norm, parse_doc)

INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)
CLOB_NFRA = ROOT / "data" / "raw" / "clob"
CLOB_BRANCH = ROOT / "data" / "raw" / "branch_clob"


def load_meta() -> tuple[dict, dict]:
    meta = {}
    idx = INTERIM / "doc_index.json"
    if idx.exists():
        for m in json.loads(idx.read_text(encoding="utf-8")):
            meta[int(m["docId"])] = {"publishDate": m.get("publishDate", ""),
                                     "docTitle": m.get("docTitle", "")}
    bidx = INTERIM / "branch_index.csv"
    if bidx.exists():
        df = pd.read_csv(bidx)
        for m in df.to_dict("records"):
            meta[int(m["docId"])] = {"publishDate": str(m.get("publishDate", "")),
                                     "docTitle": m.get("docTitle", "")}
    return meta, {}


def reparse(folder: Path, source: str, meta: dict) -> list[dict]:
    if not folder.exists():
        return []
    files = sorted(folder.glob("*.json.gz"))
    print(f"  {source}: {len(files)} 份缓存", flush=True)
    rows = []
    for i, p in enumerate(files, 1):
        doc_id = int(p.stem.split(".")[0])
        try:
            with gzip.open(p, "rt", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:                            # noqa: BLE001
            continue
        for r in parse_doc(doc_id, data, meta.get(doc_id, {})):
            r = enrich_record(r)
            r["数据来源"] = source
            rows.append(r)
        if i % 5000 == 0:
            print(f"    {i}/{len(files)} → {len(rows)} 条", flush=True)
    return rows


def main() -> int:
    meta, _ = load_meta()
    print(f"元数据索引 {len(meta)} 期")
    rows = []
    rows += reparse(CLOB_NFRA, "总局机关", meta)
    rows += reparse(CLOB_BRANCH, "派出机构", meta)
    df = pd.DataFrame(rows)
    print(f"\n总记录 {len(df)}")
    df = df[[c for c in EVENT_COLUMNS + ["数据来源"] if c in df.columns]]
    out = PROCESSED / "events_all.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"已存 {out}")

    lines = []
    def rep(title, obj):
        lines.append("\n" + "=" * 60 + f"\n{title}\n" + "=" * 60)
        lines.append(obj if isinstance(obj, str) else obj.to_string())
        print("\n" + "=" * 60 + f"\n{title}\n" + "=" * 60)
        print(obj)

    rep("数据来源", df["数据来源"].value_counts())
    rep("正文格式", df["_fmt"].value_counts())
    rep("当事人类型", df["当事人类型"].value_counts())
    rep("行业分布", df["行业"].value_counts())
    rep("银行机构类型", df.loc[df["行业"] == "银行", "机构类型"].value_counts())
    rep("违规类型", df["违规类型"].value_counts())
    rep("信贷相关", df["信贷相关"].value_counts())
    rep("有金额记录", str(int((df["罚没合计万元"] > 0).sum()))
        + f" / {len(df)}，合计 {df['罚没合计万元'].sum():,.0f} 万元")
    rep("按年记录数", df["年份"].value_counts().sort_index())

    # 其他违规的高频表述 → 用来迭代关键词
    other = df.loc[df["违规类型"] == "其他违规", "违法违规事实"].dropna()
    cnt = Counter()
    for t in other:
        for seg in str(t).split("、"):
            seg = norm(seg)
            if 4 <= len(seg) <= 18:
                cnt[seg] += 1
    rep("其他违规 高频表述 Top30（用于补关键词）",
        pd.Series(dict(cnt.most_common(30))))

    (PROCESSED / "diagnostics.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n诊断已存 {PROCESSED / 'diagnostics.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
