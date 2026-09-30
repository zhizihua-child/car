import os
import re
import xml.etree.ElementTree as ET

import xacro
from launch import LaunchDescription
from launch.actions import LogInfo, TimerAction
from launch_ros.actions import Node

# 要遍历的 urdf 目录（源码布局为 src/urdf，安装布局为 share/TestRobot/urdf）
URDF_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'urdf')
# 根据发现的模型动态生成的 rviz2 配置文件
RVIZ_CONFIG = '/tmp/testrobot_rviz_display.rviz'


def _safe_name(name: str) -> str:
    """把文件名转成合法的 ROS2 命名（小写字母/数字/下划线）"""
    return re.sub(r'[^0-9a-zA-Z_]', '_', name).lower()


def _load_models():
    """遍历 URDF_DIR，把每个 .urdf / .xacro 解析成 URDF 字符串"""
    models = []
    if not os.path.isdir(URDF_DIR):
        print(f'[display_all] 目录不存在：{URDF_DIR}')
        return models

    for file_name in sorted(os.listdir(URDF_DIR)):
        path = os.path.join(URDF_DIR, file_name)
        if not os.path.isfile(path):
            continue
        if not file_name.endswith(('.urdf', '.xacro')):
            continue
        if os.path.getsize(path) == 0:
            print(f'[display_all] 跳过空文件：{file_name}')
            continue

        try:
            urdf_xml = xacro.process_file(path).toxml()
            robot = ET.fromstring(urdf_xml)
        except Exception as exc:
            print(f'[display_all] 跳过 {file_name}：解析失败（{exc}）')
            continue

        if robot.tag != 'robot':
            print(f'[display_all] 跳过 {file_name}：缺少 <robot> 根标签')
            continue

        links = [link.get('name') for link in robot.findall('link')]
        if not links:
            print(f'[display_all] {file_name}：模块文件（只含宏定义），'
                  f'由总装配文件引用，不单独显示')
            continue

        children = set()
        for joint in robot.findall('joint'):
            child = joint.find('child')
            if child is not None:
                children.add(child.get('link'))

        root_links = [link for link in links if link not in children]
        root_link = root_links[0] if root_links else links[0]

        has_movable_joint = any(
            joint.get('type') != 'fixed' for joint in robot.findall('joint'))

        models.append({
            'file': file_name,
            'name': _safe_name(file_name.split('.')[0]),
            'urdf': urdf_xml,
            'root_link': root_link,
            'has_movable_joint': has_movable_joint,
        })

    return models


def _write_rviz_config(models):
    """为每个模型生成一个 RobotModel 显示，固定坐标系统一用 world"""
    displays = [
        '    - Class: rviz_default_plugins/Grid\n'
        '      Enabled: true\n'
        '      Name: Grid\n'
        '      Value: true\n'
    ]

    for model in models:
        displays.append(
            '    - Class: rviz_default_plugins/RobotModel\n'
            '      Description Source: Topic\n'
            '      Description Topic:\n'
            '        Depth: 5\n'
            '        Durability Policy: Volatile\n'
            '        History Policy: Keep Last\n'
            '        Reliability Policy: Reliable\n'
            f'        Value: /{model["name"]}/robot_description\n'
            '      Enabled: true\n'
            '      Mass Properties:\n'
            '        Inertia: true\n'
            '        Mass: true\n'
            f'      Name: {model["name"]}\n'
            f'      TF Prefix: {model["name"]}\n'
            '      Value: true\n'
        )

    config = (
        'Panels:\n'
        '  - Class: rviz_common/Displays\n'
        '    Name: Displays\n'
        'Visualization Manager:\n'
        '  Class: ""\n'
        '  Displays:\n'
        + ''.join(displays) +
        '  Global Options:\n'
        '    Background Color: 48; 48; 48\n'
        '    Fixed Frame: world\n'
        '    Frame Rate: 30\n'
        '  Name: root\n'
        '  Tools:\n'
        '    - Class: rviz_default_plugins/MoveCamera\n'
        '    - Class: rviz_default_plugins/FocusCamera\n'
        '    - Class: rviz_default_plugins/Measure\n'
        '      Line color: 128; 128; 0\n'
        '  Value: true\n'
        'Window Geometry:\n'
        '  Height: 800\n'
        '  Width: 1200\n'
    )

    with open(RVIZ_CONFIG, 'w', encoding='utf-8') as f:
        f.write(config)
    return RVIZ_CONFIG


def generate_launch_description():
    models = _load_models()
    actions = []

    if not models:
        actions.append(LogInfo(msg='[display_all] urdf 目录下没有可用的模型'))
    else:
        actions.append(LogInfo(
            msg=f'[display_all] 共发现 {len(models)} 个模型：'
                f'{[m["name"] for m in models]}'))

    for index, model in enumerate(models):
        name = model['name']
        # RViz 的 TF Prefix 会自动拼成 "<prefix>/<link>"，所以 TF 这边也要用 "/" 分隔，
        # 保证 TF 帧名 robot/base_link 与 RViz 查找的名字一致
        frame_prefix = name + '/'
        root_frame = frame_prefix + model['root_link']

        # 1. 每个模型一个 robot_state_publisher，用 namespace + frame_prefix 避免帧名冲突
        actions.append(Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            namespace=name,
            name='robot_state_publisher',
            parameters=[{
                'robot_description': model['urdf'],
                'frame_prefix': frame_prefix,
            }],
            output='screen',
        ))

        # 2. 把模型的根 link 挂到公共的 world 坐标系下，多个模型并排摆放
        actions.append(Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            namespace=name,
            name=f'world_to_{name}',
            arguments=[
                '--x', str(index * 0.5), '--y', '0', '--z', '0',
                '--frame-id', 'world',
                '--child-frame-id', root_frame,
            ],
            output='log',
        ))

        # 3. 有活动关节的模型才需要 joint_state_publisher
        if model['has_movable_joint']:
            actions.append(Node(
                package='joint_state_publisher',
                executable='joint_state_publisher',
                namespace=name,
                output='log',
            ))

    # 4. 延迟 3 秒再启动 rviz2：
    #    robot_state_publisher / static_transform_publisher 的 /tf_static 是"锁存只发一次"，
    #    RViz 若与它们同时启动，可能因 DDS 发现竞态错过静态变换，从而报 "No transform ... to [world]"。
    actions.append(TimerAction(
        period=3.0,
        actions=[Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', _write_rviz_config(models)],
            output='screen',
        )],
    ))

    return LaunchDescription(actions)
