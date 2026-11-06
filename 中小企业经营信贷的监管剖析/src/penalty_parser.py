# -*- coding: utf-8 -*-
"""
penalty_parser —— 处罚公示正文（docClob）解析模块
=================================================
被 stage2_parse.py（总局机关）与 stage4_branch_events.py（派出机构）共用。

支持三类正文格式：
  A 列表式汇总表  「序号 | 当事人名称 | 主要违法违规行为 | 行政处罚内容 | 作出决定机关」
  B 行政处罚信息公开表  「字段名 | 内容」两列键值对
  C 行政处罚决定书  纯段落文本

字段口径说明（重要，写论文时要交代）：
  · 罚款万元 / 没收万元 / 罚没合计万元
      优先取正文中的「罚没合计 / 合计 / 共计」金额，避免与分项重复累加；
      无合计口径时才用「罚款 + 没收」分项求和。
  · 当事人类型 ：机构 / 个人（按名称关键词与「员工」类表述判定）
  · 机构名称   ：从当事人中剥离「及相关责任人员」「（以下简称…）」「员工张三」等后缀
"""
import re

from bs4 import BeautifulSoup

# ------------------------------------------------------------------ 字典
BANK_TYPE_RULES = [
    ("政策性银行", ["国家开发银行", "进出口银行", "农业发展银行"]),
    ("国有大型银行", ["中国工商银行", "中国农业银行", "中国银行", "中国建设银行",
                     "交通银行", "中国邮政储蓄银行", "邮政储蓄", "工商银行",
                     "农业银行", "建设银行", "邮储银行"]),
    ("股份制银行", ["招商银行", "浦发银行", "上海浦东发展", "中信银行", "光大银行",
                    "华夏银行", "民生银行", "兴业银行", "广发银行", "平安银行",
                    "浙商银行", "渤海银行", "恒丰银行"]),
    ("村镇银行", ["村镇银行"]),
    ("农村中小银行", ["农村商业银行", "农村合作银行", "农村信用", "农信社", "农商行",
                    "信用合作联社", "信用合作社", "农村商业"]),
    ("民营银行", ["微众银行", "网商银行", "富民银行", "新网银行", "华瑞银行",
                  "金城银行", "三湘银行", "亿联银行", "苏宁银行", "众邦银行",
                  "蓝海银行", "振兴银行", "客商银行", "中关村银行", "民商银行"]),
]
INSURANCE_KEYS = ["保险", "人寿", "财险", "再保险", "健康险", "养老险", "保险资产"]
NONBANK_KEYS = ["理财", "信托", "金融租赁", "融资租赁", "资产管理", "证券", "基金",
                "期货", "消费金融", "汽车金融", "财务有限公司", "支付", "小额贷款",
                "科技集团", "金服"]
BANK_KEYS = ["银行", "信用社", "信用合作联社", "农信社", "信用合作社"]

ORG_KEYS = ["银行", "公司", "信用社", "联社", "保险", "中心", "集团", "合作社",
            "事务所", "厂", "店", "医院", "学校", "研究院", "协会", "基金"]

