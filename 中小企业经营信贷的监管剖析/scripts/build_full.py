# -*- coding: utf-8 -*-
"""
build_full —— 生成唯一的「完整版」汇报 notebook
==============================================
一份 notebook 里同时具备：
  · 理论页（两篇 docx 整理，66 页）
  · 配图页（6 张网络配图）
  · **真实可执行的代码 cell**（29 段）
  · 每段代码的**运行结果**（图/表/结论数字，执行后内嵌）

关键：**代码与结果分两页**
  · 前一页：markdown 里的 ```python 代码块（只显示代码，供讲解）
  · 后一页：真实的代码 cell —— 放映时由 customize_slides.py 注入的 CSS
            隐藏其输入区，只显示运行结果
  这样代码是"活的"（可重跑、可改参数），页面上又不会代码+图+表挤成一页。

执行顺序：本脚本只生成 notebook，随后需执行一次以产生输出：
  python scripts/build_full.py
  python -m jupyter nbconvert --to notebook --execute --inplace \
      --ExecutePreprocessor.timeout=2400 "汇报_中小企业经营信贷的监管剖析.ipynb"
"""
import sys
from pathlib import Path

import nbformat as nbf
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_notebook as bn          # noqa: E402  提供 (kind, source) 序列
import deck_theory as dt             # noqa: E402  提供理论页

OUT = ROOT / "汇报_中小企业经营信贷的监管剖析.ipynb"
WEB = ROOT / "assets" / "web"
CREDITS = WEB / "credits.json"
MAT = ROOT / "汇报材料"
TABLE_WRAP = ('<div style="font-size:0.86em;line-height:1.4;'
              'max-height:96%;overflow:auto">{html}</div>')
CONCL_WRAP = ('<div style="background:#f6f9fd;border-left:3px solid #2e75b6;'
              'padding:8px 12px;border-radius:4px;margin-top:10px;font-size:0.88em">'
              '\n\n**实测结果**\n\n{body}\n\n</div>')

PHOTO_FILE = {
    "factory": "photo_factory.jpg", "shop": "photo_shop.jpg",
    "bank": "photo_bank.jpg", "regulate": "photo_regulate.jpg",
    "contract": "photo_contract.jpg", "data": "photo_data.jpg",
}
IMG_CAPTION = {
    "factory": "中小企业生产车间实景——本汇报讨论的正是这类企业的经营信贷",
    "shop": "面向个体工商户的政策服务活动（“全国个体工商户服务月”座谈会）",
    "regulate": "地方金融监管部门与银行保险机构的监管工作座谈会",
    "bank": "银行营业网点柜台业务办理现场",
    "contract": "创业担保贷款三方协议签约仪式（面向小微企业的政策性信贷）",
    "data": "数据分析大屏——违规图谱与损失分布建模的工作场景",
}

COVER = r"""<div style="text-align:center;padding:50px 0 16px 0">

# 中小企业经营信贷的监管剖析

### —— 研究对象是中小企业，观察窗口是监管处罚

<br>

**理论 · 代码 · 运行结果，一页一件事**

<br>

<div style="color:#666;font-size:15px;line-height:1.9">
企业侧：新三板/北交所 <b>679 家</b>中小企业 × <b>3,381</b> 个企业-年的财务面板<br>
监管侧：金融监管总局处罚公示 29,858 期 → 37,236 条记录，其中 <b>745 条</b>指向中小企业客群<br>
理论侧：两篇原始文献整理的 66 页制度框架
</div>

<div style="color:#999;font-size:13px;margin-top:14px">
本 notebook 里的代码全部可执行：每一页代码之后，紧跟它的真实运行结果
</div>
</div>"""

TOC = r"""## 目录：六个回合，代码与结果分页

<div style="background:#f0f7ff;border-left:4px solid #1f4e79;padding:10px 14px;border-radius:4px;font-size:0.92em">

**研究对象是中小企业。** 监管处罚只能开给银行，所以证据分两层：

| 证据层 | 回答什么 | 数据 |
|---|---|---|
| **企业侧**（需求方） | 中小企业长什么样？谁会陷入困境？能否事前识别？ | 679 家企业财务面板 |
| **监管侧**（供给方） | 银行为中小企业放贷时，实际出了什么问题？ | **745 条 SME 专项处罚** |

**翻页规律**：`内容页 → 代码页 → 结果页`。代码页是这段分析的程序，
结果页是它跑出来的图与数字（输入区在放映时自动隐藏，可点控制条「代码」展开）。

</div>

| 回合 | 内容（两篇文献） | 紧接着的证据 |
|---|---|---|
| ① | 中小企业的地位、融资困境、划型标准、四个特点 | 数据来源 + **中小企业画像** + 困境组 vs 健康组 |
| ② | 信贷风险三分类 · 巴塞尔定义 · 七类事件逐项 | **745 条 SME 专项**：趋势、放贷方、环节、结构对比、划型问题；再给全量背景 |
| ③ | 三种计量方法 BIA / SA / AMA | **SME 专项损失分布 + VaR**，与全量处罚对照 |
| ④ | 传统三法 · 现代三模型 · 新兴方法 · 文献脉络 | 事前识别：Z′ / 评分卡 / GBDT 模型阶梯 |
| ⑤ | 现行体系五类问题 · 四个业务环节风险 · 内外部因素 | 小结：从违规到资本 |
| ⑥ | 三重挑战 · 两个案例 · 管控六策略 · 研究设计 | 结论、建议、局限 |
"""

