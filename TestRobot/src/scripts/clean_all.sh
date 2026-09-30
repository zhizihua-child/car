#!/usr/bin/env bash
# 一键清理所有仿真/导航相关进程（独立进程模式下必须清干净，避免旧节点污染 TF/时钟）
# 用法：bash src/scripts/clean_all.sh
set -u
PATTERNS=(
  '[g]zserver' '[g]zclient'
  '[r]obot_state_publisher'
  '[s]lam_toolbox'
  '[m]ap_server' '[a]mcl'
  '[l]ifecycle_manager' '[n]av2_container' '[c]omponent_container'
  '[c]ontroller_server' '[p]lanner_server' '[b]t_navigator'
  '[b]ehavior_server' '[s]moother_server' '[w]aypoint_follower'
  '[v]elocity_smoother' '[c]ollision_monitor' '[r]viz2'
  '[t]eleop_twist' '[s]pawn_entity'
)

# 收集调用者的祖先 PID，避免误杀"命令行里恰好包含关键词"的外层 shell
ancestors=" $$ "
pid=$$
for _ in $(seq 1 8); do
  pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
  [ -z "$pid" ] || [ "$pid" = "0" ] || [ "$pid" = "1" ] && break
  ancestors="$ancestors$pid "
done

kill_pattern() {
  local pat=$1
  for pid in $(pgrep -f "$pat" 2>/dev/null); do
    case "$ancestors" in
      *" $pid "*) continue ;;   # 跳过调用链上的进程（含当前 shell）
    esac
    kill -9 "$pid" 2>/dev/null || true
  done
}

echo "清理残留进程..."
for p in "${PATTERNS[@]}"; do
  kill_pattern "$p"
done
sleep 3
left=""
for pid in $(pgrep -f '[g]zserver|[r]obot_state_publisher|[a]mcl|[c]ontroller_server|[p]lanner_server|[b]t_navigator' 2>/dev/null); do
  case "$ancestors" in *" $pid "*) continue ;; esac
  left="$left$(ps -o args= -p "$pid" 2>/dev/null)
"
done
if [ -n "$left" ]; then
  echo "仍有残留："; printf '%s' "$left"
else
  echo "已清理干净"
fi
if ss -tln 2>/dev/null | grep -q ':11345 '; then
  echo "警告：端口 11345 仍被占用"
else
  echo "端口 11345 空闲"
fi
