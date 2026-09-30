import os

import launch
import launch_ros
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory

# 本包资源根目录：源码布局为 <ws>/src，安装布局为 install/.../share/TestRobot，
# 两种布局下都含 launch/urdf/worlds/models/config/maps/scripts（用 __file__ 推导，仓库可整体搬移）
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(SRC_DIR, 'models')
WORLDS_DIR = os.path.join(SRC_DIR, 'worlds')
URDF_FILE = os.path.join(SRC_DIR, 'urdf', 'Robot.urdf.xacro')

# worlds/ 目录为空时的兜底：Gazebo 自带的空世界
GAZEBO_EMPTY_WORLD = '/usr/share/gazebo-11/worlds/empty.world'


def _find_default_world():
    """自动使用 src/worlds/ 目录下第一个 .world 文件（按文件名排序）"""
    if os.path.isdir(WORLDS_DIR):
        worlds = sorted(f for f in os.listdir(WORLDS_DIR) if f.endswith('.world'))
        if worlds:
            return os.path.join(WORLDS_DIR, worlds[0])
    return GAZEBO_EMPTY_WORLD


def generate_launch_description():
    # 声明可调参数（默认出生点：房子中央大厅内，四周留足转向余量）
    declare_x = launch.actions.DeclareLaunchArgument('x', default_value='-2.8')
    declare_y = launch.actions.DeclareLaunchArgument('y', default_value='-0.5')
    declare_z = launch.actions.DeclareLaunchArgument('z', default_value='0.2')
    declare_gui = launch.actions.DeclareLaunchArgument('gui', default_value='true')
    # world 参数：默认自动扫描 src/worlds/*.world，也可以在命令行覆盖
    declare_world = launch.actions.DeclareLaunchArgument(
        'world',
        default_value=_find_default_world(),
        description='world 文件路径；默认自动使用 src/worlds/ 下第一个 .world')

    # 让 Gazebo 能找到 model://xxx 和 ~/.gazebo/models 里的家具；
    # 注意要拼上 Gazebo 默认模型路径，否则 sun/ground_plane/家具 都会找不到
    default_models_path = '/usr/share/gazebo-11/models'
    user_models_path = os.path.expanduser('~/.gazebo/models')
    set_model_path = launch.actions.SetEnvironmentVariable(
        'GAZEBO_MODEL_PATH',
        MODELS_DIR + ':' + default_models_path + ':' + user_models_path)

    # 禁用在线模型库（避免启动时卡在 models.gazebosim.org 下载）
    disable_model_db = launch.actions.SetEnvironmentVariable(
        'GAZEBO_MODEL_DATABASE_URI', '')

    # 提示当前用的是哪个 world
    log_world = launch.actions.LogInfo(
        msg=['[gazebo] 使用的 world: ', launch.substitutions.LaunchConfiguration('world')])

    # 用 xacro 展开机器人描述，交给 robot_state_publisher
    robot_description = launch_ros.parameter_descriptions.ParameterValue(
        launch.substitutions.Command(['xacro ', URDF_FILE]),
        value_type=str)

    robot_state_publisher_node = launch_ros.actions.Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description,
                     'use_sim_time': True}],
    )

    # 启动 Gazebo（带选定的 world）
    launch_gazebo = launch.actions.IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(
            get_package_share_directory('gazebo_ros'), 'launch', 'gazebo.launch.py')]),
        launch_arguments=[
            ('world', launch.substitutions.LaunchConfiguration('world')),
            ('gui', launch.substitutions.LaunchConfiguration('gui')),
            ('verbose', 'true'),
        ],
    )

    # 把小车的 URDF 加载进 Gazebo（出生点由 x/y/z 参数决定）
    spawn_entity_node = launch_ros.actions.Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=[
            '-topic', '/robot_description',
            '-entity', 'robot',
            '-x', launch.substitutions.LaunchConfiguration('x'),
            '-y', launch.substitutions.LaunchConfiguration('y'),
            '-z', launch.substitutions.LaunchConfiguration('z'),
        ],
        output='screen',
    )

    return launch.LaunchDescription([
        declare_x,
        declare_y,
        declare_z,
        declare_gui,
        declare_world,
        set_model_path,
        disable_model_db,
        log_world,
        robot_state_publisher_node,
        launch_gazebo,
        spawn_entity_node,
    ])
