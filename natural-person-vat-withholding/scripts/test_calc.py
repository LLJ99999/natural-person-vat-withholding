"""测试用例主要取自国家税务总局《境内单位代扣代缴自然人增值税政策即问即答》（2026-11-13）。
全部为合成数据，证件号由校验算法生成，不对应真实个人。"""
import os
import sys
import tempfile
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calc  # noqa: E402


def fake_id(seed):
    body = f"110105199001{seed:05d}"[:17]
    w = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    return body + "10X98765432"[sum(int(body[i]) * w[i] for i in range(17)) % 11]


_row = [1]


def rec(name, seed, date, amount, cat="软件服务", item=None, **kw):
    _row[0] += 1
    r = {"_row": _row[0], "姓名": name, "身份证件号码": fake_id(seed), "付款日期": date,
         "金额": str(amount), "服务大类": cat}
    if item:
        r["应税交易项目"] = item
    r.update(kw)
    return r


def run(records, period, basis="不含税", relief="减按1%", city="市区", **kw):
    return calc.compute(records, period, basis, relief, city, **kw)


class OfficialCases(unittest.TestCase):
    def test_q20_basic_1pct(self):
        r = run([rec("徐某", 1, "2026-12-01", 10000)], "2026-12")
        m = r.main[0]
        self.assertEqual((m[8], m[10], m[11]), ("1", "200.00", "100.00"))
        self.assertEqual(r.summary["状态"], "可复核")

    def test_q24_under_threshold_still_declared(self):
        r = run([rec("王某", 2, "2026-11-19", 500, "设计服务", "文印晒图")], "2026-11")
        self.assertEqual(len(r.main), 1)
        self.assertEqual(r.main[0][11], "0.00")
        self.assertEqual(r.main[0][8], "未达起征点")

    def test_q26_days_judged_separately(self):
        r = run([rec("蔡某", 3, "2026-12-05", 800, "广播影视节目（作品）制作服务", "剪辑"),
                 rec("蔡某", 3, "2026-12-10", 1200, "广播影视节目（作品）制作服务", "剪辑")], "2026-12")
        self.assertEqual([m[11] for m in r.main], ["0.00", "12.00"])

    def test_q39_two_days_two_rows(self):
        r = run([rec("徐某", 4, "2027-08-08", 5800, item="软件维护服务"),
                 rec("徐某", 4, "2027-08-15", 7200, item="软件维护服务")], "2027-08")
        self.assertEqual([(m[10], m[11]) for m in r.main], [("116.00", "58.00"), ("144.00", "72.00")])
        self.assertIn("01011608", r.main[0][9])

    def test_q40_same_day_same_item_merged(self):
        r = run([rec("顾某", 5, "2027-08-18", 1500, item="软件测试服务"),
                 rec("顾某", 5, "2027-08-18", 1800, item="软件测试服务")], "2027-08")
        self.assertEqual(len(r.main), 1)
        self.assertEqual((r.main[0][7], r.main[0][10], r.main[0][11]), ("3300.00", "66.00", "33.00"))

    def test_q41_same_day_two_items_two_rows(self):
        r = run([rec("郭某", 6, "2027-08-22", 28000, "咨询服务", "法律咨询"),
                 rec("郭某", 6, "2027-08-22", 5000, "教育服务", "非学历教育服务")], "2027-08")
        self.assertEqual([(m[10], m[11]) for m in r.main], [("560.00", "280.00"), ("100.00", "50.00")])

    def test_q42_invoiced_dashes(self):
        r = run([rec("景某", 7, "2027-09-01", 5000, "设计服务", "工程设计服务",
                     是否已代开发票="是", 代开时已缴税="是")], "2027-09")
        self.assertEqual(r.main[0][8:13], ["——"] * 5)
        self.assertEqual(r.attach[0][5:], ["——"] * 14)

    def test_q27_q43_invoiced_exempt_part_needs_makeup(self):
        r = run([rec("郑某", 8, "2027-09-02", 500, item="软件测试服务", 是否已代开发票="是", 代开时已缴税="否"),
                 rec("郑某", 8, "2027-09-02", 800, item="软件测试服务")], "2027-09")
        unpaid = [m for m in r.main if m[6] == "否"][0]
        self.assertEqual((unpaid[10], unpaid[11]), ("16.00", "8.00"))
        self.assertEqual(r.summary["可能需补扣增值税（已代开部分）"], "5.00")

    def test_q44_waive_relief_3pct(self):
        r = run([rec("黄某", 9, "2027-08-05", 1200, "咨询服务", "一般税务咨询", 优惠="无优惠")], "2027-08")
        m = r.main[0]
        self.assertEqual((m[8], m[9], m[10], m[11]), ("3", "——", "——", "36.00"))

    def test_q45_disabled_exempt(self):
        r = run([rec("赵某", 10, "2027-08-11", 2000, "设计服务", "专业设计服务", 优惠="残疾人免税")], "2027-08")
        m = r.main[0]
        self.assertEqual((m[8], m[10], m[11], m[12]), ("免税", "60.00", "0.00", "0.00"))

    def test_q28_surcharges_halved(self):
        r = run([rec("吕某", 11, "2026-11-05", 120000, "设计服务")], "2026-11")
        a = r.attach[0]
        self.assertEqual((a[5], a[9], a[13], a[17], a[18]), ("1200.00", "42.00", "18.00", "12.00", "72.00"))
        self.assertEqual(r.main[0][12], "72.00")

    def test_tax_inclusive_2000(self):
        r = run([rec("李某", 12, "2026-11-05", 2000, "文化服务", "稿费")], "2026-11", basis="含税")
        self.assertEqual((r.main[0][7], r.main[0][11]), ("1980.20", "19.80"))
        self.assertEqual(r.attach[0][9], "0.69")


