# -*- coding: utf-8 -*-
"""给监管侧 md 补充「抓全部 + 约5小时」的运行时说明。"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "汇报_中小企业经营信贷的监管剖析.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))

NEW = """##### 监管侧：NFRA 抓全部 → 大模型筛出「中小企业信贷」

1. **抓取**：从金融监管总局的处罚公示接口，目录 → 详情，**抓全部**（本篇累计 29,859 期 / 37,236 条）。
2. **筛选**：每抓一页就立刻丢给大模型，判断"是否与中小企业信贷有关"，**只把有关的落本地**。
3. **循环**：抓一页 → 判一页 → 落盘 → 下一页，直到抓完（`MAX_PAGES=None`）。

> ⚠️ 完整跑完约 **5 小时**（~1,500 页 × 10 条，每条 1 次详情 + 1 次大模型）；本页展示的是前几页的演示输出。
> 想快跑就把 `MAX_PAGES` 改成 5 之类的数字。
"""

done = False
for c in nb["cells"]:
    s = "".join(c.get("source", []))
    if "##### 监管侧" in s:
        first = s.splitlines()[0] if s.splitlines() else ""
        prefix = first + "\n" if first.strip().startswith("#### 第一部分") else ""
        c["source"] = prefix + NEW
        done = True
        print("监管侧 md 已更新")
        break
print("done" if done else "NOT FOUND")

NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
