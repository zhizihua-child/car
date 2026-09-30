#!/usr/bin/env bash
# 运行时自检（测试桩）：检查建图/定位/导航所需话题与 TF 链是否正常。
# 用法：先启动任一流程（gazebo / mapping / localization / navigation），再另开终端：
#   bash src/scripts/check_topics.sh        # 在 TestRobot/ 目录下执行
# 说明：没有仿真运行时，话题/TF 全部报 FAIL 属于正常现象。
# 退出码：0 = 全部必需项通过；1 = 有 FAIL。

# 注意：必须在 set -u 之前 source，setup.bash 会引用未定义变量
source /opt/ros/humble/setup.bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # 指向 src/
if [ -f "$DIR/../install/setup.bash" ]; then
    source "$DIR/../install/setup.bash"
fi

set -u

rc=0

check_topic() { # 话题名 期望类型
    local name=$1 type=$2
    if ros2 topic list 2>/dev/null | grep -qx "$name"; then
        if ros2 topic info "$name" 2>/dev/null | grep -q "Type: $type"; then
            echo "OK   话题 $name ($type)"
        else
            echo "FAIL 话题 $name 类型不符（期望 $type）"
            ros2 topic info "$name" 2>/dev/null | grep "Type:" | sed 's/^/      /'
            rc=1
        fi
    else
        echo "FAIL 话题 $name 不存在"
        rc=1
    fi
}

check_tf() { # 父坐标系 子坐标系
    local parent=$1 child=$2
    local out
    out=$(timeout 5 ros2 run tf2_ros tf2_echo "$parent" "$child" 2>&1 || true)
    if echo "$out" | grep -q "Translation:"; then
        echo "OK   TF $parent -> $child"
    else
        echo "FAIL TF $parent -> $child 不可用"
        rc=1
    fi
}

echo "=== 必需话题 ==="
check_topic /scan sensor_msgs/msg/LaserScan
check_topic /odom nav_msgs/msg/Odometry

echo "=== TF 链 ==="
check_tf odom base_link
if ros2 topic list 2>/dev/null | grep -qx "/map"; then
    check_tf map odom
else
    echo "SKIP map -> odom（未发布 /map，仅建图/定位/导航流程需要）"
fi

echo "=== /scan 频率（仅提示，不计入通过/失败）==="
hz=$(timeout 8 ros2 topic hz /scan 2>&1 | grep -m1 "average rate:" || true)
if [ -n "$hz" ]; then
    echo "INFO $hz"
else
    echo "INFO 8 秒内未统计到 /scan 数据"
fi

if [ "$rc" -eq 0 ]; then
    echo "结果：全部必需项通过"
else
    echo "结果：存在 FAIL 项（若未启动仿真属正常）"
fi
exit "$rc"
