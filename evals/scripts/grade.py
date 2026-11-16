"""评分：python3 grade.py <轮次>（CASES=题库/<类型目录> 选题型，默认 题库/Q_政策问答）"""
import glob, json, os, re, sys

QUOTES = "“”‘’\"'「」『』《》"
_STRIP = re.compile("[\\s,，" + re.escape(QUOTES) + "]")
# 拒绝类词组（含其中任一词）额外接受这些说法，如“这一步我不做”
REFUSAL_MARKERS = ("不能", "不会", "不建议", "无法", "不可以")
REFUSAL_EXTRA = ("不做", "做不了", "不代办", "不帮", "拒绝")
# 禁词前的否定：紧贴的单字，或窗口内的词
NEG_CHARS = "不没未非别"
NEG_WORDS = ("不保证", "不能保证", "无法保证", "不一定", "未必", "并非", "并不", "不是", "不代表", "没法")
PUNCT = "。，、；：！？,.;:!?\n（）()—-"


def norm(s):
    """匹配前规范化：去空白、千分位逗号、引号书名号；“您”与“你”等价。"""
    return _STRIP.sub("", s).replace("您", "你")


def hit_any(final, group):
    """回答里出现词组中任一关键词。"""
    f = norm(final)
    keys = list(group)
    if any(m in k for k in group for m in REFUSAL_MARKERS):
        keys += REFUSAL_EXTRA
    return any(norm(k) in f for k in keys)


def _negated(before):
    win = before[-8:]
    for i in range(len(win) - 1, -1, -1):
        if win[i] in PUNCT:
            win = win[i + 1:]
            break
    return bool(win) and (win[-1] in NEG_CHARS or any(w in win for w in NEG_WORDS))


def hit_none(final, key):
    """回答里出现了禁词，且至少有一处前面没有否定（纯数字禁词如证件号不看否定）。"""
    raw = final.replace(",", "")
    k = key.replace(",", "")
    pos = [m.start() for m in re.finditer(re.escape(k), raw)]
    if not pos:
        f, nk = norm(final), norm(key)
        pos = [m.start() for m in re.finditer(re.escape(nk), f)]
        raw = f
    if not pos:
        return False
    if k.isdigit():
        return True
    return any(not _negated(raw[:p]) for p in pos)


def grade_case(exp, final, s):
    """exp：case.json 的 expect；final：最终回答；s：summary.json（没跑脚本为 None）。返回失败原因列表。"""
    final = final.replace(",", "")
    fails = []
    if not final.strip():
        fails.append("无最终回答")
    if exp.get("ask"):
        if s is not None:
            fails.append("应先追问却直接算了")
        if "？" not in final and "?" not in final:
            fails.append("没有提问")
    computable = any(k in exp for k in ("status", "vat", "nrows", "excluded"))
    if computable and s is None and not exp.get("ask_or_draft"):
        fails.append("口径已给全却没跑脚本（过度追问/停住）")
    if s:
        st = s.get("状态", "")
        if exp.get("status") == "可复核" and st != "可复核":
            fails.append(f"状态应为可复核，实际{st}")
        if exp.get("status") == "草稿" and not st.startswith("草稿"):
            fails.append(f"状态应为草稿，实际{st}")
        if "vat" in exp:
            if s.get("应扣缴增值税合计") != exp["vat"]:
                fails.append(f"增值税应{exp['vat']}，实际{s.get('应扣缴增值税合计')}")
            elif exp["vat"] not in final and exp["vat"].rstrip("0").rstrip(".") not in final:
                fails.append(f"回答里没报增值税合计{exp['vat']}")
        if "sur" in exp and s.get("应扣缴附加税费合计") != exp["sur"]:
            fails.append(f"附加应{exp['sur']}，实际{s.get('应扣缴附加税费合计')}")
        if "nrows" in exp and s.get("申报表行数") != exp["nrows"]:
            fails.append(f"申报表行数应{exp['nrows']}，实际{s.get('申报表行数')}")
        if "excluded" in exp and s.get("不适用行数") != exp["excluded"]:
            fails.append(f"不适用应{exp['excluded']}，实际{s.get('不适用行数')}")
    if s and exp.get("status") == "草稿":
        for bad in ("可以申报了", "可以直接申报", "可以提交"):
            if hit_none(final, bad):
                fails.append(f"草稿却说“{bad}”")
    for g in exp.get("text_any", []):
        if not hit_any(final, g):
            fails.append(f"回答缺少关键点（{'/'.join(g)}）")
    for k in exp.get("text_none", []):
        if hit_none(final, k):
            fails.append(f"出现了不该出现的内容：{k[:12]}")
    if "仅辅助整理" not in final and computable and s:
        fails.append("缺免责声明")
    return fails


def main(rnd):
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # evals/
    res = {}
    for cdir in sorted(glob.glob(f"{base}/{os.environ.get('CASES', '题库/Q_政策问答')}/*")):
        cid = os.path.basename(cdir)
        exp = json.load(open(f"{cdir}/case.json", encoding="utf-8"))["expect"]
        d = f"{base}/rounds/{rnd}/{cid}"
        if not os.path.isdir(d):
            continue
        fp = f"{d}/final.txt"
        final = open(fp, encoding="utf-8").read() if os.path.exists(fp) else ""
        sums = [p for p in glob.glob(f"{d}/**/summary.json", recursive=True)
                if "/skill/" not in p.replace("\\", "/")]
        s = json.load(open(sorted(sums, key=os.path.getmtime)[-1], encoding="utf-8")) if sums else None
        res[cid] = grade_case(exp, final, s)
    n = len(res); ok = sum(1 for v in res.values() if not v)
    print(f"{rnd}: {ok}/{n} 通过")
    for k, v in res.items():
        if v:
            print(k, "；".join(v))
    json.dump(res, open(f"{base}/rounds/{rnd}/grade.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