VIOLATION_RULES = [
    ("贷款三查不到位", ["贷前调查", "贷后管理", "贷中审查", "尽职调查", "三查",
                       "贷款调查", "授信调查", "审查不尽职", "调查不尽职",
                       "贷后检查", "贷前调查不尽职", "贷后管理不到位"]),
    ("贷款资金挪用", ["挪用", "资金用途", "受托支付", "资金流向", "回流", "用途管控",
                     "贷款资金"]),
    ("违规发放贷款", ["违规发放", "不符合条件", "违反审慎经营", "授信审批", "超权限",
                     "审批不审慎", "违规授信", "授信集中度", "集中度", "违规办理",
                     "发放贷款", "以贷"]),
    ("掩盖不良与五级分类", ["掩盖", "虚假转让", "借新还旧", "以贷还贷", "五级分类",
                          "不良贷款", "资产质量不真实", "虚假出表", "隐性", "核销"]),
    ("信贷管理不到位", ["信贷业务管理", "信贷管理", "贷款管理", "授信管理",
                       "信贷业务", "贷款业务", "贷款审查", "授信业务", "信贷",
                       "统一授信", "集团客户", "资本金审查", "保理", "信用证",
                       "银行承兑", "国内证", "贸易背景"]),
    ("违规经营与指标不实", ["虚增存贷款", "存贷挂钩", "浮利分费", "冲时点",
                          "虚增", "以贷转存", "存款业务管理"]),
    ("内控与员工行为", ["内控", "内部控制", "员工行为", "轮岗", "案件防控", "内外勾结",
                     "违规操作", "私刻", "印章", "强行休假", "对账", "违规兼职",
                     "履职", "案防", "许可证", "员工异常", "员工从事", "管理不善",
                     "员工管理"]),
    ("数据报送与统计", ["报送", "数据不真实", "统计", "报表", "信息不真实", "信息科技"]),
    ("同业理财与票据", ["同业", "理财", "票据", "贴现", "表外", "通道", "转贴现"]),
    ("收费与销售行为", ["收费", "服务价格", "销售", "误导", "代销", "捆绑", "变相",
                       "牟取", "利益", "隐瞒", "代客操作"]),
    ("关联交易与关系人", ["关联交易", "关系人", "关联方", "股东", "股权"]),
    ("其他违规", []),
]
CREDIT_KEYS = ["贷款", "授信", "信贷", "贷前", "贷中", "贷后", "受托支付", "挪用",
               "三查", "小微企业", "普惠", "担保", "抵押", "票据", "贴现"]

PUNISH_FLAGS = {
    "警告": ["警告"],
    "罚款": ["罚款", "罚没"],
    "没收": ["没收"],
    "禁业": ["禁止", "禁业"],
    "取消任职资格": ["取消", "任职资格"],
    "责令整改": ["责令", "整改"],
    "吊销停业": ["吊销", "停业", "撤销"],
}

# 金额：合计口径优先，避免分项重复累加
RE_TOTAL = re.compile(r"(?:罚没合计|合计罚没|共计|合计)[^\d]{0,8}([\d,]+(?:\.\d+)?)\s*(万元|亿元)")
RE_FINE = re.compile(r"罚款[^\d没]{0,8}([\d,]+(?:\.\d+)?)\s*(万元|亿元)")
RE_CONF = re.compile(r"没收(?:违法所得)?[^\d罚]{0,8}([\d,]+(?:\.\d+)?)\s*(万元|亿元)")
RE_DOCNO = re.compile(r"[〔\[]\s*(\d{4})\s*[〕\]]\s*(\d+)\s*号")
RE_PARTY_PARA = re.compile(r"当事人[：:]\s*([^\n，,。]{2,40})")
UNIT = {"万元": 1.0, "亿元": 10000.0}


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _to_wan(num: str, unit: str) -> float:
    return float(num.replace(",", "")) * UNIT[unit]


# ------------------------------------------------------------------ 分类
def classify_industry(name: str) -> str:
    if any(k in name for k in BANK_KEYS):
        return "银行"
    if any(k in name for k in INSURANCE_KEYS):
        return "保险"
    if any(k in name for k in NONBANK_KEYS):
        return "非银机构"
    return "其他"


def classify_bank_type(name: str) -> str:
    for label, keys in BANK_TYPE_RULES:
        if any(k in name for k in keys):
            return label
    if "银行" in name:
        return "城商行/其他银行"
    return ""


INSURANCE_VIOLATION_RULES = [
    ("保险销售与费用", ["虚列费用", "编制虚假", "套取费用", "欺骗投保人", "误导",
                     "虚列业务", "牟取", "利益", "佣金", "培训和管理"]),
    ("保险条款费率", ["保险条款", "保险费率", "未经批准", "未按照规定使用"]),
    ("保险中介管理", ["中介业务", "代理人", "经纪", "代理机构", "跨区域经营"]),
    ("保险业务记录", ["未如实记录", "承保", "理赔", "虚假理赔", "数据质量"]),
    ("其他违规", []),
]
HEADER_LABELS = {"主要违法违规事实（案由）", "主要违法违规事实", "主要违法违规行为",
                 "违法违规事实", "行政处罚内容", "作出决定机关", "当事人名称",
                 "行政处罚决定书文号", "序号", "行政处罚决定", "被处罚当事人姓名"}


