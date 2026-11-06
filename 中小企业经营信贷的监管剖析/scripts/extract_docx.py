# -*- coding: utf-8 -*-
"""
extract_docx —— 把两篇原始 docx 抽成结构化文本，供放映版引用
==========================================================
输出：
  data/source_docx/doc1_操作风险.txt    逐段文本（段落间空行）
  data/source_docx/doc2_风险评估.txt
  data/source_docx/doc1_操作风险.headings.txt   仅标题行（含层级）
  data/source_docx/doc2_风险评估.headings.txt
"""
import re
from pathlib import Path

import docx

SRC_DIR = Path(r"E:\互联网金融")
OUT = Path(__file__).resolve().parents[1] / "data" / "source_docx"
OUT.mkdir(parents=True, exist_ok=True)

FILES = {
    "doc1_操作风险": "中小银行中小企业信贷操作风险剖析与管控策略探究.docx",
    "doc2_风险评估": "破局与重塑：我国商业银行中小企业信贷风险评估体系的深度剖析与优化路径.docx",
}

HEAD_RE = re.compile(r"^(?:[一二三四五六七八九十]+、|\d+(?:\.\d+){0,3}\s*|第[一二三四五六七八九十]+章)")


def main() -> int:
    for key, fn in FILES.items():
        p = SRC_DIR / fn
        if not p.exists():
            print(f"缺少 {fn}")
            continue
        d = docx.Document(str(p))
        paras = []
        for para in d.paragraphs:
            t = (para.text or "").strip()
            if not t:
                continue
            style = (para.style.name or "").lower()
            is_head = ("heading" in style or "标题" in style
                       or (HEAD_RE.match(t) and len(t) <= 40))
            paras.append({"text": t, "head": is_head, "style": style})

        txt = OUT / f"{key}.txt"
        txt.write_text("\n\n".join(x["text"] for x in paras), encoding="utf-8")

        heads = OUT / f"{key}.headings.txt"
        lines = []
        for x in paras:
            if x["head"]:
                lines.append(f"[{'H' if x['head'] else ' '}] {x['text']}")
        heads.write_text("\n".join(lines), encoding="utf-8")

        n_head = sum(1 for x in paras if x["head"])
        chars = sum(len(x["text"]) for x in paras)
        print(f"{key}: 段落 {len(paras)}，标题 {n_head}，字符 {chars:,}")
        print(f"   → {txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
