#!/usr/bin/env bash
# 保存当前 SLAM 建好的地图到 src/maps/
# 用法：在 mapping.launch.py 运行、地图建好后，另开终端执行
#   bash src/scripts/save_map.sh          # 默认保存为 map
#   bash src/scripts/save_map.sh mymap    # 保存为 mymap
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # 指向 src/
MAP_DIR="$DIR/maps"
NAME="${1:-map}"

mkdir -p "$MAP_DIR"

source /opt/ros/humble/setup.bash
if [ -f "$DIR/../install/setup.bash" ]; then
    source "$DIR/../install/setup.bash"
fi

echo "正在保存地图到: $MAP_DIR/$NAME"
ros2 run nav2_map_server map_saver_cli -f "$MAP_DIR/$NAME" \
    --ros-args -p use_sim_time:=true

echo "完成：$MAP_DIR/$NAME.pgm  $MAP_DIR/$NAME.yaml"
