# 评测题库：450 题 × agent 实跑

题目和标准答案由 opus5.5 生成，依据 28 号公告、19 号公告填报说明和税务总局《即问即答》（2026-11-13）。跑评测时 agent 只拿 skill 干活，不参与出题。

- `题库总表.xlsx`：每题一行（题号、批次、类型、用户消息、附件、标准答案/评分要点）
- `cases/`（50 题）：C 计算 30、E 闸门 8、B 行为 12
- `cases2/`（100 题）：官方问答延伸、随机月度流水、不规范表格、异常、行为
- `cases3/`（300 题）：政策问答 60、官方问答改编计算 40、随机流水 100、不规范格式 30（英文表头、分号、UTF-16、撇号证件号、RMB 金额等）、异常边界 30、行为 40
- 每题一个目录：`case.json`（prompt + expect）和附件 `流水.*`

## 脚本

- `build_cases*.py`：重新生成题目（结果固定，可复现）
- `ref.py`：独立参考实现，计算题的标准答案由它算出
- `run.sh`：用 codex CLI 当 agent 逐题实跑
- `grade.py`：评分。文字规则匹配前会去掉空白、千分位逗号和引号书名号，“您”“你”等价；拒绝类关键点也认“不做/做不了/拒绝”等说法；禁词前面紧跟否定（如“不保证能直接导入”）不算违规，证件号除外
- `test_grade.py`：评分规则的单元测试，`python3 -m unittest test_grade -v`
- `xcheck.py`：不经 agent，直接用 skill 的脚本对照标准答案

```bash
./run.sh ../natural-person-vat-withholding r1                    # 第一批
CASES=cases3 PAR=8 ./run.sh ../natural-person-vat-withholding r3 # 第三批，8 并发
CASES=cases3 python3 grade.py r3
python3 xcheck.py ../natural-person-vat-withholding cases3
```

注意：全量 450 题会调用 450 次模型，按自己的 API 费用掂量；可以在 run.sh 后面只列要跑的题号。

## 结果（v0.0.1 发布前，单次运行）

450 题通过 446 题。没过的 4 题是模型偶发失误，针对它们改过 skill 后还没有重跑。
