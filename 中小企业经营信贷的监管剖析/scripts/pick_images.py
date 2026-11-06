# -*- coding: utf-8 -*-
"""
pick_images —— 按人工挑选的编号下载原图
=====================================
候选图见 assets/web/sheet_{topic}.png（每张 4x3，左上角是编号）。
本脚本按 PICKS 里的编号下载原图、统一成 JPEG（宽度≤1600），
并把来源与标题写入 credits.json，供图注标注出处。

用法：python scripts/pick_images.py
"""
import json
import sys
import time
import urllib.request
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "assets" / "web"
CANDS = WEB / "cands.json"
CREDITS = WEB / "credits.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 人工挑选结果（题材 → 候选编号，按优先级排列，下载失败自动退到下一个）
PICKS = {
    "factory": [0, 5, 9],       # 车间工人在设备前作业
    "shop": [4, 7, 5],          # 个体小店经营实景
    "bank": [4, 6, 0],          # 银行柜台办理业务
    "regulate": [7, 5, 2, 11],  # 地方金融监管工作会议
    "contract": [1, 7, 2, 8],   # 创业担保贷款签约仪式
    "data": [0, 8, 2],          # 数据可视化大屏实景
}


def _get(url, tries=3, timeout=20):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Referer": "https://cn.bing.com/images/",
                "Accept": "image/*,*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:                        # noqa: BLE001
            last = e
            time.sleep(1.2 * (i + 1))
    raise RuntimeError(str(last))


def normalize(blob: bytes, dst: Path, max_w: int = 1600) -> bool:
    from PIL import Image
    try:
        im = Image.open(BytesIO(blob))
        im.load()
        if im.width < 700:
            return False
        if im.mode != "RGB":
            im = im.convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)),
                           Image.LANCZOS)
        im.save(dst, "JPEG", quality=88, optimize=True)
        return dst.stat().st_size > 20_000
    except Exception as e:                            # noqa: BLE001
        print("    归一化失败:", type(e).__name__)
        return False


def main() -> int:
    cands = json.loads(CANDS.read_text(encoding="utf-8"))
    credits = json.loads(CREDITS.read_text(encoding="utf-8")) if CREDITS.exists() else {}
    ok = 0
    for topic, idx_list in PICKS.items():
        items = cands.get(topic) or []
        if not isinstance(idx_list, list):
            idx_list = [idx_list]
        dst = WEB / f"{topic}.jpg"
        if dst.exists() and dst.stat().st_size > 20_000:
            print(f"  已有 {dst.name}")
            ok += 1
            continue
        done = False
        for idx in idx_list:
            hit = next((it for it in items if it.get("idx") == idx), None)
            if not hit:
                print(f"  {topic}: 无编号 {idx}")
                continue
            # 依次尝试 原图 / 中图 / 缩略图
            for key in ("murl", "mid", "turl", "thumb"):
                url = hit.get(key)
                if not url:
                    continue
                try:
                    blob = _get(url, tries=2, timeout=15)
                except Exception:                     # noqa: BLE001
                    continue
                if normalize(blob, dst):
                    host = hit["purl"].split("/")[2] if "//" in hit.get("purl", "") else ""
                    credits[topic] = {"file": dst.name, "title": hit["title"],
                                      "source": hit.get("purl", ""), "host": host,
                                      "via": key}
                    print(f"  ✅ {dst.name}  {dst.stat().st_size/1024:.0f} KB  "
                          f"[#{idx}/{key}]  {hit['title'][:34]} ← {host}")
                    ok += 1
                    done = True
                    break
                print(f"     #{idx}/{key} 不合格，换下一个")
            if done:
                break
            time.sleep(0.4)
        if not done:
            print(f"  ⚠️ {topic}: 所有候选都失败")
    CREDITS.write_text(json.dumps(credits, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    print(f"\n完成 {ok}/{len(PICKS)} 张 → {WEB}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
