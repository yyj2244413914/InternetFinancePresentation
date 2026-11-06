# -*- coding: utf-8 -*-
"""
make_offline_html —— 生成可离线放映的 HTML / 幻灯片
==================================================
问题：nbconvert 输出的 HTML 会引用外部 CDN
  - slides 模式：unpkg 的 reveal.css / simple.css、cdnjs 的 jquery / require
  - 静态 HTML：cdnjs 的 require.js / mathjax
教室断网或校园网屏蔽 CDN 时，幻灯片会丢失样式而"白屏"。

本脚本：把所需静态资源下载到 slides_assets/，再把 HTML 里的外链改写为本地相对路径，
使产物在完全离线的电脑上也能正常放映（U 盘拷走即可用）。
"""
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "slides_assets"
ASSETS.mkdir(exist_ok=True)

NB = "汇报_中小企业经营信贷的监管剖析.ipynb"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

# 远程地址 → 本地文件名
REMOTE = {
    "https://unpkg.com/reveal.js@4.0.2/dist/reveal.css": "reveal.css",
    "https://unpkg.com/reveal.js@4.0.2/dist/theme/simple.css": "reveal-simple.css",
    # ↓ 关键：reveal.js 主体与 notes 插件是用 RequireJS 在线加载的。
    #   不本地化的话，断网/慢网时 require 超时 → Reveal.initialize 永不执行 → 白屏。
    "https://unpkg.com/reveal.js@4.0.2/dist/reveal.js": "reveal-4.0.2.js",
    "https://unpkg.com/reveal.js@4.0.2/plugin/notes/notes.js": "reveal-notes.js",
    "https://unpkg.com/jquery@3.7.1/dist/jquery.min.js": "jquery.min.js",
    "https://unpkg.com/requirejs@2.1.10/require.min.js": "require.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/jquery/2.0.3/jquery.min.js": "jquery.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/require.js/2.1.10/require.min.js": "require.min.js",
}
# 备用镜像（某个 CDN 超时也能取到）
MIRRORS = {
    "jquery.min.js": ["https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js",
                      "https://cdn.bootcdn.net/ajax/libs/jquery/3.7.1/jquery.min.js"],
    "require.min.js": ["https://cdn.jsdelivr.net/npm/requirejs@2.1.10/require.min.js"],
    "reveal.css": ["https://cdn.jsdelivr.net/npm/reveal.js@4.0.2/dist/reveal.css"],
    "reveal-simple.css": ["https://cdn.jsdelivr.net/npm/reveal.js@4.0.2/dist/theme/simple.css"],
    "reveal-4.0.2.js": ["https://cdn.jsdelivr.net/npm/reveal.js@4.0.2/dist/reveal.js"],
    "reveal-notes.js": ["https://cdn.jsdelivr.net/npm/reveal.js@4.0.2/plugin/notes/notes.js"],
}
# 整段删除的在线依赖（本放映稿没有 mermaid 图，留着只会白等 15 秒）
DROP_PATTERNS = [
    r'<script[^>]*type=["\']module["\'][^>]*>(?:(?!</script>).)*?mermaid(?:(?!</script>).)*?</script>',
    r'<link[^>]+href=["\']https?://[^"\']*mermaid[^"\']*["\'][^>]*>',
]


def download() -> None:
    for url, name in REMOTE.items():
        dst = ASSETS / name
        if dst.exists() and dst.stat().st_size > 1000:
            print(f"  已有 {name}")
            continue
        got = False
        for src in [url] + MIRRORS.get(name, []):
            try:
                req = urllib.request.Request(src, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=25) as r:
                    data = r.read()
                if len(data) > 1000:
                    dst.write_bytes(data)
                    print(f"  下载 {name}  ({len(data):,} bytes)  ← {src.split('/')[2]}")
                    got = True
                    break
            except Exception:                          # noqa: BLE001
                continue
        if not got:
            print(f"  ⚠️ 无法获取 {name}")


