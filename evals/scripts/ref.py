"""独立参考实现：只按规则本身算期望值，不调用 calc.py。"""
from decimal import Decimal as D, ROUND_HALF_UP
import datetime as dt
from collections import OrderedDict

RATE = {"减按1%": D("0.01"), "无优惠": D("0.03"), "残疾人免税": D("0")}
CITY = {"市区": D("0.07"), "县城镇": D("0.05"), "其他": D("0.01")}
q = lambda x: x.quantize(D("0.01"), rounding=ROUND_HALF_UP)


def expect(rows, basis, default_relief, city, half=True):
    """rows: dicts with 证件, 日期(date), 金额(str), 项目, 代开(bool), 已缴(str), 优惠, 销售方, 平台"""
    good, excluded = [], 0
    for r in rows:
        if r.get("销售方", "自然人") != "自然人" or r.get("平台") == "是" or r["日期"] < dt.date(2026, 11, 1) or r.get("类别") == "不适用":
            excluded += 1
            continue
        good.append(dict(r, rel=r.get("优惠") or default_relief))
    days = OrderedDict()
    for g in good:
        days.setdefault((g["证件"], g["日期"]), []).append(g)
    lines = OrderedDict()
    for k, gs in days.items():
        net = sum((D(g["金额"]) if basis == "不含税" else D(g["金额"]) / (1 + RATE[g["rel"]])) for g in gs)
        taxed = q(net) >= D(1000)
        for g in gs:
            s = q(D(g["金额"]) / (1 + RATE[g["rel"]])) if (basis == "含税" and taxed) else q(D(g["金额"]))
            lk = (g["证件"], g["日期"], g["项目"], g.get("代开", False), g["rel"])
            ln = lines.setdefault(lk, {"s": D(0), "taxed": taxed, "inv": g.get("代开", False), "rate": RATE[g["rel"]]})
            ln["s"] += s
    vat = sur = D(0)
    f = D("0.5") if half else D(1)
    for ln in lines.values():
        if ln["inv"] or not ln["taxed"]:
            continue
        v = q(ln["s"] * ln["rate"])
        vat += v
        sur += sum(q(v * r * f) for r in (CITY[city], D("0.03"), D("0.02")))
    return {"vat": f"{vat:.2f}", "sur": f"{sur:.2f}", "nrows": len(lines), "excluded": excluded}
