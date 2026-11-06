# -*- coding: utf-8 -*-
"""
rebuild_firm_panel —— 从原始财务缓存重建企业面板
==============================================
东财列表接口限速导致「公司名单」抓不全，但已抓到的财务原文都在
data/processed/firm_raw/{code}.json.gz 里。本脚本直接遍历缓存重建面板，
不再依赖名单接口 —— 抓多少用多少，且可随时补齐后续扩样。

输出：data/processed/firm_panel.csv
"""
import gzip
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW = PROCESSED / "firm_raw"

FIELDS = [
    "SECURITY_CODE", "SECURITY_NAME_ABBR", "REPORT_DATE", "REPORT_TYPE",
    "TOTALOPERATEREVE", "PARENTNETPROFIT", "TOTALOPERATEREVETZ", "PARENTNETPROFITTZ",
    "ZCFZL", "LD", "SD", "XJLLB", "XSMLL", "XSJLL", "ROEJQ", "ROIC", "ZZCJLL",
    "TOTAL_ASSETS_PK", "LIABILITY", "TOTAL_EQUITY_PK", "NETCASH_OPERATE_PK",
    "INTSTCOVRATE", "TOAZZL", "YSZKZZL", "CHZZL", "CA_TA", "CL_TL",
    "MGWFPLR", "PER_EBIT", "TOTAL_SHARE", "OI_YOYRATIO_PK", "TA_YOYRATIO_PK",
]
KEEP_YEARS = ("2020", "2021", "2022", "2023", "2024", "2025")


def main() -> int:
    files = sorted(RAW.glob("*.json.gz"))
    print(f"财务缓存 {len(files)} 份")
    rows = []
    for i, p in enumerate(files, 1):
        code = p.stem.split(".")[0]
        try:
            with gzip.open(p, "rt", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:                            # noqa: BLE001
            continue
        if not data:
            continue
        for r in data:
            rd = str(r.get("REPORT_DATE", ""))
            if not rd.startswith(KEEP_YEARS) or "12-31" not in rd:
                continue
            rec = {k: r.get(k) for k in FIELDS}
            name = str(r.get("SECURITY_NAME_ABBR") or "")
            rec["code"] = code
            rec["name"] = name
            rec["st"] = int("ST" in name)
            rec["mktcap_yi"] = None
            rows.append(rec)
        if i % 200 == 0:
            print(f"  {i}/{len(files)} → {len(rows)} 条", flush=True)

    df = pd.DataFrame(rows)
    if df.empty:
        print("无数据")
        return 1
    df["year"] = df["REPORT_DATE"].astype(str).str[:4].astype(int)
    df = df.sort_values(["code", "year"]).reset_index(drop=True)
    out = PROCESSED / "firm_panel.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n已存 {out}  形状 {df.shape}")
    print(f"公司数 {df['code'].nunique()}  年份 {df['year'].min()}-{df['year'].max()}")
    print(df["year"].value_counts().sort_index().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
