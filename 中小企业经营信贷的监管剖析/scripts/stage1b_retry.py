# -*- coding: utf-8 -*-
"""
Stage 1b：慢速补抓被限速（403）挡掉的期数
=========================================
Stage 1 一次性并发偏高，触发站点限速，94 期返回 403。
策略：只补抓缺失的期数，请求间隔 3s + 随机抖动，403 时指数退避重试。
已抓到的走缓存，绝不重复下载。
"""
import gzip
import json
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOB_DIR = ROOT / "data" / "raw" / "clob"
INTERIM = ROOT / "data" / "interim"

BASE = "http://www.nfra.gov.cn/cbircweb"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

SLEEP = 3.0            # 基础间隔（秒）
MAX_TRIES = 6


def fetch_doc(doc_id: int) -> dict:
    url = f"{BASE}/DocInfo/SelectByDocId?docId={doc_id}"
    last = None
    for i in range(MAX_TRIES):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Referer": "http://www.nfra.gov.cn/cn/view/pages/ItemDetail.html",
                "Accept": "application/json, text/plain, */*",
            })
            with urllib.request.urlopen(req, timeout=45) as r:
                payload = json.loads(r.read().decode("utf-8"))
            if payload.get("rptCode") == 200:
                return payload["data"]
            raise RuntimeError(f"rptCode={payload.get('rptCode')}")
        except Exception as e:                       # noqa: BLE001
            last = e
            wait = SLEEP * (2 ** i) + random.uniform(0, 2)
            print(f"    docId={doc_id} 第{i+1}次失败({type(e).__name__})，等 {wait:.1f}s",
                  flush=True)
            time.sleep(wait)
    raise RuntimeError(str(last)[:100])


def main() -> int:
    index = json.loads((INTERIM / "doc_index.json").read_text(encoding="utf-8"))
    todo = [m for m in index if not (CLOB_DIR / f"{m['docId']}.json.gz").exists()]
    print(f"缺失 {len(todo)} 期，开始慢速补抓（间隔 {SLEEP}s）")
    ok = fail = 0
    for i, meta in enumerate(todo, 1):
        doc_id = meta["docId"]
        try:
            data = fetch_doc(doc_id)
            with gzip.open(CLOB_DIR / f"{doc_id}.json.gz", "wt", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            ok += 1
            print(f"  [{i:03d}/{len(todo)}] {doc_id} OK", flush=True)
        except Exception as e:                       # noqa: BLE001
            fail += 1
            print(f"  [{i:03d}/{len(todo)}] {doc_id} 放弃: {e}", flush=True)
        time.sleep(SLEEP + random.uniform(0, 1.5))
    print(f"\n补抓完成：成功 {ok}，仍失败 {fail}")
    left = [m['docId'] for m in todo if not (CLOB_DIR / f"{m['docId']}.json.gz").exists()]
    if left:
        print(f"仍缺失 {len(left)} 期: {left[:20]}{'...' if len(left) > 20 else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
