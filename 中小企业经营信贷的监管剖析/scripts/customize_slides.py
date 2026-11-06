# -*- coding: utf-8 -*-
"""
customize_slides —— 修复幻灯片超出屏幕 / 被裁切，并加鼠标控制条
=============================================================
必须在 make_offline_html.py 之后运行（可重复运行，幂等）。

【为什么会超出屏幕】
nbconvert 的 slides 模板把 reveal 画布写死成：
    Reveal.initialize({ width: 960, height: 700, ... })
reveal 会按这个虚拟画布缩放，**超出 700px 的内容直接被裁掉**。
而本项目的图以 160dpi 保存，单张就约 736px 高，必然溢出。

【修复方案（四层叠加）】
  1. 放大画布并开启自动缩放：1500×940 + minScale，内容整体等比缩放，永不裁切
  2. 顶部对齐（center:false）：长页面从顶上开始排，不会被上下各裁一半
  3. 尺寸按画布像素收紧：图片限高、表格/正文字号缩小，让常见页面一屏装下
  4. 兜底滚动：仍然超高的页面可页内滚动，保证任何内容都看得到、丢不了
  5. 顺手加鼠标控制条（翻页/总览/全屏/字号/代码开关/页码），不依赖键盘
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "汇报_中小企业经营信贷的监管剖析.slides.html"

BEGIN = "<!-- ds-custom:begin -->"
END = "<!-- ds-custom:end -->"
STUB_BEGIN = "<!-- ds-mathjax-stub:begin -->"
STUB_END = "<!-- ds-mathjax-stub:end -->"

# ---------------------------------------------------------------- 白屏修复
# nbconvert 的 slides 模板里有这段代码：
#     var update = function(event){
#       if (MathJax.Hub.getAllJax(Reveal.getCurrentSlide())) { ... }
#     };
#     Reveal.addEventListener('slidechanged', update);
# 它**无条件**引用全局 MathJax。而本放映稿的公式已改成 HTML，
# make_offline_html.py 会把 MathJax 的 <script> 移除 ——
# 于是每次翻页 update() 都抛 ReferenceError，
# reveal 的翻页流程被异常打断，表现就是"翻页后一片空白"。
# 解决：在 <head> 最前面放一个空实现的 MathJax 桩，保证任何调用都安全。
STUB = r"""<!-- ds-mathjax-stub:begin -->
<script id="ds-mathjax-stub">
/* 公式已预渲染为 HTML，此处仅提供空实现，防止模板回调抛 ReferenceError */
window.MathJax = window.MathJax || {
  Hub: {
    getAllJax: function () { return null; },
    Rerender: function () {},
    Config: function () {},
    Queue: function () {},
    Typeset: function () {},
    Register: { StartupHooks: { Add: function () {} } }
  },
  Typeset: function () {},
  Queue: function () {}
};
</script>
<!-- ds-mathjax-stub:end -->
"""

CSS_JS = r"""<!-- ds-custom:begin -->
<style id="ds-style">
/* ================= 1. 页面尺寸：按 1500x940 画布收紧 ================= */
.reveal .slides { text-align: left; }
.reveal .slides > section,
.reveal .slides > section > section {
  /* 兜底：仍然超高的页面可以页内滚动，保证内容不被裁掉 */
  max-height: 100% !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  box-sizing: border-box;
  padding: 4px 10px 8px 10px !important;
}
.reveal .slides ::-webkit-scrollbar { width: 7px; }
.reveal .slides ::-webkit-scrollbar-thumb {
  background: rgba(31,78,121,.45); border-radius: 4px;
}
.reveal .slides ::-webkit-scrollbar-track { background: transparent; }

