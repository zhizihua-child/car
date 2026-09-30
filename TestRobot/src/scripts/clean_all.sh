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
echo "清理残留进程..."
for p in "${PATTERNS[@]}"; do
  pkill -9 -f "$p" 2>/dev/null || true
done
sleep 3
left=$(pgrep -af '[g]zserver|[r]obot_state_publisher|[a]mcl|[c]ontroller_server|[p]lanner_server|[b]t_navigator' || true)
if [ -n "$left" ]; then
  echo "仍有残留："; echo "$left"
else
  echo "已清理干净"
fi
if ss -tln 2>/dev/null | grep -q ':11345 '; then
  echo "警告：端口 11345 仍被占用"
else
  echo "端口 11345 空闲"
fi
