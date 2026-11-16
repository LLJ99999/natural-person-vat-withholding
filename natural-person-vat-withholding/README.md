# 代扣代缴自然人增值税助手（Agent Skill）

版本 v0.0.1 · 作者 Microsoft Office User · 由 opus5.5 生成

12 月 1 日至 15 日是《境内单位代扣代缴自然人增值税管理办法》（财政部 税务总局公告2026年第28号）的首次扣缴申报期。这个 Skill 把一个月的劳务费付款流水，整理成《境内单位代扣代缴自然人增值税及附加税费申报表》及附列资料的草稿（格式按税务总局公告2026年第19号）。

- **算数交给脚本**：按人按日合并、1000 元按次起征点、减按 1%、附加税费减半，都由 Python 标准库脚本完成，AI 不心算
- **数据留在本机**：脚本不联网；AI 判断服务类别时只看“摘要”文字，不读姓名和证件号
- **闸门**：5 项自检（每行都有去处、两表合计一致、逐行复算等），任何一项不过或有异常，输出文件自动带“草稿_有异常_”前缀
- **测试来自官方**：31 个单元测试，大部分取自国家税务总局 2026-11-13《即问即答》第10–45问的算例

> 仅辅助整理与计算，不构成税务意见。申报前请在自然人电子税务局（扣缴端）核对。

## 安装

- 下载：[Releases](https://github.com/LLJ99999/natural-person-vat-withholding/releases/latest) 里的 `natural-person-vat-withholding-v0.0.1.zip`
- **WorkBuddy**：技能 → 添加技能 → 上传技能，选这个 zip
- **Claude Code**：把 zip 解压到 `~/.claude/skills/`
- **Codex**：把 zip 解压到 `~/.codex/skills/`

然后对 Agent 说：“帮我把 11 月付给个人的劳务费整理成代扣增值税申报表。”

## 直接用脚本

```bash
python3 scripts/calc.py template --out 流水模板.csv
python3 scripts/calc.py summaries --input 流水.xlsx
python3 scripts/calc.py run --input assets/示例流水.csv --period 2026-11 \
  --amount-basis 不含税 --default-relief 减按1% --city-rate 市区 --out ./输出
python3 -m unittest discover -s scripts
```

## 不做什么

不处理个人所得税；不登录电子税务局、不提交申报；不处理退款更正、按月计税的自然人、未内置的优惠。这些情况会列为异常，交给人处理。

## 还没核实的地方

见 `references/policy.json` 的 `unverified`，例如“减按 1%”的截止日期、未达起征点行第 9–11 列的填法、附加税费的减免性质代码。欢迎有实操经验的会计提 issue。

## 反馈

提 issue 时请只给合成数据，不要上传真实的身份证号、工资表或流水。
