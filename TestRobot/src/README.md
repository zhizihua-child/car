# TestRobot —— 移动机器人仿真建图与自主导航

基于 **Ubuntu 22.04 + ROS 2 Humble + Gazebo Classic 11** 的差速移动机器人仿真：
自建八边形室内场景，支持手动遥控、SLAM 建图、地图保存/加载、AMCL 定位与 Nav2 自主导航。

**验收指标（本工程实测均达标）**

| 验收项 | 要求 | 本工程 |
| --- | --- | --- |
| 到点位置误差 | ≤ 0.25 m | 到点容差 0.15 m（实测 ≤ 0.16 m） |
| 到点朝向误差 | ≤ 15° | 到点容差 0.20 rad ≈ 11.5° |
| 单目标限时 | ≤ 60 s | 实测 14~35 s |
| 碰撞次数 | < 2 次 | `/bumper_states` 实测 0 次 |
| 激光-地图对齐 | 基本重合 | `check_alignment.py` 实测 100% |

---

## 一、环境与依赖

| 项目 | 版本 |
| --- | --- |
| 系统 | Ubuntu 22.04 LTS |
| ROS 2 | Humble |
| 仿真 | Gazebo Classic 11（gazebo_ros / gazebo_plugins） |
| 建图 | slam_toolbox |
| 导航 | navigation2 / nav2_bringup |

```bash
sudo apt update
sudo apt install -y \
  ros-humble-gazebo-ros-pkgs ros-humble-slam-toolbox \
  ros-humble-navigation2 ros-humble-nav2-bringup \
  ros-humble-teleop-twist-keyboard

# 构建（launch 用 __file__ 动态推导资源路径，仓库可整体搬移）
cd ~/test_ros/logo_ros/TestRobot
colcon build --packages-select TestRobot
source install/setup.bash
```

> 用 `ros2 launch src/launch/...` 从源码启动时，改 config/world/urdf 即时生效；
> 用 `ros2 launch TestRobot ...` 从 install 启动时，需先重新 `colcon build`。

## 二、目录结构

```
TestRobot/
├── run_gazebo.sh               # 一键干净启动 Gazebo（内置全量清理）
├── src/
│   ├── launch/
│   │   ├── gazebo.launch.py        # 场景 + 机器人（可单独遥控）
│   │   ├── mapping.launch.py       # 建图：场景 + slam_toolbox + RViz
│   │   ├── localization.launch.py  # 定位：场景 + 地图 + AMCL + RViz
│   │   └── navigation.launch.py    # 导航：场景 + Nav2 完整栈 + RViz
│   ├── config/
│   │   ├── slam_params.yaml        # slam_toolbox 参数
│   │   ├── nav2_params.yaml        # Nav2 参数（AMCL/代价地图/规划/控制/到点容差）
│   │   ├── mapping.rviz            # 建图用 RViz 配置
│   │   └── navigation.rviz         # 导航用 RViz 配置
│   ├── scripts/                    # 保存地图与自检脚本（见第六节）
│   ├── urdf/                       # 机器人模型（模块化 xacro）
│   ├── worlds/octagon.world        # 场景：八边形围墙 + 十字形 4 圆柱
│   ├── models/mine_world/          # 旧房子场景模型（历史保留，当前 world 未引用）
│   └── maps/map.pgm|yaml           # 已保存地图（八边形场地）
└── ../world_backup/                # 历史场景与地图备份
```

## 三、机器人配置

| 项目 | 说明 |
| --- | --- |
| 底盘 | 差速两轮 + 前后万向轮（`libgazebo_ros_diff_drive.so`） |
| 控制 | `/cmd_vel`（geometry_msgs/Twist） |
| 里程计 | `/odom`（nav_msgs/Odometry）+ TF `odom → base_link`（世界坐标） |
| 激光雷达 | `/scan`（sensor_msgs/LaserScan），360°，10Hz，0.12~8m |
| 摄像头（可选）| `/camera/image_raw`、`/camera/camera_info`，640×480，30Hz |
| 碰撞检测 | `/bumper_states`（gazebo_msgs/ContactsState，车体接触传感器） |
| 坐标系 | `map → odom → base_link → laser_link/...` |
| 场景 | 八边形围墙（外接半径 4.5m）+ 内部十字形 4 圆柱（半径 0.25m、高 0.5m），出生点=场地中心 `(-2.8, -0.5)` |

## 四、快速开始

