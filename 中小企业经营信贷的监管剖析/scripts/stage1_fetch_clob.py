# -*- coding: utf-8 -*-
"""
Stage 1：抓取全部 661 期公示正文（docClob）
==========================================
Stage 0 的结论：
  - 目录接口共 661 期，2006-03-22 ~ 2026-09-24
  - 2020 年起才有 PDF 附件（326 期），2020 年前 335 期无附件
  - 但详情接口 /DocInfo/SelectByDocId 的 docClob 字段存有全文 HTML，
    661 期全部覆盖 —— 因此放弃 PDF 解析，统一走 docClob

本脚本：逐期抓 SelectByDocId，原文落盘缓存（gzip），供后续重复解析而无需重爬。

输出：
  data/raw/clob/{docId}.json.gz     每期的完整详情（含 docClob）
  data/interim/fetch_report.csv     抓取状态与 documentType 分布
"""
import gzip
import json
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOB_DIR = ROOT / "data" / "raw" / "clob"
INTERIM = ROOT / "data" / "interim"
CLOB_DIR.mkdir(parents=True, exist_ok=True)

BASE = "http://www.nfra.gov.cn/cbircweb"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def fetch_doc(doc_id: int, timeout: int = 40, tries: int = 4) -> dict:
    url = f"{BASE}/DocInfo/SelectByDocId?docId={doc_id}"
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                payload = json.loads(r.read().decode("utf-8"))
            if payload.get("rptCode") == 200:
                return payload["data"]
            raise RuntimeError(f"rptCode={payload.get('rptCode')} {payload.get('msg')}")
        except Exception as e:                       # noqa: BLE001
            last = e
            time.sleep(1.2 * (i + 1))
    raise RuntimeError(f"docId={doc_id} 抓取失败: {last}")


def main() -> int:
    index = json.loads((INTERIM / "doc_index.json").read_text(encoding="utf-8"))
    total = len(index)
    print(f"待抓取: {total} 期")

    rows, ok, fail, cached = [], 0, 0, 0
    for i, meta in enumerate(index, 1):
        doc_id = meta["docId"]
        path = CLOB_DIR / f"{doc_id}.json.gz"
        if path.exists() and path.stat().st_size > 200:
            cached += 1
            with gzip.open(path, "rt", encoding="utf-8") as f:
                data = json.load(f)
        else:
            try:
                data = fetch_doc(doc_id)
                with gzip.open(path, "wt", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                time.sleep(0.35)
            except Exception as e:                   # noqa: BLE001
                fail += 1
                rows.append({"docId": doc_id, "status": "fail", "err": str(e)[:80]})
                print(f"  [{i:03d}/{total}] {doc_id} FAIL {e}")
                continue
        clob = data.get("docClob") or ""
        rows.append({
            "docId": doc_id,
            "status": "ok",
            "publishDate": (data.get("publishDate") or meta["publishDate"])[:10],
            "documentType": data.get("documentType"),
            "title": data.get("docTitle") or "",
            "clob_len": len(clob),
            "has_table": int("<table" in clob.lower()),
        })
        ok += 1
        if i % 25 == 0 or i == total:
            print(f"  [{i:03d}/{total}] 已完成  缓存{cached} 新抓{ok-cached if ok>=cached else ok} "
                  f"失败{fail}", flush=True)

    import csv
    with (INTERIM / "fetch_report.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["docId", "status", "publishDate",
                                          "documentType", "title", "clob_len", "has_table", "err"])
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})

    print("\n" + "=" * 60)
    print(f"成功 {ok} / 失败 {fail} / 走缓存 {cached}")
    dtypes = Counter(r.get("documentType") for r in rows if r["status"] == "ok")
    print(f"documentType 分布: {dict(dtypes)}")
    with_tbl = sum(1 for r in rows if r["status"] == "ok" and r.get("has_table"))
    print(f"正文含 <table> 的期数: {with_tbl}")
    empty = [r for r in rows if r["status"] == "ok" and r.get("clob_len", 0) < 50]
    print(f"正文为空的期数: {len(empty)}")
    if empty:
        print(f"  样例: {[r['docId'] for r in empty[:10]]}")
    lens = sorted(r["clob_len"] for r in rows if r["status"] == "ok")
    if lens:
        print(f"正文字符数 中位数 {lens[len(lens)//2]}  最小 {lens[0]}  最大 {lens[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
