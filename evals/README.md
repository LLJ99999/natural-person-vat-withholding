# 评测题库：3450 题，按类型分 7 份

用来检验一个 Agent 拿着 `natural-person-vat-withholding` 这个 skill，能不能把代扣代缴自然人增值税的活干对：数算得对不对、该问的问没问、不该做的有没有拒绝。

题目和标准答案由 opus5.5 生成。计算题的标准答案由独立参考实现 [`scripts/ref.py`](scripts/ref.py) 算出，不调用 skill 的脚本；带附件的题又拿 skill 脚本逐题对过一遍。证件号都是按校验位合成的假号码，不对应任何真实个人。

依据：财政部 税务总局公告2026年第28号、税务总局公告2026年第19号、税务总局《即问即答》（2026-11-13）。

## 七种题型

| 前缀 | 类型 | 题数 | 有附件 | 考什么 | 单独下载 |
|---|---|---:|---|---|---|
| Q | 政策问答 | 577 | 否 | 服务分类、适用范围、起征点、申报期限、附加税率、代开发票、平台代办 | `vat-eval-Q-policy-577.zip` |
| K | 口算 | 500 | 否 | 单人单日的增值税、附加税费，含税/不含税、1%/3%、市区/县城/其他 | `vat-eval-K-quick-calc-500.zip` |
| G | 官方算例 | 82 | 是 | 《即问即答》算例改编：同日合并、已代开、放弃优惠、残疾人免税、平台代办、跨月 | `vat-eval-G-official-82.zip` |
| M | 月度流水 | 700 | 是 | 1–100 行的随机月度流水，所属期 2026年11月至2027年12月 | `vat-eval-M-monthly-700.zip` |
| F | 不规范格式 | 575 | 是 | 30 种乱表格：别名/英文表头、GBK、UTF-16、分号、合计行、序列日期、撇号证件号、RMB 金额… | `vat-eval-F-messy-format-575.zip` |
| X | 异常边界 | 453 | 是 | 护照、15位身份证、校验位错、负数退款、缺字段、金额模糊、重复行、同号不同名、非自然人… | `vat-eval-X-edge-case-453.zip` |
| B | 行为 | 563 | 部分 | 缺口径要追问；注入、要求心算/删声明/代提交/登录、拆单逃税、索要证件号、施压写“可以申报” | `vat-eval-B-behavior-563.zip` |

下载地址：[Releases](https://github.com/LLJ99999/natural-person-vat-withholding/releases/latest)。也有一个包含全部 7 类的 `vat-eval-all-3450.zip`。

## 目录

```
evals/
├── 题库总表.xlsx          # 第一页总览，后面每种类型一页：题号、用户消息、附件、评分要点
├── 题库/
│   ├── Q_政策问答/Q0001/case.json
│   ├── G_官方算例/G0001/case.json + 流水.csv
│   └── …
└── scripts/
    ├── build_cases*.py    # 生成题目（固定随机种子，可复现）
    ├── organize.py        # 按类型整理到 题库/，生成总表
    ├── ref.py             # 独立参考实现，算计算题的标准答案
    ├── run.sh             # 用 codex CLI 当 Agent 逐题实跑
    ├── grade.py           # 评分（匹配前去空白、千分位逗号、引号；“您”“你”等价；拒绝类也认“不做/拒绝”；禁词前有否定不算违规，证件号除外）
    ├── test_grade.py      # 评分规则的单元测试：cd scripts; python3 -m unittest test_grade -v
    └── xcheck.py          # 不经 Agent，直接拿 skill 脚本对答案
```

每题一个目录：`case.json` 里有 `prompt`（发给 Agent 的话）和 `expect`（评分要点），有附件的另有 `流水.csv` 或 `流水.xlsx`。

`expect` 里可能有这些字段：

| 字段 | 意思 |
|---|---|
| `status` | 脚本输出的状态应为“可复核”或“草稿” |
| `vat` / `sur` | 增值税合计 / 附加税费合计 |
| `nrows` / `excluded` | 申报表行数 / 不适用行数 |
| `ask` | 应该先追问，不能直接出表 |
| `text_any` | 每组关键词里，回答至少要出现一个 |
| `text_none` | 回答里不能出现的内容（如完整证件号、“可以申报了”） |

## 怎么跑

需要 Python 3 和 [codex CLI](https://github.com/openai/codex)（模型和接口随意）。

```bash
cd evals
# 跑一类：每道题调用一次模型，先看清题数再跑
CASES=题库/K_口算 PAR=8 ./scripts/run.sh ../natural-person-vat-withholding k1
CASES=题库/K_口算 python3 scripts/grade.py k1

# 只跑几道
CASES=题库/X_异常边界 ./scripts/run.sh ../natural-person-vat-withholding x1 X0001 X0002

# 不花模型钱：只用 skill 脚本核对带附件的题
python3 scripts/xcheck.py ../natural-person-vat-withholding 题库/M_月度流水
```

全量 3450 题就是 3450 次模型调用，按自己的 API 费用掂量。

重新生成题目：

```bash
cd evals/scripts
python3 build_cases.py && python3 build_cases2.py && python3 build_cases3.py && python3 build_cases4.py
python3 organize.py
```

## 结果

| 时间 | skill | 范围 | 通过 |
|---|---|---|---|
| 2026-11-16 | v0.0.1 发布前 | 最早的 450 题（现分散在各类型里） | 446 / 450（单次） |

没过的 4 题是模型偶发失误。其余 3000 题还没有用模型实跑过；带附件的题已用脚本核对。

## 已知局限

- 政策问答和口算按关键词评分，会放过“关键词对了但说法错了”的回答，也会误伤换了说法的正确回答。
- 有 40 道“口头补数”的行为题，要 Agent 把用户补充的证件号或金额写进表里再算，`xcheck.py` 查不了。
- 部分老题的消息里只写“所属期12月”不写年份，`xcheck.py` 读不出所属期会报差异，用 Agent 实跑不受影响。
- 题目和标准答案没有经过执业会计复核。发现错题欢迎提 issue。
