# -*- coding: utf-8 -*-
"""
Stage 3：抓取「派出机构」行政处罚公示目录（74,878 期）
====================================================
Stage 0-1 只碰了总局机关的 661 期，其中银行类仅 47 条 —— 因为
中小银行（城商行/农商行/村镇银行）的处罚由各地监管局/分局作出。

实测栏目结构（itemId 931 行政处罚）：
  4113 总局机关      661 期
  4293 派出机构    74,878 期   ← 本脚本目标（= 4114 监管局本级 + 4115 监管分局本级 + 4292 支局）
  4114 监管局本级  32,983 期
  4115 监管分局本级 41,894 期
  4292 监管支局本级     2 期

接口 pageSize 上限 20，故需约 3,744 次翻页。
支持断点续传：每 50 页落盘一次，重跑自动从断点继续。

输出：
  data/interim/branch_index.csv        派出机构全部公示元数据
  data/interim/branch_index_ckpt.json  断点
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
CKPT = INTERIM / "branch_index_ckpt.json"
OUT = INTERIM / "branch_index.csv"

ITEM_ID = 4293
PAGE_SIZE = 20
BASE = "http://www.nfra.gov.cn/cbircweb/DocInfo/SelectDocByItemIdAndChild"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
SLEEP = 0.45
FIELDS = ["docId", "publishDate", "docTitle", "docSubtitle",
          "pdfFileUrl", "docFileUrl", "generaltype"]


def fetch_page(page: int, tries: int = 6) -> list[dict]:
    url = f"{BASE}?itemId={ITEM_ID}&pageSize={PAGE_SIZE}&pageIndex={page}"
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Referer": "http://www.nfra.gov.cn/"})
            with urllib.request.urlopen(req, timeout=40) as r:
                payload = json.loads(r.read().decode("utf-8"))
            if payload.get("rptCode") == 200:
                return payload["data"]["rows"] or []
            raise RuntimeError(f"rptCode={payload.get('rptCode')}")
        except Exception as e:                       # noqa: BLE001
            wait = 2.0 * (2 ** i)
            print(f"    第{page}页 第{i+1}次失败({type(e).__name__})，等{wait:.0f}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"第 {page} 页彻底失败")


def main() -> int:
    ck = json.loads(CKPT.read_text(encoding="utf-8")) if CKPT.exists() else {}
    start = ck.get("next_page", 1)
    rows = ck.get("rows", [])
    total = ck.get("total")
    print(f"断点续传：从第 {start} 页开始，已有 {len(rows)} 条")

    page = start
    while True:
        batch = fetch_page(page)
        if not batch:
            print(f"第 {page} 页返回空，结束")
            break
        for r in batch:
            rows.append({k: r.get(k) for k in FIELDS})
        if page % 50 == 0:
            CKPT.write_text(json.dumps(
                {"next_page": page + 1, "rows": rows, "total": total},
                ensure_ascii=False), encoding="utf-8")
            print(f"  第 {page} 页 → 累计 {len(rows)} 条（已落盘）", flush=True)
        page += 1
        time.sleep(SLEEP)

    # 去重
    seen, uniq = set(), []
    for r in rows:
        if r["docId"] not in seen:
            seen.add(r["docId"])
            uniq.append(r)
    df = pd.DataFrame(uniq)
    df["year"] = df["publishDate"].str[:4]
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    CKPT.unlink(missing_ok=True)
    print(f"\n完成：{len(df)} 条 → {OUT}")
    print("\n按年份分布：")
    print(df["year"].value_counts().sort_index().to_string())
    print("\n各年份有 PDF 附件的占比：")
    t = df.assign(has_pdf=df["pdfFileUrl"].notna()).groupby("year")["has_pdf"].mean()
    print((t * 100).round(0).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
