# -*- coding: utf-8 -*-
"""删除 data 下没被用到的旧文件/中间产物（保留 events_all/bank_fin/firm_panel/sme_credit_events 等）。"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# 明确没被任何代码引用 / 已被 events_all.csv 取代的旧文件
targets = [
    "processed/llm_indicators.txt",        # 旧的大模型输出（已被 llm_records.csv 取代）
    "processed/penalty_events.csv",        # stage2 旧中间产物
    "processed/penalty_events_nfra.csv",   # stage2 旧中间产物
    "processed/branch_events.csv",         # stage4 中间产物（已并入 events_all.csv）
    "interim/stage0_pdf_stats.csv",        # stage0 旧统计
]
for rel in targets:
    p = (DATA / rel).resolve()
    if p.exists():
        size = p.stat().st_size
        p.unlink()
        print(f"删除 {p.relative_to(ROOT)}  ({size/1e6:.1f} MB)")
    else:
        print(f"跳过（不存在）{rel}")

# 旧 PDF 缓存
d = (DATA / "raw" / "nfra_pdf").resolve()
if d.exists():
    n = len(list(d.glob("*.pdf")))
    shutil.rmtree(d)
    print(f"删除 {d.relative_to(ROOT)} 目录（{n} 个 PDF）")

print("\n剩余空间：")
for sub in ["raw", "interim", "processed", "source_docx"]:
    p = DATA / sub
    if p.exists():
        files = [x for x in p.rglob("*") if x.is_file()]
        total = sum(x.stat().st_size for x in files)
        print(f"  {sub:12s} files={len(files):>6}  {total/1e6:8.1f} MB")
