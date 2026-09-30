#!/usr/bin/env bash
# 一键干净启动 Gazebo
# 作用：启动前先清理残留的 gzserver/gzclient，避免：
#   1) 端口 11345 被占，新 gzserver 起不来（表现为"没有小车/还是老 world"）
#   2) 旧实例没退，新旧画面重叠
#
# 用法：
#   ./run_gazebo.sh                # 带界面启动
#   ./run_gazebo.sh gui:=false     # 无界面（headless）
#   ./run_gazebo.sh x:=1 y:=2 z:=0.3   # 指定出生点
set -e

WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[1/3] 清理残留仿真/导航进程（含 slam/nav2 独立进程）..."
if [ -x "$WS_DIR/src/scripts/clean_all.sh" ]; then
    bash "$WS_DIR/src/scripts/clean_all.sh" || true
else
    pkill -f gzclient 2>/dev/null || true
    pkill -f gzserver 2>/dev/null || true
    sleep 2
fi

if ss -tln 2>/dev/null | grep -q ':11345 '; then
    echo "错误: 端口 11345 仍被占用，请检查："
    ss -tlnp 2>/dev/null | grep ':11345 '
    exit 1
fi
echo "      端口 11345 已空闲"

echo "[2/3] 加载 ROS2 环境..."
source /opt/ros/humble/setup.bash
if [ -f "$WS_DIR/install/setup.bash" ]; then
    source "$WS_DIR/install/setup.bash"
fi

echo "[3/3] 启动 Gazebo..."
exec ros2 launch "$WS_DIR/src/launch/gazebo.launch.py" "$@"
