#!/usr/bin/env python3
"""境内单位代扣代缴自然人增值税 计算器（28号公告 / 19号公告）

只用标准库，不联网。所有金额用 Decimal，四舍五入到分。

用法：
  python3 calc.py template --out 流水模板.csv
  python3 calc.py summaries --input 流水.xlsx            # 只列摘要，不含姓名证件号
  python3 calc.py quick --amounts 2000 --amount-basis 不含税   # 估算单人单日税额
  python3 calc.py run --input 流水.xlsx --period 2026-11 \
      --amount-basis 不含税 --default-relief 减按1% --city-rate 市区 --out ./out

输出（--out 目录）：
  申报表.csv / 附列资料.csv     对应 19 号公告申报表 14 列、附列资料 19 列
  异常与提示.csv               必须人工处理的问题（有任何“异常”即为草稿）
  不适用清单.csv               不在代扣范围的付款及理由
  summary.json                汇总与闸门结果（不含证件号）
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import OrderedDict, defaultdict
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
POLICY_PATH = os.path.join(HERE, "..", "references", "policy.json")

CENT = Decimal("0.01")
DASH = "——"

INPUT_COLUMNS = [
    "姓名", "身份证件类型", "身份证件号码", "付款日期", "金额", "摘要",
    "应税交易项目", "服务大类", "是否已代开发票", "代开时已缴税", "优惠",
    "销售方类型", "平台代办", "备注",
]
REQUIRED = ["姓名", "身份证件号码", "付款日期", "金额"]

MAIN_HEADER = [
    "序号", "姓名", "身份证件类型", "身份证件号码", "扣缴义务发生日期", "应税交易项目",
    "是否已代开发票", "销售额", "规定征收率（%）", "增值税减免性质代码", "增值税减免税额",
    "应扣缴增值税", "应扣缴附加税费", "备注",
]
ATTACH_HEADER = [
    "序号", "姓名", "身份证件号码", "扣缴义务发生日期", "应税交易项目", "应扣缴增值税",
    "城建税税率（%）", "城建税减免性质代码", "城建税减免税额", "城建税应扣缴税额",
    "教育费附加费率（%）", "教育费附加减免性质代码", "教育费附加减免费额", "教育费附加应扣缴费额",
    "地方教育附加费率（%）", "地方教育附加减免性质代码", "地方教育附加减免费额", "地方教育附加应扣缴费额",
    "应扣缴附加税费合计",
]


def money(x):
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


def fmt(d):
    return f"{money(d):.2f}"


def pct(rate):
    """Decimal('0.01') -> '1'"""
    s = f"{(Decimal(rate) * 100).normalize():f}"
    return s


def load_policy(path=POLICY_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- input

def _sheet_rows(z, sheet_path, shared, ns):
    root = ET.fromstring(z.read(sheet_path))
    rows = []
    for r in root.iter(f"{{{ns['m']}}}row"):
        cells = {}
        for c in r.findall("m:c", ns):
            ref = c.get("r", "")
            col = 0
            for ch in re.match(r"[A-Z]+", ref).group(0):
                col = col * 26 + (ord(ch) - 64)
            t = c.get("t")
            v = c.find("m:v", ns)
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(f"{{{ns['m']}}}t"))
            else:
                val = v.text if v is not None else ""
            cells[col] = val
        if cells:
            rows.append([cells.get(i, "") for i in range(1, max(cells) + 1)])
    return rows


def _xlsx_sheets(path):
    """返回 [(工作表名, 行列表)]，按工作簿中的顺序。"""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        order = []
        try:
            wb = ET.fromstring(z.read("xl/workbook.xml"))
            rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            target = {r.get("Id"): r.get("Target") for r in rels}
            for sh in wb.iter(f"{{{ns['m']}}}sheet"):
                t = target.get(sh.get(f"{{{rns}}}id"), "")
                t = t.lstrip("/")
                t = t if t.startswith("xl/") else "xl/" + t
                order.append((sh.get("name", ""), t))
        except KeyError:
            pass
        if not order:
            order = [("", n) for n in sorted(x for x in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", x))]
        if not order:
            raise ValueError("xlsx 中没有工作表")
        return [(name, _sheet_rows(z, p, shared, ns)) for name, p in order if p in z.namelist()]


HEADER_ALIASES = {
    "姓名": ["姓名", "收款人", "收款人姓名", "领款人", "人员姓名", "户名", "name", "payeename", "fullname", "payee"],
    "身份证件类型": ["身份证件类型", "证件类型", "idtype", "documenttype"],
    "身份证件号码": ["身份证件号码", "证件号码", "身份证号", "身份证号码", "证件号", "idnumber", "idno", "id", "idcard",
                 "idcardnumber"],
    "付款日期": ["付款日期", "支付日期", "发放日期", "付款时间", "支付时间", "日期", "paymentdate", "paydate", "date"],
    "金额": ["金额", "金额（元）", "金额(元)", "付款金额", "支付金额", "实付金额", "发放金额", "amount", "paymentamount",
           "amount(cny)", "amount(rmb)"],
    "摘要": ["摘要", "用途", "事由", "款项用途", "付款事由", "说明", "description", "purpose", "memo"],
    "服务大类": ["服务大类", "服务类别", "服务类型", "类别", "servicecategory", "category"],
    "应税交易项目": ["应税交易项目", "taxableitem", "item"],
    "是否已代开发票": ["是否已代开发票", "已代开发票", "invoiceissued"],
    "代开时已缴税": ["代开时已缴税", "taxpaidoninvoice"],
    "优惠": ["优惠", "relief"],
    "销售方类型": ["销售方类型", "收款方类型", "sellertype"],
    "平台代办": ["平台代办", "platformfiled"],
    "备注": ["备注", "remarks", "remark", "note"],
}
_ALIAS = {a.lower(): k for k, v in HEADER_ALIASES.items() for a in v}
TOTAL_WORDS = ("合计", "总计", "小计", "本页合计")
CATEGORY_ALIASES = {"研发": "研发服务", "技术开发": "研发服务", "技术开发服务": "研发服务", "软件": "软件服务",
                    "设计": "设计服务", "咨询": "咨询服务", "文化": "文化服务", "教育": "教育服务",
                    "广播影视": "广播影视节目（作品）制作服务", "影视制作": "广播影视节目（作品）制作服务",
                    "广播影视节目制作服务": "广播影视节目（作品）制作服务", "广播影视节目(作品)制作服务": "广播影视节目（作品）制作服务"}
NATURAL_SELLERS = ("", "自然人", "个人", "境内自然人")
NON_NATURAL_SELLERS = ("个体工商户", "个体户", "公司", "企业", "单位", "有限公司", "合伙企业", "个人独资企业", "其他组织")


def _clean(x):
    x = str(x).replace("\u3000", " ").strip()
    return x[1:].strip() if x.startswith("'") else x


def _norm_header(h):
    h = re.sub(r"\s+", "", str(h)).replace("（", "(").replace("）", ")")
    for cand in (h, h.lower(), h.replace("(", "（").replace(")", "）")):
        if cand in _ALIAS:
            return _ALIAS[cand]
    return h


def _find_header(raw):
    for i, r in enumerate(raw[:15]):
        hs = [_norm_header(x) for x in r]
        if all(c in hs for c in REQUIRED):
            return i, hs
    return None, None


def _read_csv(path):
    data = open(path, "rb").read()
    text = None
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = data.decode("utf-16")
    else:
        for enc in ("utf-8-sig", "gb18030"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
    if text is None:
        raise ValueError("无法识别 CSV 编码（试过 UTF-8、GBK、UTF-16）")
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    delim = max([",", "\t", ";", "|"], key=lambda d: first.count(d))
    if first.count(delim) == 0:
        delim = ","
    return list(csv.reader(text.splitlines(), delimiter=delim))


def read_rows(path, notes=None):
    """notes: 可选 list，收集读取时的提示（如忽略了合计行、用了别名表头）。"""
    notes = notes if notes is not None else []
    if path.lower().endswith(".xlsx"):
        sheets = _xlsx_sheets(path)
    else:
        sheets = [("", _read_csv(path))]
    raw, hi, header = None, None, None
    for name, rows in sheets:
        hi, header = _find_header(rows)
        if hi is not None:
            raw = rows
            if name and name != sheets[0][0]:
                notes.append(f"数据取自工作表“{name}”")
            break
    if raw is None:
        first = sheets[0][1][0] if sheets and sheets[0][1] else []
        raise ValueError(f"找不到含必填列（{'、'.join(REQUIRED)}）的表头；首行是：{first[:8]}。"
                         "请把表头改成模板列名，或用 template 命令生成模板。")
    orig = [str(x).strip() for x in raw[hi]]
    renamed = [f"{o}→{h}" for o, h in zip(orig, header) if o and o != h]
    if renamed:
        notes.append("表头按同义词识别：" + "、".join(renamed))
    if hi > 0:
        notes.append(f"跳过表头前的 {hi} 行（标题等）")
    out = []
    for i, r in enumerate(raw[hi + 1:], start=hi + 2):
        r = [_clean(x) for x in r]
        if not any(r):
            continue
        rec = {h: (r[j] if j < len(r) else "") for j, h in enumerate(header)}
        rec["_row"] = i
        if any(x.replace(" ", "") in TOTAL_WORDS for x in r) and not rec.get("身份证件号码"):
            notes.append(f"第{i}行是合计行，已忽略")
            continue
        if sum(1 for x in r if x and _norm_header(x) in INPUT_COLUMNS) >= 3:
            notes.append(f"第{i}行是重复/第二行表头，已忽略")
            continue
        if not rec.get("身份证件号码") and not rec.get("付款日期") and not rec.get("金额"):
            notes.append(f"第{i}行没有证件号、日期和金额（像说明行，如“{'、'.join(x for x in r if x)[:20]}”），已忽略")
            continue
        out.append(rec)
    return out


def parse_date(s):
    s = str(s).strip()
    if not s:
        return None
    if re.fullmatch(r"\d+(\.0+)?", s) and 20000 < float(s) < 80000:  # Excel 序列号
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(float(s)))
    for pat in (r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?(\s.*)?", r"(\d{4})(\d{2})(\d{2})"):
        m = re.fullmatch(pat, s)
        if m:
            try:
                return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                return None
    return None


def parse_amount(s):
    s = re.sub(r"(?i)^(rmb|cny|人民币)", "", re.sub(r"\s+", "", str(s)))
    s = s.replace(",", "").replace("，", "").replace("¥", "").replace("￥", "").replace("元", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


def id_checksum_ok(idno):
    if not re.fullmatch(r"\d{17}[\dXx]", idno):
        return False
    w = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    codes = "10X98765432"
    s = sum(int(idno[i]) * w[i] for i in range(17))
    return codes[s % 11] == idno[17].upper()


def mask(idno):
    idno = str(idno)
    return idno[:3] + "*" * max(len(idno) - 7, 0) + idno[-4:] if len(idno) > 7 else "****"


def yes(v):
    return str(v).strip() in ("是", "Y", "y", "yes", "Yes", "YES", "1", "true", "True", "已代开", "已开", "已开票", "已缴", "已交")


def paid_flag(v):
    v = str(v).strip()
    if v in ("是", "已缴", "已交", "已缴税", "Y", "y", "yes", "Yes"):
        return "是"
    if v in ("否", "未缴", "未交", "N", "n", "no", "No"):
        return "否"
    return v


# ---------------------------------------------------------------- core

class Result:
    def __init__(self):
        self.main = []        # 申报表行
        self.attach = []      # 附列资料行
        self.issues = []      # dict(row, level, reason, who)
        self.excluded = []    # dict(row, who, amount, reason)
        self.summary = {}

    def issue(self, rows, level, reason, who=""):
        self.issues.append({"行号": ",".join(str(r) for r in rows), "级别": level, "对象": who, "说明": reason})


def compute(records, period, amount_basis, default_relief, city_rate_key,
            half_relief=True, category_map=None, policy=None):
    policy = policy or load_policy()
    if amount_basis not in ("含税", "不含税"):
        raise ValueError("--amount-basis 必须是 含税 或 不含税")
    reliefs = policy["reliefs"]
    if default_relief not in reliefs:
        raise ValueError(f"--default-relief 必须是 {'/'.join(reliefs)}")
    sur = policy["surcharges"]
    if city_rate_key not in sur["city_rates"]:
        raise ValueError(f"--city-rate 必须是 {'/'.join(sur['city_rates'])}")
    city_rate = Decimal(sur["city_rates"][city_rate_key])
    edu_rate = Decimal(sur["education_rate"])
    local_rate = Decimal(sur["local_education_rate"])
    threshold = Decimal(policy["threshold_per_day"])
    statutory = Decimal(policy["statutory_rate"])
    effective = dt.date.fromisoformat(policy["effective_from"])
    categories = set(policy["categories"])
    category_map = category_map or {}
    py, pm = (int(x) for x in period.split("-"))

    res = Result()
    input_total = Decimal(0)
    good = []
    for rec in records:
        row = rec["_row"]
        name = rec.get("姓名", "")
        if re.fullmatch(r"[\u4e00-\u9fff\s·]+", name or ""):
            name = re.sub(r"\s+", "", name)
        idno = rec.get("身份证件号码", "").replace(" ", "")
        who = f"{name}({mask(idno)})" if name else f"行{row}"
        amt = parse_amount(rec.get("金额", ""))
        if amt is not None:
            input_total += amt
        date = parse_date(rec.get("付款日期", ""))
        seller = (rec.get("销售方类型") or "").strip()
        if seller not in NATURAL_SELLERS and seller not in NON_NATURAL_SELLERS:
            res.issue([row], "异常", f"销售方类型“{seller}”无法识别（应为自然人/个体工商户/公司等）", who)
            continue
        if seller in NON_NATURAL_SELLERS:
            res.excluded.append({"行号": row, "对象": who, "金额": rec.get("金额", ""),
                                 "理由": f"销售方为{seller}，不属于代扣范围（即问即答第10问）"})
            continue
        if yes(rec.get("平台代办", "")):
            res.excluded.append({"行号": row, "对象": who, "金额": rec.get("金额", ""),
                                 "理由": "互联网平台已代办申报（28号公告第十四条）"})
            continue
        problems = []
        if not name:
            problems.append("缺姓名")
        if not idno:
            problems.append("缺身份证件号码")
        idtype = rec.get("身份证件类型") or "居民身份证"
        if idno and idtype == "居民身份证" and not id_checksum_ok(idno):
            problems.append("居民身份证号码校验位不对，请核对")
        if date is None:
            problems.append("付款日期无法识别")
        if amt is None:
            problems.append("金额无法识别")
        elif amt <= 0:
            problems.append("金额≤0：退款/折让须更正原所属期申报（28号公告第七条），本工具不处理")
        if problems:
            res.issue([row], "异常", "；".join(problems), who)
            continue
        if date < effective:
            res.excluded.append({"行号": row, "对象": who, "金额": fmt(amt),
                                 "理由": "2026-11-01 前的交易由自然人自行申报（28号公告第十五条）"})
            continue
        if (date.year, date.month) != (py, pm):
            res.issue([row], "异常", f"付款日期 {date} 不在所属期 {period}，请按月分开处理", who)
            continue
        cat = rec.get("服务大类", "") or category_map.get(rec.get("摘要", ""), "")
        if cat in CATEGORY_ALIASES:
            res.issue([row], "提示", f"服务大类“{cat}”按“{CATEGORY_ALIASES[cat]}”处理", who)
            cat = CATEGORY_ALIASES[cat]
        if cat in ("不适用", "非七类"):
            res.excluded.append({"行号": row, "对象": who, "金额": fmt(amt),
                                 "理由": "不属于七类服务（经人工确认）"})
            continue
        if cat not in categories:
            res.issue([row], "异常", f"服务类别待确认（摘要：{rec.get('摘要', '') or '空'}；填写值：{cat or '空'}）", who)
            continue
        relief = rec.get("优惠") or default_relief
        if relief not in reliefs:
            res.issue([row], "异常", f"优惠“{relief}”未内置，请人工处理", who)
            continue
        rinfo = reliefs[relief]
        if rinfo.get("valid_until") and date > dt.date.fromisoformat(rinfo["valid_until"]):
            res.issue([row], "异常", f"{relief}政策按快照于{rinfo['valid_until']}到期，请核对最新政策", who)
            continue
        good.append({
            "row": row, "name": name, "idtype": idtype, "id": idno, "who": who, "date": date,
            "amount": amt, "item": rec.get("应税交易项目") or cat, "cat": cat,
            "invoiced": yes(rec.get("是否已代开发票", "")),
            "invoice_paid": paid_flag(rec.get("代开时已缴税", "")),
            "relief": relief, "rate": Decimal(rinfo["applied_rate"]), "note": rec.get("备注", ""),
            "summary": rec.get("摘要", ""),
        })

    # 疑似重复录入：证件号、日期、金额、摘要完全相同
    seen = defaultdict(list)
    for g in good:
        seen[(g["id"], g["date"], g["amount"], g["summary"])].append(g["row"])
    for k, rows in seen.items():
        if len(rows) > 1:
            res.issue(rows, "提示", f"这{len(rows)}行证件号、日期、金额、摘要完全相同，疑似重复录入；"
                      "本工具已按多笔分别付款合计，若是重复请删掉多余行后重跑",
                      next(g["who"] for g in good if g["row"] == rows[0]))

    # 同一证件号多个姓名 / 同一姓名多个证件号
    by_id = defaultdict(set)
    by_name = defaultdict(set)
    for g in good:
        by_id[g["id"]].add(g["name"])
        by_name[g["name"]].add(g["id"])
    bad_ids = {i for i, ns in by_id.items() if len(ns) > 1}
    for name, ids in by_name.items():
        if len(ids) > 1:
            res.issue([g["row"] for g in good if g["name"] == name], "提示",
                      f"同名不同证件号（{len(ids)}个），请确认是否为不同的人", name)
    if bad_ids:
        for i in bad_ids:
            rows = [g["row"] for g in good if g["id"] == i]
            res.issue(rows, "异常", "同一证件号对应多个姓名（28号公告第九条：不得擅自更改，须与本人核实）", mask(i))
        good = [g for g in good if g["id"] not in bad_ids]

    # 按 人+日 判断起征点（含已代开部分，即问即答第27、43问）
    day_groups = OrderedDict()
    for g in sorted(good, key=lambda x: (x["date"], x["id"], x["row"])):
        day_groups.setdefault((g["id"], g["date"]), []).append(g)

    day_taxed = {}
    for key, gs in day_groups.items():
        if amount_basis == "不含税":
            net = sum(g["amount"] for g in gs)
        else:
            net = sum(g["amount"] / (1 + g["rate"]) for g in gs)
        taxed = money(net) >= threshold
        day_taxed[key] = taxed
        for g in gs:
            if amount_basis == "含税" and taxed:
                g["sales"] = money(g["amount"] / (1 + g["rate"]))
            else:
                g["sales"] = money(g["amount"])

    # 拆单提示：同一人本月 ≥2 天的当日合计落在 [900,1000)
    near = defaultdict(list)
    for (pid, d), gs in day_groups.items():
        tot = sum(g["sales"] for g in gs)
        if Decimal("900") <= tot < threshold:
            near[pid].append(d)
    for pid, ds in near.items():
        if len(ds) >= 2:
            rows = [g["row"] for (p, _), gs in day_groups.items() if p == pid for g in gs]
            res.issue(rows, "提示", f"本月有{len(ds)}天当日合计在900–1000元之间，请确认不存在人为拆分（仅提示，不作结论）",
                      day_groups[(pid, ds[0])][0]["who"])

    # 输出行：人+日+项目+是否代开+优惠 合并（填报说明第5、6列；即问即答第40、41问）
    lines = OrderedDict()
    for key, gs in day_groups.items():
        for g in gs:
            lk = (g["id"], g["date"], g["item"], g["invoiced"], g["relief"])
            if lk not in lines:
                lines[lk] = dict(g, rows=[g["row"]], sales=Decimal(0), taxed=day_taxed[key],
                                 invoice_unpaid=False, notes=[])
            ln = lines[lk]
            if g["row"] not in ln["rows"]:
                ln["rows"].append(g["row"])
            ln["sales"] += g["sales"]
            if g["invoiced"] and g["invoice_paid"] not in ("是", "否"):
                res.issue([g["row"]], "异常", "已代开发票的行须填写“代开时已缴税”（是/否）", g["who"])
            if g["invoiced"] and g["invoice_paid"] == "否":
                ln["invoice_unpaid"] = True
            if g["note"]:
                ln["notes"].append(g["note"])

    seq = 0
    vat_total = Decimal(0)
    sur_total = Decimal(0)
    sales_total = Decimal(0)
    makeup = []
    for lk, ln in lines.items():
        seq += 1
        sales = money(ln["sales"])
        sales_total += sales
        datestr = ln["date"].isoformat()
        base = [str(seq), ln["name"], ln["idtype"], ln["id"], datestr, ln["item"],
                "是" if ln["invoiced"] else "否", fmt(sales)]
        note = "；".join(ln["notes"])
        if ln["invoiced"]:
            main = base + [DASH] * 5 + [note]
            attach = [str(seq), ln["name"], ln["id"], datestr, ln["item"]] + [DASH] * 14
            if ln["taxed"] and ln["invoice_unpaid"]:
                owe = money(sales * ln["rate"])
                makeup.append(owe)
                res.issue(ln["rows"], "提示",
                          f"已代开的 {fmt(sales)} 元当时按未达起征点免税，但当日合计已达起征点，"
                          f"申报时系统会提示补扣增值税约 {fmt(owe)} 元及附加（即问即答第43问）", ln["who"])
            res.main.append(main)
            res.attach.append(attach)
            continue
        if not ln["taxed"]:
            vat = Decimal(0)
            main = base + ["未达起征点", "", "0.00", "0.00", "0.00",
                           (note + "；" if note else "") + "当日合计未达1000元按次起征点"]
            res.issue(ln["rows"], "提示", "未达起征点行第9–11列填法填报说明未举例，申报前请在系统中核对", ln["who"])
        else:
            rinfo = reliefs[ln["relief"]]
            rate = ln["rate"]
            vat = money(sales * rate)
            if ln["relief"] == "无优惠":
                main = base + [pct(rate), DASH, DASH, fmt(vat)]
            elif rate == 0:
                main = base + ["免税", f"{rinfo['label']}|{rinfo['code']}", fmt(sales * statutory), "0.00"]
            else:
                main = base + [pct(rate), f"{rinfo['label']}|{rinfo['code']}",
                               fmt(sales * (statutory - rate)), fmt(vat)]
            main = main + [None, note]
        # 附加税费（填报说明附列资料第7–19列；即问即答第28问）
        def part(r):
            full = money(vat * r)
            due = money(vat * r * Decimal("0.5")) if half_relief else full
            return full - due, due
        c_rel, c_due = part(city_rate)
        e_rel, e_due = part(edu_rate)
        l_rel, l_due = part(local_rate)
        sur_sum = c_due + e_due + l_due
        code = "（按减免税政策代码目录填写）" if half_relief and vat > 0 else ""
        attach = [str(seq), ln["name"], ln["id"], datestr, ln["item"], fmt(vat),
                  pct(city_rate), code, fmt(c_rel), fmt(c_due),
                  pct(edu_rate), code, fmt(e_rel), fmt(e_due),
                  pct(local_rate), code, fmt(l_rel), fmt(l_due), fmt(sur_sum)]
        if ln["taxed"]:
            main[12] = fmt(sur_sum)
        vat_total += vat
        sur_total += sur_sum
        res.main.append(main)
        res.attach.append(attach)

    # ------------------------------------------------ 闸门（gates）
    gates = OrderedDict()
    placed = {str(g["row"]) for g in good} | {str(e["行号"]) for e in res.excluded} | {
        r for i in res.issues if i["级别"] == "异常" for r in i["行号"].split(",")}
    gates["每一行都有去处（申报/不适用/异常）"] = {str(x["_row"]) for x in records} <= placed
    main_vat = sum(Decimal(m[11]) for m in res.main if m[11] not in (DASH, ""))
    att_vat = sum(Decimal(a[5]) for a in res.attach if a[5] != DASH)
    gates["申报表第12列合计 = 附列资料第6列合计"] = main_vat == att_vat == vat_total
    gates["申报表第13列 = 附列资料第19列（逐行）"] = all(
        m[12] == a[18] for m, a in zip(res.main, res.attach))
    recompute_ok = True
    for m in res.main:
        if m[8] not in (DASH, "免税", "未达起征点"):
            if money(Decimal(m[7]) * Decimal(m[8]) / 100) != Decimal(m[11]):
                recompute_ok = False
    gates["逐行复算：销售额×征收率 = 应扣缴增值税"] = recompute_ok
    gates["申报表销售额合计 = 已纳入行销售额之和"] = money(sum(Decimal(m[7]) for m in res.main)) == money(sales_total)

    n_err = sum(1 for i in res.issues if i["级别"] == "异常")
    status = "可复核" if n_err == 0 and all(gates.values()) else "草稿-有异常，不可直接申报"
    res.summary = OrderedDict([
        ("状态", status),
        ("所属期", period),
        ("金额口径", amount_basis),
        ("默认优惠", default_relief),
        ("城建税地点", city_rate_key),
        ("附加税费减半", half_relief),
        ("输入行数", len(records)),
        ("输入金额合计", fmt(input_total)),
        ("纳入申报的付款行数", len(good)),
        ("申报表行数", len(res.main)),
        ("不适用行数", len(res.excluded)),
        ("异常数", n_err),
        ("提示数", sum(1 for i in res.issues if i["级别"] == "提示")),
        ("销售额合计", fmt(sales_total)),
        ("应扣缴增值税合计", fmt(vat_total)),
        ("应扣缴附加税费合计", fmt(sur_total)),
        ("可能需补扣增值税（已代开部分）", fmt(sum(makeup, Decimal(0)))),
        ("申报期限", _deadline(period)),
        ("闸门", gates),
        ("政策快照", policy["snapshot_date"]),
        ("未核实事项", policy["unverified"]),
        ("声明", "仅辅助整理与计算，不构成税务意见；申报前请在自然人电子税务局（扣缴端）核对。"),
    ])
    return res


def _deadline(period):
    y, m = (int(x) for x in period.split("-"))
    y2, m2 = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y2}-{m2:02d}-01 至 {y2}-{m2:02d}-15（遇节假日顺延，以税务机关公布为准）"


# ---------------------------------------------------------------- output

def write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def save(res, out):
    os.makedirs(out, exist_ok=True)
    prefix = "" if res.summary["状态"] == "可复核" else "草稿_有异常_"
    write_csv(os.path.join(out, prefix + "申报表.csv"), MAIN_HEADER, res.main)
    write_csv(os.path.join(out, prefix + "附列资料.csv"), ATTACH_HEADER, res.attach)
    write_csv(os.path.join(out, "异常与提示.csv"), ["行号", "级别", "对象", "说明"],
              [[i["行号"], i["级别"], i["对象"], i["说明"]] for i in res.issues])
    write_csv(os.path.join(out, "不适用清单.csv"), ["行号", "对象", "金额", "理由"],
              [[e["行号"], e["对象"], e["金额"], e["理由"]] for e in res.excluded])
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(res.summary, f, ensure_ascii=False, indent=2)


def load_category_map(path):
    m = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("摘要") and r.get("服务大类"):
                m[r["摘要"].strip()] = r["服务大类"].strip()
    return m


def main(argv=None):
    p = argparse.ArgumentParser(description="代扣代缴自然人增值税计算器（本地运行，不联网）")
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("template", help="生成输入模板")
    t.add_argument("--out", required=True)
    s = sub.add_parser("summaries", help="列出去重后的摘要（不含姓名、证件号），供判断服务类别")
    s.add_argument("--input", required=True)
    r = sub.add_parser("run", help="计算并生成申报表草稿")
    r.add_argument("--input", required=True)
    r.add_argument("--period", required=True, help="所属期 YYYY-MM（按付款日期）")
    r.add_argument("--amount-basis", required=True, choices=["含税", "不含税"])
    r.add_argument("--default-relief", required=True, help="减按1%% / 无优惠 / 残疾人免税")
    r.add_argument("--city-rate", required=True, help="扣缴地点：市区 / 县城镇 / 其他")
    r.add_argument("--no-half-relief", action="store_true", help="附加税费不减半")
    r.add_argument("--category-map", help="摘要→服务大类 的确认表 CSV（列：摘要,服务大类）")
    r.add_argument("--out", required=True)
    q = sub.add_parser("quick", help="估算一个人某一天的税额（不需要证件号，不出申报表）")
    q.add_argument("--amounts", nargs="+", required=True, help="当天本单位付给此人的各笔金额")
    q.add_argument("--date", default="2026-12-01", help="付款日期 YYYY-MM-DD")
    q.add_argument("--amount-basis", required=True, choices=["含税", "不含税"])
    q.add_argument("--relief", default="减按1%")
    q.add_argument("--city-rate", default="市区")
    q.add_argument("--no-half-relief", action="store_true")
    a = p.parse_args(argv)

    if a.cmd == "template":
        write_csv(a.out, INPUT_COLUMNS, [[
            "张三", "居民身份证", "11010519491231002X", "2026-11-05", "2000.00", "11月讲座费",
            "非学历教育服务", "教育服务", "否", "", "", "自然人", "否", ""]])
        print(f"模板已生成：{a.out}")
        return 0
    if a.cmd == "summaries":
        notes = []
        recs = read_rows(a.input, notes)
        need, done = OrderedDict(), OrderedDict()
        for x in recs:
            k = x.get("摘要", "")
            c = x.get("服务大类", "")
            if c:
                done[(k, c)] = done.get((k, c), 0) + 1
            else:
                need[k] = need.get(k, 0) + 1
        print(json.dumps({
            "说明": "“表里已填类别”是用户在流水里自己填的，视为已确认，不用再问；只需确认“待确认类别”。",
            "待确认类别": [{"摘要": k, "笔数": v} for k, v in need.items()],
            "表里已填类别": [{"摘要": k, "服务大类": c, "笔数": v} for (k, c), v in done.items()],
            "读取说明": notes,
        }, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "quick":
        recs = [{"_row": i + 2, "姓名": "（估算）", "身份证件类型": "估算", "身份证件号码": "ESTIMATE-1",
                 "付款日期": a.date, "金额": x, "摘要": "估算", "服务大类": "咨询服务", "优惠": a.relief}
                for i, x in enumerate(a.amounts)]
        res = compute(recs, a.date[:7], a.amount_basis, a.relief, a.city_rate,
                      half_relief=not a.no_half_relief)
        print(json.dumps(OrderedDict([
            ("用途", "估算：同一个人、同一天、本单位付款，不生成申报表"),
            ("当日金额", a.amounts), ("金额口径", a.amount_basis), ("优惠", a.relief), ("城建税地点", a.city_rate),
            ("当日合计达起征点", any(m[8] not in ("未达起征点",) for m in res.main)),
            ("销售额", res.summary["销售额合计"]),
            ("应扣缴增值税", res.summary["应扣缴增值税合计"]),
            ("应扣缴附加税费", res.summary["应扣缴附加税费合计"]),
            ("声明", res.summary["声明"]),
        ]), ensure_ascii=False, indent=2))
        return 0
    notes = []
    recs = read_rows(a.input, notes)
    cmap = load_category_map(a.category_map) if a.category_map else None
    res = compute(recs, a.period, a.amount_basis, a.default_relief, a.city_rate,
                  half_relief=not a.no_half_relief, category_map=cmap)
    res.summary["读取说明"] = notes
    save(res, a.out)
    print(json.dumps(res.summary, ensure_ascii=False, indent=2))
    print("\n【回复最后一行必须原样写上】" + res.summary.get("声明", "仅辅助整理与计算，不构成税务意见；申报前请在自然人电子税务局（扣缴端）核对。"))
    return 0 if res.summary["状态"] == "可复核" else 2


if __name__ == "__main__":
    sys.exit(main())
