# -*- coding: utf-8 -*-
"""验证大模型判断：拿已知 SME 处罚 vs 普通处罚各一条，看它判得对不对。"""
import json, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import data_access as da
from llm_config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

def ask(title, text):
    prompt = (
        "下面是金融监管的一条处罚公示。请判断它是否与**中小企业信贷**直接相关"
        "（涉及小微/普惠/个体工商户/经营贷/涉农等客群，且与信贷业务有关）。"
        '只输出 JSON：{"有关": true 或 false, "理由": "一句话"}\n\n'
        f"标题：{title}\n正文：{text[:1000]}"
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
        return json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]

sme = da.sme_credit_events()
allv = da.events()
s = sme.iloc[0]
g = allv[~allv["docId"].isin(sme["docId"])].iloc[0]

print("【已知 SME 处罚】", str(s["标题"])[:40])
print(ask(str(s["标题"]), str(s["违法违规事实"])))
print()
print("【普通处罚】", str(g["标题"])[:40])
print(ask(str(g["标题"]), str(g["违法违规事实"])))
