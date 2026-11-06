# -*- coding: utf-8 -*-
"""给 3.3 每一步的 md 补「使用数据 + 处理方式」说明。"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "汇报_中小企业经营信贷的监管剖析.ipynb"
nb = json.loads(NB.read_text(encoding="utf-8"))
cells = nb["cells"]

def src(c):
    return "".join(c.get("source", []))

NEW_MD = {
"#### 第一步：爬取东方财富": """#### 第一步：爬取东方财富——中小企业财务面板

- **使用数据**：企业名单 `data/processed/firm_panel.csv`（679 家代码，本地已抓）；财务指标实时来自 `datacenter.eastmoney.com` 的 F10 接口。
- **处理方式**：按代码逐家调 `RPT_F10_FINANCE_MAINFINADATA`（`.NQ` / `.BJ` 兜底），取最新一期营收、净利润、资产负债率，拼成表展示。
""",
"#### 第二步：爬取 NFRA": """#### 第二步：爬取 NFRA——监管处罚公示

- **使用数据**：实时接口 `www.nfra.gov.cn/cbircweb/...`（目录 `SelectDocByItemIdAndChild` + 详情 `SelectByDocId`）；被限流时回退本地 `data/processed/events_all.csv`（37,236 条）。
- **处理方式**：目录接口翻页 → 详情接口取 `docClob` 正文 → 存成记录列表（docId / 标题 / 日期 / 正文）。
""",
"#### 第三步：丢给大模型做自然语言处理": """#### 第三步：丢给大模型做自然语言处理

- **使用数据**：第二步抓到的处罚正文（`_rows`）+ DeepSeek API。
- **处理方式**：把每条「标题 + 正文」交给大模型，输出 JSON「是否与中小企业信贷有关 + 理由」；只把"有关"的落本地 `data/processed/llm_sme_selected.csv`。
""",
"#### 第四步：数据可视化": """#### 第四步：数据可视化

- **使用数据**：`data/processed/events_all.csv`（37,236 条处罚）→ `da.sme_credit_events()` 筛出 **745 条**中小企业信贷专项。
- **处理方式**：客群词（小微/普惠/经营贷/涉农…）+ 信贷词双重过滤 → 按年份聚合、按违规类型计数 → 趋势图 + 环节图。
""",
"#### 困境 vs 健康：中小企业财务特征差在哪": """#### 困境 vs 健康：中小企业财务特征差在哪

- **使用数据**：`data/processed/firm_panel.csv` → `da.sme_profile()`（679 家中小企业，含 t+1 困境标签）。
- **处理方式**：按"下一年是否困境"分两组，逐指标做 Mann-Whitney 检验并比较中位数 → 表 + 柱状图。
""",
"#### 第五步：只用 XGBoost 建模": """#### 第五步：只用 XGBoost 建模

- **使用数据**：`data/processed/firm_panel.csv` → `dm.build_panel()`（特征 = t 年财务指标；标签 = t+1 是否困境，严格前视）。
- **处理方式**：剔除关键特征缺失过半的样本 → XGBoost 训练 → ROC / AUC / KS → 特征重要度 Top12。
""",
}

n = 0
for c in cells:
    s = src(c).strip()
    for key, new in NEW_MD.items():
        if s.startswith(key):
            c["source"] = new
            n += 1
            break

nb["cells"] = cells
NB.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"已更新 {n} 个步骤 md")
