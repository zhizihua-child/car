#!/usr/bin/env python3
# 导航验收测试桩：发送单个 Nav2 目标点并报告结果。
# 用法（导航流程已启动后，另开终端）：
#   python3 src/scripts/send_nav_goal.py X Y [YAW_DEG]
# 参数：map 坐标系下的目标位置（m）与朝向（度，默认 0）。
# 输出：action 状态、耗时、到点后的位置误差/朝向误差，并写入 DEV_LOG 时可作证据。
# 退出码：0 = SUCCEEDED；1 = 失败/超时。
import math
import sys
import time

import rclpy
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from tf2_ros import Buffer, TransformListener

SUCCEEDED = 4  # action_msgs/msg/GoalStatus.STATUS_SUCCEEDED


class GoalSender(Node):
    def __init__(self):
        super().__init__(
            'send_nav_goal_test',
            parameter_overrides=[rclpy.parameter.Parameter(
                'use_sim_time', rclpy.parameter.Parameter.Type.BOOL, True)])
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)

    def send(self, x, y, yaw_deg):
        if not self.client.wait_for_server(timeout_sec=15.0):
            print('FAIL: /navigate_to_pose 服务不可用（Nav2 是否已启动？）')
            return 1

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y
        yaw = math.radians(yaw_deg)
        goal.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(yaw / 2.0)

        t0 = time.monotonic()
        handle = None
        for attempt in (1, 2):
            future = self.client.send_goal_async(goal)
            deadline = time.monotonic() + 15.0
            while rclpy.ok() and not future.done() and time.monotonic() < deadline:
                rclpy.spin_once(self, timeout_sec=0.1)
            if future.done():
                handle = future.result()
                break
            print(f'WARN: 目标响应超时（第 {attempt} 次），{"重试" if attempt == 1 else "放弃"}')
        if handle is None:
            print('FAIL: 目标未被响应（action server 无响应）')
            return 1
        if not handle.accepted:
            print('FAIL: 目标被拒绝')
            return 1

        result_future = handle.get_result_async()
        try:
            rclpy.spin_until_future_complete(self, result_future)
        except (KeyboardInterrupt, ExternalShutdownException):
            print(f'目标 ({x:.2f}, {y:.2f}) 被中断（未在限时内完成）')
            return 1
        elapsed = time.monotonic() - t0
        status = result_future.result().status

        line = (f'目标 ({x:.2f}, {y:.2f}, {yaw_deg:.0f}deg): status={status}, '
                f'耗时={elapsed:.1f}s')
        try:
            deadline = time.monotonic() + 5.0
            tf = None
            while time.monotonic() < deadline:
                try:
                    tf = self.buffer.lookup_transform('map', 'base_link',
                                                      rclpy.time.Time())
                    break
                except Exception:
                    rclpy.spin_once(self, timeout_sec=0.2)
            if tf is not None:
                t = tf.transform.translation
                q = tf.transform.rotation
                cur_yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                                     1.0 - 2.0 * (q.y * q.y + q.z * q.z))
                err_xy = math.hypot(x - t.x, y - t.y)
                err_yaw = abs(math.atan2(math.sin(yaw - cur_yaw),
                                         math.cos(yaw - cur_yaw)))
                line += (f', 终点=({t.x:.2f}, {t.y:.2f}), '
                         f'位置误差={err_xy:.3f}m, 朝向误差={math.degrees(err_yaw):.1f}deg')
        except Exception as exc:  # noqa: BLE001
            line += f', (无法读取 TF: {exc})'
        print(line)
        return 0 if status == SUCCEEDED else 1


def main():
    if len(sys.argv) not in (3, 4):
        print(__doc__ or '用法: send_nav_goal.py X Y [YAW_DEG]')
        return 2
    x, y = float(sys.argv[1]), float(sys.argv[2])
    yaw_deg = float(sys.argv[3]) if len(sys.argv) == 4 else 0.0
    rclpy.init()
    node = GoalSender()
    try:
        return node.send(x, y, yaw_deg)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
