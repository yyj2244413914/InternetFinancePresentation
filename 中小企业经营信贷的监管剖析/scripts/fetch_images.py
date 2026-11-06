# -*- coding: utf-8 -*-
"""
fetch_images —— 抓取配图并记录来源与许可
========================================
环境限制：commons.wikimedia.org / openverse / pixabay 网页均不可达，
只有 www.bing.com 可访问。因此改用 Bing 图片搜索，并**强制授权筛选**：

    qft=+filterui:license-L2_L3_L4
      L2 = Free to share and use
      L3 = Free to share and use commercially
      L4 = Free to modify, share, and use commercially

抓到的每张图都会记录：检索词、来源页面（purl）、图片直链（murl），
写入 assets/web/credits.json，汇报时在图注下方标注出处。

输出：assets/web/{name}.jpg  +  credits.json
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "web"
OUT.mkdir(parents=True, exist_ok=True)
CREDITS = OUT / "credits.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
BING = "https://www.bing.com/images/search"

# 想配图的位置 → 多组检索词（中英混用，提高命中合适题材的概率）
WANTED = {
    "sme_factory":   ["small factory workshop production line",
                      "中小企业 工厂 车间 生产"],
    "sme_shop":      ["small business shop owner street market",
                      "小微企业 店铺 经营"],
    "bank_branch":   ["bank branch counter customer service",
                      "银行 营业厅 柜台"],
    "regulator":     ["banking supervision conference meeting",
                      "金融监管 会议 合规"],
    "loan_docs":     ["loan agreement contract signing documents",
                      "贷款 合同 签署 文件"],
    "data_risk":     ["data analysis dashboard computer screen finance",
                      "数据分析 屏幕 金融"],
    "audit_review":  ["auditor reviewing financial documents desk",
                      "审计 财务报表 核对"],
    "sme_support":   ["government support small business finance policy",
                      "普惠金融 小微企业 扶持"],
}

LICENSE_QFT = "+filterui:license-L2_L3_L4"     # 可商用 / 可修改


def _get(url: str, tries: int = 3, timeout: int = 20) -> bytes:
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,image/*,*/*",
                "Referer": "https://www.bing.com/",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:                        # noqa: BLE001
            last = e
            time.sleep(1.2 * (i + 1))
    raise RuntimeError(str(last))


def search(query: str, n: int = 12) -> list[dict]:
    """返回 [{murl, purl, title}]，来自 Bing 图片 HTML 内嵌的 m="..." JSON。"""
    params = {"q": query, "qft": LICENSE_QFT, "form": "HDRSC2", "first": "1"}
    html = _get(BING + "?" + urllib.parse.urlencode(params)).decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r'm="(\{[^"]*?\})"', html):
        raw = m.group(1).replace("&quot;", '"')
        try:
            d = json.loads(raw)
        except Exception:                             # noqa: BLE001
            continue
        murl, purl = d.get("murl"), d.get("purl")
        if not murl or not purl:
            continue
        out.append({"murl": murl, "purl": purl,
                    "title": re.sub(r"<[^>]+>", "", d.get("t") or "")[:80]})
        if len(out) >= n:
            break
    return out


def normalize(blob: bytes, dst: Path, max_w: int = 1600) -> bool:
    """校验并统一成 JPEG（宽度上限 max_w），失败返回 False。"""
    try:
        from io import BytesIO

        from PIL import Image
    except ImportError:
        dst.write_bytes(blob)
        return True
    try:
        im = Image.open(BytesIO(blob))
        im.load()
        if im.width < 700 or im.height < 380:
            return False
        if im.mode in ("RGBA", "P", "LA"):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im.convert("RGBA"), mask=im.convert("RGBA").split()[-1])
            im = bg
        elif im.mode != "RGB":
            im = im.convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)),
                           Image.LANCZOS)
        im.save(dst, "JPEG", quality=86, optimize=True)
        return dst.stat().st_size > 15_000
    except Exception:                                 # noqa: BLE001
        return False


def main() -> int:
    credits = json.loads(CREDITS.read_text(encoding="utf-8")) if CREDITS.exists() else {}
    got = 0
    for name, queries in WANTED.items():
        dst = OUT / f"{name}.jpg"
        if dst.exists() and dst.stat().st_size > 15_000:
            print(f"  已有 {name}.jpg")
            got += 1
            continue
        done = False
        for q in queries:
            try:
                cands = search(q)
            except Exception as e:                    # noqa: BLE001
                print(f"  {name}: 检索失败 {type(e).__name__}")
                continue
            print(f"  {name}: 「{q}」命中 {len(cands)} 条候选")
            for c in cands:
                try:
                    blob = _get(c["murl"], tries=2, timeout=15)
                except Exception:                     # noqa: BLE001
                    continue
                if len(blob) < 15_000:
                    continue
                if not normalize(blob, dst):
                    continue
                credits[name] = {
                    "file": dst.name, "query": q,
                    "title": c["title"], "page": c["purl"],
                    "license_filter": "Bing license L2/L3/L4 (可共享·可商用·可修改)",
                }
                print(f"    ✅ {dst.name}  {dst.stat().st_size/1024:.0f} KB  ← {c['purl'][:60]}")
                got += 1
                done = True
                break
            if done:
                break
            time.sleep(0.5)
        if not done:
            print(f"    ⚠️ {name}: 未取到")
    CREDITS.write_text(json.dumps(credits, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    print(f"\n完成 {got}/{len(WANTED)} 张 → {OUT}")
    return 0 if got else 1


if __name__ == "__main__":
    sys.exit(main())