/* ================= 2. 字号阶梯 ================= */
.reveal h1 { font-size: 30px !important; line-height: 1.28; margin: 6px 0 10px; }
.reveal h2 { font-size: 25px !important; line-height: 1.3;  margin: 4px 0 9px; }
.reveal h3 { font-size: 21px !important; line-height: 1.32; margin: 4px 0 8px; }
.reveal h4 { font-size: 18px !important; }
.reveal p, .reveal li, .reveal td, .reveal th, .reveal blockquote {
  font-size: 16px !important; line-height: 1.5;
}
.reveal li { margin: 2px 0; }
.reveal table { margin: 6px auto !important; border-collapse: collapse; }
.reveal td, .reveal th { padding: 3px 8px !important; }
.reveal blockquote { padding: 6px 12px; margin: 6px 0; }

/* ================= 3. 图片与表格自适应 ================= */
/* 放映版的图在 markdown 里（<img>），分析版在 cell 输出里，两种都覆盖 */
.reveal .jp-RenderedMarkdown img,
.reveal .jp-OutputArea-output img,
.reveal .slides section img {
  /* 同时用 px 与 vh 取小值：slides.html 与分析版/RISE 两种场合都能自适应 */
  max-height: min(860px, 76vh) !important;
  max-width: 100% !important;
  width: auto !important; height: auto !important;
  display: block; margin: 2px auto;
  object-fit: contain;
}
.reveal .jp-RenderedHTMLCommon table,
.reveal .jp-RenderedMarkdown table,
.reveal .slides section table {
  font-size: 14px !important;
  border-collapse: collapse;
}
.reveal .jp-RenderedHTMLCommon td, .reveal .jp-RenderedHTMLCommon th,
.reveal .jp-RenderedMarkdown td,  .reveal .jp-RenderedMarkdown th,
.reveal .slides section td, .reveal .slides section th {
  padding: 3px 9px !important; line-height: 1.35 !important;
}

/* ================= 4. 只隐藏「代码 cell」的输入区 ================= */
/* 重要：nbconvert 把 markdown 的内容也放在 .jp-InputArea 内，
   若不加 .jp-CodeCell 限定，会连所有文字页一起隐藏 → 整本幻灯片空白。
   （这个坑踩过一次：DOM 里元素都在，但页面全白） */
body:not(.ds-show-code) .reveal .jp-CodeCell .jp-InputArea,
body:not(.ds-show-code) .reveal .jp-CodeCell .jp-InputPrompt,
body:not(.ds-show-code) .reveal .jp-CodeCell .jp-Collapser { display: none !important; }

/* 展开代码时：代码与输出各占一半高度，各自滚动 */
body.ds-show-code .reveal .jp-CodeCell .jp-InputArea {
  max-height: 330px; overflow: auto;
  font-size: 12px !important; background: #f7f9fc; border-radius: 6px;
}
body.ds-show-code .reveal .jp-CodeCell .jp-InputArea * { font-size: 12px !important;
  line-height: 1.42 !important; }
body.ds-show-code .reveal .jp-OutputArea-output img { max-height: 300px !important; }
body.ds-show-code .reveal .jp-OutputArea { max-height: 400px; overflow: auto; }

