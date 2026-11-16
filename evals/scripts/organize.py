"""把 build_cases*.py 生成的题目按类型整理到 ../题库/，并生成 ../题库总表.xlsx。

用法：
    python3 build_cases.py && python3 build_cases2.py && python3 build_cases3.py && python3 build_cases4.py
    python3 organize.py
"""
import glob, json, os, shutil
import openpyxl
from openpyxl.styles import Alignment, Font

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "题库")

TYPES = [  # 前缀, 目录名, 说明
    ("Q", "政策问答", "无附件。服务分类、适用范围、起征点、申报期限、附加税率、代开发票、平台代办等政策与操作问题，按回答里的关键词评分。"),
    ("K", "口算", "无附件。给出单人单日的金额和口径，算增值税或附加税费，按数值评分。"),
    ("G", "官方算例", "带附件。由税务总局《即问即答》算例改编的场景计算：合并、起征点、已代开、放弃优惠、残疾人免税、平台代办、跨月等。"),
    ("M", "月度流水", "带附件。随机生成的月度付款流水（1–100 行，2026年11月至2027年12月），按合计、行数、状态评分。"),
    ("F", "不规范格式", "带附件。别名表头、英文表头、GBK、UTF-16、分号、合计行、标题行、Excel 序列日期、撇号证件号、RMB 金额等 30 种写法。"),
    ("X", "异常边界", "带附件。外国护照、15位身份证、校验位错误、跨月、负数退款、缺字段、金额模糊、重复行、同号不同名、非自然人、未内置优惠等。"),
    ("B", "行为", "缺口径须追问、表内与提示词注入、要求心算/删声明/代提交/登录、拆分逃税、索要证件号、施压写可申报、繁体/英文/错别字、口头补数等。"),
]
NAME = {p: n for p, n, _ in TYPES}


def has_attach(d):
    return any(f.startswith("流水") for f in os.listdir(d))


def classify(batch, cid, d, exp):
    a = has_attach(d)
    if batch == "cases":
        g = cid[0]
        if g == "C":
            return "G"
        if g == "E":
            return "X"
        return "B" if (a or exp.get("ask")) else "Q"
    if batch == "cases2":
        n = int(cid[1:])
        if n <= 25:
            return "G" if a else "Q"
        return "M" if n <= 55 else "F" if n <= 70 else "X" if n <= 85 else "B"
    if batch == "cases3":
        n = int(cid[1:])
        if n <= 60:
            return "Q"
        if n <= 100:
            return "G"
        if n <= 170:
            return "M"
        if n <= 230:
            return "F"
        return "X" if n <= 260 else "B"
    return cid[0]  # cases4 的题号前缀就是类型


items = []
for batch in ("cases", "cases2", "cases3", "cases4"):
    for cj in sorted(glob.glob(os.path.join(HERE, batch, "**", "case.json"), recursive=True)):
        d = os.path.dirname(cj)
        c = json.load(open(cj))
        t = classify(batch, os.path.basename(d), d, c["expect"])
        items.append((t, d, c))

shutil.rmtree(OUT, ignore_errors=True)
count = {p: 0 for p, _, _ in TYPES}
rows = {p: [] for p, _, _ in TYPES}
for t, d, c in items:
    count[t] += 1
    nid = f"{t}{count[t]:04d}"
    dst = os.path.join(OUT, f"{t}_{NAME[t]}", nid)
    os.makedirs(dst)
    for f in os.listdir(d):
        if f != "case.json":
            shutil.copy(os.path.join(d, f), dst)
    out = {"id": nid, "type": NAME[t], "sub": c.get("sub", ""), "prompt": c["prompt"], "expect": c["expect"]}
    json.dump(out, open(os.path.join(dst, "case.json"), "w"), ensure_ascii=False, indent=1)
    att = [f for f in os.listdir(dst) if f != "case.json"]
    rows[t].append([nid, out["sub"], c["prompt"], att[0] if att else "无"] + [c["expect"]])


def readable(e):
    p = []
    if e.get("ask"):
        p.append("应先追问，不直接出表")
    if "status" in e:
        p.append(f"状态={e['status']}")
    for k, n in (("vat", "增值税合计"), ("sur", "附加税费合计"), ("nrows", "申报表行数"), ("excluded", "不适用行数")):
        if k in e:
            p.append(f"{n}={e[k]}")
    for g in e.get("text_any", []):
        p.append("回答须含其一：" + " / ".join(g))
    if e.get("text_none"):
        p.append("不得出现：" + " / ".join(x if len(x) < 20 else x[:6] + "…" for x in e["text_none"][:8]))
    return "；".join(p)


wb = openpyxl.Workbook()
ws = wb.active
ws.title = "总览"
ws.append(["类型", "题号范围", "题数", "说明"])
for p, n, desc in TYPES:
    ws.append([n, f"{p}0001–{p}{count[p]:04d}", count[p], desc])
ws.append(["合计", "", sum(count.values()), ""])
for col, w in zip("ABCD", [12, 16, 8, 100]):
    ws.column_dimensions[col].width = w
for p, n, _ in TYPES:
    s = wb.create_sheet(n)
    s.append(["题号", "子类", "用户消息", "附件", "标准答案/评分要点"])
    for r in rows[p]:
        s.append(r[:4] + [readable(r[4])])
    for col, w in zip("ABCDE", [8, 14, 70, 12, 70]):
        s.column_dimensions[col].width = w
    for row in s.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    s.freeze_panes = "A2"
for s in wb.worksheets:
    for cell in s[1]:
        cell.font = Font(bold=True)
wb.properties.creator = wb.properties.lastModifiedBy = "Microsoft Office User"
wb.save(os.path.join(os.path.dirname(HERE), "题库总表.xlsx"))
print("organized", sum(count.values()), count)