def classify_violation(text: str, industry: str = "") -> str:
    rules = INSURANCE_VIOLATION_RULES if industry == "保险" else VIOLATION_RULES
    for label, keys in rules:
        if keys and any(k in text for k in keys):
            return label
    return "其他违规"


def classify_party_type(name: str) -> str:
    if any(k in name for k in ORG_KEYS):
        return "机构"
    return "个人"


# ------------------------------------------------------------------ 字段抽取
def _decision_sentences(text: str) -> str:
    """只保留「含罚款/没收/罚没 且 含决定/给予/对」的句子，剔除涉案金额等干扰。"""
    parts = re.split(r"[。；;\n]", text or "")
    keep = [p for p in parts
            if re.search(r"罚款|没收|罚没", p)
            and re.search(r"决定|给予|处|罚|对", p)]
    return "。".join(keep)


def extract_amounts(text: str, strict: bool = True) -> tuple[float, float, float]:
    """返回 (罚款万元, 没收万元, 罚没合计万元)。"""
    src = _decision_sentences(text) if strict else (text or "")
    if not src:
        src = text or ""

    totals = [_to_wan(n, u) for n, u in RE_TOTAL.findall(src)]
    fines = [_to_wan(n, u) for n, u in RE_FINE.findall(src)]
    confs = [_to_wan(n, u) for n, u in RE_CONF.findall(src)]

    fine = round(sum(fines), 2)
    conf = round(sum(confs), 2)
    if totals:
        total = round(max(totals), 2)          # 官方合计口径，优先
    else:
        total = round(fine + conf, 2)
    # 有合计口径时，避免 fine/conf 与合计并存造成误解：保持分项原值，合计单列
    return fine, conf, total


def punish_flags(text: str) -> dict:
    return {f"是否{f}": int(any(k in text for k in keys))
            for f, keys in PUNISH_FLAGS.items()}


def _tidy_org(s: str) -> str:
    """统一清理机构名：去说明性括号、去职务前缀与时态词。"""
    s = re.sub(r"[（(][^）)]*(?:原|简|下称|曾用名)[^）)]*[）)]\s*$", "", s)
    s = re.sub(r"[（(][^）)]{6,}[）)]\s*$", "", s)
    s = re.sub(r"^(?:时任|原任|现任|系|原|现)+", "", s) if re.match(
        r"^(?:时任|原任|现任|系|原|现)+[\u4e00-\u9fa5]{2,}"
        r"(?:银行|信用社|公司|联社|支公司|分公司)", s) else s
    return s.strip("、，（( ")


def clean_party(raw: str) -> tuple[str, str]:
    """『中国农业发展银行员工张眉』→ ('中国农业发展银行', '张眉')
       『周路（时任…河南省分行副行长）』→ ('中国银行股份有限公司河南省分行', '周路')

    返回 (机构名称, 个人姓名)；纯机构时个人姓名留空。
    """
    s = norm(raw)
    s = re.sub(r"^[（(]?\d+[）)]?[、.]?", "", s)          # 前导序号
    s = re.sub(r"[（(]以下简称[^）)]*[）)]", "", s)
    s = re.sub(r"[（(]以下简.*$", "", s)
    s = re.sub(r"[（(]下称[^）)]*[）)]", "", s)

    person = ""
    # 形式一：张三（时任XX银行XX分行副行长）—— 从括号里反推机构全称
    m = re.match(r"^([\u4e00-\u9fa5]{2,4})[（(]([^）)]*)[）)]$", s)
    if m and re.search(r"银行|信用社|公司|联社|支公司|分公司", m.group(2)):
        person = m.group(1)
        cand = re.findall(
            r"[\u4e00-\u9fa5]{2,40}?(?:银行|信用社|信用合作联社|公司|支公司|分公司)"
            r"(?:[\u4e00-\u9fa5]{0,12}(?:分行|支行|分公司|支公司|营业部|中心支公司))?",
            m.group(2))
        return _tidy_org(max(cand, key=len) if cand else ""), person

    # 形式二：XX银行员工张三 / XX银行原职工张三
    m = re.search(r"(?:员工|职工|工作人员)\s*([\u4e00-\u9fa5、]{2,20})$", s)
    if m:
        person = m.group(1)
        s = s[:m.start()]
    s = re.sub(r"(及)?(相关)?(有关)?(责任人员|责任人).*$", "", s)
    s = re.sub(r"(等)?\d+人$", "", s)
    s = _tidy_org(s)
    if not person and s and classify_party_type(s) == "个人":
        person, s = s, ""
    return s, person


