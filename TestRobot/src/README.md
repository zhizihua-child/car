# TestRobot —— 移动机器人仿真建图与导航

基于 **Ubuntu 22.04 + ROS 2 Humble + Gazebo Classic 11** 的差速移动机器人仿真，
支持：手动遥控、激光 SLAM 建图、地图保存、AMCL 定位、Nav2 自主导航。

## 一、软件版本与依赖

| 项目 | 版本 |
| --- | --- |
| 系统 | Ubuntu 22.04 LTS |
| ROS 2 | Humble |
| 仿真 | Gazebo Classic 11（gazebo_ros / gazebo_plugins）|
| 建图 | slam_toolbox |
| 导航 | navigation2 / nav2_bringup |

安装依赖：

```bash
sudo apt update
sudo apt install -y \
  ros-humble-gazebo-ros-pkgs ros-humble-slam-toolbox \
  ros-humble-navigation2 ros-humble-nav2-bringup \
  ros-humble-teleop-twist-keyboard
```

构建工作空间：

```bash
cd ~/test_ros/logo_ros/TestRobot
colcon build --packages-select TestRobot
source install/setup.bash
```

> launch 文件用 `__file__` 动态推导资源路径，仓库可整体搬移（换目录/换机器克隆后无需改路径）。
> 用 `ros2 launch src/launch/...` 从源码启动时，改 config/world/urdf 即时生效；
> 用 `ros2 launch TestRobot ...` 从 install 启动时，需先重新 `colcon build`。

## 二、目录结构

```
src/
├── launch/
│   ├── gazebo.launch.py        # Gazebo 场景 + 机器人（可单独手动遥控）
│   ├── mapping.launch.py       # 建图：场景 + slam_toolbox + RViz
│   ├── localization.launch.py  # 定位：场景 + 地图 + AMCL + RViz
│   └── navigation.launch.py    # 导航：场景 + Nav2 完整栈 + RViz
├── config/
│   ├── slam_params.yaml        # slam_toolbox 参数
│   ├── nav2_params.yaml        # Nav2 参数（AMCL/代价地图/规划/控制）
│   ├── mapping.rviz            # 建图用 RViz 配置
│   └── navigation.rviz         # 导航用 RViz 配置
├── scripts/
│   ├── save_map.sh             # 保存地图脚本
│   ├── check_topics.sh         # 自检（测试桩）：话题与 TF 链
│   ├── check_alignment.py      # 自检（测试桩）：激光端点与地图重合度
│   ├── send_nav_goal.py        # 自检（测试桩）：发目标点并报告到点误差
│   ├── check_nav_rooms.py      # 自检（测试桩）：多目标导航 + 碰撞事件计数
│   └── drive_waypoints.py      # 自检（测试桩）：按路点自动行驶（建图覆盖/验证）
├── urdf/                       # 机器人模型（模块化 xacro）
├── models/mine_world/          # 自定义场景模型
├── worlds/mine.world           # 仿真世界
└── maps/                       # 保存的地图（.pgm + .yaml）
```

## 三、机器人配置

| 项目 | 说明 |
| --- | --- |
| 底盘 | 差速两轮 + 前后万向轮（`libgazebo_ros_diff_drive.so`）|
| 控制 | `/cmd_vel`（geometry_msgs/Twist）|
| 里程计 | `/odom`（nav_msgs/Odometry）+ TF `odom → base_link` |
| 激光雷达 | `/scan`（sensor_msgs/LaserScan），360°，10Hz，0.12~8m |
| 摄像头（可选）| `/camera/image_raw`、`/camera/camera_info`，640×480，30Hz |
| 碰撞检测（验收自检）| `/bumper_states`（gazebo_msgs/ContactsState），base_link 接触传感器 |
| 坐标系 | `map → odom → base_link → laser_link/...` |

## 四、使用流程

### 0. 一键干净启动（推荐）

