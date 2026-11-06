# -*- coding: utf-8 -*-
"""把「数据源/接口」markdown 加回 3.3，数据源表加 Key 列。"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "汇报_中小企业经营信贷的监管剖析.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))
cells = nb["cells"]

def src(c):
    return "".join(c.get("source", []))

DATA_SRC_MD = """##### 为什么用处罚数据
1. **公开可得**：国家金融监督管理总局按月公示行政处罚，是唯一覆盖全国、逐案可查的监管外部数据
2. **有金额**：每案披露罚款/没收金额，可作为"违规经济代价"的量化代理
3. **有事实**：披露违法违规事实，可借助自然语言处理技术做文本分析

##### 数据抓取口径

| 项 | 内容 |
|---|---|
| 栏目 | 国家金融监督管理总局 → 政务信息 → 行政处罚 |
| 范围 | **总局机关** 661 期 + **派出机构** 29,198 期（2022-01 起） |
| 覆盖 | 省监管局 + 市监管分局 + 监管支局 |
| 原文 | 详情接口 `docClob` 字段（HTML 全文），无需解析 PDF |
| 合规 | 公开政府信息、限速抓取、仅学术用途 |

> 注：中小企业主要由**地市监管分局**监管，因此必须以"派出机构"为主样本。
> 只抓总局本级会得到 661 期、其中银行类仅 47 条 —— 会完全错失研究对象。

##### 关注对象：中小企业以及相关的中小银行

⚠️ **监管处罚的开具对象只能是银行**（金融监管部门处罚的是金融机构，不是企业）。所以本项目用两层证据锁定"中小企业"：

| 证据层 | 回答什么 | 数据 | 规模 |
|---|---|---|---|
| **企业侧（需求方）** | 中小企业长什么样？能否事前识别风险？ | 新三板/北交所财务面板（东方财富 F10） | 679 家 × 3,381 企业-年 |
| **监管侧（供给方）** | 银行为中小企业放贷时出了什么违规？ | SME 专项处罚（小微/普惠/个体工商户/经营贷 关键词 + 信贷相关） | 745 条（占全部 2.0%） |

##### 数据源（接口 + Key）

| 模式 | 接口 | Key | 返回结果 |
|---|---|---|---|
| 爬虫 | `www.nfra.gov.cn/cbircweb/DocInfo/SelectDocByItemIdAndChild?itemId=4293&pageSize=10&pageIndex=1` | 无（公开接口） | 处罚公示目录 |
| 爬虫 | `www.nfra.gov.cn/cbircweb/DocInfo/SelectByDocId?docId={docId}` | 无（公开接口） | 处罚正文 `docClob` |
| 爬虫 | `datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_F10_FINANCE_MAINFINADATA&filter=(SECUCODE="{code}.NQ")` | 无（公开接口） | 中小企业财务面板 |
| 大模型 | `api.deepseek.com/chat/completions`（`deepseek-chat`） | `sk-d77f922299ae4e8881f93c10497b9b85` | 从真实处罚正文抽取结构化字段 |

> ⚠️ 大模型 Key 只写在 `src/llm_config.py`，此处仅为演示说明；**公开分享前请重置**。

##### 本地数据仓库

| 文件名 | 数据内容 | 包含属性 | 总记录数 |
|---|---|---|---|
| `data/processed/events_all.csv` | 监管处罚事件总表 | docId、机构名称、违法违规事实、罚没合计万元… | 37,236 |
| `data/processed/firm_panel.csv` | 中小企业财务面板 | 代码、名称、报告期、营收、净利润、资产负债率… | 4,060 |
| `data/processed/sme_credit_events.csv` | 中小企业信贷专项处罚 | docId、机构名称、违规类型、罚没合计万元… | 745 |
| `data/processed/llm_records.csv` | 大模型抽取/政策记录 | 字段按任务而定 | 6 |
"""

new_cell = {
    "cell_type": "markdown",
    "metadata": {"slideshow": {"slide_type": "subslide"}},
    "source": DATA_SRC_MD,
}

# 插到「第一部分：数据挖掘」那个 cell 之后
idx = next(i for i, c in enumerate(cells) if src(c).strip().startswith("#### 第一部分：数据挖掘"))
cells.insert(idx + 1, new_cell)
print(f"已插入数据源 cell 到 [{idx+1}]")

nb["cells"] = cells
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("done, cells =", len(cells))
