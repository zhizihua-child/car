import os

import launch
import launch_ros
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory

# 本包资源根目录：源码布局为 <ws>/src，安装布局为 install/.../share/TestRobot
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def generate_launch_description():
    declare_gui = launch.actions.DeclareLaunchArgument('gui', default_value='true')
    declare_rviz = launch.actions.DeclareLaunchArgument('rviz', default_value='true')

    # 1. Gazebo 场景 + 机器人（复用 gazebo.launch.py）
    gazebo = launch.actions.IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(SRC_DIR, 'launch', 'gazebo.launch.py')),
        launch_arguments=[('gui', launch.substitutions.LaunchConfiguration('gui'))])

    # 2. SLAM 建图（slam_toolbox 在线异步）
    slam = launch.actions.IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(
            get_package_share_directory('slam_toolbox'), 'launch', 'online_async_launch.py')]),
        launch_arguments=[
            ('slam_params_file', os.path.join(SRC_DIR, 'config', 'slam_params.yaml')),
            ('use_sim_time', 'true'),
        ])

    # 3. RViz（显示地图 / 激光 / 机器人）
    rviz = launch_ros.actions.Node(
        package='rviz2', executable='rviz2', name='rviz2',
        arguments=['-d', os.path.join(SRC_DIR, 'config', 'mapping.rviz')],
        output='screen',
        condition=launch.conditions.IfCondition(
            launch.substitutions.LaunchConfiguration('rviz')))

    return launch.LaunchDescription([
        declare_gui,
        declare_rviz,
        gazebo,
        slam,
        rviz,
    ])
