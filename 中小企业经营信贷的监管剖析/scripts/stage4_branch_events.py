# -*- coding: utf-8 -*-
"""
Stage 4：并发抓取派出机构处罚正文并流式解析
==========================================
输入：data/interim/branch_index.csv（Stage 3b 产出的目录，2022 年至今）
处理：逐期请求 /DocInfo/SelectByDocId 取 docClob，用 penalty_parser 解析成事件，
      原文 gzip 落盘以便复核，解析结果追加写入 CSV。
特性：4 并发 + 403 指数退避 + 断点续传（按已完成 docId 集合跳过）

输出：
  data/raw/branch_clob/{docId}.json.gz        原文缓存
  data/processed/branch_events.csv            事件表（增量追加）
  data/interim/branch_failed.json             失败清单（可重跑补抓）
"""
import gzip
import json
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from penalty_parser import EVENT_COLUMNS, enrich_record, parse_doc  # noqa: E402

INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
CLOB_DIR = ROOT / "data" / "raw" / "branch_clob"
CLOB_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED.mkdir(parents=True, exist_ok=True)

OUT = PROCESSED / "branch_events.csv"
DONE = INTERIM / "branch_done.json"
FAILED = INTERIM / "branch_failed.json"

BASE = "http://www.nfra.gov.cn/cbircweb/DocInfo/SelectByDocId"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
WORKERS = 4

_lock = threading.Lock()
_stat = {"ok": 0, "fail": 0, "empty": 0, "403": 0}


def fetch_one(doc_id: int, tries: int = 5) -> dict | None:
    url = f"{BASE}?docId={doc_id}"
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Referer": "http://www.nfra.gov.cn/"})
            with urllib.request.urlopen(req, timeout=35) as r:
                payload = json.loads(r.read().decode("utf-8"))
            if payload.get("rptCode") == 200:
                return payload["data"]
            raise RuntimeError(f"rptCode={payload.get('rptCode')}")
        except Exception as e:                       # noqa: BLE001
            if getattr(e, "code", None) == 403:
                with _lock:
                    _stat["403"] += 1
            time.sleep(0.8 * (2 ** i))
    return None


def work(meta: dict) -> tuple[int, list[dict] | None, dict | None]:
    doc_id = int(meta["docId"])
    path = CLOB_DIR / f"{doc_id}.json.gz"
    if path.exists() and path.stat().st_size > 200:
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:                            # noqa: BLE001
            data = fetch_one(doc_id)
    else:
        data = fetch_one(doc_id)
    if data is None:
        return doc_id, None, None
    if not path.exists():
        try:
            with gzip.open(path, "wt", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:                            # noqa: BLE001
            pass
    if not (data.get("docClob") or "").strip():
        return doc_id, [], data
    try:
        recs = [enrich_record(r) for r in parse_doc(doc_id, data, meta)]
    except Exception:                                # noqa: BLE001
        recs = []
    return doc_id, recs, data


def main(limit: int | None = None) -> int:
    index = pd.read_csv(INTERIM / "branch_index.csv")
    index = index[index["publishDate"].astype(str) >= "2022-01-01"]
    done = set(json.loads(DONE.read_text(encoding="utf-8"))) if DONE.exists() else set()
    todo = index[~index["docId"].isin(done)]
    if limit:
        todo = todo.head(limit)
    print(f"目录 {len(index)} 期（>=2022-01-01），已完成 {len(done)}，"
          f"本次待抓 {len(todo)}")
    if todo.empty:
        print("无待抓任务")
        return 0

    metas = todo.to_dict("records")
    failed: list[int] = []
    buffer: list[dict] = []
    first_write = not OUT.exists()
    fh = OUT.open("a", newline="", encoding="utf-8-sig")
    if first_write:
        fh.write(",".join(EVENT_COLUMNS) + "\n")

    t0 = time.time()
    n_docs = 0
    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(work, m): m for m in metas}
            for fut in as_completed(futures):
                doc_id, recs, data = fut.result()
                n_docs += 1
                if recs is None:
                    failed.append(doc_id)
                    _stat["fail"] += 1
                else:
                    done.add(doc_id)
                    if not recs:
                        _stat["empty"] += 1
                    _stat["ok"] += 1
                    for r in recs:
                        buffer.append({c: r.get(c, "") for c in EVENT_COLUMNS})
                if len(buffer) >= 400:
                    for row in buffer:
                        fh.write(",".join(
                            '"' + str(row[c]).replace('"', "'").replace("\n", " ")
                            + '"' for c in EVENT_COLUMNS) + "\n")
                    fh.flush()
                    buffer.clear()
                if n_docs % 200 == 0:
                    el = time.time() - t0
                    rate = n_docs / el
                    eta = (len(metas) - n_docs) / max(rate, 1e-6) / 60
                    DONE.write_text(json.dumps(sorted(done)), encoding="utf-8")
                    print(f"  {n_docs}/{len(metas)}  {rate:.1f} 期/秒  "
                          f"记录 {_stat['ok']}  空 {_stat['empty']}  "
                          f"失败 {_stat['fail']}  403 {_stat['403']}  "
                          f"剩余 {eta:.0f} 分钟", flush=True)
    finally:
        for row in buffer:
            fh.write(",".join('"' + str(row[c]).replace('"', "'").replace("\n", " ")
                              + '"' for c in EVENT_COLUMNS) + "\n")
        fh.close()
        DONE.write_text(json.dumps(sorted(done)), encoding="utf-8")
        FAILED.write_text(json.dumps(sorted(failed)), encoding="utf-8")

    print(f"\n完成 {n_docs} 期，统计 {_stat}，用时 {(time.time()-t0)/60:.1f} 分钟")
    print(f"失败 {len(failed)} 期已记录到 {FAILED}")
    return 0


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    sys.exit(main(lim))
