# -*- coding: utf-8 -*-
"""
Stage 3b：并发抓取「派出机构」处罚公示目录（按年份截止）
=======================================================
用途：派出机构共 74,878 期，但我们只需 2022 年至今（汇报口径：近五年）。
      列表按发布时间倒序，故从第 1 页往后翻，遇到早于截止日期的批次即停。

实测：单请求 ~0.2s，4 并发 + 批间休眠约 6-9 页/秒；
      带 403 指数退避，失败页自动重试。

输出：data/interim/branch_index.csv
"""
import json
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
OUT = INTERIM / "branch_index.csv"
CKPT = INTERIM / "branch_index_ckpt.json"

ITEM_ID = 4293
PAGE_SIZE = 20
CUTOFF = "2021-10-01"          # 略早于 2022-01，多留几天缓冲
BASE = "http://www.nfra.gov.cn/cbircweb/DocInfo/SelectDocByItemIdAndChild"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
FIELDS = ["docId", "publishDate", "docTitle", "docSubtitle",
          "pdfFileUrl", "docFileUrl", "generaltype"]

_lock = threading.Lock()
_stat = {"ok": 0, "fail": 0, "forbidden": 0}


def fetch_page(page: int, tries: int = 5) -> list[dict]:
    url = f"{BASE}?itemId={ITEM_ID}&pageSize={PAGE_SIZE}&pageIndex={page}"
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Referer": "http://www.nfra.gov.cn/"})
            with urllib.request.urlopen(req, timeout=30) as r:
                payload = json.loads(r.read().decode("utf-8"))
            if payload.get("rptCode") == 200:
                with _lock:
                    _stat["ok"] += 1
                return payload["data"]["rows"] or []
            raise RuntimeError(f"rptCode={payload.get('rptCode')}")
        except Exception as e:                       # noqa: BLE001
            code = getattr(e, "code", None)
            if code == 403:
                with _lock:
                    _stat["forbidden"] += 1
            time.sleep(1.0 * (2 ** i))
    with _lock:
        _stat["fail"] += 1
    return []


def main() -> int:
    ck = json.loads(CKPT.read_text(encoding="utf-8")) if CKPT.exists() else {}
    start = ck.get("next_page", 1) if not OUT.exists() else 1
    rows: list[dict] = ck.get("rows", []) if not OUT.exists() else []
    print(f"起始页 {start}，已有 {len(rows)} 条")

    # 若已有完整 CSV，直接复用
    if OUT.exists():
        df = pd.read_csv(OUT)
        print(f"复用已有目录 {len(df)} 条")
        print(df["publishDate"].str[:4].value_counts().sort_index().to_string())
        return 0

    page = start
    stop = False
    t0 = time.time()
    while not stop:
        batch_pages = list(range(page, page + 8))
        with ThreadPoolExecutor(max_workers=4) as ex:
            results = list(ex.map(fetch_page, batch_pages))
        for pg, batch in zip(batch_pages, results):
            if not batch:
                stop = True
                break
            for r in batch:
                rows.append({k: r.get(k) for k in FIELDS})
            oldest = min(r["publishDate"][:10] for r in batch if r.get("publishDate"))
            if oldest < CUTOFF:
                stop = True
                print(f"  第 {pg} 页最早 {oldest} < {CUTOFF}，到达截止点")
                break
        page += 8
        if page % 80 < 8:
            CKPT.write_text(json.dumps({"next_page": page, "rows": rows},
                                       ensure_ascii=False), encoding="utf-8")
            done = len(rows)
            rate = done / max(time.time() - t0, 1e-6)
            print(f"  已翻至第 {page} 页，累计 {done} 条，"
                  f"{rate:.1f} 条/秒，403 次数 {_stat['forbidden']}", flush=True)
        time.sleep(0.15)

    seen, uniq = set(), []
    for r in rows:
        if r["docId"] not in seen:
            seen.add(r["docId"])
            uniq.append(r)
    df = pd.DataFrame(uniq)
    df["year"] = df["publishDate"].str[:4]
    df = df[df["publishDate"] >= CUTOFF]
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    if CKPT.exists():
        CKPT.unlink()
    print(f"\n完成：{len(df)} 条 → {OUT}")
    print(f"统计 {_stat}")
    print("\n按年份：")
    print(df["year"].value_counts().sort_index().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
