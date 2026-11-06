# -*- coding: utf-8 -*-
"""
Stage 2：把 docClob 正文解析成结构化处罚事件表
==============================================
三类正文格式（Stage 0/1 实测）：
  A 列表式汇总表  「序号 | 当事人名称 | 主要违法违规行为 | 行政处罚内容 | 作出决定机关」
     一期含多条记录（2020 年后的公示主流形式）
  B 行政处罚信息公开表  「字段名 | 内容」两列键值对
     一期一条记录（2019 年前后主流形式）
  C 行政处罚决定书  纯段落文本
     一期一条记录，正文含当事人、违法事实、处罚决定

输出：data/processed/penalty_events.csv
     一行 = 一个被处罚当事人（机构或个人）
"""
import gzip
import json
import re
import sys
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CLOB_DIR = ROOT / "data" / "raw" / "clob"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ 字典
BANK_TYPE_RULES = [
    ("政策性银行", ["国家开发银行", "进出口银行", "农业发展银行"]),
    ("国有大型银行", ["中国工商银行", "中国农业银行", "中国银行", "中国建设银行",
                     "交通银行", "中国邮政储蓄银行", "邮政储蓄"]),
    ("股份制银行", ["招商银行", "浦发银行", "上海浦东发展", "中信银行", "中国光大银行",
                   "华夏银行", "中国民生银行", "兴业银行", "广发银行", "平安银行",
                   "浙商银行", "渤海银行", "恒丰银行"]),
    ("村镇银行", ["村镇银行"]),
    ("农村中小银行", ["农村商业银行", "农村合作银行", "农村信用", "农信社",
                    "信用合作联社", "农商行"]),
    ("民营银行", ["微众银行", "网商银行", "富民银行", "新网银行", "华瑞银行",
                 "金城银行", "三湘银行", "亿联银行", "苏宁银行", "众邦银行",
                 "蓝海银行", "振兴银行", "客商银行", "中关村银行", "民商银行"]),
]
INSURANCE_KEYS = ["保险", "人寿", "财险", "再保险", "健康险", "养老险", "保险资产"]
NONBANK_KEYS = ["理财", "信托", "金融租赁", "融资租赁", "资产管理", "证券", "基金",
                "期货", "消费金融", "汽车金融", "财务有限公司", "支付", "小额贷款"]
BANK_KEYS = ["银行", "信用社", "信用合作联社", "农信社"]

# 违规类型（规则式归类，覆盖信贷主线）
VIOLATION_RULES = [
    ("贷款三查不到位", ["贷前调查", "贷后管理", "贷中审查", "尽职调查", "三查",
                       "贷款调查", "授信调查", "审查不尽职", "调查不尽职"]),
    ("违规发放贷款", ["违规发放", "不符合条件", "违反审慎经营", "授信审批",
                     "超权限", "审批不审慎", "违规授信", "授信集中度", "集中度"]),
    ("贷款资金挪用", ["挪用", "资金用途", "受托支付", "资金流向", "回流"]),
    ("掩盖不良与五级分类", ["掩盖", "虚假转让", "借新还旧", "以贷还贷", "五级分类",
                          "不良贷款", "资产质量不真实", "虚假出表"]),
    ("内控与员工行为", ["内控", "内部控制", "员工行为", "轮岗", "案件防控",
                     "内外勾结", "违规操作", "私刻", "印章"]),
    ("数据报送与统计", ["报送", "数据不真实", "统计", "报表", "信息不真实"]),
    ("同业理财与票据", ["同业", "理财", "票据", "贴现", "表外", "通道"]),
    ("收费与销售行为", ["收费", "服务价格", "销售", "误导", "代销", "捆绑"]),
    ("关联交易与关系人", ["关联交易", "关系人", "关联方", "股东"]),
    ("其他违规", []),
]
CREDIT_KEYS = ["贷款", "授信", "信贷", "贷前", "贷中", "贷后", "受托支付", "挪用",
               "三查", "小微企业", "普惠", "担保", "抵押", "票据", "贴现"]

RE_AMT_WAN = re.compile(r"([\d,]+(?:\.\d+)?)\s*万元")
RE_AMT_YI = re.compile(r"([\d,]+(?:\.\d+)?)\s*亿元")
RE_DOCNO = re.compile(r"[〔\[]\s*(\d{4})\s*[〕\]]\s*(\d+)\s*号")
RE_PERSON = re.compile(r"当事人[：:]\s*([^\n，,。]{2,40})")

PUNISH_FLAGS = {
    "警告": ["警告"],
    "罚款": ["罚款", "罚没"],
    "没收": ["没收"],
    "禁业": ["禁止", "终身禁业", "禁业"],
    "取消任职资格": ["取消", "任职资格"],
    "责令整改": ["责令", "整改"],
    "吊销停业": ["吊销", "停业", "撤销"],
}


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def classify_industry(name: str) -> str:
    if any(k in name for k in BANK_KEYS):
        return "银行"
    if any(k in name for k in INSURANCE_KEYS):
        return "保险"
    if any(k in name for k in NONBANK_KEYS):
        return "非银机构"
    return "其他/个人"


