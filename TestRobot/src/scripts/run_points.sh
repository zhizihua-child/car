#!/usr/bin/env bash
# 按顺序导航到多个固定点（Gazebo 与导航流程已启动时使用）
#
# 前置：另开终端已运行
#   bash src/scripts/clean_all.sh
#   ros2 launch src/launch/navigation.launch.py
#
# 用法：
#   1) 直接编辑下面的 POINTS 数组（map 坐标系：X,Y[,朝向度]），保存后运行：
#        bash src/scripts/run_points.sh
#   2) 命令行临时指定若干点：
#        bash src/scripts/run_points.sh "0.0,-0.5" "-0.82,1.48,90"
#   3) 每点限时（默认 90 秒）：
#        bash src/scripts/run_points.sh --timeout 120

TIMEOUT=90

# ============ 可编辑的固定点列表（X,Y,朝向度；朝向可省略=0） ============
POINTS=(
    "-0.82,1.48,0"      # 1 东北对角（八边形场地，中心 -2.8,-0.5）
    "-4.78,-2.48,0"     # 2 西南对角
    "-4.78,1.48,0"      # 3 西北对角
    "-0.82,-2.48,0"     # 4 东南对角
    # "-2.80,-0.50,0"   # 5 场地中心（示例：需要时取消注释或自己加行）
)
# ======================================================================

ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --timeout) TIMEOUT="$2"; shift 2 ;;
        *) ARGS+=("$1"); shift ;;
    esac
done
if [ ${#ARGS[@]} -gt 0 ]; then
    POINTS=("${ARGS[@]}")
fi

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source /opt/ros/humble/setup.bash
if [ -f "$DIR/../../install/setup.bash" ]; then
    # shellcheck disable=SC1091
    source "$DIR/../../install/setup.bash"
fi
set -u

echo "[points] 等待 Nav2 就绪（最多 60s）..."
for _ in $(seq 1 30); do
    if ros2 action list 2>/dev/null | grep -q 'navigate_to_pose'; then
        echo "[points] /navigate_to_pose 可用"
        break
    fi
    sleep 2
done
if ! ros2 action list 2>/dev/null | grep -q 'navigate_to_pose'; then
    echo "[points] 错误：导航未启动（先运行 ros2 launch src/launch/navigation.launch.py）"
    exit 1
fi

ok=0
n=0
for p in "${POINTS[@]}"; do
    IFS=',' read -r X Y YAW <<< "$p"
    YAW="${YAW:-0}"
    n=$((n + 1))
    echo "[points] === 第 $n/$(( ${#POINTS[@]} )) 个点: ($X, $Y, ${YAW}°) ==="
    if timeout "$TIMEOUT" python3 "$DIR/send_nav_goal.py" "$X" "$Y" "$YAW"; then
        ok=$((ok + 1))
    else
        echo "[points] 该点未在 ${TIMEOUT}s 内到达，继续下一个"
    fi
    sleep 2
done
echo "[points] 完成：$ok/$n 个点到达"
[ "$ok" -eq "$n" ]