```bash
cd ~/test_ros/logo_ros/TestRobot && source install/setup.bash
./run_gazebo.sh                 # 场景 + 机器人（自动清理残留进程）
ros2 launch src/launch/mapping.launch.py        # 建图（下一个终端）
ros2 launch src/launch/navigation.launch.py     # 导航（建图保存后重启系统再用）
```

## 五、完整使用流程（按考核顺序）

### 0. 启动前清理（重要）

```bash
cd ~/test_ros/logo_ros/TestRobot
bash src/scripts/clean_all.sh   # 清理 gz/slam/nav2 残留进程（./run_gazebo.sh 已内置）
```

> 独立进程模式下，残留的 amcl/nav2 节点会与本实例重名并用**旧时钟**发布 TF，
> 表现为 `map->odom` 冻结、`Transform data too old`、定位假死、到点误差假大。

### 1. 启动仿真并观察（验收项：仿真启动）

```bash
./run_gazebo.sh                 # 无界面：./run_gazebo.sh gui:=false
# 另开终端自检（期望全部 OK，退出码 0）：
bash src/scripts/check_topics.sh
```

观察：机器人可运动（遥控 `ros2 run teleop_twist_keyboard teleop_twist_keyboard`），
`/scan`、`/odom`、TF `odom→base_link` 正常。

### 2. 建图与保存地图（验收项：地图生成）

```bash
# 终端1：启动建图（Gazebo + slam_toolbox + RViz）
ros2 launch src/launch/mapping.launch.py

# 终端2：遥控（先按几次 z 降速；i 前 , 后 j 左 l 右 k 停）
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

覆盖建议：沿八边形围墙走一圈，再从中心出发绕 4 个圆柱各一圈，回到出生点收尾。
RViz（Fixed Frame=`map`）中墙线连续、通道清晰。

```bash
# 终端3：建图运行中保存（默认覆盖 src/maps/map.pgm|yaml）
bash src/scripts/save_map.sh map
```

验收证据：命令输出 `Map saved successfully` + `src/maps/` 下的 `.pgm/.yaml`。

### 3. 加载地图与定位（验收项：地图加载与定位）

```bash
# 结束建图流程后重新启动：
bash src/scripts/clean_all.sh
ros2 launch src/launch/localization.launch.py    # 自动加载 src/maps/ 第一个 .yaml
```

- RViz 检查：激光点云与地图墙线基本重合、位姿稳定；若初始错位用 **2D Pose Estimate** 重新指定；
- 数值证据（另开终端）：

```bash
bash src/scripts/check_topics.sh          # 期望 OK map->odom
python3 src/scripts/check_alignment.py    # 平均命中率 ≥50% 为 PASS（实测 100%）
```

### 4. 自主导航与到点（验收项：导航执行与到点判定）

```bash
bash src/scripts/clean_all.sh
ros2 launch src/launch/navigation.launch.py      # 等 30~60s 到 lifecycle active