# ------------------------------------------------------------------ HTML
def soup_of(clob: str) -> BeautifulSoup:
    soup = BeautifulSoup(clob or "", "lxml")
    for t in soup(["style", "script", "xml", "o:p", "meta", "link"]):
        t.decompose()
    return soup


def table_to_grid(tb) -> list[list[str]]:
    """把 <table> 展开成规整二维网格，正确处理 rowspan / colspan。

    监管公示表格常见「主要违法违规行为」「作出决定机关」纵向合并，
    后续行会直接省略被合并的单元格；若按位置取值就会整行错位。
    本函数按合并关系把被省略的位置补回原值。
    """
    grid: dict[tuple[int, int], str] = {}
    trs = [tr for tr in tb.find_all("tr") if tr.find_parent("table") is tb]
    for r, tr in enumerate(trs):
        c = 0
        for cell in tr.find_all(["td", "th"], recursive=False):
            while (r, c) in grid:
                c += 1
            text = norm(cell.get_text())
            try:
                rs = int(cell.get("rowspan") or 1)
            except (TypeError, ValueError):
                rs = 1
            try:
                cs = int(cell.get("colspan") or 1)
            except (TypeError, ValueError):
                cs = 1
            for dr in range(min(rs, 60)):
                for dc in range(min(cs, 12)):
                    grid[(r + dr, c + dc)] = text
            c += cs
    if not grid:
        return []
    ncols = max(c for _, c in grid) + 1
    nrows = len(trs)
    return [[grid.get((r, c), "") for c in range(ncols)] for r in range(nrows)]


def html_tables(clob: str) -> list[list[list[str]]]:
    soup = soup_of(clob)
    out = []
    for tb in soup.find_all("table"):
        rows = [r for r in table_to_grid(tb) if any(r)]
        if rows:
            out.append(rows)
    return out


def plain_text(clob: str) -> str:
    txt = soup_of(clob).get_text("\n")
    txt = re.sub(r"[ \t\u3000]+", " ", txt)
    return re.sub(r"\n{2,}", "\n", txt).strip()


# ------------------------------------------------------------------ 三类解析器
def _map_columns(rows: list[list[str]], hi: int) -> tuple[dict, int]:
    """按表头文字建立「字段 → 列号」映射，避免不同分局列顺序不一致导致错位。"""
    hdr = list(rows[hi])
    body_start = hi + 1
    # 表头可能占两行（如「主要违法」「违规行为」分两行）
    if hi + 1 < len(rows) and 0 < len(rows[hi + 1]) == len(hdr) \
            and all(len(c) <= 6 for c in rows[hi + 1] if c):
        hdr = [(a or "") + (b or "") for a, b in zip(hdr, rows[hi + 1])]
        body_start = hi + 2
    m: dict[str, int] = {}
    for idx, h in enumerate(hdr):
        if not h:
            continue
        # 注意顺序：「作出决定机关」同时含「决定」和「机关」，必须先判机关
        if "文号" in h:
            m.setdefault("docno", idx)
        elif "机关" in h or "单位" in h:
            m.setdefault("agency", idx)
        elif "当事人" in h or "被处罚" in h:
            m.setdefault("party", idx)
        elif "违法" in h or "案由" in h or "违规" in h or "事由" in h:
            m.setdefault("fact", idx)
        elif "处罚内容" in h or "处罚决定" in h or "处罚措施" in h or "决定" in h:
            m.setdefault("decision", idx)
        elif "序" in h:
            m.setdefault("seq", idx)
    return m, body_start


