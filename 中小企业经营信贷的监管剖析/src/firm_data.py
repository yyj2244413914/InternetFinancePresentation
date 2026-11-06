# -*- coding: utf-8 -*-
"""
firm_data —— 中小企业财务面板与违约标签（B 线）
==============================================
样本口径：新三板（含北交所）挂牌公司 —— 我国「中小企业」最直接的公开财务样本。
         剔除 400/420 开头的老三板（已退市），避免生存偏差与口径混杂。

数据源：东方财富 F10 主要财务指标（RPT_F10_FINANCE_MAINFINADATA，每家约 40 期）

标签定义（违约/财务困境，均可追溯到年报）：
  困境 = 下列任一在「下一年」发生
    1) 资不抵债：资产负债率 ≥ 100%
    2) 连续亏损：当年与下一年归母净利润均为负
    3) ST/*ST：证券简称含 ST
  说明：这是「财务困境」代理，非真实银行违约（银行微观数据不可得），
        论文中须明确交代该代理关系。

输出：data/processed/firm_panel.csv（一行 = 一家公司一年）
      data/processed/firm_raw/{code}.json.gz（原始财务指标缓存）
"""
from __future__ import annotations

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
PROCESSED = ROOT / "data" / "processed"
RAW = PROCESSED / "firm_raw"
RAW.mkdir(parents=True, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
WORKERS = 3
# 东财行情接口按主机分片，部分分片会随机断连；轮换分片即可稳定拿到数据
QUOTE_HOSTS = (["push2.eastmoney.com"]
               + [f"{i}.push2.eastmoney.com" for i in range(1, 100)])
_host_i = 0
_lock = threading.Lock()
_stat = {"ok": 0, "empty": 0, "fail": 0}

# 需要保留的财务字段
FIELDS = [
    "SECURITY_CODE", "SECURITY_NAME_ABBR", "REPORT_DATE", "REPORT_TYPE",
    "TOTALOPERATEREVE", "PARENTNETPROFIT", "TOTALOPERATEREVETZ", "PARENTNETPROFITTZ",
    "ZCFZL", "LD", "SD", "XJLLB", "XSMLL", "XSJLL", "ROEJQ", "ROIC", "ZZCJLL",
    "TOTAL_ASSETS_PK", "LIABILITY", "TOTAL_EQUITY_PK", "NETCASH_OPERATE_PK",
    "INTSTCOVRATE", "TOAZZL", "YSZKZZL", "CHZZL", "CA_TA", "CL_TL",
    "MGWFPLR", "PER_EBIT", "TOTAL_SHARE", "OI_YOYRATIO_PK", "TA_YOYRATIO_PK",
]


def _get(url: str, tries: int = 8) -> dict:
    """带分片轮换的请求：东财 push2 分片会随机断连，换分片重试即可。"""
    global _host_i
    import random
    import re as _re
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA,
                              "Referer": "https://quote.eastmoney.com/"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except Exception:                            # noqa: BLE001
            if "clist" in url:
                with _lock:
                    _host_i += random.randint(1, 7)
                    host = QUOTE_HOSTS[_host_i % len(QUOTE_HOSTS)]
                url = _re.sub(r"//[^/]*push2[^/]*\.eastmoney\.com", f"//{host}", url)
            time.sleep(0.25 + 0.35 * i)
    return {}


def board_list(total_pages: int = 71) -> list[dict]:
    """新三板 + 北交所全部挂牌公司。

    东财列表接口偶发整段断连，故不依赖 total 判断终止，
    而是固定翻 total_pages 页，并对失败页做多轮补抓。
    """
    out, pending = [], set(range(1, total_pages + 1))
    for rnd in range(6):
        if not pending:
            break
        print(f"  列表翻页 第 {rnd+1} 轮，待抓 {len(pending)} 页", flush=True)
        for pn in sorted(pending):
            url = ("https://push2.eastmoney.com/api/qt/clist/get"
                   f"?ut=bd1d9ddb04089700cf9c27f6f7426281&pn={pn}&pz=100"
                   "&po=1&np=1&fltt=2&invt=2&fs=m:0+t:81&fields=f12,f13,f14,f20")
            d = _get(url, tries=4)
            data = d.get("data") or {}
            diff = data.get("diff") or {}
            items = list(diff.values()) if isinstance(diff, dict) else diff
            if items:
                out.extend(items)
                pending.discard(pn)
            time.sleep(0.45)
        if pending:
            time.sleep(6)
    seen, uniq = set(), []
    for f in out:
        code = str(f.get("f12") or "")
        if code and code not in seen:
            seen.add(code)
            uniq.append(f)
    print(f"  列表完成：{len(uniq)} 家（仍缺页 {sorted(pending)}）")
    return uniq


def fetch_firm(code: str, name: str, mktcap: float) -> list[dict] | None:
    path = RAW / f"{code}.json.gz"
    rows = None
    if path.exists() and path.stat().st_size > 200:
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                rows = json.load(f)
        except Exception:                            # noqa: BLE001
            rows = None
    if rows is None:
        url = ("https://datacenter.eastmoney.com/securities/api/data/v1/get"
               "?reportName=RPT_F10_FINANCE_MAINFINADATA&columns=ALL&quoteColumns="
               f"&filter=(SECUCODE%3D%22{code}.NQ%22)&pageNumber=1&pageSize=60")
        d = _get(url)
        rows = ((d.get("result") or {}).get("data")) or []
        if not rows and code.startswith(("8", "9", "4")):
            url = url.replace(".NQ", ".BJ")
            d = _get(url)
            rows = ((d.get("result") or {}).get("data")) or []
        try:
            with gzip.open(path, "wt", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False)
        except Exception:                            # noqa: BLE001
            pass
    with _lock:
        if rows:
            _stat["ok"] += 1
        else:
            _stat["empty"] += 1
    if not rows:
        return None
    annual = [r for r in rows if str(r.get("REPORT_DATE", "")).startswith(("2020", "2021",
                                                                          "2022", "2023",
                                                                          "2024", "2025",
                                                                          "2026"))
              and "12-31" in str(r.get("REPORT_DATE", ""))]
    recs = []
    for r in annual:
        rec = {k: r.get(k) for k in FIELDS}
        rec["code"] = code
        rec["name"] = name
        rec["st"] = int("ST" in str(name))
        rec["mktcap_yi"] = round((mktcap or 0) / 1e8, 2)
        recs.append(rec)
    return recs


def main() -> int:
    firms = board_list()
    # 剔除老三板（400/420 开头为退市股）
    firms = [f for f in firms if not str(f.get("f12", "")).startswith(("400", "420"))]
    print(f"候选公司 {len(firms)} 家（已剔除老三板）")

    rows: list[dict] = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch_firm, str(f.get("f12")), f.get("f14") or "",
                          f.get("f20")): f for f in firms}
        done = 0
        for fut in as_completed(futs):
            done += 1
            try:
                recs = fut.result()
            except Exception:                        # noqa: BLE001
                recs = None
                _stat["fail"] += 1
            if recs:
                rows.extend(recs)
            if done % 400 == 0:
                el = time.time() - t0
                print(f"  {done}/{len(firms)}  {done/max(el,1e-6):.1f} 家/秒  "
                      f"记录 {len(rows)}  空 {_stat['empty']}  失败 {_stat['fail']}  "
                      f"剩余 {(len(firms)-done)/max(done/max(el,1e-6),1e-6)/60:.0f} 分钟",
                      flush=True)

    df = pd.DataFrame(rows)
    if df.empty:
        print("未取得任何数据")
        return 1
    df["year"] = df["REPORT_DATE"].astype(str).str[:4].astype(int)
    df = df.sort_values(["code", "year"])
    out = PROCESSED / "firm_panel.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n已存 {out}  形状 {df.shape}")
    print(f"公司数 {df['code'].nunique()}  年份 {df['year'].min()}-{df['year'].max()}")
    print(df["year"].value_counts().sort_index().to_string())
    print(f"统计 {_stat}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
