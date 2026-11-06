# -*- coding: utf-8 -*-
"""
Stage 0：数据可行性验证
=========================
目的：在投入全量解析之前，用抽样验证三件事
  1) 处罚公示目录能否完整拉取（661 期）
  2) 公示 PDF 是否有文本层（不是扫描件）
  3) 核心字段（决定书文号 / 机构 / 处罚金额 / 违法违规事实）的抽取完整率

输出：
  data/interim/doc_index.json        目录元数据
  data/interim/stage0_pdf_stats.csv  抽样期的字段统计
  data/raw/nfra_pdf/{docId}.pdf      抽样 PDF 原件（缓存）
"""
import io
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
RAW_PDF = ROOT / "data" / "raw" / "nfra_pdf"
INTERIM = ROOT / "data" / "interim"
for d in (RAW_PDF, INTERIM):
    d.mkdir(parents=True, exist_ok=True)

BASE = "http://www.nfra.gov.cn/cbircweb"
ITEM_ID = 4113                      # 行政处罚信息公示
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

SAMPLE_N = 10                       # 抽样期数（Stage 0 只看 10 期）


# ---------------------------------------------------------------- 网络
def fetch(url: str, timeout: int = 30, tries: int = 3) -> bytes:
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


# ---------------------------------------------------------------- 目录
def build_index() -> list[dict]:
    """拉取处罚公示目录全量元数据（翻页直到收齐 total）。"""
    rows, page, total = [], 1, None
    while True:
        url = (f"{BASE}/DocInfo/SelectDocByItemIdAndChild"
               f"?itemId={ITEM_ID}&pageSize=18&pageIndex={page}")
        payload = json.loads(fetch(url).decode("utf-8"))
        if payload.get("rptCode") != 200:
            raise RuntimeError(f"接口返回异常: {payload.get('msg')}")
        data = payload["data"]
        total = data["total"]
        batch = data.get("rows") or []
        if not batch:
            break
        rows.extend(batch)
        print(f"  第 {page} 页 → 累计 {len(rows)}/{total}", flush=True)
        if len(rows) >= total:
            break
        page += 1
        time.sleep(0.3)                              # 限速，别把人家站点打疼
    # 去重保序
    seen, uniq = set(), []
    for r in rows:
        if r["docId"] not in seen:
            seen.add(r["docId"])
            uniq.append(r)
    return uniq


# ---------------------------------------------------------------- PDF
def pdf_text(blob: bytes) -> tuple[str, int]:
    reader = PdfReader(io.BytesIO(blob))
    pages = [(p.extract_text() or "") for p in reader.pages]
    return "\n".join(pages), len(reader.pages)


# ---------------------------------------------------------------- 字段探测
RE_DOCNO = re.compile(r"〔\s*\d{4}\s*〕\s*\d+\s*号")          # 决定书文号
RE_AMT_WAN = re.compile(r"[\d,]+(?:\.\d+)?\s*万元")           # 金额（万元）
RE_AMT_YUAN = re.compile(r"[\d,]+(?:\.\d+)?\s*元")            # 金额（元）
RE_ORG = re.compile(r"[\u4e00-\u9fa5()（）]{2,25}?"
                    r"(?:银行|信用社|信用合作联社|农信社|支行|分行|支局)")
RE_FACT = re.compile(r"贷款|授信|贷前|贷中|贷后|受托支付|挪用|三查|"
                     r"尽职|审慎|小微|普惠|担保|抵押|挪用贷款资金")
RE_PERSON = re.compile(r"姓名[：:]|身份证号|住址")


def probe(text: str) -> dict:
    docno = RE_DOCNO.findall(text)
    amt_wan = RE_AMT_WAN.findall(text)
    amt_yuan = RE_AMT_YUAN.findall(text)
    orgs = RE_ORG.findall(text)
    facts = RE_FACT.findall(text)
    return {
        "chars": len(text),
        "docno_cnt": len(docno),
        "amt_wan_cnt": len(amt_wan),
        "amt_yuan_cnt": len(amt_yuan),
        "org_cnt": len(set(orgs)),
        "fact_hits": len(facts),
        "has_person": bool(RE_PERSON.search(text)),
    }


