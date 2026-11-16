# 评测题库：3450 道题，分 7 类

用来检验 AI 用这个技能能不能把代扣增值税的活干对：数算得对不对、该问的问没问、不该做的有没有拒绝。

题目和标准答案由 opus5.5 生成。计算题的答案由一套独立的计算程序算出，再和技能的计算结果逐题对过。题里的身份证号都是编的，不对应真人。

## 点击下载

| 下载 | 类型 | 题数 | 考什么 |
|---|---|---:|---|
| **[点击下载](https://github.com/LLJ99999/natural-person-vat-withholding/releases/download/v0.0.1/vat-eval-Q-policy-577.zip)** | 政策问答 | 577 | 哪些要扣、起征点、什么时候报、代开发票怎么办 |
| **[点击下载](https://github.com/LLJ99999/natural-person-vat-withholding/releases/download/v0.0.1/vat-eval-K-quick-calc-500.zip)** | 口算 | 500 | 一笔钱该扣多少增值税和附加税费 |
| **[点击下载](https://github.com/LLJ99999/natural-person-vat-withholding/releases/download/v0.0.1/vat-eval-G-official-82.zip)** | 官方算例 | 82 | 税务总局《即问即答》里的例子改编 |
| **[点击下载](https://github.com/LLJ99999/natural-person-vat-withholding/releases/download/v0.0.1/vat-eval-M-monthly-700.zip)** | 月度流水 | 700 | 1 到 100 笔的整月流水出表 |
| **[点击下载](https://github.com/LLJ99999/natural-person-vat-withholding/releases/download/v0.0.1/vat-eval-F-messy-format-575.zip)** | 不规范格式 | 575 | 表头乱写、带合计行、日期格式怪等 30 种乱表格 |
| **[点击下载](https://github.com/LLJ99999/natural-person-vat-withholding/releases/download/v0.0.1/vat-eval-X-edge-case-453.zip)** | 异常边界 | 453 | 护照、证件号错、退款负数、缺信息、重复录入等 |
| **[点击下载](https://github.com/LLJ99999/natural-person-vat-withholding/releases/download/v0.0.1/vat-eval-B-behavior-563.zip)** | 行为 | 563 | 该问的会不会问，要它代登录、拆单逃税会不会拒绝 |
| **[点击下载](https://github.com/LLJ99999/natural-person-vat-withholding/releases/download/v0.0.1/vat-eval-all-3450.zip)** | 全部 | 3450 | 以上 7 类，加生成和评分程序 |

每份里都有一张总表（Excel）：第一页是总览，后面每类一页，能直接看每道题问了什么、标准答案是什么。

## 目前成绩

最早的 450 题实测通过 446 题（没过的 4 题是 AI 偶尔失误）。其余 3000 题还没用 AI 实跑，但带表格的题已经用计算程序逐题核对过。

## 已知不足

- 政策问答和口算按关键词打分，比较粗：说法换了可能被误判，关键词对了但意思错了也可能被放过。
- 题目和标准答案还没有经过执业会计复核。发现错题欢迎[留言](https://github.com/LLJ99999/natural-person-vat-withholding/issues)。

---

## 给开发者

### 目录

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

### 怎么跑

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

### 补充

- 有 40 道“口头补数”的行为题，要 Agent 把用户补充的证件号或金额写进表里再算，`xcheck.py` 查不了。
- 部分老题的消息里只写“所属期12月”不写年份，`xcheck.py` 读不出所属期会报差异，用 Agent 实跑不受影响。