DIVIDER = r"""<div style="text-align:center;padding:110px 0">

# 开始

## 内容 → 代码 → 结果

<div style="color:#666;margin-top:18px;font-size:15px">
每一页代码之后，紧跟它的真实运行结果；<br>
企业侧与监管侧交替出现，研究对象始终是中小企业。
</div>

<div style="color:#999;margin-top:32px;font-size:13px">
内容来源：《中小银行中小企业信贷操作风险剖析与管控策略探究》<br>
《破局与重塑：我国商业银行中小企业信贷风险评估体系的深度剖析与优化路径》<br>
证据来源：中小企业财务面板（新三板/北交所）+ 金融监管总局处罚公示
</div>
</div>"""

SME_WRAP = r"""## 把两层证据合起来：关于中小企业信贷的三个判断

<div style="background:#f6f9fd;border-left:4px solid #2e75b6;padding:10px 14px;border-radius:4px">

**企业侧告诉我们"风险长什么样"，监管侧告诉我们"风险在哪里被漏掉"。**

</div>

| # | 判断 | 企业侧证据 | 监管侧证据 |
|---|---|---|---|
| 1 | 中小企业的问题不是"规模小"，而是**盈利与现金流的脆弱** | 困境组净利润率 −8.9% vs 健康组 +6.7% | 违规集中在贷前调查与贷后管理 |
| 2 | 风险在**过程环节**被漏掉，而不是在结果环节被发现 | 财务指标次年才恶化，事前可见 | 「贷款三查不到位」是 SME 专项最高频事由（43.6%） |
| 3 | **监管指标本身也可能失真** | 困境率约 4 成，客群风险确实高 | 「小微企业划型不准确」29 条、罚没 3.96 亿元 |

<div style="background:#fff4f4;border-left:4px solid #c00000;padding:10px 14px;border-radius:4px;margin-top:10px">

**对监管的含义**：如果连"谁是中小企业"这层统计都可能被修饰，
那么基于该口径的普惠考核、资本计量与风险判断都需要交叉验证。

</div>
"""

CREDIT_NOTE = r"""## 图片来源说明（学术诚信）

共使用 **6 张网络配图**，均来自公开新闻或行业网站，仅用于课堂讲解的场景说明，
**不用于公开发表**。每张图在其所在页面下方均标注了标题与来源域名。

<div style="background:#fff8e6;border-left:4px solid #bf9000;padding:10px 14px;border-radius:4px;font-size:0.9em;margin-top:10px">

若要整理成论文或公开材料，请把配图替换为：① 自摄照片；② 政府/机构授权图；
③ 开源图库（Unsplash、Pixabay、CC 协议图片）。<br>
报告中的 **23 张图表、26 张数据表与全部数字**都由本 notebook 的代码从公开数据计算生成，
不存在版权问题，可放心引用。

</div>
"""

# ---------------------------------------------------------------- 回合结构
BLOCKS = [
    ("theory", dt.P1_BACKGROUND),
    ("images", ["factory"]), ("images", ["shop"]),
    ("cells",  [4, 5, 6, 7]),
    ("cells",  [43, 44]), ("cells", [45, 46]),

    ("theory", dt.P2_RISK + dt.P2_DETAIL),
    ("images", ["regulate"]), ("images", ["bank"]),
    ("cells",  [47, 48]), ("cells", [49, 50]),
    ("cells",  [51, 52]), ("cells", [53, 54]),
    ("cells",  [57, 58]),
    ("cells",  [8, 9, 10, 11, 12, 13]),
    ("cells",  [14, 15, 16, 17, 18, 19]),

    ("theory", dt.P3_METHOD[:4]),
    ("images", ["contract"]), ("images", ["data"]),
    ("cells",  [55, 56]),
    ("cells",  [20, 21, 22, 23, 24, 25, 26, 27]),
    ("cells",  [28, 29, 30, 31, 32]),

    ("theory", dt.P3_METHOD[4:]),
    ("cells",  [33, 34, 35, 36, 37, 38, 39, 40, 41, 42]),

    ("theory", dt.P4_STATUS + dt.P4_PROCESS + dt.P4_FACTORS),
    ("theory", (SME_WRAP,)),
    ("theory", dt.P5_CASE[:-1] + dt.P5_CASE_OP + dt.P6_RESEARCH),
    ("theory", (dt.P5_CASE[-1],)),
    ("cells",  [59, 60, 61, 62]),
]


