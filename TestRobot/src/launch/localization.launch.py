import os

import launch
import launch_ros
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory

# 本包资源根目录：源码布局为 <ws>/src，安装布局为 install/.../share/TestRobot
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS_DIR = os.path.join(SRC_DIR, 'maps')


def _find_default_map():
    """自动使用 src/maps/ 下第一个 .yaml 地图（按文件名排序）"""
    if os.path.isdir(MAPS_DIR):
        maps = sorted(f for f in os.listdir(MAPS_DIR) if f.endswith('.yaml'))
        if maps:
            return os.path.join(MAPS_DIR, maps[0])
    return ''



# world 默认值：src/worlds/ 下排序第一个 .world（可用 world:= 覆盖）
WORLDS_DIR = os.path.join(SRC_DIR, 'worlds')


def _find_default_world():
    if os.path.isdir(WORLDS_DIR):
        worlds = sorted(f for f in os.listdir(WORLDS_DIR) if f.endswith('.world'))
        if worlds:
            return os.path.join(WORLDS_DIR, worlds[0])
    return '/usr/share/gazebo-11/worlds/empty.world'

def generate_launch_description():
    declare_gui = launch.actions.DeclareLaunchArgument('gui', default_value='true')
    declare_world = launch.actions.DeclareLaunchArgument(
        'world', default_value=_find_default_world(),
        description='world 文件路径；默认 src/worlds/ 下第一个 .world')
    declare_rviz = launch.actions.DeclareLaunchArgument('rviz', default_value='true')
    declare_map = launch.actions.DeclareLaunchArgument(
        'map', default_value=_find_default_map(),
        description='地图 yaml 路径；默认自动用 src/maps/ 下第一个 .yaml')

    # 1. Gazebo 场景 + 机器人
    gazebo = launch.actions.IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(SRC_DIR, 'launch', 'gazebo.launch.py')),
        launch_arguments=[
            ('gui', launch.substitutions.LaunchConfiguration('gui')),
            ('world', launch.substitutions.LaunchConfiguration('world'))])

    # 2. 地图服务 + AMCL 定位（nav2_bringup 官方 launch）
    localization = launch.actions.IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(
            get_package_share_directory('nav2_bringup'), 'launch', 'localization_launch.py')]),
        launch_arguments=[
            ('map', launch.substitutions.LaunchConfiguration('map')),
            ('use_sim_time', 'true'),
            ('params_file', os.path.join(SRC_DIR, 'config', 'nav2_params.yaml')),
            ('autostart', 'true'),
        ])

    # 3. RViz（地图 / 激光 / 粒子云对齐检查）
    rviz = launch_ros.actions.Node(
        package='rviz2', executable='rviz2', name='rviz2',
        arguments=['-d', os.path.join(SRC_DIR, 'config', 'navigation.rviz')],
        output='screen',
        condition=launch.conditions.IfCondition(
            launch.substitutions.LaunchConfiguration('rviz')))

    return launch.LaunchDescription([
        declare_gui,
        declare_world,
        declare_rviz,
        declare_map,
        gazebo,
        localization,
        rviz,
    ])