```bash
cd ~/test_ros/logo_ros/TestRobot
./run_gazebo.sh              # 先清理残留 Gazebo，再启动场景+机器人
```

手动遥控（另开终端）：

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
# i 前进  , 后退  j 左转  l 右转  k 停止（终端需保持焦点）
```

### 1. 建图（SLAM）

```bash
ros2 launch src/launch/mapping.launch.py
```

- 打开 RViz：Fixed Frame = `map`，可看到不断生长的栅格地图
- 用遥控驱动机器人覆盖场景
- 地图建好后，**另开终端**保存：

```bash
bash src/scripts/save_map.sh          # 保存为 src/maps/map.pgm + map.yaml
```

### 2. 定位（加载地图 + AMCL）

```bash
ros2 launch src/launch/localization.launch.py
```

- 在 RViz 中检查：地图、激光点云、机器人位姿是否基本重合
- 若初始位置不对：RViz 左上角 **2D Pose Estimate** 在地图上点选机器人实际位姿

### 3. 自主导航（Nav2）

```bash
ros2 launch src/launch/navigation.launch.py
```

- 在 RViz 用 **2D Goal Pose** 指定目标点（绿色箭头为朝向）
- 观察：全局路径（绿线）、局部代价地图（避障）、机器人到点停车

也可以用命令行发目标点：

```bash
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
  "{pose: {header: {frame_id: map}, pose: {position: {x: 1.0, y: 0.0}, orientation: {w: 1.0}}}}"
```

## 五、常用命令

```bash
# 查看话题/频率
ros2 topic list
ros2 topic hz /scan
ros2 topic echo /odom

# 查看 TF 树
ros2 run tf2_tools view_frames

# 检查导航节点状态
ros2 lifecycle get /amcl
ros2 lifecycle get /controller_server
```

## 六、自检脚本（测试桩）

```bash
# 1) 仿真/建图/定位/导航运行中：检查 /scan、/odom、TF 链（通过退出码 0）
bash src/scripts/check_topics.sh

# 2) 定位或导航运行中：统计激光端点落在地图占据栅格的比例（平均 ≥50% 为通过）
python3 src/scripts/check_alignment.py

# 3) 导航运行中：发送单个目标点并报告耗时/位置误差/朝向误差（SUCCEEDED 退出码 0）
python3 src/scripts/send_nav_goal.py X Y [YAW_DEG]

# 4) 建图运行中：按给定路点（map 坐标）自动行驶，前向激光保护（到达全部路点退出码 0）
python3 src/scripts/drive_waypoints.py X,Y X,Y ... [--no-spin] [--verbose]

# 5) 导航运行中：依次发多个目标点并统计成功/误差/碰撞事件（全部到达且碰撞<2 退出码 0）
python3 src/scripts/check_nav_rooms.py X,Y X,Y ... [--timeout 秒]
```

开发阶段与验收步骤见 `../../docs/PHASES.md`，改动记录见 `../../docs/DEV_LOG.md`。

## 七、参数调整

| 参数 | 文件 | 位置 |
| --- | --- | --- |
| 目标容差（≤0.25m / ≤15°）| `config/nav2_params.yaml` | `general_goal_checker` |
| 最大速度 | `config/nav2_params.yaml` | `FollowPath.desired_linear_vel` |
| 机器人半径 | `config/nav2_params.yaml` | 代价地图 `robot_radius` |
| 建图分辨率 | `config/slam_params.yaml` | `resolution` |
| 墙高 / 场景 | `worlds/mine.world` | 场景模型内 |

## 八、本工程编写与集成说明

- 机器人模型（URDF/xacro）、Gazebo 插件配置、场景 world、建图/定位/导航 launch
  与参数、RViz 配置、保存地图脚本均为本工程编写。
- 第三方功能包：`slam_toolbox`、`navigation2`、`gazebo_ros`（均为 ROS 2 Humble 官方发行版），
  通过 apt 安装，未修改其源码。
