# -*- coding: utf-8 -*-
"""
diagnose_slides —— 结构体检：定位 slides.html 打不开的原因
=======================================================
检查项：
  1. <script> / </script> 是否配平（不平衡会让整页脚本失效 → 白屏）
  2. 我注入的代码块是否落在 <body> 之外或嵌进了别处
  3. reveal.js 本体是否内联存在
  4. 是否存在裸 MathJax 调用
  5. <section> 数量与页数是否一致
  6. 是否有非法字符/未闭合的 <img> 或 data URI
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "汇报_放映版.slides.html"


def main() -> int:
    if not TARGET.exists():
        print("文件不存在:", TARGET)
        return 1
    txt = TARGET.read_text(encoding="utf-8", errors="ignore")
    print(f"文件: {TARGET.name}   {len(txt)/1024/1024:.2f} MB\n")

    ok = True

    # ---- 1. script 配平
    open_s = len(re.findall(r"<script\b", txt, re.I))
    close_s = len(re.findall(r"</script>", txt, re.I))
    print(f"[1] <script> {open_s} 个 / </script> {close_s} 个", "✅" if open_s == close_s else "❌ 不配平")
    ok &= open_s == close_s

    # ---- 2. 结构位置
    i_body = txt.find("<body")
    i_body_end = txt.rfind("</body>")
    i_custom = txt.find("ds-custom:begin")
    i_stub = txt.find("ds-mathjax-stub")
    i_init = txt.find("Reveal.initialize")
    print(f"[2] <body>={i_body}  ds-custom:begin={i_custom}  </body>={i_body_end}")
    print(f"    桩位置={i_stub}  Reveal.initialize={i_init}")
    in_body = i_body < i_custom < i_body_end
    stub_before = 0 <= i_stub < i_init
    print(f"    控制条在 body 内: {'✅' if in_body else '❌'}"
          f"   MathJax 桩在 init 之前: {'✅' if stub_before else '❌'}")
    ok &= in_body and stub_before

    # ---- 3. reveal 本体
    has_reveal = txt.count("Reveal.initialize") >= 1 and (
        "var Reveal" in txt or "window.Reveal" in txt or "Reveal = " in txt)
    print(f"[3] reveal.js 内联存在: {'✅' if has_reveal else '❌'}")
    ok &= has_reveal

    # ---- 4. 裸 MathJax
    bare = len(re.findall(r"if\(\s*MathJax\.Hub", txt))
    print(f"[4] 裸 MathJax 调用: {bare} 处 {'✅' if bare == 0 else '❌'}")
    ok &= bare == 0

    # ---- 5. section 与页数
    n_sec = len(re.findall(r"<section\b", txt))
    print(f"[5] <section> 数量: {n_sec}（= 页数 × 2，nbconvert 固定双层）")

    # ---- 6. 危险片段
    print("[6] 危险片段扫描:")
    for pat, desc in [
        (r"</script>\s*</body>", "script 提前闭合"),
        (r"<script[^>]*>\s*<script", "script 嵌套"),
        (r'alt="[^"]*"[^>]*>base64', "base64 混入属性"),
    ]:
        hits = len(re.findall(pat, txt, re.I))
        print(f"    {desc}: {hits}")

    # ---- 7. 外部依赖
    ext = re.findall(r'(?:src|href)="(https?://[^"]+)"', txt)
    print(f"[7] 外部依赖: {len(ext)} 处")
    for e in ext[:8]:
        print("    ", e)

    print()
    print("结论:", "✅ 结构正常" if ok else "❌ 存在结构问题")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