def main() -> int:
    print("=" * 68)
    print("步骤 1｜拉取处罚公示目录")
    print("=" * 68)
    index = build_index()
    (INTERIM / "doc_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    dates = sorted(r["publishDate"][:10] for r in index if r.get("publishDate"))
    print(f"  目录条目: {len(index)} 期")
    print(f"  时间范围: {dates[0]} ~ {dates[-1]}")
    print(f"  已存: {INTERIM / 'doc_index.json'}")

    print()
    print("=" * 68)
    print(f"步骤 2｜抽样下载并解析前 {SAMPLE_N} 期 PDF")
    print("=" * 68)
    stats, first_text = [], ""
    for i, row in enumerate(index[:SAMPLE_N], 1):
        doc_id = row["docId"]
        pdf_path = RAW_PDF / f"{doc_id}.pdf"
        if pdf_path.exists() and pdf_path.stat().st_size > 1000:
            blob = pdf_path.read_bytes()
            cached = True
        else:
            blob = fetch("http://www.nfra.gov.cn" + row["pdfFileUrl"])
            pdf_path.write_bytes(blob)
            cached = False
            time.sleep(0.4)
        text, npages = pdf_text(blob)
        rec = {"docId": doc_id,
               "publishDate": row["publishDate"][:10],
               "pages": npages,
               "pdf_kb": round(len(blob) / 1024, 1),
               "cached": cached}
        rec.update(probe(text))
        stats.append(rec)
        print(f"  [{i:02d}] {doc_id} {rec['publishDate']} "
              f"{npages}页 {rec['pdf_kb']:>7.1f}KB 字符{rec['chars']:>6d} "
              f"文号{rec['docno_cnt']:>3d} 万元{rec['amt_wan_cnt']:>3d} "
              f"机构{rec['org_cnt']:>3d} 违规词{rec['fact_hits']:>3d}"
              f"{' [缓存]' if cached else ''}")
        if i == 1:
            first_text = text

    print()
    print("=" * 68)
    print("步骤 3｜字段完整率汇总")
    print("=" * 68)
    n = len(stats)
    def rate(key):
        return sum(1 for s in stats if s[key] > 0) / n
    print(f"  抽样期数            : {n}")
    print(f"  PDF 有文本层(可解析): {rate('chars'):.0%}   "
          f"(最低字符数 {min(s['chars'] for s in stats)})")
    print(f"  含决定书文号        : {rate('docno_cnt'):.0%}   "
          f"(共 {sum(s['docno_cnt'] for s in stats)} 个文号)")
    print(f"  含万元口径金额      : {rate('amt_wan_cnt'):.0%}   "
          f"(共 {sum(s['amt_wan_cnt'] for s in stats)} 处)")
    print(f"  含元口径金额        : {rate('amt_yuan_cnt'):.0%}")
    print(f"  可识别机构名称      : {rate('org_cnt'):.0%}   "
          f"(去重后 {len(set())} 个)")
    print(f"  命中信贷违规关键词  : {rate('fact_hits'):.0%}   "
          f"(共 {sum(s['fact_hits'] for s in stats)} 处)")
    print(f"  含个人处罚信息      : {rate('has_person'):.0%}")

    import csv
    with (INTERIM / "stage0_pdf_stats.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(stats[0].keys()))
        w.writeheader()
        w.writerows(stats)
    print(f"\n  已存: {INTERIM / 'stage0_pdf_stats.csv'}")

    print()
    print("=" * 68)
    print("步骤 4｜首个 PDF 的原始文本（前 1200 字，用于设计解析规则）")
    print("=" * 68)
    print(first_text[:1200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
