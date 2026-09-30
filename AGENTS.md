# AGENTS.md — logo_ros / TestRobot

ROS 2 Humble + Gazebo Classic 11 移动机器人仿真项目（建图 / 定位 / Nav2 导航考核）。
工作目录为 `/home/yfc/test_ros/logo_ros`；`chap3/`、`chap4/`、`chap6/` 是无关的旧练习工作空间，不要改动。

## 结构与构建

- colcon 工作空间根目录是 `TestRobot/`，ROS 包根目录是 `TestRobot/src`（包名 `TestRobot`，ament_cmake，只安装文件、无编译代码）。
- 构建：`cd TestRobot && colcon build --packages-select TestRobot && source install/setup.bash`。
- launch 用 `__file__` 动态推导资源根目录（源码布局 `<ws>/src`，安装布局 `share/TestRobot`），仓库可整体搬移，不要改回硬编码绝对路径。
- 改 launch/config/world/urdf/maps 后，从 `ros2 launch src/launch/...` 启动即时生效；`ros2 launch TestRobot ...`（install 布局）需先重新 `colcon build`。
- 文档：`docs/PHASES.md`（开发阶段与验收）、`docs/DEV_LOG.md`（开发日志）；运行时自检 `TestRobot/src/scripts/check_topics.sh`。

## 常用命令（除注明外均在 `TestRobot/` 下执行）

- 干净启动 Gazebo：`./run_gazebo.sh`（先杀残留 gzserver/gzclient 并检查端口 11345；`gui:=false` 无界面，`x:= y:= z:=` 指定出生点）。
- 建图：`ros2 launch src/launch/mapping.launch.py`；保存地图（另开终端，建图运行中）：`bash src/scripts/save_map.sh [名字]`，默认写 `src/maps/map.pgm|yaml`。
- 定位：`ros2 launch src/launch/localization.launch.py`；导航：`ros2 launch src/launch/navigation.launch.py`。无头检查加 `gui:=false rviz:=false`。
- 指定地图：`map:=/abs/path/xxx.yaml`；不指定时自动取 `src/maps/` 下排序第一个 `.yaml`（world 同理取 `src/worlds/` 第一个 `.world`）。
- 遥控：`ros2 run teleop_twist_keyboard teleop_twist_keyboard`。
- 发导航目标：`ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose "{pose: {header: {frame_id: map}, pose: {position: {x: 1.0, y: 0.0}, orientation: {w: 1.0}}}}"`
- 自检（测试桩）：`bash src/scripts/check_topics.sh`，检查 /scan、/odom、TF 链；通过时退出码 0，无仿真运行时话题/TF 报 FAIL 属正常。

## 必须知道的坑

- 全系统 `use_sim_time: true`。手动起 rviz2 或分析话题时也要 `--ros-args -p use_sim_time:=true`，否则时间轴对不上、数据不显示。
- 出生点 `gazebo.launch.py` 默认 `x=-2.8 y=-0.5 z=0.2` 必须与 `config/nav2_params.yaml` 中 AMCL 的 `initial_pose` 一致（Gazebo 里程计从出生点世界坐标起算）。改一处必须同步另一处。
- 到点阈值在 `config/nav2_params.yaml` 的 `general_goal_checker`：`xy_goal_tolerance: 0.2`（要求 ≤0.25m）、`yaw_goal_tolerance: 0.26` rad（≈14.9°，要求 ≤15°）。
- `map_server.yaml_filename` 是占位符，实际地图由 nav2_bringup launch 的 `map` 参数覆盖，不要在那里硬编码路径。
- 场景模型依赖 `GAZEBO_MODEL_PATH`（launch 已设置）：`src/models` + `/usr/share/gazebo-11/models` + `~/.gazebo/models`。缺模型报错先查这三个目录（`number1..9`、`cafe_table`、`bookshelf` 在 `~/.gazebo/models`）。
- 当前 URDF 无 IMU、无 world→base_link TF；根目录 `frames_*.gv/pdf` 是旧 TF 快照（含 `imu_link`），不要当现状依据。
- 旧练习残留的 `robot_state_publisher`（`first_robot` 模型）会往 TF 里混入 `imu_link` 等无关帧；排查 TF 异常前先 `pkill -f '[r]obot_state_publisher'`（方括号防止 pkill 匹配到当前命令行而杀掉自己）。
- `world_backup/`、`src/worlds/*.bak*`、`src/models/*.bak*` 是历史快照，编辑时不要改错文件。
- `colcon test` 只跑 ament lint，没有功能性测试；功能验证只能靠实际启动 + 话题/TF/RViz/动作结果检查。

## 开发规范（用户要求）

- 不臆想：任何结论必须有代码、命令输出或日志依据；信息不足先向用户提问，不猜测。
- 每次改动前在 `docs/DEV_LOG.md` 追加条目（日期、目标、改动文件、执行命令、结果证据），完成后补结果。
- 按 `docs/PHASES.md` 的阶段推进，每阶段结束执行对应验收命令并留存输出/截图证据。
- 每阶段结束把证据（指标/日志路径 + 需目视确认的清单）交用户审查，确认后记入 `docs/DEV_LOG.md` 再进入下一阶段；自动测试不代替目视结论（见 `docs/PHASES.md` 审查机制）。
- 新增脚本/测试桩放 `TestRobot/src/scripts/`，保证可执行且 `bash -n` 通过；注释与文档沿用中文。
- `README.md` 是考核提交物，启动流程/命令变化后同步更新。
- 尚未 `git init`；提交 GitHub 前确认 `.gitignore` 已排除 `TestRobot/{build,install,log}` 与 `__pycache__`。