def image_page(topic: str) -> str:
    import json
    fname = PHOTO_FILE.get(topic)
    credits = json.loads(CREDITS.read_text(encoding="utf-8")) if CREDITS.exists() else {}
    c = credits.get(topic) or {}
    cap = IMG_CAPTION.get(topic, "")
    return (
        '<div style="text-align:center">\n\n'
        f'<img src="汇报材料/{fname}" '
        'style="max-height:70vh;max-width:100%;border-radius:6px;'
        'box-shadow:0 2px 10px rgba(0,0,0,.12)"/>\n\n'
        f'<div style="font-size:0.74em;color:#555;margin-top:10px;line-height:1.5">'
        f'{cap}<br><span style="color:#999">图片来源：{c.get("host", "")}'
        + (f'｜{(c.get("title") or "")[:52]}' if c.get("title") else "")
        + "</span></div>\n\n</div>"
    )


def main() -> int:
    src_cells = bn.cells          # [(kind, source), ...] 原始分析序列
    print(f"分析源：{len(src_cells)} 个 cell（来自 build_notebook.py）")

    out: list = []
    stat = {"theory": 0, "image": 0, "codepage": 0, "codecell": 0, "md": 0}

    def md(s: str) -> None:
        out.append(("md", s))
        stat["md"] += 1

    def codecell(src: str) -> None:
        out.append(("code", src))
        stat["codecell"] += 1

    md(COVER)
    md(TOC)
    # 环境初始化（放映时跳过，不占页）。因为放映版把分析 cell 按"回合"重排过，
    # 模块导入必须集中放在最前面，否则后面的 cell 可能先用到未导入的模块。
    boot = src_cells[1][1].rstrip() + (
        "\n\n# ---- 模块导入集中在此，避免重排后出现 NameError ----\n"
        "import lda_model as lm\n"
        "import text_analysis as ta\n"
        "import default_model as dm\n"
    )
    out.append(("skip", boot))
    # 监管闭环路线图（原 cell 2/3）
    for idx in (2, 3):
        k, s = src_cells[idx]
        if k == "md":
            md(s)
        else:
            md("```python\n" + s.strip() + "\n```")
            codecell(s)

    md(DIVIDER)

    for kind, payload in BLOCKS:
        if kind == "theory":
            for page in payload:
                md(page)
                stat["theory"] += 1
            continue
        if kind == "images":
            for topic in payload:
                md(image_page(topic))
                stat["image"] += 1
            continue
        for idx in payload:
            k, s = src_cells[idx]
            if k == "md":                    # 注意：build_notebook 用 'md' 标记
                md(s)
            else:
                md("```python\n" + s.strip() + "\n```")   # 代码页
                stat["codepage"] += 1
                codecell(s)                              # 结果页（输入被 CSS 隐藏）

    md(CREDIT_NOTE)

    # 组装 notebook
    cells = []
    for kind, src in out:
        if kind in ("code", "skip"):
            # 「skip」也是代码 cell（环境初始化），只是放映时不占页
            c = new_code_cell(src)
            c.metadata["slideshow"] = {
                "slide_type": "skip" if kind == "skip" else "slide"}
        else:
            c = new_markdown_cell(src)
            c.metadata["slideshow"] = {"slide_type": "slide"}
        cells.append(c)

    nb = new_notebook(cells=cells)
    nb.metadata.update({
        "kernelspec": {"display_name": "Python 3", "language": "python",
                       "name": "python3"},
        "language_info": {"name": "python", "version": "3.13"},
        "title": "中小企业经营信贷的监管剖析（完整版）",
    })
    nbf.write(nb, str(OUT))

    print(f"已生成 {OUT.name}")
    print(f"  总 cell {len(cells)}")
    print(f"    理论页 {stat['theory']} · 配图页 {stat['image']} · "
          f"其他 markdown {stat['md'] - stat['theory'] - stat['image']}")
    print(f"    代码页(markdown 代码块) {stat['codepage']} · 真实代码 cell {stat['codecell']}"
          f"（放映时隐藏输入，只显示结果）")
    print("\n下一步必须执行一次以产生运行结果：")
    print('  python -m jupyter nbconvert --to notebook --execute --inplace '
          '--ExecutePreprocessor.timeout=2400 '
          f'"{OUT.name}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