class Scope(unittest.TestCase):
    def test_exclusions(self):
        r = run([rec("B经营部", 20, "2026-12-20", 3000, "设计服务", 销售方类型="个体工商户"),
                 rec("徐某", 21, "2026-12-05", 2000, "不适用", "经纪代理"),
                 rec("樊某", 22, "2026-12-05", 3000, 平台代办="是"),
                 rec("早某", 23, "2026-10-30", 3000)], "2026-12")
        self.assertEqual(len(r.excluded), 4)
        self.assertEqual(len(r.main), 0)


class Gates(unittest.TestCase):
    def test_unknown_category_blocks(self):
        r = run([rec("某甲", 30, "2026-11-05", 3000, "")], "2026-11")
        self.assertEqual(r.summary["状态"], "草稿-有异常，不可直接申报")
        self.assertEqual(len(r.main), 0)

    def test_category_map_resolves(self):
        x = rec("某甲", 30, "2026-11-05", 3000, "", 摘要="讲课费")
        r = run([x], "2026-11", category_map={"讲课费": "教育服务"})
        self.assertEqual(r.main[0][11], "30.00")

    def test_bad_id_checksum(self):
        x = rec("某乙", 31, "2026-11-05", 3000)
        x["身份证件号码"] = x["身份证件号码"][:-1] + ("0" if x["身份证件号码"][-1] != "0" else "1")
        r = run([x], "2026-11")
        self.assertEqual(r.summary["异常数"], 1)

    def test_missing_amount_never_zero(self):
        x = rec("某丙", 32, "2026-11-05", "")
        r = run([x], "2026-11")
        self.assertEqual(len(r.main), 0)
        self.assertEqual(r.summary["状态"], "草稿-有异常，不可直接申报")

    def test_wrong_period(self):
        r = run([rec("某丁", 33, "2026-12-05", 3000)], "2026-11")
        self.assertEqual(r.summary["异常数"], 1)

    def test_same_id_two_names(self):
        a = rec("郑某", 34, "2026-12-10", 2000)
        b = rec("张某", 34, "2026-12-11", 2000)
        r = run([a, b], "2026-12")
        self.assertEqual(len(r.main), 0)
        self.assertEqual(r.summary["异常数"], 1)

    def test_split_hint(self):
        r = run([rec("某戊", 35, f"2026-11-0{d}", 950) for d in (3, 4, 5)], "2026-11")
        self.assertTrue(any("拆分" in i["说明"] for i in r.issues))

    def test_relief_expiry(self):
        r = run([rec("某己", 36, "2028-01-05", 3000)], "2028-01")
        self.assertEqual(r.summary["异常数"], 1)

    def test_gates_all_true_and_files(self):
        r = run([rec("徐某", 37, "2026-11-05", 3000), rec("王某", 38, "2026-11-06", 300)], "2026-11")
        self.assertTrue(all(r.summary["闸门"].values()))
        with tempfile.TemporaryDirectory() as d:
            calc.save(r, d)
            self.assertTrue(os.path.exists(os.path.join(d, "申报表.csv")))

    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "in.csv")
            calc.write_csv(src, calc.INPUT_COLUMNS, [
                ["张三", "居民身份证", fake_id(40), "2026-11-05", "2000", "讲座", "", "教育服务", "否", "", "", "", "", ""]])
            code = calc.main(["run", "--input", src, "--period", "2026-11", "--amount-basis", "不含税",
                              "--default-relief", "减按1%", "--city-rate", "市区", "--out", d])
            self.assertEqual(code, 0)


