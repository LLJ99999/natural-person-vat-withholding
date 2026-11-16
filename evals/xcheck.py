import json,glob,os,subprocess,sys,re,tempfile
skill=sys.argv[1]; cases=sys.argv[2]
CITY={"市区":"市区","县城":"县城镇","乡镇":"其他"}
for d in sorted(glob.glob(f"{cases}/*")):
    c=json.load(open(d+"/case.json")); e=c["expect"]; p=c["prompt"]
    if "vat" not in e or e.get("ask"): continue
    f=[x for x in os.listdir(d) if x.startswith("流水")]
    if not f: continue
    m=re.search(r"所属期(\d{4})年(\d+)月",p)
    per=f"{m.group(1)}-{int(m.group(2)):02d}" if m else "2026-11"
    basis="含税" if "金额都是含税" in p else "不含税"
    city="县城镇" if "县城" in p else ("其他" if "乡镇" in p else "市区")
    half="不享受减半" not in p and "不减半" not in p
    relief="无优惠" if "按3%" in p else "减按1%"
    out=tempfile.mkdtemp()
    cmd=["python3",f"{skill}/scripts/calc.py","run","--input",f"{d}/{f[0]}","--period",per,"--amount-basis",basis,"--default-relief",relief,"--city-rate",city,"--out",out]+([] if half else ["--no-half-relief"])
    r=subprocess.run(cmd,capture_output=True,text=True)
    try: s=json.load(open(out+"/summary.json"))
    except Exception: print(os.path.basename(d),"CRASH",r.stderr.strip()[-150:]); continue
    bad=[]
    if s["应扣缴增值税合计"]!=e["vat"]: bad.append(f"vat {s['应扣缴增值税合计']}!={e['vat']}")
    if "sur" in e and s["应扣缴附加税费合计"]!=e["sur"]: bad.append(f"sur {s['应扣缴附加税费合计']}!={e['sur']}")
    if "nrows" in e and s["申报表行数"]!=e["nrows"]: bad.append(f"rows {s['申报表行数']}!={e['nrows']}")
    if e.get("status")=="可复核" and s["状态"]!="可复核": bad.append(s["状态"])
    if bad: print(os.path.basename(d),"; ".join(bad))
