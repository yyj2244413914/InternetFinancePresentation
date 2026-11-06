# -*- coding: utf-8 -*-
"""把监管侧改成流水线：① 抓取函数 ② 循环「抓一页→过大模型→落盘」直到抓完。"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "汇报_中小企业经营信贷的监管剖析.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))
cells = nb["cells"]

def src(c):
    return "".join(c.get("source", []))

CELL1 = '''# 监管侧 ①：NFRA 抓取函数（按页抓，可一直抓到全部）
import json, time, urllib.request

_UA_NFRA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

def _get_nfra(url, timeout=25):
    req = urllib.request.Request(url, headers={**_UA_NFRA, "Referer": "http://www.nfra.gov.cn/"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8-sig", "ignore"))

def crawl_page(page, page_size=10):
    """抓第 page 页（目录 → 详情），返回记录列表。"""
    d = _get_nfra("http://www.nfra.gov.cn/cbircweb/DocInfo/SelectDocByItemIdAndChild"
                  f"?itemId=4293&pageSize={page_size}&pageIndex={page}")
    out = []
    for r in d["data"]["rows"]:
        try:
            detail = _get_nfra("http://www.nfra.gov.cn/cbircweb/DocInfo/SelectByDocId"
                               f"?docId={r['docId']}")["data"]
        except Exception:
            detail = {}
        out.append({"docId": r["docId"],
                    "标题": r.get("docTitle") or r.get("docSubtitle") or "",
                    "日期": str(r.get("publishDate") or "")[:10],
                    "正文": detail.get("docClob") or ""})
    return out

# 先抓第 1 页看看
_p1 = crawl_page(1)
display(Markdown(f"第 1 页抓到 **{len(_p1)} 条**（下一步会把每页都丢给大模型逐条判断）"))
display(pd.DataFrame(_p1)[["docId", "标题", "日期"]])
'''

CELL2 = '''# 监管侧 ②：循环「抓一页 → 丢给大模型 → 落盘」→ 下一页，直到抓完
import json, time, urllib.request
try:
    from llm_config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
except ImportError:
    import os
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"
    DEEPSEEK_MODEL = "deepseek-chat"

def _ask_sme(title, text):
    prompt = (
        "下面是金融监管的一条处罚公示。请判断它是否与**中小企业信贷**直接相关"
        "（涉及小微/普惠/个体工商户/经营贷/涉农等客群，且与信贷业务有关）。"
        '只输出 JSON：{"有关": true 或 false, "理由": "一句话"}\\n\\n'
        f"标题：{title}\\n正文：{text[:1000]}"
    )
    payload = {"model": DEEPSEEK_MODEL,
               "messages": [{"role": "system", "content": "你是金融监管文本判断助手，只输出严格 JSON。"},
                            {"role": "user", "content": prompt}],
               "temperature": 0, "max_tokens": 200, "stream": False}
    req = urllib.request.Request(f"{DEEPSEEK_BASE_URL}/chat/completions",
                                 data=json.dumps(payload).encode("utf-8"),
                                 headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read().decode("utf-8"))
    ans = resp["choices"][0]["message"]["content"]
    import re
    m = re.search(r"\\{.*\\}", ans, re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}

MAX_PAGES = 5          # 演示抓 5 页；设为 None 就是一直抓到全部（约 1,500 页，耗时很长）
PAGE_SIZE = 10

selected = []
page = 1
t0 = time.time()
while True:
    if MAX_PAGES and page > MAX_PAGES:
        break
    rows = crawl_page(page, PAGE_SIZE)
    if not rows:
        break
    for r in rows:
        rec = _ask_sme(r["标题"], r["正文"])
        r.update(rec)
        if rec.get("有关"):
            selected.append(r)
    if selected:
        pd.DataFrame(selected)[["docId", "标题", "日期", "理由"]].to_csv(
            "data/processed/llm_sme_selected.csv", index=False, encoding="utf-8-sig")
    print(f"第 {page:>3} 页：本页 {len(rows)} 条，累计命中 {len(selected)} 条")
    page += 1

display(Markdown(f"循环抓了 **{page-1} 页 / {page-1}×{PAGE_SIZE} 条**，"
                 f"大模型判定与中小企业信贷有关 **{len(selected)} 条**，已落本地"
                 f"（耗时 {time.time()-t0:.1f}s）"))
if selected:
    display(pd.DataFrame(selected)[["docId", "标题", "理由"]])
else:
    display(Markdown("本批未命中；把 `MAX_PAGES` 调大再跑。"))
'''

idx = next(i for i, c in enumerate(cells) if "crawl_nfra" in src(c))
nxt = idx + 1
assert "_ask_sme" in src(cells[nxt]), "下一个 cell 不是大模型筛选"
cells[idx]["source"] = CELL1
cells[nxt]["source"] = CELL2
print(f"已替换 [{idx}] 抓取函数 + [{nxt}] 循环筛选")

nb["cells"] = cells
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("done")