/* ================= 5. 控制条 ================= */
#ds-ctrl {
  position: fixed; right: 12px; bottom: 12px; z-index: 99999;
  display: flex; align-items: center; gap: 5px; padding: 6px 9px;
  border-radius: 10px; background: rgba(26,30,36,.84);
  -webkit-backdrop-filter: blur(6px); backdrop-filter: blur(6px);
  box-shadow: 0 4px 18px rgba(0,0,0,.3);
  font-family: "Microsoft YaHei", system-ui, sans-serif; font-size: 13px;
  color: #fff; opacity: .28; transition: opacity .18s;
  user-select: none; -webkit-user-select: none;
}
#ds-ctrl:hover { opacity: 1; }
#ds-ctrl button {
  border: 0; border-radius: 7px; padding: 5px 9px; cursor: pointer;
  background: rgba(255,255,255,.15); color: #fff; font-size: 13px;
  font-family: inherit; line-height: 1.25; transition: background .14s;
}
#ds-ctrl button:hover { background: rgba(255,255,255,.34); }
#ds-ctrl button.ds-on { background: #2e75b6; }
#ds-ctrl .ds-page {
  padding: 0 7px; min-width: 54px; text-align: center;
  color: #cfe3ff; font-variant-numeric: tabular-nums;
}
#ds-ctrl .ds-sep { width: 1px; height: 17px; background: rgba(255,255,255,.22); }
#ds-ctrl.ds-hidden { display: none; }
#ds-show {
  position: fixed; right: 12px; bottom: 12px; z-index: 99998;
  width: 32px; height: 32px; border-radius: 50%; border: 0; cursor: pointer;
  background: rgba(26,30,36,.5); color: #fff; font-size: 15px; display: none;
}
#ds-show.on { display: block; }
@media print { #ds-ctrl, #ds-show { display: none !important; } }
</style>

<div id="ds-ctrl">
  <button id="ds-prev" title="上一页">⏮</button>
  <button id="ds-next" title="下一页">⏭</button>
  <span class="ds-sep"></span>
  <button id="ds-over" title="缩略图总览（ESC）">▦ 总览</button>
  <button id="ds-full" title="全屏 / 退出全屏">⛶ 全屏</button>
  <span class="ds-sep"></span>
  <button id="ds-fminus" title="整体缩小">A−</button>
  <button id="ds-fplus" title="整体放大">A+</button>
  <span class="ds-sep"></span>
  <button id="ds-code" title="在结果页上显示 / 隐藏源码">代码</button>
  <span class="ds-sep"></span>
  <span class="ds-page" id="ds-page">1 / 1</span>
  <button id="ds-hide" title="隐藏控制条（按 H 唤回）">✕</button>
</div>
<button id="ds-show" title="显示控制条">⋯</button>

<script>
(function () {
  function bars() { return document.getElementById('ds-ctrl'); }

  function boot() {
    var bar = document.getElementById('ds-ctrl');
    var showBtn = document.getElementById('ds-show');
    var pageEl = document.getElementById('ds-page');
    var revealEl = document.querySelector('.reveal');
    // 等 reveal 把 .reveal 加上 ready 类（不依赖 window.Reveal）
    if (!revealEl || !revealEl.classList.contains('ready')) {
      if (++boot.tries < 600) { return setTimeout(boot, 80); }
    }
    boot.ready = true;
    var zoom = 1;

    function stop(e) { e.stopPropagation(); }

    function secs() {
      return Array.prototype.slice.call(
        document.querySelectorAll('.reveal .slides > section'));
    }
    function curIdx() {
      var s = secs();
      for (var i = 0; i < s.length; i++) {
        if (s[i].classList.contains('present')) { return i; }
      }
      return 0;
    }
    function updatePage() {
      try {
        pageEl.textContent = (curIdx() + 1) + ' / ' + secs().length;
      } catch (err) {}
    }
    // 给 reveal 派发键盘事件（它监听 document 的 keydown）
    function key(code) {
      ['keydown', 'keyup'].forEach(function (type) {
        var ev = new KeyboardEvent(type, {
          key: code === 37 ? 'ArrowLeft' : code === 39 ? 'ArrowRight'
             : code === 27 ? 'Escape' : 'Unidentified',
          keyCode: code, which: code, bubbles: true, cancelable: true
        });
        document.dispatchEvent(ev);
      });
    }
    function fit() { window.dispatchEvent(new Event('resize')); }

    document.getElementById('ds-prev').onclick = function (e) { stop(e); key(37); };
    document.getElementById('ds-next').onclick = function (e) { stop(e); key(39); };
    document.getElementById('ds-over').onclick = function (e) { stop(e); key(27); };
    document.getElementById('ds-fminus').onclick = function (e) {
      stop(e); zoom = Math.max(0.6, zoom - 0.08);
      document.documentElement.style.zoom = zoom; fit();
    };
    document.getElementById('ds-fplus').onclick = function (e) {
      stop(e); zoom = Math.min(1.8, zoom + 0.08);
      document.documentElement.style.zoom = zoom; fit();
    };
    document.getElementById('ds-code').onclick = function (e) {
      stop(e);
      // 在结果页上显示 / 隐藏该 cell 的源码（放映时默认隐藏，避免代码挤压结果）
      var on = document.body.classList.toggle('ds-show-code');
      this.classList.toggle('ds-on', on);
      fit();
    };
    document.getElementById('ds-full').onclick = function (e) {
      stop(e);
      var d = document, el = d.documentElement;
      if (!d.fullscreenElement && !d.webkitFullscreenElement) {
        var req = el.requestFullscreen || el.webkitRequestFullscreen
                  || el.msRequestFullscreen;
        if (req) { req.call(el); }
      } else {
        var exit = d.exitFullscreen || d.webkitExitFullscreen || d.msExitFullscreen;
        if (exit) { exit.call(d); }
      }
      setTimeout(fit, 250);
    };
    document.getElementById('ds-hide').onclick = function (e) {
      stop(e); bar.classList.add('ds-hidden'); showBtn.classList.add('on');
    };
    showBtn.onclick = function (e) {
      stop(e); bar.classList.remove('ds-hidden'); showBtn.classList.remove('on');
    };
    window.addEventListener('keydown', function (ev) {
      if ((ev.key === 'h' || ev.key === 'H')
          && bar.classList.contains('ds-hidden')) {
        bar.classList.remove('ds-hidden'); showBtn.classList.remove('on');
      }
    });
    // reveal 在 .reveal 元素上派发这些事件
    ['ready', 'slidechanged', 'fragmentshown', 'fragmenthidden']
      .forEach(function (ev) {
        revealEl.addEventListener(ev, function () { updatePage(); });
      });
    window.addEventListener('resize', updatePage);
    // 兜底轮询：即使事件没触发，页码也会在翻页后 400ms 内更新
    setInterval(updatePage, 400);
    updatePage();
  }
  boot.tries = 0;
  boot();
})();
</script>

<script>
/* 滚轮：只在当前 slide 内滚动，不翻页（翻页用 ←/→ 或右下角控制条） */
(function () {
  function scroller() {
    var sec = document.querySelector('.reveal .slides > section.present');
    if (!sec) return null;
    var sub = sec.querySelector('section.present');
    var cands = [sub, sec];
    for (var i = 0; i < cands.length; i++) {
      var s = cands[i];
      if (s && s.scrollHeight > s.clientHeight + 2) return s;
    }
    return null;
  }
  document.addEventListener('wheel', function (e) {
    var s = scroller();
    if (s) {
      var atTop = s.scrollTop <= 0;
      var atBottom = s.scrollTop + s.clientHeight >= s.scrollHeight - 2;
      if (!(e.deltaY > 0 && atBottom) && !(e.deltaY < 0 && atTop)) {
        s.scrollTop += e.deltaY;
        e.preventDefault();
        return;
      }
    }
    // 滚到边界也不翻页，只停在当前 slide
  }, { passive: false });
})();
</script>
<!-- ds-custom:end -->
"""


def validate_js(html_path: Path) -> bool:
    """用 node --check 校验所有内联 <script> 的语法。

    这一步是为了防止「正则改坏 JS → 整个 script 块失效 → 页面全白」
    这类事故再次发生（曾经真的发生过一次）。
    """
    import shutil
    import subprocess
    import tempfile

    node = shutil.which("node")
    if not node:
        print("  ⚠️ 未找到 node，跳过 JS 语法校验")
        return True

    txt = html_path.read_text(encoding="utf-8", errors="ignore")
    blocks = re.findall(r"<script\b([^>]*)>(.*?)</script>", txt, flags=re.S | re.I)
    n_ok = n_bad = 0
    for attrs, body in blocks:
        if "type=" in attrs and "javascript" not in attrs and "module" not in attrs:
            continue                      # 跳过 text/x-mathjax-config、json 等
        if not body.strip():
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(body)
            tmp = f.name
        r = subprocess.run([node, "--check", tmp], capture_output=True, text=True,
                           encoding="utf-8", errors="ignore")
        if r.returncode == 0:
            n_ok += 1
        else:
            n_bad += 1
            print(f"  ❌ JS 语法错误（脚本块 {n_ok + n_bad}）:")
            for line in (r.stderr or "").splitlines()[:6]:
                print("     ", line)
        Path(tmp).unlink(missing_ok=True)
    print(f"  JS 语法校验：{n_ok} 个脚本块通过" +
          ("" if not n_bad else f"，{n_bad} 个失败"))
    return n_bad == 0


def main() -> int:
    if not TARGET.exists():
        print(f"缺少 {TARGET.name}，请先运行 make_offline_html.py")
        return 1
    txt = TARGET.read_text(encoding="utf-8", errors="ignore")

    # ---- 0. 注入 MathJax 桩（必须在模板脚本之前，否则翻页白屏）
    if STUB_BEGIN in txt:
        txt = re.sub(re.escape(STUB_BEGIN) + r".*?" + re.escape(STUB_END), "", txt, flags=re.S)
    if "<head>" in txt:
        txt = txt.replace("<head>", "<head>\n" + STUB, 1)
        print("  已注入 MathJax 桩（修复翻页白屏）")
    else:
        print("  ⚠️ 未找到 <head>，无法注入 MathJax 桩")

    # ---- 0b. 把模板里引用 MathJax 的 slidechanged 回调整体换成空实现
    #        （不要用「插入判断」的写法 —— 上一版就是正则跨过括号，
    #         产生 if(window.MathJax && MathJax.Hub.getAllJax)(...) 这种
    #         语法错误，导致整个 script 块失效、Reveal 不初始化、页面全白）
    txt, n_fix = re.subn(
        r"var\s+update\s*=\s*function\s*\(\s*event\s*\)\s*\{.*?\}\s*;",
        "var update = function (event) { /* 公式已预渲染为 HTML，无需 MathJax 重排 */ };\n",
        txt, flags=re.S)
    if n_fix:
        print(f"  已替换 {n_fix} 处 MathJax 回调为空实现（翻页白屏根因）")

    # ---- 1. 放大画布并开启缩放（替换模板里写死的 960x700）
    old_cfg = re.search(r"width:\s*960\s*,\s*height:\s*700\s*,?", txt)
    if old_cfg:
        new_cfg = ("width: 1500, height: 940, margin: 0.02,\n"
                   "            minScale: 0.30, maxScale: 1.15,\n"
                   "            center: false, touch: false, mouseWheel: false,")
        txt = txt[:old_cfg.start()] + new_cfg + txt[old_cfg.end():]
        print("  已替换画布：960x700 → 1500x940（minScale 0.30，顶部对齐）")
    else:
        print("  ⚠️ 未找到 width:960/height:700，可能已改过，跳过")

    # ---- 2. 幂等清理旧注入
    if BEGIN in txt:
        txt = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), "", txt, flags=re.S)

    # ---- 3. 注入样式与控制条
    if "</body>" not in txt:
        print("找不到 </body>，放弃注入")
        return 1
    txt = txt.replace("</body>", CSS_JS + "\n</body>", 1)
    TARGET.write_text(txt, encoding="utf-8")

    print(f"已写入：{TARGET.name}")
    print("  · 画布 1500×940 + 自动缩放：任何内容都等比缩放到屏幕内，不再裁切")
    print("  · 顶部对齐 center:false：长页面不会被上下各切一半")
    print("  · 图片限高 min(860px,76vh)、表格自适应：常见页面一屏装下")
    print("  · 超高页面可页内滚动（右侧细滚动条），内容绝不丢")
    print("  · 右下角控制条：⏮ ⏭ ▦总览 ⛶全屏 A−A+ 代码 页码 ✕")
    print()
    ok = validate_js(TARGET)
    if not ok:
        print("\n❌ 存在 JS 语法错误，页面会白屏，请先修复")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