def classify_bank_type(name: str) -> str:
    for label, keys in BANK_TYPE_RULES:
        if any(k in name for k in keys):
            return label
    if "银行" in name:
        return "城商行/其他银行"
    return ""


def classify_violation(text: str) -> str:
    for label, keys in VIOLATION_RULES:
        if any(k in text for k in keys):
            return label
    return "其他违规"


def extract_amounts(text: str) -> tuple[float, float]:
    """返回 (罚款万元, 没收万元)；无金额返回 0。"""
    fine = sum(float(x.replace(",", "")) for x in RE_AMT_WAN.findall(text))
    fine += sum(float(x.replace(",", "")) * 10000 for x in RE_AMT_YI.findall(text))
    confiscate = 0.0
    for seg in re.findall(r"没收[^。；]{0,40}", text):
        for x in RE_AMT_WAN.findall(seg):
            confiscate += float(x.replace(",", ""))
        for x in RE_AMT_YI.findall(seg):
            confiscate += float(x.replace(",", "")) * 10000
    return round(fine, 2), round(confiscate, 2)


def punish_flags(text: str) -> dict:
    return {f"是否{f}": int(any(k in text for k in keys))
            for f, keys in PUNISH_FLAGS.items()}


def clean_party(name: str) -> str:
    """『浦银理财有限责任公司及相关责任人员』→ 机构名。"""
    name = norm(name)
    name = re.sub(r"(及)?(相关)?(责任人员|有关责任人员|责任人).*$", "", name)
    name = re.sub(r"[（(].*?[）)]$", "", name)
    return name.strip()


def soup_of(clob: str) -> BeautifulSoup:
    soup = BeautifulSoup(clob or "", "lxml")
    for t in soup(["style", "script", "xml", "o:p", "meta", "link"]):
        t.decompose()
    return soup


def html_tables(clob: str) -> list[list[list[str]]]:
    soup = soup_of(clob)
    out = []
    for tb in soup.find_all("table"):
        rows = []
        for tr in tb.find_all("tr"):
            cells = [norm(td.get_text()) for td in tr.find_all(["td", "th"])]
            if any(cells):
                rows.append(cells)
        if rows:
            out.append(rows)
    return out


def plain_text(clob: str) -> str:
    soup = soup_of(clob)
    txt = soup.get_text("\n")
    txt = re.sub(r"[ \t\u3000]+", " ", txt)
    return re.sub(r"\n{2,}", "\n", txt).strip()


# ------------------------------------------------------------------ 解析器
def parse_list_table(rows: list[list[str]]) -> list[dict]:
    """格式 A：序号|当事人名称|主要违法违规行为|行政处罚内容|作出决定机关"""
    header_idx = None
    for i, r in enumerate(rows[:3]):
        joined = "".join(r)
        if "当事人" in joined and ("违法" in joined or "处罚" in joined):
            header_idx = i
            break
    if header_idx is None:
        return []
    out = []
    for r in rows[header_idx + 1:]:
        if len(r) < 3:
            continue
        if r[0].isdigit():                      # 有 序号 列
            seq, party, fact, decision, agency = (
                r + [""] * 5)[:5]
        else:
            seq, party, fact = "", r[0], r[1]
            decision = r[2] if len(r) > 2 else ""
            agency = r[3] if len(r) > 3 else ""
        if not party:
            continue
        fine, conf = extract_amounts(decision or fact)
        out.append({
            "序号": seq, "当事人": party, "机构名称": clean_party(party),
            "违法违规事实": fact, "处罚内容": decision, "处罚机关": agency,
            "罚款万元": fine, "没收万元": conf, "_fmt": "A列表表",
        })
    return out


def parse_kv_table(rows: list[list[str]]) -> dict:
    """格式 B：两列『字段名 | 内容』"""
    kv = {}
    for r in rows:
        if len(r) >= 2 and r[0] and r[1]:
            kv.setdefault(r[0], r[1])
        elif len(r) >= 4:                        # 偶见四列合排
            if r[0] and r[1]:
                kv.setdefault(r[0], r[1])
            if r[2] and r[3]:
                kv.setdefault(r[2], r[3])
    return kv


def kv_longest(kv: dict, *keys: str) -> str:
    best = ""
    for k, v in kv.items():
        if any(x in k for x in keys) and len(v) > len(best):
            best = v
    return best


def parse_kv_record(kv: dict) -> dict:
    if not kv:
        return {}
    fact = kv_longest(kv, "违法", "案由", "违规")
    decision = kv_longest(kv, "处罚决定", "处罚内容", "行政处罚决定")
    party = kv_longest(kv, "当事人", "被处罚")
    if not (fact or decision or party):
        return {}
    fine, conf = extract_amounts(decision or fact)
    return {
        "序号": "", "当事人": party, "机构名称": clean_party(party),
        "违法违规事实": fact, "处罚内容": decision,
        "处罚机关": kv_longest(kv, "机关", "作出处罚"),
        "罚款万元": fine, "没收万元": conf, "_fmt": "B信息公开表",
    }


