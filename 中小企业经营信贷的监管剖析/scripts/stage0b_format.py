# -*- coding: utf-8 -*-
"""
Stage 0b：分层抽样 + 表格抽取能力验证
=====================================
Stage 0 的发现：近年的公示 PDF 是「表格」——列为
    序号 | 当事人名称 | 主要违法违规行为 | 行政处罚内容 | 作出决定机关
pypdf 抽出来是竖排碎行，需要按表格结构解析。

本脚本验证两件事：
  1) 2006–2026 各年份的公示格式是否一致（分层抽样，每年取 2 期）
  2) pdfplumber 的 extract_tables() 能否直接抽出规整表格
     （若能 → 解析质量从「正则硬抠」升级为「表格结构化」）

输出：
  data/interim/stage0b_format.csv   每期的格式与可解析性统计
  data/interim/stage0b_tables.json  抽出的表格样本（供人工核对）
"""
import io
import json
import re
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

from pypdf import PdfReader

try:
    import pdfplumber
    HAS_PLUMBER = True
except ImportError:
    HAS_PLUMBER = False

ROOT = Path(__file__).resolve().parents[1]
RAW_PDF = ROOT / "data" / "raw" / "nfra_pdf"
INTERIM = ROOT / "data" / "interim"
RAW_PDF.mkdir(parents=True, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 表格表头特征（列表式公示）
HEADER_KEYS = ["当事人", "违法违规行为", "行政处罚内容", "作出决定机关", "行政处罚决定书文号"]
BANK_RE = re.compile(r"银行|信用社|信用合作联社|农信社|村镇银行|农商行")
CREDIT_RE = re.compile(r"贷款|授信|贷前|贷中|贷后|受托支付|挪用|三查|尽职|票据|贴现")


def fetch(url: str, timeout: int = 40, tries: int = 3) -> bytes:
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:                       # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"下载失败 {url}: {last}")


def get_pdf(row: dict) -> bytes:
    p = RAW_PDF / f"{row['docId']}.pdf"
    if p.exists() and p.stat().st_size > 1000:
        return p.read_bytes()
    blob = fetch("http://www.nfra.gov.cn" + row["pdfFileUrl"])
    p.write_bytes(blob)
    time.sleep(0.4)
    return blob


def pypdf_text(blob: bytes) -> tuple[str, int]:
    rd = PdfReader(io.BytesIO(blob))
    return "\n".join((p.extract_text() or "") for p in rd.pages), len(rd.pages)


def plumber_tables(blob: bytes) -> list[list[list[str | None]]]:
    """返回所有页抽出的表格（每张表是二维列表）。"""
    out = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page in pdf.pages:
            for tb in (page.extract_tables() or []):
                if tb:
                    out.append(tb)
    return out


def normalize(rows: list[list[str | None]]) -> list[list[str]]:
    """把 pdfplumber 的表格规整：去掉纯换行、合并被折断的中文列。"""
    clean = []
    for r in rows:
        cells = [re.sub(r"\s+", "", (c or "")) for c in r]
        if any(cells):
            clean.append(cells)
    return clean


def main() -> int:
    index = json.loads((INTERIM / "doc_index.json").read_text(encoding="utf-8"))
    print(f"pdfplumber 可用: {HAS_PLUMBER}")

    # ---- 分层抽样：每年最多 2 期（年初 + 年中各一）
    by_year = defaultdict(list)
    for r in index:
        by_year[r["publishDate"][:4]].append(r)
    sample = []
    for y in sorted(by_year):
        docs = sorted(by_year[y], key=lambda x: x["publishDate"])
        sample.append(docs[0])
        if len(docs) > 2:
            sample.append(docs[len(docs) // 2])
    print(f"分层抽样: {len(sample)} 期，覆盖 {len(by_year)} 个年份 "
          f"({min(by_year)}~{max(by_year)})")

    records, table_samples = [], {}
    for i, row in enumerate(sample, 1):
        blob = get_pdf(row)
        text, npages = pypdf_text(blob)
        rec = {
            "docId": row["docId"],
            "year": row["publishDate"][:4],
            "publishDate": row["publishDate"][:10],
            "pages": npages,
            "chars": len(text),
        }
        # 表头特征
        hit = [k for k in HEADER_KEYS if k in re.sub(r"\s+", "", text)]
        rec["header_hits"] = "|".join(hit)

        ntables, nrows, ncols = 0, 0, 0
        if HAS_PLUMBER:
            try:
                tabs = plumber_tables(blob)
                ntables = len(tabs)
                if tabs:
                    biggest = max(tabs, key=len)
                    clean = normalize(biggest)
                    nrows, ncols = len(clean), max((len(r) for r in clean), default=0)
                    if len(table_samples) < 6:
                        table_samples[row["docId"]] = clean[:4]
            except Exception as e:                    # noqa: BLE001
                rec["plumber_err"] = str(e)[:60]
        rec.update({"tables": ntables, "tbl_rows": nrows, "tbl_cols": ncols,
                    "bank_hits": len(BANK_RE.findall(text)),
                    "credit_hits": len(CREDIT_RE.findall(text))})
        records.append(rec)
        print(f"  [{i:02d}] {rec['publishDate']} {row['docId']} "
              f"{npages}页 字符{rec['chars']:>6d} "
              f"表{ntables}张/{nrows}行/{ncols}列 "
              f"表头{'✓' if hit else '✗'} 银行{rec['bank_hits']:>3d} "
              f"信贷词{rec['credit_hits']:>3d}")

    # ---- 汇总
    print("\n" + "=" * 68)
    print("格式一致性检验")
    print("=" * 68)
    n = len(records)
    with_tbl = sum(1 for r in records if r["tbl_rows"] > 1)
    with_hdr = sum(1 for r in records if r["header_hits"])
    print(f"  抽样期数                : {n}")
    print(f"  能抽出表格(>1行)        : {with_tbl}/{n} = {with_tbl/n:.0%}")
    print(f"  含标准表头关键词        : {with_hdr}/{n} = {with_hdr/n:.0%}")
    print(f"  平均每期抽出行数        : {sum(r['tbl_rows'] for r in records)/n:.1f}")
    print(f"  含银行类主体的期数      : {sum(1 for r in records if r['bank_hits'])/n:.0%}")
    print(f"  含信贷违规词的期数      : {sum(1 for r in records if r['credit_hits'])/n:.0%}")
    print(f"  页面总行数(估计记录数)  : {sum(r['tbl_rows'] for r in records)} 条")

    import csv
    with (INTERIM / "stage0b_format.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        w.writeheader()
        w.writerows(records)
    (INTERIM / "stage0b_tables.json").write_text(
        json.dumps(table_samples, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  已存: {INTERIM / 'stage0b_format.csv'}")
    print(f"  已存: {INTERIM / 'stage0b_tables.json'}")

    if table_samples:
        print("\n" + "=" * 68)
        print("表格抽取样例（前 4 行）")
        print("=" * 68)
        doc_id, rows = next(iter(table_samples.items()))
        print(f"docId={doc_id}")
        for r in rows:
            print("  ", r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
