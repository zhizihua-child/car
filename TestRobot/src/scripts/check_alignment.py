#!/usr/bin/env python3
# 定位对齐测试桩：统计激光扫描端点落在已建地图中的占据/空闲比例。
# 用法（localization 或 navigation 流程已启动后，另开终端）：
#   python3 src/scripts/check_alignment.py
# 输出：每次采样的占据命中率（端点落在地图占据栅格的比例），以及平均值。
# 退出码：0 = 平均命中率 >= 0.5（说明激光与地图基本重合）；1 = 不达标/无数据。
import math
import sys
import time

import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import (QoSDurabilityPolicy, QoSProfile,
                       QoSReliabilityPolicy)
from rclpy.time import Time
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener

MAX_SAMPLES = 5
MIN_RATIO = 0.5
OCCUPIED = 65


class AlignmentChecker(Node):
    def __init__(self):
        super().__init__(
            'check_alignment_test',
            parameter_overrides=[rclpy.parameter.Parameter(
                'use_sim_time', rclpy.parameter.Parameter.Type.BOOL, True)])
        qos = QoSProfile(depth=1,
                         durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
                         reliability=QoSReliabilityPolicy.RELIABLE)
        self.create_subscription(OccupancyGrid, 'map', self.on_map, qos)
        self.create_subscription(LaserScan, 'scan', self.on_scan, 10)
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.grid = None
        self.results = []
        self.failed_once = False

    def on_map(self, msg):
        self.grid = msg

    def _lookup(self, scan):
        last_exc = None
        for stamp in (Time.from_msg(scan.header.stamp), Time()):
            try:
                return self.buffer.lookup_transform(
                    'map', scan.header.frame_id, stamp,
                    timeout=rclpy.duration.Duration(seconds=0.3))
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        if not self.failed_once:
            self.failed_once = True
            print(f'TF 查询失败: {last_exc}')
            print(self.buffer.all_frames_as_string())
        return None

    def on_scan(self, scan):
        if self.grid is None or len(self.results) >= MAX_SAMPLES:
            return
        info = self.grid.info
        tf = self._lookup(scan)
        if tf is None:
            print('取样失败：无法查询 map -> %s 的 TF' % scan.header.frame_id)
            return
        tx = tf.transform.translation
        q = tf.transform.rotation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                         1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        occ = free = unknown = out = 0
        for i, r in enumerate(scan.ranges):
            if not math.isfinite(r) or r >= scan.range_max * 0.98:
                continue
            a = scan.angle_min + i * scan.angle_increment
            x, y = r * math.cos(a), r * math.sin(a)
            wx = tx.x + x * math.cos(yaw) - y * math.sin(yaw)
            wy = tx.y + x * math.sin(yaw) + y * math.cos(yaw)
            c = int((wx - info.origin.position.x) / info.resolution)
            rr = int((wy - info.origin.position.y) / info.resolution)
            if not (0 <= c < info.width and 0 <= rr < info.height):
                out += 1
                continue
            v = self.grid.data[rr * info.width + c]
            if v < 0:
                unknown += 1
            elif v >= OCCUPIED:
                occ += 1
            else:
                free += 1
        total = occ + free
        ratio = occ / total if total else 0.0
        self.results.append(ratio)
        print(f'采样{len(self.results)}: 命中占据={occ}, 落在空闲={free}, '
              f'未知={unknown}, 地图外={out}, 命中率={ratio:.1%}')


def main():
    rclpy.init()
    node = AlignmentChecker()
    deadline = time.monotonic() + 45.0
    try:
        while (rclpy.ok() and len(node.results) < MAX_SAMPLES
               and time.monotonic() < deadline):
            rclpy.spin_once(node, timeout_sec=0.5)
        if len(node.results) < 3:
            print('FAIL: 有效采样不足（/map 或 /scan 未就绪？）')
            return 1
        avg = sum(node.results) / len(node.results)
        ok = avg >= MIN_RATIO
        print(f'平均命中率={avg:.1%} （阈值 {MIN_RATIO:.0%}）=> '
              + ('PASS' if ok else 'FAIL'))
        return 0 if ok else 1
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
