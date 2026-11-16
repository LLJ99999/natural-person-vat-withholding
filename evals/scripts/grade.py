import glob, json, os, sys
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # evals/
rnd = sys.argv[1]
res = {}
for cdir in sorted(glob.glob(f"{BASE}/{os.environ.get('CASES','题库/Q_政策问答')}/*")):
    cid = os.path.basename(cdir)
    exp = json.load(open(f"{cdir}/case.json"))["expect"]
    d = f"{BASE}/rounds/{rnd}/{cid}"
    if not os.path.isdir(d):
        continue
    final = (open(f"{d}/final.txt").read() if os.path.exists(f"{d}/final.txt") else "").replace(",", "")
    sums = [p for p in glob.glob(f"{d}/**/summary.json", recursive=True) if "/skill/" not in p]
    s = json.load(open(sorted(sums, key=os.path.getmtime)[-1])) if sums else None
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
            if bad in final:
                fails.append(f"草稿却说“{bad}”")
    for g in exp.get("text_any", []):
        if not any(k in final for k in g):
            fails.append(f"回答缺少关键点（{'/'.join(g)}）")
    for k in exp.get("text_none", []):
        if k in final:
            fails.append(f"出现了不该出现的内容：{k[:12]}")
    if "仅辅助整理" not in final and computable and s:
        fails.append("缺免责声明")
    res[cid] = fails
n = len(res); ok = sum(1 for v in res.values() if not v)
print(f"{rnd}: {ok}/{n} 通过")
for k, v in res.items():
    if v:
        print(k, "；".join(v))
json.dump(res, open(f"{BASE}/rounds/{rnd}/grade.json", "w"), ensure_ascii=False, indent=1)
