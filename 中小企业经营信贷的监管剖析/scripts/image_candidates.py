# -*- coding: utf-8 -*-
"""
image_candidates —— 生成候选拼图，供人工挑选
==========================================
为什么要拼图：Bing 的匹配质量一般（搜 "small factory" 会给你《small》期刊封面），
逐张下载再看太慢。这里先把每个题材的候选缩略图拼成一张带编号的大图，
一眼挑出合适的编号，再下原图。

输出：assets/web/sheet_{topic}.png   每张 3x4 共 12 个候选，左上角标编号
      assets/web/cands.json         候选清单（编号 → murl/purl/标题）
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "web"
OUT.mkdir(parents=True, exist_ok=True)
CANDS = OUT / "cands.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
BING = "https://cn.bing.com/images/async"     # 必应中国，中文结果相关性明显更好
QFT = "+filterui:aspect-wide"

# 题材 → 中文检索词（偏向新闻实景照片，避开素材站渲染图与展厅效果图）
TOPICS = {
    "factory":  ["中小企业 生产车间 实景 工人"],
    "shop":     ["小微企业 个体工商户 店铺 经营 实景"],
    "bank":     ["银行 营业厅 客户 办理业务 现场"],
    "regulate": ["金融监管 工作会议 现场"],
    "contract": ["创业担保贷款 签约 仪式 银行"],
    "data":     ["金融 数据分析 大屏 现场"],
}

COLS, ROWS = 4, 3


def _get(url, tries=2, timeout=10, binary=False):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Referer": "https://cn.bing.com/images/",
                "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:                        # noqa: BLE001
            last = e
            time.sleep(0.8 * (i + 1))
    raise RuntimeError(str(last))


def search(query, n=12):
    url = (BING + "?q=" + urllib.parse.quote(query)
           + f"&first=0&count={n}&mkt=zh-CN&adlt=off")
    html = _get(url, tries=3, timeout=18).decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r'm="(\{[^"]*?\})"', html):
        raw = (m.group(1).replace("&quot;", '"').replace("&amp;", "&")
               .replace("\\/", "/"))
        try:
            d = json.loads(raw)
        except Exception:                             # noqa: BLE001
            continue
        if not d.get("murl"):
            continue
        out.append({"murl": d["murl"], "turl": d.get("turl") or d["murl"],
                    "purl": d.get("purl", ""),
                    "title": re.sub(r"<[^>]+>", "", str(d.get("t") or ""))[:70]})
        if len(out) >= n:
            break
    return out


def build_sheet(topic, items):
    from PIL import Image, ImageDraw, ImageFont
    cell_w, cell_h, pad = 380, 250, 8
    sheet = Image.new("RGB", (COLS * cell_w, ROWS * cell_h), (245, 246, 248))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("msyh.ttc", 22)
    except Exception:                                 # noqa: BLE001
        font = ImageFont.load_default()
    kept = []
    for idx, it in enumerate(items[:COLS * ROWS]):
        try:
            blob = _get(it["turl"], tries=2, timeout=12)
            im = Image.open(BytesIO(blob)).convert("RGB")
        except Exception:                             # noqa: BLE001
            continue
        im.thumbnail((cell_w - 2 * pad, cell_h - 2 * pad - 26))
        r, c = divmod(len(kept), COLS)
        x = c * cell_w + (cell_w - im.width) // 2
        y = r * cell_h + 26 + (cell_h - 26 - im.height) // 2
        sheet.paste(im, (x, y))
        label = f"#{len(kept)}"
        draw.rectangle([c * cell_w + 4, r * cell_h + 2,
                        c * cell_w + 74, r * cell_h + 28], fill=(31, 78, 121))
        draw.text((c * cell_w + 10, r * cell_h + 3), label, fill=(255, 255, 255),
                  font=font)
        it["idx"] = len(kept)
        kept.append(it)
    p = OUT / f"sheet_{topic}.png"
    sheet.save(p, "PNG")
    return p, kept


def main():
    registry = json.loads(CANDS.read_text(encoding="utf-8")) if CANDS.exists() else {}
    for topic, queries in TOPICS.items():
        items = []
        for q in queries:
            try:
                items += search(q)
            except Exception as e:                    # noqa: BLE001
                print(f"  {topic}: 检索失败 {type(e).__name__}")
            if len(items) >= COLS * ROWS:
                break
            time.sleep(0.4)
        # 去重
        seen, uniq = set(), []
        for it in items:
            if it["murl"] not in seen:
                seen.add(it["murl"])
                uniq.append(it)
        p, kept = build_sheet(topic, uniq)
        registry[topic] = kept
        print(f"  {topic}: 候选 {len(kept)} 个 → {p.name}")
    CANDS.write_text(json.dumps(registry, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"\n候选清单 → {CANDS}")
    print("下一步：查看 sheet_*.png，把选中的编号告诉我，或直接改 TOPIC_PICKS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
