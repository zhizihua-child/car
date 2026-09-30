# 开发阶段与验收（PHASES）

依据 `timu.txt` 的考核任务与验收标准划分。每阶段必须留下可复现的证据（命令输出/截图/日志），
证据记录到 `docs/DEV_LOG.md`。前一阶段未通过验收，不进入下一阶段。

## 审查机制（因无头自动测试看不到视觉现象）

- 自动测试只能验证状态/数值（话题、TF、action 结果、误差、日志），**不能替代人工目视**：
  地图轮廓、激光与地图对齐、全局/局部路径、到点停车等必须由用户在 RViz/Gazebo 里确认。
- 每个阶段结束：代理汇总证据（指标 + 证据文件路径 + 需要目视确认的清单），提交用户审查；
  用户在 `docs/DEV_LOG.md` 里确认（通过/不通过 + 日期）后，才进入下一阶段。
- 证据文件统一放 `/tmp/opencode/` 或写进 DEV_LOG；不把「未目视确认」当成「已通过」。

## 阶段 0：环境与依赖

- 目标：Ubuntu 22.04 + ROS 2 Humble + Gazebo Classic 11 + slam_toolbox + navigation2 可用。
- 验收：`ros2 --version`、`gazebo --version`、`dpkg -l | grep ros-humble-navigation2`。
- 证据：命令输出。

## 阶段 1：仿真场景与机器人模型

- 目标：自建室内场景 + 差速小车，可移动，激光/里程计/TF 正常。
- 启动：`cd TestRobot && ./run_gazebo.sh`（无界面加 `gui:=false`）。
- 验收：`bash src/scripts/check_topics.sh` 中 /scan、/odom、odom→base_link 全部 OK；
  遥控后机器人移动、`ros2 topic hz /scan` 约 10Hz。
- 证据：check_topics.sh 输出、Gazebo 截图。

## 阶段 2：建图与地图保存

- 启动：`ros2 launch src/launch/mapping.launch.py`，遥控覆盖场景。
- 验收：RViz 中栅格地图连续、主要通道清晰；另开终端 `bash src/scripts/save_map.sh` 成功，
  产出 `src/maps/map.pgm` + `map.yaml`（yaml 中 image/resolution/origin 与实际一致）。
- 证据：建图截图、保存命令输出、map.pgm/yaml 文件列表。

## 阶段 3：地图加载与定位

- 启动：`ros2 launch src/launch/localization.launch.py`（默认自动加载 `src/maps/` 第一个 yaml）。
- 验收：check_topics.sh 中 map→odom 存在；RViz 里激光扫描与地图边界基本重合、位姿稳定。
- 证据：RViz 对齐截图、TF 链输出。

## 阶段 4：自主导航与到点判定

- 启动：`ros2 launch src/launch/navigation.launch.py`。
- 按顺序发 n 个目标点（直行、转弯、绕障至少各覆盖一种）：
  `ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose ...`
- 验收（与 `config/nav2_params.yaml` 的 `general_goal_checker` 对应）：
  位置误差 ≤0.25m、朝向误差 ≤15°、单目标 60s 内到达；至少 n-1 个到达；碰撞 <2 次。
- 证据：每个目标的 action 结果（succeeded）、RViz 路径截图。

## 阶段 5：复现材料与讲解

- README 与当前命令一致（按 README 可复现全部流程）。
- 运行证据：场景/地图/定位对齐/路径规划/到点截图，录屏 ≤3 分钟。
- 第三方来源说明（slam_toolbox、navigation2、gazebo_ros 为官方 apt 包）。
- 提交 GitHub 仓库地址（先确认 `.gitignore` 排除 build/install/log，`docs/DEV_LOG.md` 完整）。
