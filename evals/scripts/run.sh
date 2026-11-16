#!/bin/bash
# usage: run.sh <skill_dir> <round_name> [case_ids...]
# 需要已安装并配置好 codex CLI（任意模型/接口均可）
SKILL=$1; ROUND=$2; shift 2
BASE=$(cd "$(dirname "$0")/.." && pwd)  # evals/
CASES=${CASES:-题库/Q_政策问答}
IDS=${@:-$(ls $BASE/$CASES)}
mkdir -p $BASE/rounds/$ROUND
run_one() {
  id=$1; d=$BASE/rounds/$ROUND/$id
  rm -rf $d; mkdir -p $d
  cp -r $SKILL $d/skill
  cp $BASE/$CASES/$id/流水.* $d/ 2>/dev/null
  prompt=$(python3 -c "import json;print(json.load(open('$BASE/$CASES/$id/case.json'))['prompt'])")
  files=$(cd $d && ls 流水.* 2>/dev/null)
  cat > $d/prompt.txt <<EOF
你是某公司财务部的助理，用 ./skill 这个技能干活（先完整读 ./skill/SKILL.md，严格照做）。
工作目录里的附件：${files:-（无附件）}
这是一次性的对话：你没法再追问用户。如果按技能必须先问用户才能继续，就不要继续算，直接把你要问的问题作为最终回答。
最终回答用中文，就是你要发给这位同事的消息。

同事的消息：
$prompt
EOF
  timeout 400 codex exec --skip-git-repo-check --ephemeral -C $d -s workspace-write -o $d/final.txt - < $d/prompt.txt > $d/log.txt 2>&1
  echo "$id done $?"
}
export -f run_one; export BASE ROUND SKILL CASES
printf "%s\n" $IDS | xargs -P ${PAR:-8} -I{} bash -c 'run_one {}'