def localize(html_path: Path) -> tuple[int, int]:
    """把外链替换为 slides_assets/ 下的本地文件；返回(替换数, 剩余外链数)。

    注意：外链有三种形态，都要处理
      1. <script src="https://...">  /  <link href="https://...">
      2. RequireJS 数组里的 "https://unpkg.com/reveal.js..."   ← 曾经漏掉这个，导致白屏
      3. ES module 的 import ... from "https://..."
    """
    txt = html_path.read_text(encoding="utf-8", errors="ignore")
    n = 0

    # 0. 先删掉用不上的在线依赖（mermaid）
    for pat in DROP_PATTERNS:
        txt, k = re.subn(pat, "<!-- dropped online dependency -->", txt,
                         flags=re.S | re.I)
        n += k

    # 1/2. 逐条替换 REMOTE 里的 URL（src/href 与 require 数组都用同一个字符串）
    for url, name in REMOTE.items():
        if not (ASSETS / name).exists():
            continue
        if url in txt:
            txt = txt.replace(url, f"slides_assets/{name}")
            n += 1

    # 3. MathJax 未本地化时直接移除（公式已改为 HTML）
    txt, k = re.subn(r'<script[^>]+src="https?://[^"]*mathjax[^"]*"[^>]*>\s*</script>',
                     "<!-- mathjax removed: formulas are pre-rendered as HTML -->", txt,
                     flags=re.I)
    n += k

    # 4. 兜底：任何残留的 http(s) 依赖（含 import from）统一报出来
    html_path.write_text(txt, encoding="utf-8")
    residue = re.findall(r'<(?:script[^>]*src|link[^>]*href)="(https?://[^"]+)"', txt)
    # data: URI 与注释里的示例链接不算
    residue = [u for u in residue if "data:image" not in u and "w3.org" not in u]
    return n, len(residue)


def inline_images(html_path: Path) -> int:
    """把 <img src="汇报材料/xxx.png"> 改成 base64 内嵌。

    目的：slides.html 不再依赖「汇报材料」文件夹，拷走一个 html 就能放映。
    （reveal.js 仍在 slides_assets，那是另一回事，见 README。）
    """
    import base64
    txt = html_path.read_text(encoding="utf-8", errors="ignore")
    n = 0
    for rel in sorted(set(re.findall(r'src="(汇报材料/[^"]+)"', txt))):
        f = html_path.parent / rel
        if not f.exists():
            continue
        mime = {".png": "image/png", ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg"}.get(f.suffix.lower(), "image/png")
        b64 = base64.b64encode(f.read_bytes()).decode("ascii")
        txt = txt.replace(f'src="{rel}"', f'src="data:{mime};base64,{b64}"')
        n += 1
    if n:
        html_path.write_text(txt, encoding="utf-8")
    return n


def report_leftovers(html_path: Path) -> int:
    """列出仍然存在的在线地址（只统计资源引用 src=/link href=，正文里的网址文字不算）。"""
    txt = html_path.read_text(encoding="utf-8", errors="ignore")
    urls = [u for u in re.findall(r'<(?:script[^>]*src|link[^>]*href)="(https?://[^"]+)"', txt)
            if "data:image" not in u and "w3.org" not in u]
    if urls:
        print(f"   仍有 {len(urls)} 处在线地址：")
        for u in sorted(set(urls))[:8]:
            print(f"     - {u}")
    return len(urls)


def main() -> int:
    print("1) 下载静态资源")
    download()

    print("2) 导出 HTML 与幻灯片")
    for target, suffix in (("html", ".html"), ("slides", ".slides.html")):
        out = subprocess.run(
            [sys.executable, "-m", "jupyter", "nbconvert", NB,
             "--to", target, "--output",
             Path(NB).stem],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="ignore")
        if out.returncode != 0:
            print(f"   nbconvert {target} 失败:\n{out.stderr[-600:]}")
            return 1
        print(f"   已生成 {Path(NB).stem}{suffix}")

    print("3) 改写外链为本地路径")
    bad = 0
    for fn in (f"{Path(NB).stem}.html", f"{Path(NB).stem}.slides.html"):
        p = ROOT / fn
        if not p.exists():
            continue
        n, left = localize(p)
        mark = "✅ 完全离线可用" if left == 0 else f"⚠️ 仍有 {left} 处在线地址"
        print(f"   {fn}: 替换 {n} 处，{mark}")
        if left:
            report_leftovers(p)
            bad += 1

    print("4) 把「汇报材料」里的图片内嵌进 html（幻灯片可单文件拷走）")
    for fn in (f"{Path(NB).stem}.html", f"{Path(NB).stem}.slides.html"):
        p = ROOT / fn
        if p.exists():
            k = inline_images(p)
            print(f"   {fn}: 内嵌图片 {k} 张")

    print("\n离线放映包：")
    print(f"  {ROOT / (Path(NB).stem + '.slides.html')}   ← 双击用浏览器放映")
    print(f"  {ROOT / (Path(NB).stem + '.html')}          ← 滚动式全文")
    print(f"  {ASSETS}                                     ← reveal.js 等（需与 html 同级）")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