def parse_list_table(rows: list[list[str]]) -> list[dict]:
    header_idx = None
    for i, r in enumerate(rows[:5]):
        joined = "".join(r)
        if ("当事人" in joined or "被处罚" in joined) and \
                ("违法" in joined or "处罚" in joined or "案由" in joined):
            header_idx = i
            break
    if header_idx is None:
        return []
    cmap, body = _map_columns(rows, header_idx)
    if "party" not in cmap:
        return []

    out = []
    for r in rows[body:]:
        if len(r) < 2:
            continue

        def get(key: str, default: str = "") -> str:
            idx = cmap.get(key)
            return r[idx] if idx is not None and idx < len(r) else default

        party = get("party")
        if not party or party in HEADER_LABELS or len(party) > 80:
            continue
        seq = get("seq") or (r[0] if r and r[0].isdigit() else "")
        fact = get("fact")
        decision = get("decision")
        if fact in HEADER_LABELS:
            fact = ""
        if decision in HEADER_LABELS:
            decision = ""
        # 列错位自愈：若「违法事实」格里只有文号，说明整行右移了一位
        if fact and RE_DOCNO.fullmatch(norm(fact)):
            shifted = r[cmap["fact"] + 1:] if "fact" in cmap else []
            if shifted:
                fact = shifted[0]
                decision = shifted[1] if len(shifted) > 1 else decision
        # 位置兜底（无表头映射时）
        if not fact and not decision:
            cells = [c for c in r if c]
            if len(cells) >= 4:
                _, party2, fact, decision, agency = (cells + [""] * 5)[:5]
                party = party or party2
        fine, conf, total = extract_amounts(decision or fact)
        out.append({"序号": seq, "当事人": party,
                    "违法违规事实": fact, "处罚内容": decision,
                    "处罚机关": get("agency"),
                    "罚款万元": fine, "没收万元": conf,
                    "罚没合计万元": total, "_fmt": "A列表表"})
    return out


SUBHEADER_LABELS = {"单位", "个人姓名", "名称", "姓名", "职务",
                    "法定代表人姓名", "法定代表人", "主要负责人",
                    "法定代表人（主要负责人）姓名"}


def parse_kv_table(rows: list[list[str]]) -> dict:
    """信息公开表的键值对提取。

    这类表常把字段名横向合并成 3 列、值放在最后一列，展开后形如
        ['主要违法违规事实（案由）', '…', '…', '一、农业银行…']
    因此取「首格为键、末格为值」；字段名与值相同的行是纯标签行，跳过。
    """
    kv: dict[str, str] = {}
    for r in rows:
        cells = [c for c in r if c and c not in SUBHEADER_LABELS]
        if len(cells) < 2:
            continue
        key, val = cells[0], cells[-1]
        if not key or not val or key == val:
            continue
        kv.setdefault(key, val)
    return kv


def kv_longest(kv: dict, *keys: str) -> str:
    best = ""
    for k, v in kv.items():
        if any(x in k for x in keys) and len(v) > len(best):
            best = v
    return best


def kv_bucket(kv: dict) -> dict:
    """按字段名语义把键值对归入固定槽位，避免「文号」「日期」被误当处罚内容/机关。

    「行政处罚决定书文号」含"决定"但不含处罚内容，
    「作出处罚决定的日期」含"决定"但属于日期 —— 必须靠语义优先级区分。
    """
    out = {"party": "", "fact": "", "decision": "", "agency": "",
           "docno": "", "date": "", "basis": ""}

    def take(slot, v):
        if v and len(v) > len(out[slot]):
            out[slot] = v

    for k, v in kv.items():
        if "文号" in k:
            take("docno", v)
        elif "日期" in k:
            take("date", v)
        elif "机关" in k:
            take("agency", v)
        elif "依据" in k:
            take("basis", v)
        elif "违法" in k or "案由" in k or "违规" in k:
            take("fact", v)
        elif "处罚决定" in k or "处罚内容" in k or "处罚措施" in k or "决定" in k:
            take("decision", v)
        elif "当事人" in k or "被处罚" in k:
            take("party", v)
    return out


def parse_kv_record(kv: dict) -> dict:
    if not kv:
        return {}
    b = kv_bucket(kv)
    fact, decision, party = b["fact"], b["decision"], b["party"]
    if fact in HEADER_LABELS or fact.startswith("主要违法"):
        fact = ""
    if decision in HEADER_LABELS or decision.startswith("行政处罚决定书"):
        decision = ""
    if party in HEADER_LABELS or party in SUBHEADER_LABELS:
        party = ""
    if not (fact or decision or party):
        return {}
    fine, conf, total = extract_amounts(decision or fact)
    return {"序号": "", "当事人": party,
            "违法违规事实": fact, "处罚内容": decision,
            "处罚机关": b["agency"],
            "罚款万元": fine, "没收万元": conf, "罚没合计万元": total,
            "_fmt": "B信息公开表"}