# 就绪确认（终端2）
ros2 lifecycle get /amcl                          # active [3]
ros2 action list | grep navigate_to_pose
```

发送目标点（三种方式任选）：

```bash
# A. RViz：2D Goal Pose 依次点选目标（绿色箭头为朝向）
# B. 命令行单点（会打印耗时/位置误差/朝向误差）
python3 src/scripts/send_nav_goal.py -0.82 1.48 0
# C. 顺序多点脚本（见下一节）
python3 src/scripts/run_points.py
```

判定标准：位置 ≤0.25m、朝向 ≤15°、单点 ≤60s、至少 n-1 个到达、碰撞 <2 次。

### 5. 顺序到点脚本 `run_points.py`（可自己加/改点）

```bash
# 编辑脚本顶部的 POINTS 数组（map 坐标系：x, y, 朝向度），加行即增加目标点
# 或命令行临时指定：
python3 src/scripts/run_points.py "-0.82,1.48,0" "-4.78,-2.48,0" --timeout 120
```

默认 4 个对角点（八边形场地）：

| # | 坐标 (map) | 说明 |
| --- | --- | --- |
| 1 | (-0.82, 1.48) | 东北对角 |
| 2 | (-4.78, -2.48) | 西南对角 |
| 3 | (-4.78, 1.48) | 西北对角 |
| 4 | (-0.82, -2.48) | 东南对角 |

输出：每个点的状态/耗时/到点误差，结束时统计到达数与碰撞事件数。

## 六、自检脚本（测试桩，位于 `src/scripts/`）

| 脚本 | 用途 |
| --- | --- |
| `clean_all.sh` | 清理 gz/slam/nav2 残留进程（启动任何流程前执行） |
| `check_topics.sh` | 检查 `/scan`、`/odom`、TF 链（通过退出码 0） |
| `check_alignment.py` | 激光端点与地图重合度（平均 ≥50% 通过） |
| `send_nav_goal.py` | 发单个目标点，报告状态/耗时/到点误差 |
| `check_nav_rooms.py` | 多目标顺序导航 + 碰撞事件计数 |
| `run_points.py` / `run_points.sh` | 带可编辑点列表的顺序到点运行脚本 |
| `save_map.sh` | 保存当前 SLAM 地图到 `src/maps/` |
| `drive_waypoints.py` | 按路点自动行驶（建图覆盖/验证用，含前向激光保护） |

## 七、参数调整

| 参数 | 文件 | 位置 |
| --- | --- | --- |
| 到点容差（≤0.25m / ≤15°）| `config/nav2_params.yaml` | `general_goal_checker` |
| 最大速度 / 前视距离 | `config/nav2_params.yaml` | `FollowPath` |
| 机器人足迹 / 膨胀半径 | `config/nav2_params.yaml` | 代价地图 `footprint`/`inflation_radius` |
| 初始位姿（须与出生点一致）| `config/nav2_params.yaml` | AMCL `initial_pose` |
| 建图分辨率 / 范围 | `config/slam_params.yaml` | `resolution` / `max_laser_range` |
| 墙高 / 圆柱尺寸 | `worlds/octagon.world` | 模型 `box`/`cylinder` 参数 |

指定文件（不指定时自动取 `src/maps/` 或 `src/worlds/` 下排序第一个）：

```bash
ros2 launch src/launch/navigation.launch.py map:=/abs/path/xxx.yaml world:=/abs/path/xxx.world
```

## 八、常见问题（FAQ）

- **定位假死 / `Transform data too old` / 到点误差异常大**：先 `bash src/scripts/clean_all.sh`
  再启动；这类现象几乎都是残留 Nav2 节点污染 TF/时钟导致。
- **全系统 `use_sim_time: true`**：手动起 rviz2 或分析话题时也要加 `--ros-args -p use_sim_time:=true`。
- **出生点与 AMCL 初始位姿**：`gazebo.launch.py` 默认出生点与 `nav2_params.yaml` 的 AMCL
  `initial_pose` 必须一致（当前均为 `-2.8, -0.5`）；改一处要同步另一处。
- **地图改名**：若重命名 `map.pgm`，须同步修改 `map.yaml` 里的 `image` 字段。
- **TF 树混入无关帧**：多为旧练习的 `robot_state_publisher` 残留，`clean_all.sh` 会一并清理。
- **无界面检查**：launch 加 `gui:=false rviz:=false`；`./run_gazebo.sh gui:=false`。
- **GitHub 推送**：需要代理环境（本项目通过 Clash `127.0.0.1:7897` 配置 git/SSH）。

## 九、提交材料与运行证据

1. 完整工程源代码（本仓库）；2. 地图文件 `src/maps/map.pgm|yaml`；
3. 本 README；4. 运行截图/录屏（建议 ≤3 分钟）：

| 证据 | 内容 | 存放 |
| --- | --- | --- |
| 场景 | Gazebo 八边形场景 + 机器人 | `docs/evidence/` |
| 地图 | 建图过程与保存后的地图（RViz） | `docs/evidence/` |
| 定位对齐 | 激光与地图重合、粒子云 | `docs/evidence/` |
| 路径与到点 | 全局路径、局部避障、到点停车 | `docs/evidence/` |

仓库地址：https://github.com/zhizihua-child/car

## 十、第三方功能包与本工程编写内容

- 第三方（均为 ROS 2 Humble 官方 apt 发行版，未修改源码）：
  `slam_toolbox`、`navigation2 / nav2_bringup`、`gazebo_ros / gazebo_plugins`。
- 本工程编写/配置/集成：机器人 URDF/xacro 与 Gazebo 插件配置、八边形场景 `octagon.world`、
  建图/定位/导航 launch 与参数、RViz 配置、保存地图与自检脚本、README 与开发文档
  （`../../docs/PHASES.md`、`../../docs/DEV_LOG.md`）。
