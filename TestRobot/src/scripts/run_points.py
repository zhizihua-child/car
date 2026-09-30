#!/usr/bin/env python3
# 顺序导航到多个固定点（Gazebo + 导航流程已启动时使用）
#
# 前置（另开两个终端）：
#   bash src/scripts/clean_all.sh
#   ros2 launch src/launch/navigation.launch.py
# 然后运行本脚本：
#   python3 src/scripts/run_points.py
#
# 自定义点：
#   1) 直接编辑下面的 POINTS（map 坐标系：x, y, 朝向度），加行即可；
#   2) 或命令行临时指定：python3 src/scripts/run_points.py "X,Y[,YAW]" ...
#   3) 每点限时（默认 90s）：python3 src/scripts/run_points.py --timeout 120
#
# 输出：每个点的状态/耗时/到点误差；结束时统计到达数与碰撞事件数。
import math
import sys
import time

import rclpy
from gazebo_msgs.msg import ContactsState
from nav_msgs.msg import Odometry
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from tf2_ros import Buffer, TransformListener

SUCCEEDED = 4

# ==================== 可编辑的固定点（map 坐标：x, y, 朝向度）====================
POINTS = [
    (-0.82, 1.48, 0.0),     # 1 东北对角（八边形场地，中心 -2.8,-0.5）
    (-4.78, -2.48, 0.0),    # 2 西南对角
    (-4.78, 1.48, 0.0),     # 3 西北对角
    (-0.82, -2.48, 0.0),    # 4 东南对角
    # (-2.80, -0.50, 0.0),  # 示例：需要时取消注释或自行加行
]
# =============================================================================


class PointRunner(Node):
    def __init__(self, timeout):
        super().__init__(
            'run_points',
            parameter_overrides=[rclpy.parameter.Parameter(
                'use_sim_time', rclpy.parameter.Parameter.Type.BOOL, True)])
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.buf = Buffer()
        self.listener = TransformListener(self.buf, self)
        self.odom_xy = None
        self.create_subscription(Odometry, 'odom', self.on_odom, 10)
        self.create_subscription(ContactsState, 'bumper_states', self.on_bump, 10)
        self.timeout = timeout
        self.collisions = 0
        self.in_contact = False

    def on_odom(self, msg):
        self.odom_xy = (msg.pose.pose.position.x, msg.pose.pose.position.y)

    def on_bump(self, msg):
        has = len(msg.states) > 0
        if has and not self.in_contact:
            self.collisions += 1
            print(f'  [碰撞事件 #{self.collisions}]', flush=True)
        self.in_contact = has

    def pose(self):
        """优先 TF map->base_link；失败则回退 /odom（世界坐标）并标注。"""
        try:
            tf = self.buf.lookup_transform('map', 'base_link', rclpy.time.Time())
            t = tf.transform.translation
            return t.x, t.y, ''
        except Exception:  # noqa: BLE001
            if self.odom_xy is not None:
                return self.odom_xy[0], self.odom_xy[1], ' (TF失效，用/odom)'
            return None, None, ''

    def send(self, x, y, yaw_deg):
        if not self.client.wait_for_server(timeout_sec=15.0):
            print('FAIL: /navigate_to_pose 不可用（Nav2 是否已启动？）')
            return False
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y
        yaw = math.radians(yaw_deg)
        goal.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(yaw / 2.0)
        handle = None
        for attempt in (1, 2):
            fut = self.client.send_goal_async(goal)
            rclpy.spin_until_future_complete(self, fut, timeout_sec=15.0)
            if fut.done():
                handle = fut.result()
                break
            print(f'  WARN: 目标响应超时（第 {attempt} 次）')
        if handle is None or not handle.accepted:
            print(f'FAIL: 目标 ({x:.2f},{y:.2f}) 未被接受')
            return False
        t0 = time.monotonic()
        rf = handle.get_result_async()
        rclpy.spin_until_future_complete(self, rf, timeout_sec=self.timeout)
        el = time.monotonic() - t0
        if not rf.done():
            print(f'FAIL: 目标 ({x:.2f},{y:.2f}) 超时 {el:.1f}s')
            handle.cancel_goal_async()
            return False
        status = rf.result().status
        px, py, note = self.pose()
        line = f'  结果: status={status} 耗时={el:.1f}s'
        if px is not None:
            line += (f' 终点=({px:.2f},{py:.2f}){note} '
                     f'位置误差={math.hypot(x-px, y-py):.3f}m')
        print(line, flush=True)
        return status == SUCCEEDED


def main():
    args = sys.argv[1:]
    timeout = 90.0
    points = []
    i = 0
    while i < len(args):
        if args[i] == '--timeout' and i + 1 < len(args):
            timeout = float(args[i + 1])
            i += 2
        elif ',' in args[i]:
            parts = args[i].split(',')
            x, y = float(parts[0]), float(parts[1])
            yaw = float(parts[2]) if len(parts) > 2 else 0.0
            points.append((x, y, yaw))
            i += 1
        else:
            i += 1
    if not points:
        points = list(POINTS)

    rclpy.init()
    node = PointRunner(timeout)
    print(f'共 {len(points)} 个目标点（每点限时 {timeout:.0f}s）：')
    for k, (x, y, yaw) in enumerate(points, 1):
        print(f'  {k}. ({x:.2f}, {y:.2f}, {yaw:.0f}°)')
    ok = 0
    try:
        for k, (x, y, yaw) in enumerate(points, 1):
            print(f'[点 {k}/{len(points)}] 前往 ({x:.2f}, {y:.2f})', flush=True)
            if node.send(x, y, yaw):
                ok += 1
            time.sleep(2.0)
        print(f'完成：{ok}/{len(points)} 个点到达；碰撞事件 {node.collisions} 次')
        return 0 if ok == len(points) else 1
    except KeyboardInterrupt:
        print('\n已中断')
        return 1
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
