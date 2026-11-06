# -*- coding: utf-8 -*-
"""
bank_fin —— 上市银行营业收入数据（A 线资本对照用）
================================================
数据源：东方财富公开接口
  成分股   push2.eastmoney.com/api/qt/clist/get?fs=b:BK0475
  财务指标 datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_LICO_FN_CPD

用途：为「基本指标法 K=α·GI」与「新标准法 K=β(BI)·BI」提供 GI/BI，
      与 LDA 得到的实测损失 VaR 做量级对比。

口径说明：
  · GI 取年报（12-31）营业总收入 TOTAL_OPERATE_INCOME，单位亿元
  · 新标准法的业务指标 BI 严格口径为「利息租赁股利+服务+金融资产」，
    此处以营业总收入近似，属偏保守（略高估）的替代口径
输出：data/processed/bank_fin.csv
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

BANK_TYPE = [
    ("国有大型银行", ["工商银行", "农业银行", "中国银行", "建设银行", "交通银行",
                     "邮储银行", "邮政储蓄"]),
    ("股份制银行", ["招商银行", "浦发银行", "中信银行", "光大银行", "华夏银行",
                   "民生银行", "兴业银行", "广发银行", "平安银行", "浙商银行",
                   "渤海银行", "恒丰银行"]),
    ("农商行", ["常熟银行", "紫金银行", "无锡银行", "张家港行", "苏农银行",
               "江阴银行", "瑞丰银行", "沪农商行", "渝农商行", "青农商行",
               "农商行", "农村商业银行"]),
    ("城商行", ["北京银行", "上海银行", "江苏银行", "南京银行", "宁波银行",
               "杭州银行", "成都银行", "长沙银行", "郑州银行", "青岛银行",
               "苏州银行", "西安银行", "贵阳银行", "齐鲁银行", "兰州银行",
               "厦门银行", "重庆银行"]),
]


def _get(url: str, tries: int = 3) -> dict:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except Exception:                            # noqa: BLE001
            time.sleep(1.2 * (i + 1))
    return {}


def bank_list() -> list[dict]:
    out, page = [], 1
    while True:
        url = (f"https://push2.eastmoney.com/api/qt/clist/get?pn={page}&pz=50"
               f"&po=1&np=1&fltt=2&invt=2&fs=b:BK0475&fields=f12,f14,f20")
        d = _get(url)
        data = d.get("data") or {}
        diff = data.get("diff") or {}
        items = list(diff.values()) if isinstance(diff, dict) else diff
        if not items:
            break
        out.extend(items)
        if len(out) >= (data.get("total") or 0):
            break
        page += 1
        time.sleep(0.2)
    return out


def classify(name: str) -> str:
    for label, keys in BANK_TYPE:
        if any(k in name for k in keys):
            return label
    if "农商" in name or "农村" in name:
        return "农商行"
    if "银行" in name:
        return "城商行"
    return "其他"


def financials(code: str) -> pd.DataFrame:
    url = ("https://datacenter-web.eastmoney.com/api/data/v1/get"
           f"?reportName=RPT_LICO_FN_CPD&columns=ALL"
           f"&filter=(SECURITY_CODE%3D%22{code}%22)"
           "&pageNumber=1&pageSize=40&sortColumns=REPORTDATE&sortTypes=-1")
    d = _get(url)
    res = d.get("result") or {}
    rows = res.get("data") or []
    return pd.DataFrame(rows)


def main() -> int:
    banks = bank_list()
    print(f"上市银行 {len(banks)} 家")
    records = []
    for i, b in enumerate(banks, 1):
        code = b.get("f12")
        name = b.get("f14")
        if not code or not name:
            continue
        df = financials(code)
        if df.empty:
            print(f"  [{i:02d}] {code} {name} 无财务数据")
            continue
        df["year"] = df["REPORTDATE"].astype(str).str[:4]
        annual = df[df["REPORTDATE"].astype(str).str.contains("12-31")]
        annual = annual.drop_duplicates("year").set_index("year")
        rec = {"code": code, "name": name, "bank_type": classify(name),
               "mktcap_yi": round((b.get("f20") or 0) / 1e8, 1)}
        for y in ["2022", "2023", "2024", "2025"]:
            if y in annual.index:
                v = annual.loc[y, "TOTAL_OPERATE_INCOME"]
                rec[f"gi_{y}"] = round(v / 1e8, 2) if pd.notna(v) else None
        gis = [rec.get(f"gi_{y}") for y in ["2022", "2023", "2024", "2025"]]
        gis = [g for g in gis if g and g > 0]
        rec["gi_avg3"] = round(sum(gis[-3:]) / len(gis[-3:]), 2) if gis else None
        records.append(rec)
        print(f"  [{i:02d}] {code} {name:<8} {rec['bank_type']:<7} "
              f"GI均值3年 {rec['gi_avg3']} 亿元")
        time.sleep(0.25)

    df = pd.DataFrame(records).sort_values("gi_avg3", ascending=False)
    out = PROCESSED / "bank_fin.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n已存 {out}  共 {len(df)} 家")
    print(df.groupby("bank_type")["gi_avg3"].describe().round(1).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
