# 代扣代缴自然人增值税助手（Agent Skill）

版本 v0.0.1 · MIT · 作者 Microsoft Office User · 由 opus5.5 生成

把单位一个月付给个人的劳务费流水，整理成《境内单位代扣代缴自然人增值税及附加税费申报表》及附列资料草稿（财政部 税务总局公告2026年第28号、税务总局公告2026年第19号）。12 月 1 日至 15 日是首次扣缴申报期。

> 仅辅助整理与计算，不构成税务意见。申报前请在自然人电子税务局（扣缴端）核对。

## 安装

- **WorkBuddy**：技能 → 添加技能 → 上传技能，选这个 zip
- **Claude Code**：解压到 `~/.claude/skills/`
- **Codex**：解压到 `~/.codex/skills/`

只需要 Python 3 标准库，不联网，不要 API Key。

## 对 Agent 说

- “帮我把 11 月付给个人的劳务费整理成代扣增值税申报表。金额含税，按小规模减按 1%，单位在市区，附加减半。”（附上流水表）
- “讲课费 3000 元含税，要代扣多少增值税？”
- “个体户给我们做设计，要我们代扣吗？”

没有流水表，可以先让它生成模板。

## 它会做什么

1. 问清口径：金额含税还是不含税、默认优惠、单位所在地、附加是否减半
2. 读表：认得别名表头、英文表头、GBK/UTF-16、合计行、Excel 日期等常见写法
3. 建议服务类别（只看摘要文字），等你确认
4. 跑脚本：按人按日合并、判断 1000 元起征点、算增值税和附加税费、填 14 列
5. 自检 5 道闸门，交给你：申报表、附列资料、异常与提示、不适用清单、summary.json

有异常时文件名带“草稿_有异常_”前缀，它不会说“可以申报”。

## 规则

| 规则 | 说明 |
|---|---|
| 起征点 | 同一人同一天在本单位合计，不含税销售额满 1000 元全额计税；不满不扣，但要申报 |
| 征收率 | 小规模减按 1%（执行至 2027-12-31）；放弃优惠 3%；残疾人免税 |
| 含税换算 | 含税金额 ÷ (1 + 征收率) |
| 附加税费 | 城建 7% / 5% / 1%，教育费附加 3%，地方教育附加 2%，可选减半 |
| 不适用 | 个体工商户、公司、平台已代办、2026-11-01 前付款、七类服务以外 |
| 已代开已缴税 | 照样申报，不再扣 |

## 红线

不心算，不补数，类别由人确认，回复里证件号打码；不处理个人所得税，不登录电子税务局，不代为提交，不帮拆单或改日期少缴税。

## 直接用脚本

```bash
python3 scripts/calc.py template --out 流水模板.csv
python3 scripts/calc.py summaries --input 流水.xlsx
python3 scripts/calc.py run --input assets/示例流水.csv --period 2026-11 \
  --amount-basis 含税 --default-relief 减按1% --city-rate 市区 --out ./输出
python3 scripts/calc.py quick --amounts 3000 --amount-basis 含税 --relief 减按1% --city-rate 市区
python3 -m unittest discover -s scripts
```

## 文件

| 文件 | 内容 |
|---|---|
| `SKILL.md` | 给 Agent 的规则和流程 |
| `scripts/calc.py` | 读表、计算、出表、闸门 |
| `scripts/test_calc.py` | 31 个单元测试，多取自税务总局《即问即答》（2026-11-13）算例 |
| `references/policy.json` | 政策快照（税率、期限、未核实事项） |
| `references/categories.md` | 七类服务范围 |
| `references/faq.md` | 常见问答，带出处 |
| `assets/示例流水.csv` | 示例输入 |

## 还没核实

见 `references/policy.json` 的 `unverified`：减按 1% 截止日、未达起征点行第 9–11 列填法、减免性质代码等。

## 反馈

https://github.com/LLJ99999/natural-person-vat-withholding/issues 。请只用合成数据，不要上传真实身份证号或流水。
