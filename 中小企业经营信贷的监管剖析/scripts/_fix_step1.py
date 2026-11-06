# -*- coding: utf-8 -*-
"""修正第一步 code：换成真正的东财爬取代码（而不是 md 文本）。"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "汇报_中小企业经营信贷的监管剖析.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))
cells = nb["cells"]

FIRM = '''# 第一步：实时抓取 5 家中小企业财务指标（东财 datacenter）
import json, time, urllib.request

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={**_UA, "Referer": "https://data.eastmoney.com/"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8-sig", "ignore"))

def _fin(code):
    """抓一家公司的财务指标（新三板 .NQ，北交所 .BJ 兜底）"""
    for suffix in (".NQ", ".BJ"):
        url = ("https://datacenter.eastmoney.com/securities/api/data/v1/get"
               "?reportName=RPT_F10_FINANCE_MAINFINADATA&columns=ALL&quoteColumns="
               f"&filter=(SECUCODE%3D%22{code}{suffix}%22)&pageNumber=1&pageSize=2")
        try:
            d = _get(url)
            data = ((d.get("result") or {}).get("data")) or []
            if data:
                return data[0]
        except Exception:
            pass
    return None

try:
    panel = da.firm_panel()
    codes = panel[["code", "name"]].drop_duplicates("code").head(5).values.tolist()
    display(Markdown(f"**实时抓取 {len(codes)} 家中小企业财务指标**（东财 datacenter 接口）"))

    rows = []
    t0 = time.time()
    for code, name in codes:
        r = _fin(code)
        if r:
            rows.append({
                "代码": code,
                "名称": name,
                "报告期": str(r.get("REPORT_DATE"))[:10],
                "营业总收入(亿元)": round((r.get("TOTALOPERATEREVE") or 0) / 1e8, 2),
                "归母净利润(亿元)": round((r.get("PARENTNETPROFIT") or 0) / 1e8, 2),
                "资产负债率(%)": round(r.get("ZCFZL") or 0, 2),
            })
    display(pd.DataFrame(rows))
    display(Markdown(f"耗时 **{time.time()-t0:.2f}s**"))
except Exception as e:
    display(Markdown(f"⚠️ 抓取失败（`{type(e).__name__}`），改用本地已抓取面板。"))
'''

for i, c in enumerate(cells):
    s = "".join(c.get("source", []))
    if c.get("cell_type") == "code" and s.strip().startswith("#### 第一部分"):
        c["source"] = FIRM
        c["outputs"] = []
        c["execution_count"] = None
        print(f"cell [{i}] 已换成东财抓取代码")
        break

NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("done")