class MessyInput(unittest.TestCase):
    """来自 100 题评测中真实财务表格的毛病。"""

    def _csv(self, d, rows, enc="utf-8-sig"):
        import csv as _csv
        path = os.path.join(d, "in.csv")
        with open(path, "w", encoding=enc, newline="") as f:
            _csv.writer(f).writerows(rows)
        return path

    def test_alias_header_title_row_total_row_gbk(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._csv(d, [["某公司11月劳务费明细"], [],
                                 ["收款人", "证件号码", "支付日期", "金额（元）", "用途", "服务类别"],
                                 ["张三", fake_id(41), "2026/11/05", "￥3,000.00", "讲课", "教育服务"],
                                 ["合计", "", "", "3000", "", ""]], enc="gbk")
            notes = []
            recs = calc.read_rows(path, notes)
            self.assertEqual(len(recs), 1)
            self.assertTrue(any("合计行" in n for n in notes))
            r = run(recs, "2026-11")
            self.assertEqual(r.summary["应扣缴增值税合计"], "30.00")

    def test_invalid_date_is_issue_not_crash(self):
        r = run([rec("周某", 42, "2026-11-31", 3000)], "2026-11")
        self.assertNotEqual(r.summary["状态"], "可复核")

    def test_duplicate_rows_hint(self):
        a = rec("吴某", 43, "2026-11-05", 3000, 摘要="讲课")
        b = dict(a, _row=a["_row"] + 100)
        r = run([a, b], "2026-11")
        self.assertTrue(any("重复" in i["说明"] for i in r.issues))

    def test_quick_estimate(self):
        import io, contextlib, json as _json
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            calc.main(["quick", "--amounts", "600", "500", "--amount-basis", "含税"])
        self.assertEqual(_json.loads(buf.getvalue())["应扣缴增值税"], "10.89")

    def test_quick_items_round_per_row(self):
        # 同日不同应税交易项目分行、逐行舍入：7.20 + 2.94 = 10.14（合并一次舍入会得 10.13）
        import io, contextlib, json as _json
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            calc.main(["quick", "--amounts", "719.69", "293.52", "--items", "咨询服务", "非学历教育服务",
                       "--amount-basis", "不含税"])
        self.assertEqual(_json.loads(buf.getvalue())["应扣缴增值税"], "10.14")


if __name__ == "__main__":
    unittest.main()


class V05Reading(unittest.TestCase):
    """读取层兼容（英文表头、分号、UTF-16、文本前导撇号、金额前缀、代开标志写法）。"""

    def _write(self, text, enc="utf-8", name="t.csv"):
        d = tempfile.mkdtemp()
        p = os.path.join(d, name)
        with open(p, "w", encoding=enc, newline="") as f:
            f.write(text)
        return p

    def _vat(self, path):
        rows = calc.read_rows(path)
        r = calc.compute(rows, "2026-11", "不含税", "减按1%", "市区")
        return r, Decimal(r.summary["应扣缴增值税合计"])

    def test_english_header(self):
        p = self._write("Name,ID Number,Payment Date,Amount,Category\n"
                        f"A,{fake_id(901)},2026-11-03,2000,设计服务\n")
        r, v = self._vat(p)
        self.assertEqual(v, Decimal("20.00"))

    def test_semicolon_utf16(self):
        p = self._write("姓名;身份证件号码;付款日期;金额;服务大类\n"
                        f"B;{fake_id(902)};2026-11-03;3000;教育服务\n", enc="utf-16")
        r, v = self._vat(p)
        self.assertEqual(v, Decimal("30.00"))

    def test_apostrophe_and_rmb(self):
        p = self._write("姓名,身份证件号码,付款日期,金额,服务大类\n"
                        f"C,'{fake_id(903)},2026-11-03,RMB 1500,软件服务\n")
        r, v = self._vat(p)
        self.assertEqual(v, Decimal("15.00"))

    def test_invoiced_flag_variants(self):
        p = self._write("姓名,身份证件号码,付款日期,金额,服务大类,是否已代开发票,代开时已缴税\n"
                        f"D,{fake_id(904)},2026-11-03,3000,咨询服务,已开,已缴\n")
        r, v = self._vat(p)
        self.assertEqual(v, Decimal("0.00"))
        self.assertEqual(len(r.main), 1)
        self.assertEqual(r.main[0][8], "——")


class EvalFindings(unittest.TestCase):
    """2026-11 评测发现的问题的回归测试。"""

    def test_big_invoice_unpaid_not_called_threshold_exempt(self):
        r = run([rec("甲某", 31, "2026-12-03", 5000, 是否已代开发票="是", 代开时已缴税="否")], "2026-12")
        msg = [i["说明"] for i in r.issues if "已代开" in i["说明"]][0]
        self.assertNotIn("按未达起征点免税", msg)
        self.assertIn("核实", msg)
        self.assertEqual(r.summary["可能需补扣增值税（已代开部分）"], "50.00")
        self.assertEqual(r.summary["可能需补扣附加税费（已代开部分）"], "3.00")

    def test_same_id_natural_and_business(self):
        r = run([rec("乙某", 32, "2026-12-03", 3000, 销售方类型="个体工商户"),
                 rec("乙某", 32, "2026-12-04", 2000)], "2026-12")
        self.assertTrue(any("同一证件号既按自然人申报" in i["说明"] for i in r.issues))

    def test_tax_inclusive_under_threshold_sales_separated(self):
        r = run([rec("丙某", 33, "2026-12-05", "1001.00")], "2026-12", basis="含税")
        self.assertEqual(r.main[0][8], "未达起征点")
        self.assertEqual(r.main[0][7], "991.09")

    def test_under_threshold_hint_says_declare_once_per_person(self):
        r = run([rec("丁某", 34, "2026-12-05", 300), rec("丁某", 34, "2026-12-06", 400)], "2026-12")
        hints = [i for i in r.issues if "未达1000元起征点" in i["说明"]]
        self.assertEqual(len(hints), 1)
        self.assertIn("仍须申报", hints[0]["说明"])

    def test_user_marked_not_applicable_reason_and_rent_hint(self):
        r = run([rec("戊某", 35, "2026-12-05", 5000, "不适用", 摘要="12月场地租金")], "2026-12")
        self.assertIn("用户自填", r.excluded[0]["理由"])
        self.assertTrue(any("第12问" in i["说明"] for i in r.issues))
        self.assertEqual(r.summary["不适用金额合计"], "5000.00")

    def test_no_half_relief_drops_rounding_item(self):
        r = run([rec("己某", 36, "2026-12-05", 2000)], "2026-12", half_relief=False)
        self.assertFalse(any("减半" in u for u in r.summary["未核实事项"]))

    def test_exempt_row_explained_and_grouped(self):
        r = run([rec("庚某", 37, "2027-04-15", 2500, 优惠="残疾人免税")], "2027-04")
        self.assertEqual(r.summary["应扣缴增值税合计"], "0.00")
        self.assertTrue(any("残疾人免税" in i["说明"] for i in r.issues))
        self.assertIn("残疾人免税", r.summary["按口径分组"])

    def test_cutoff_month_and_masking(self):
        r = run([rec("辛某某", 38, "2027-12-05", 2000)], "2027-12")
        self.assertTrue(any("截止月" in x for x in r.summary["特别提醒"]))
        self.assertEqual(calc.mask(fake_id(38))[:6], fake_id(38)[:6])
        self.assertEqual(calc.mask_name("辛某某"), "辛**")

    def test_xlsx_float_noise(self):
        self.assertEqual(calc.parse_amount("1234.5600000000001"), Decimal("1234.56"))
