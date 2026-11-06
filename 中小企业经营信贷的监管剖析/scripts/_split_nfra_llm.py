# -*- coding: utf-8 -*-
"""只改 3.3 监管侧：把「只抓 SME」拆成 ① NFRA 抓取全部 ② 大模型筛 SME 落本地。结构问题不动。"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "汇报_中小企业经营信贷的监管剖析.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))
cells = nb["cells"]

def src(c):
    return "".join(c.get("source", []))

NEW_REG = """##### 监管侧：NFRA 抓全部 → 大模型筛出「中小企业信贷」

1. **抓取**：从金融监管总局的处罚公示接口，目录 → 详情，抓取处罚（本篇累计 29,859 期 / 37,236 条）。
2. **筛选**：把每条正文交给大模型，判断"是否与中小企业信贷有关"，**只把有关的落本地**。

> 处罚对象是银行，但筛选条件锁定的是"因给中小企业放贷而出的事"。
"""

CRAWL = '''# 监管侧 ①：从 NFRA 抓取处罚公示（目录 → 详情）
import json, time, urllib.request

_UA_NFRA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

def _get_nfra(url, timeout=25):
    req = urllib.request.Request(url, headers={**_UA_NFRA, "Referer": "http://www.nfra.gov.cn/"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8-sig", "ignore"))

def crawl_nfra(max_pages=1, page_size=10):
    """抓取处罚公示：max_pages=None 表示抓全部（约 1,500 页，耗时较长）。"""
    out, page = [], 1
    while True:
        d = _get_nfra("http://www.nfra.gov.cn/cbircweb/DocInfo/SelectDocByItemIdAndChild"
                      f"?itemId=4293&pageSize={page_size}&pageIndex={page}")
        rows = d["data"]["rows"]
        for r in rows:
            try:
                detail = _get_nfra("http://www.nfra.gov.cn/cbircweb/DocInfo/SelectByDocId"
                                   f"?docId={r['docId']}")["data"]
            except Exception:
                detail = {}
            out.append({"docId": r["docId"],
                        "标题": r.get("docTitle") or r.get("docSubtitle") or "",
                        "日期": str(r.get("publishDate") or "")[:10],
                        "正文": detail.get("docClob") or ""})
        if max_pages and page >= max_pages:
            break
        page += 1
    return out

_rows = crawl_nfra(max_pages=1, page_size=10)
display(Markdown(f"从 NFRA 抓取 **{len(_rows)} 条**处罚公示"
                 f"（演示抓 1 页；要抓全部把 `max_pages` 设为 `None`）"))
display(pd.DataFrame(_rows)[["docId", "标题", "日期"]])
'''

SELECT = '''# 监管侧 ②：调用大模型判断「是否与中小企业信贷有关」，只把有关的落本地
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

_picked = []
t0 = time.time()
for r in _rows:
    rec = _ask_sme(r["标题"], r["正文"])
    r.update(rec)
    if rec.get("有关"):
        _picked.append(r)

_sme_df = pd.DataFrame(_picked)
if len(_sme_df):
    _sme_df[["docId", "标题", "日期", "理由"]].to_csv(
        "data/processed/llm_sme_selected.csv", index=False, encoding="utf-8-sig")
display(Markdown(f"大模型判定：**{len(_picked)} / {len(_rows)}** 条与中小企业信贷有关，"
                 f"已落本地 `data/processed/llm_sme_selected.csv`（耗时 {time.time()-t0:.1f}s）"))
if len(_sme_df):
    display(_sme_df[["docId", "标题", "理由"]])
else:
    display(Markdown("本批未命中；可把 `max_pages` 调大再跑。"))
'''

idx_reg = next(i for i, c in enumerate(cells) if "##### 监管侧" in src(c))
print("监管侧 md:", idx_reg)

# 保留原 cell 第一行（如果有「第一部分」结构行），只替换监管侧正文
old = src(cells[idx_reg])
first = old.splitlines()[0] if old.splitlines() else ""
prefix = first + "\n" if first.strip().startswith("#### 第一部分") else ""
cells[idx_reg]["source"] = prefix + NEW_REG

cells[idx_reg + 1:idx_reg + 1] = [
    {"cell_type": "code", "metadata": {"slideshow": {"slide_type": "subslide"}},
     "source": CRAWL, "outputs": [], "execution_count": None},
    {"cell_type": "code", "metadata": {"slideshow": {"slide_type": "subslide"}},
     "source": SELECT, "outputs": [], "execution_count": None},
]

nb["cells"] = cells
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("done, cells =", len(cells))
