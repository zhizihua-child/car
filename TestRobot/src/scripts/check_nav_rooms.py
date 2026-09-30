#!/usr/bin/env python3
# 房间导航验收测试桩：依次发送多个目标点，统计成功/耗时/误差与碰撞事件数。
# 用法（导航流程运行中，另开终端）：
#   python3 src/scripts/check_nav_rooms.py X,Y X,Y ... [--timeout 秒]
# 说明：
#   - 目标是 map 坐标系；建议给房间内绕方块的点，覆盖直行/转弯/绕障。
#   - 碰撞事件 = /bumper_states（base_link 接触传感器）连续有接触记 1 次。
#   - 退出码：0 = 全部到达且碰撞事件 <2；1 = 否则。
import math
import sys
import time

import rclpy
from gazebo_msgs.msg import ContactsState
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from tf2_ros import Buffer, TransformListener

SUCCEEDED = 4


class RoomNavTest(Node):
    def __init__(self, timeout):
        super().__init__(
            'check_nav_rooms',
            parameter_overrides=[rclpy.parameter.Parameter(
                'use_sim_time', rclpy.parameter.Parameter.Type.BOOL, True)])
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.buf = Buffer()
        self.listener = TransformListener(self.buf, self)
        self.create_subscription(ContactsState, 'bumper_states', self.on_bump, 10)
        self.timeout = timeout
        self.collisions = 0
        self.in_contact = False
        self.ok_count = 0
        self.total = 0

    def on_bump(self, msg):
        has = len(msg.states) > 0
        if has and not self.in_contact:
            self.collisions += 1
            print(f'  [碰撞事件 #{self.collisions}]', flush=True)
        self.in_contact = has

    def pose(self):
        try:
            tf = self.buf.lookup_transform('map', 'base_link', rclpy.time.Time())
            return tf.transform.translation.x, tf.transform.translation.y
        except Exception:  # noqa: BLE001
            return None

    def send(self, x, y):
        if not self.client.wait_for_server(timeout_sec=15.0):
            print('FAIL: /navigate_to_pose 不可用（Nav2 是否已启动？）')
            return False
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y
        goal.pose.pose.orientation.w = 1.0
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
        line = f'目标 ({x:.2f},{y:.2f}): status={status} 耗时={el:.1f}s'
        p = self.pose()
        if p is not None:
            line += (f' 终点=({p[0]:.2f},{p[1]:.2f}) '
                     f'位置误差={math.hypot(x-p[0], y-p[1]):.3f}m')
        print(line, flush=True)
        return status == SUCCEEDED


def main():
    args = sys.argv[1:]
    timeout = 120.0
    goals = []
    i = 0
    while i < len(args):
        if args[i] == '--timeout' and i + 1 < len(args):
            timeout = float(args[i + 1])
            i += 2
        elif ',' in args[i]:
            x, y = args[i].split(',')
            goals.append((float(x), float(y)))
            i += 1
        else:
            i += 1
    if not goals:
        print(__doc__)
        return 2
    rclpy.init()
    node = RoomNavTest(timeout)
    node.total = len(goals)
    try:
        for x, y in goals:
            print(f'=== 目标 ({x:.2f},{y:.2f}) ===', flush=True)
            if node.send(x, y):
                node.ok_count += 1
            time.sleep(2.0)
        print(f'汇总: 成功 {node.ok_count}/{node.total}; 碰撞事件 {node.collisions} 次')
        return 0 if node.ok_count == node.total and node.collisions < 2 else 1
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