def parse_free_text(txt: str) -> dict:
    """格式 C：决定书纯文本，尽力抽取。"""
    if len(txt) < 80:
        return {}
    parties = RE_PERSON.findall(txt)
    party = parties[0] if parties else ""
    m = re.search(r"(?:经查|经调查)[，,]?\s*(.{20,1500})", txt, re.S)
    fact = norm(m.group(1))[:1200] if m else norm(txt)[:800]
    m2 = re.search(r"(决定[^。]{0,200}。)", txt, re.S)
    decision = norm(m2.group(1))[:600] if m2 else ""
    fine, conf = extract_amounts(txt)
    return {
        "序号": "", "当事人": party, "机构名称": clean_party(party),
        "违法违规事实": fact, "处罚内容": decision,
        "处罚机关": "", "罚款万元": fine, "没收万元": conf, "_fmt": "C决定书",
    }


def parse_doc(doc_id: int, data: dict, meta: dict) -> list[dict]:
    clob = data.get("docClob") or ""
    title = data.get("docTitle") or meta.get("docTitle") or ""
    pub = (data.get("publishDate") or meta.get("publishDate") or "")[:10]
    tables = html_tables(clob)
    records = []
    for rows in tables:
        joined = "".join("".join(r) for r in rows[:2])
        if "当事人" in joined and ("违法" in joined or "处罚内容" in joined):
            records.extend(parse_list_table(rows))
        else:
            rec = parse_kv_record(parse_kv_table(rows))
            if rec:
                records.append(rec)
    if not records:                              # 回退到纯文本
        rec = parse_free_text(plain_text(clob))
        if rec:
            records.append(rec)
    m = RE_DOCNO.search(title) or RE_DOCNO.search(clob[:3000])
    docno = f"〔{m.group(1)}〕{m.group(2)}号" if m else ""
    for r in records:
        r.update({
            "docId": doc_id, "发布日期": pub, "年份": int(pub[:4]) if pub[:4].isdigit() else None,
            "文号": docno, "标题": title,
        })
    return records


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    df["行业"] = df["机构名称"].map(classify_industry)
    df["机构类型"] = df.apply(
        lambda r: classify_bank_type(r["机构名称"]) if r["行业"] == "银行" else "", axis=1)
    df["违规类型"] = (df["违法违规事实"].fillna("") + df["处罚内容"].fillna("")).map(classify_violation)
    credit_src = df["违法违规事实"].fillna("") + df["处罚内容"].fillna("")
    df["信贷相关"] = credit_src.map(lambda s: int(any(k in s for k in CREDIT_KEYS)))
    flags = pd.DataFrame([punish_flags(str(d) + str(f))
                          for d, f in zip(df["处罚内容"], df["违法违规事实"])])
    df = pd.concat([df.reset_index(drop=True), flags], axis=1)
    df["罚没合计万元"] = (df["罚款万元"].fillna(0) + df["没收万元"].fillna(0)).round(2)
    return df


def main() -> int:
    index = json.loads((INTERIM / "doc_index.json").read_text(encoding="utf-8"))
    all_rows, missing = [], []
    for meta in index:
        doc_id = meta["docId"]
        p = CLOB_DIR / f"{doc_id}.json.gz"
        if not p.exists():
            missing.append(doc_id)
            continue
        with gzip.open(p, "rt", encoding="utf-8") as f:
            data = json.load(f)
        all_rows.extend(parse_doc(doc_id, data, meta))

    print(f"期数 {len(index)}，缺正文 {len(missing)}，解析出记录 {len(all_rows)}")
    df = pd.DataFrame(all_rows)
    df = enrich(df)
    cols = ["docId", "文号", "发布日期", "年份", "标题", "序号", "当事人", "机构名称",
            "行业", "机构类型", "违法违规事实", "处罚内容", "处罚机关",
            "罚款万元", "没收万元", "罚没合计万元",
            "是否警告", "是否罚款", "是否没收", "是否禁业", "是否取消任职资格",
            "是否责令整改", "是否吊销停业",
            "信贷相关", "违规类型", "_fmt"]
    df = df[[c for c in cols if c in df.columns]]
    out = PROCESSED / "penalty_events.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"已存: {out}  形状 {df.shape}")

    print("\n" + "=" * 64)
    print("格式分布");            print(df["_fmt"].value_counts().to_string())
    print("\n行业分布");          print(df["行业"].value_counts().to_string())
    print("\n银行细分");          print(df.loc[df['行业'] == '银行', "机构类型"].value_counts().to_string())
    print("\n信贷相关条数");      print(int(df["信贷相关"].sum()))
    print("\n按年记录数");        print(df["年份"].value_counts().sort_index().to_string())
    print("\n有金额的记录数");    print(int((df["罚没合计万元"] > 0).sum()),
          f"  合计 {df['罚没合计万元'].sum():,.0f} 万元")
    print("\n违规类型 Top10");    print(df["违规类型"].value_counts().head(10).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