def parse_free_text(txt: str) -> dict:
    if len(txt) < 60:
        return {}
    parties = RE_PARTY_PARA.findall(txt)
    party = parties[0] if parties else ""
    m = re.search(r"(?:经查|经调查|经立案调查)[，,]?\s*(.{20,1500})", txt, re.S)
    fact = norm(m.group(1))[:1200] if m else norm(txt)[:800]
    m2 = re.search(r"(?:决定|现决定)[^。]{0,300}。", txt, re.S)
    decision = norm(m2.group(0))[:600] if m2 else ""
    fine, conf, total = extract_amounts(txt, strict=True)
    return {"序号": "", "当事人": party,
            "违法违规事实": fact, "处罚内容": decision,
            "处罚机关": "", "罚款万元": fine, "没收万元": conf,
            "罚没合计万元": total, "_fmt": "C决定书"}


# ------------------------------------------------------------------ 主入口
def parse_doc(doc_id: int, data: dict, fallback: dict | None = None) -> list[dict]:
    fallback = fallback or {}
    clob = data.get("docClob") or ""
    title = data.get("docTitle") or fallback.get("docTitle") or ""
    pub = (data.get("publishDate") or fallback.get("publishDate") or "")[:10]

    records = []
    for rows in html_tables(clob):
        joined = "".join("".join(r) for r in rows[:2])
        if "当事人" in joined and ("违法" in joined or "处罚内容" in joined):
            records.extend(parse_list_table(rows))
        else:
            rec = parse_kv_record(parse_kv_table(rows))
            if rec:
                records.append(rec)
    if not records:
        rec = parse_free_text(plain_text(clob))
        if rec:
            records.append(rec)

    m = RE_DOCNO.search(title) or RE_DOCNO.search(clob[:4000])
    docno = f"〔{m.group(1)}〕{m.group(2)}号" if m else ""

    for r in records:
        org, person = clean_party(r["当事人"])
        fact = str(r.get("违法违规事实") or "")
        if fact in HEADER_LABELS or fact.startswith("主要违法") or fact.startswith("主要违规"):
            r["违法违规事实"] = ""
            fact = ""
        if not fact and not r.get("处罚内容"):
            continue
        r.update({
            "docId": doc_id, "发布日期": pub,
            "年份": int(pub[:4]) if pub[:4].isdigit() else None,
            "文号": docno, "标题": norm(title),
            "机构名称": org, "个人姓名": person,
            "当事人类型": "机构" if org and classify_party_type(org) == "机构" else "个人",
        })
        r["_keep"] = True
    return [r for r in records if r.get("_keep")]


def enrich_record(r: dict) -> dict:
    """补齐派生字段（行业/机构类型/违规类型/信贷相关/处罚方式标记）。"""
    name = r.get("机构名称") or ""
    text = (r.get("违法违规事实") or "") + (r.get("处罚内容") or "")
    r["行业"] = classify_industry(name) if name else "个人"
    r["机构类型"] = classify_bank_type(name) if r["行业"] == "银行" else ""
    r["违规类型"] = classify_violation(text, r["行业"])
    r["信贷相关"] = int(any(k in text for k in CREDIT_KEYS))
    r.update(punish_flags(str(r.get("处罚内容") or "") + str(r.get("违法违规事实") or "")))
    return r


EVENT_COLUMNS = [
    "docId", "文号", "发布日期", "年份", "标题", "序号", "当事人", "机构名称",
    "个人姓名", "当事人类型", "行业", "机构类型", "违法违规事实", "处罚内容",
    "处罚机关", "罚款万元", "没收万元", "罚没合计万元",
    "是否警告", "是否罚款", "是否没收", "是否禁业", "是否取消任职资格",
    "是否责令整改", "是否吊销停业", "信贷相关", "违规类型", "_fmt",
]
