#!/usr/bin/env python3
# 建图覆盖驾驶测试桩：按给定路点（map 坐标系）用里程计闭环行驶，前向激光保护。
# 用法（mapping.launch.py 运行中，另开终端）：
#   python3 src/scripts/drive_waypoints.py X,Y X,Y ... [--no-spin] [--speed 0.15]
# 说明：
#   - 本仿真中 /odom 位姿为世界坐标（出生点即世界坐标），与地图坐标系一致，
#     因此路点坐标直接作为 odom 坐标使用。
#   - 每个路点：先原地转向对准，再直行；到达后默认原地旋转约 360°（利于建图）。
#   - 前向 0.22m 内检测到障碍：放弃当前路点（打印 BLOCKED）并继续下一个。
#   - 路点坐标应事先用地图自由区校验（避免直线上有墙）。
import math
import sys
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from rclpy.node import Node

BLOCK_DIST = 0.22
ARRIVE = 0.10
WAYPOINT_TIMEOUT = 50.0


class Driver(Node):
    def __init__(self, waypoints, spin=True, speed=0.15, verbose=False):
        super().__init__(
            'drive_waypoints_test',
            parameter_overrides=[rclpy.parameter.Parameter(
                'use_sim_time', rclpy.parameter.Parameter.Type.BOOL, True)])
        self.pub = self.create_publisher(Twist, 'cmd_vel', 10)
        self.create_subscription(Odometry, 'odom', self.on_odom, 10)
        self.create_subscription(LaserScan, 'scan', self.on_scan, 10)
        # 本仿真 /odom 即世界坐标，与地图坐标一致：(x, y) 同时用于控制与显示
        self.wps = [(x, y, x, y) for x, y in waypoints]
        self.spin = spin
        self.speed = speed
        self.pose = None
        self.front = float('inf')
        self.idx = 0
        self.phase = 'rotate'
        self.spin_acc = 0.0
        self.last_yaw = None
        self.seg_start = time.monotonic()
        self.blocked = []
        self.done = False
        self.verbose = verbose
        self.last_print = 0.0
        self.timer = self.create_timer(0.05, self.step)

    def on_odom(self, msg):
        p = msg.pose.pose
        q = p.orientation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                         1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        self.pose = (p.position.x, p.position.y, yaw)

    def on_scan(self, msg):
        lo = msg.angle_min
        inc = msg.angle_increment
        best = float('inf')
        for i, r in enumerate(msg.ranges):
            a = lo + i * inc
            if abs(a) <= math.radians(25.0) and math.isfinite(r) and 0.0 < r < 3.0:
                best = min(best, r)
        self.front = best if best != float('inf') else float('inf')

    def pub_cmd(self, lin, ang):
        msg = Twist()
        msg.linear.x = lin
        msg.angular.z = ang
        self.pub.publish(msg)

    def next_waypoint(self, reason):
        _, _, mx, my = self.wps[self.idx]
        print(f'  [{self.idx + 1}/{len(self.wps)}] ({mx:.2f},{my:.2f}) {reason}', flush=True)
        self.idx += 1
        self.phase = 'rotate'
        self.spin_acc = 0.0
        self.last_yaw = None
        self.seg_start = time.monotonic()
        if self.idx >= len(self.wps):
            self.pub_cmd(0.0, 0.0)
            print(f'完成：到达 {len(self.wps) - len(self.blocked)}/{len(self.wps)} 个路点，'
                  f'BLOCKED={self.blocked}', flush=True)
            self.done = True

    def step(self):
        if self.done or self.pose is None:
            return
        x, y, yaw = self.pose
        _, _, mx, my = self.wps[self.idx]
        tx, ty = self.wps[self.idx][0], self.wps[self.idx][1]
        dx, dy = tx - x, ty - y
        dist = math.hypot(dx, dy)
        heading = math.atan2(dy, dx)
        err = math.atan2(math.sin(heading - yaw), math.cos(heading - yaw))
        elapsed = time.monotonic() - self.seg_start

        now = time.monotonic()
        if self.verbose and now - self.last_print >= 1.0:
            self.last_print = now
            front = 'inf' if self.front == float('inf') else f'{self.front:.2f}'
            print(f'    t={elapsed:4.1f}s pos=({x:5.2f},{y:5.2f}) yaw={math.degrees(yaw):6.1f} '
                  f'target=({mx:5.2f},{my:5.2f}) dist={dist:4.2f} front={front} phase={self.phase}',
                  flush=True)

        if elapsed > WAYPOINT_TIMEOUT:
            self.blocked.append((round(mx, 2), round(my, 2)))
            self.next_waypoint('TIMEOUT')
            return

        if self.phase == 'rotate':
            if abs(err) < 0.08:
                self.phase = 'drive'
            else:
                self.pub_cmd(0.0, max(-0.8, min(0.8, 1.5 * err)))
        elif self.phase == 'drive':
            if dist < ARRIVE:
                if self.spin:
                    self.phase = 'spin'
                    self.last_yaw = yaw
                else:
                    self.next_waypoint('到达')
            elif self.front < BLOCK_DIST:
                self.blocked.append((round(mx, 2), round(my, 2)))
                self.next_waypoint(f'BLOCKED(前向 {self.front:.2f}m)')
            else:
                lin = min(self.speed, max(0.05, 0.6 * dist))
                self.pub_cmd(lin, max(-0.8, min(0.8, 1.0 * err)))
        elif self.phase == 'spin':
            if self.last_yaw is not None:
                dyaw = math.atan2(math.sin(yaw - self.last_yaw),
                                  math.cos(yaw - self.last_yaw))
                self.spin_acc += abs(dyaw)
            self.last_yaw = yaw
            self.pub_cmd(0.0, 0.8)
            if self.spin_acc >= 2.0 * math.pi:
                self.next_waypoint('到达+旋转')


def parse_args(argv):
    wps = []
    spin = True
    speed = 0.15
    verbose = False
    for a in argv:
        if a == '--no-spin':
            spin = False
        elif a == '--verbose':
            verbose = True
        elif a.startswith('--speed='):
            speed = float(a.split('=', 1)[1])
        elif ',' in a:
            x, y = a.split(',')
            wps.append((float(x), float(y)))
        else:
            print(f'未知参数: {a}')
            return None, None, None, None
    if not wps:
        print(__doc__)
        return None, None, None, None
    return wps, spin, speed, verbose


def main():
    wps, spin, speed, verbose = parse_args(sys.argv[1:])
    if not wps:
        return 2
    rclpy.init()
    node = Driver(wps, spin=spin, speed=speed, verbose=verbose)
    print(f'路点 {len(wps)} 个，spin={spin}，speed={speed} m/s', flush=True)
    try:
        while rclpy.ok() and not node.done:
            rclpy.spin_once(node, timeout_sec=0.1)
        return 0 if not node.blocked else 1
    except KeyboardInterrupt:
        return 1
    finally:
        node.pub_cmd(0.0, 0.0)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
