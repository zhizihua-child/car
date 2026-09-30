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


def generate_launch_description():
    declare_gui = launch.actions.DeclareLaunchArgument('gui', default_value='true')
    declare_rviz = launch.actions.DeclareLaunchArgument('rviz', default_value='true')
    declare_map = launch.actions.DeclareLaunchArgument(
        'map', default_value=_find_default_map(),
        description='地图 yaml 路径；默认自动用 src/maps/ 下第一个 .yaml')

    # 1. Gazebo 场景 + 机器人
    gazebo = launch.actions.IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(SRC_DIR, 'launch', 'gazebo.launch.py')),
        launch_arguments=[('gui', launch.substitutions.LaunchConfiguration('gui'))])

    # 2. Nav2 完整导航（地图 + AMCL 定位 + 全局规划 + 局部避障 + 行为树）
    nav2 = launch.actions.IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(
            get_package_share_directory('nav2_bringup'), 'launch', 'bringup_launch.py')]),
        launch_arguments=[
            ('slam', 'False'),
            ('map', launch.substitutions.LaunchConfiguration('map')),
            ('use_sim_time', 'true'),
            ('params_file', os.path.join(SRC_DIR, 'config', 'nav2_params.yaml')),
            ('autostart', 'true'),
        ])

    # 3. RViz（地图 / 代价地图 / 全局路径 / 粒子云）
    rviz = launch_ros.actions.Node(
        package='rviz2', executable='rviz2', name='rviz2',
        arguments=['-d', os.path.join(SRC_DIR, 'config', 'navigation.rviz')],
        output='screen',
        condition=launch.conditions.IfCondition(
            launch.substitutions.LaunchConfiguration('rviz')))

    return launch.LaunchDescription([
        declare_gui,
        declare_rviz,
        declare_map,
        gazebo,
        nav2,
        rviz,
    ])
