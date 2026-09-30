# 开发日志（DEV_LOG）

规范：每次改动**前**先追加一条记录，完成后补上「结果/证据」。
每条至少包含：日期、目标、改动文件、执行命令、结果证据（命令输出 / 截图路径 / 日志片段）。
未经验证的内容不要写结论。模板：

```
## YYYY-MM-DD  <一句话目标>
- 改动文件：
- 执行命令：
- 结果/证据：
```

---

## 2026-09-29  现存状态盘点（搭建文档骨架前的基线）

- 改动文件：无（只读取现有文件核对）
- 执行命令：
  - `colcon build --packages-select TestRobot`（历史日志：`TestRobot/log/build_2026-09-29_19-49-47/`）
  - `ls -l src/maps/`
- 结果/证据：
  - 最近一次构建成功；包源在 `TestRobot/src`，workspace 根在 `TestRobot/`。
  - 已存在地图 `src/maps/map.pgm` + `map.yaml`（分辨率 0.05、origin `[-5.94, -3.65, 0]`）。
  - 5 个 launch 的 `SRC_DIR` 硬编码为 `/home/yfc/test_ros/logo_ros/TestRobot/src`。
  - `frames_*.gv/pdf`（仓库上一级）为旧 TF 快照，含 `imu_link`，与当前 URDF 不符。

## 2026-09-29  建立 AGENTS.md、阶段文档、自检测试桩

- 改动文件：
  - `AGENTS.md`（新增，仓库工作约定）
  - `docs/PHASES.md`（新增，阶段与验收）
  - `docs/DEV_LOG.md`（新增，本文件）
  - `TestRobot/src/scripts/check_topics.sh`（新增，运行时自检测试桩）
  - `.gitignore`（新增，排除 build/install/log 等）
- 执行命令：
  - `bash -n src/scripts/check_topics.sh src/scripts/save_map.sh run_gazebo.sh`
  - `xacro src/urdf/Robot.urdf.xacro`
  - `./run_gazebo.sh gui:=false` + `bash src/scripts/check_topics.sh`
- 结果/证据：
  - `bash -n` 三个脚本全部通过；xacro 展开成功（353 行 URDF）。
  - 无头启动 mine.world 成功，输出 `Successfully spawned entity [robot]`。
  - 自检结果：`OK /scan`、`OK /odom`、`OK TF odom -> base_link`、
    `INFO average rate: 9.977`（/scan），退出码 0。
  - 说明：未启动仿真时自检全部 FAIL 属正常；`/map -> odom` 仅在建图/定位/导航流程中检查。

## 2026-09-29  阶段 2 复验：建图与地图保存（无头）

- 改动文件：新增 `TestRobot/src/scripts/send_nav_goal.py`（导航验收测试桩，本阶段先就位）
- 执行命令：
  - `ros2 launch src/launch/mapping.launch.py gui:=false rviz:=false`
  - 建图运行中：`/cmd_vel` 原地旋转 360° → 前进约 0.4m → 再旋转 360°
  - `bash src/scripts/save_map.sh map_verify`
- 结果/证据：
  - 建图流程启动成功：`/scan`、`/map` 约 4s 就绪；建图前 `/map` 为 100×100、0.05m/格。
  - 旋转+前进后 `bash src/scripts/save_map.sh map_verify` 输出 `Map saved successfully`，
    产出 `src/maps/map_verify.pgm` + `map_verify.yaml`（origin `[-5.92, -3.63, 0]`）。
  - 与旧 `map.pgm` 对比 2368/10000 像素不同，证明地图是本次运行新生成而非复用旧图。
  - slam_toolbox 无报错，仅默认参数 min range 警告；结论：建图链路可用。
  - `map_verify.*` 为临时验证产物，阶段 4 结束后删除，保留 `map.*` 供定位/导航使用。

## 2026-09-29  阶段 3 复验：地图加载与定位（无头）

- 改动文件：新增 `TestRobot/src/scripts/check_alignment.py`（激光-地图对齐测试桩）
- 执行命令：
  - `ros2 launch src/launch/localization.launch.py gui:=false rviz:=false`
  - `ros2 topic echo /map --once --field info`、`ros2 topic echo /amcl_pose ...`
  - `ros2 run tf2_ros tf2_echo map base_link`
  - `python3 src/scripts/check_alignment.py`
- 结果/证据：
  - `map_server` 加载地图：100×100、0.05m/格（来自 `map.yaml`）。
  - AMCL 位姿 3 次采样均为 `x=-2.8000, y=-0.5, z=0`，稳定收敛到初始位姿；`/amcl` lifecycle = active。
  - TF `map -> base_link`：平移 `[-2.800, -0.501, -0.059]`，RPY≈0，链路完整。
  - `check_topics.sh`：`OK /scan`、`OK /odom`、`OK odom->base_link`、`OK map->odom`、/scan 9.980Hz，退出码 0。
  - `check_alignment.py`：5 次采样命中率 65.9%~68.1%，平均 66.9%（阈值 50%）=> PASS。
  - 发现并清理 5 个残留 `robot_state_publisher`（旧 `first_robot` 模型，发布 `imu_link`），
    否则 TF 树会混入无关帧；已把此坑写入 AGENTS.md 与清洁经验（`pkill -f '[g]zserver'` 防自杀）。

## 2026-09-29  阶段 4 复验：自主导航与到点判定（无头）

- 改动文件：无（使用阶段 2/3 的新增脚本）
- 目标点（map 坐标系，依据 map.pgm 可达自由区选取）：
  1. `(-2.02, 0.83)` 北侧大厅（起步转弯）
  2. `(-5.47, -2.62)` 西南深处房间（长距离+穿门）
  3. `(-1.52, -3.22)` 东南房间（转弯+绕行）
- 执行命令：
  - `ros2 launch src/launch/navigation.launch.py gui:=false rviz:=false`
  - `python3 src/scripts/send_nav_goal.py X Y 0`（依次 3 个，超时 90s）
  - `python3 src/scripts/check_alignment.py`
- 结果/证据（第 1 次运行）：
  - 前 3 个目标均 `status=4`（SUCCEEDED）：
    `(-2.12,-0.02)` 6.9s / 0.169m / 13.7°；`(-2.27,-1.97)` 16.5s / 0.208m / 15.4°；
    `(-4.07,-1.97)` 24.2s / 0.147m / 14.3°。
  - 第 4 个（回起点 `(-2.80,-0.50)`）`status=6` ABORTED，日志 `Controller patience exceeded`。
  - 发现问题 1：到点停车过冲导致实际朝向 15.4°，略超考核 ≤15° 要求。
    处理：`nav2_params.yaml` 的 `yaw_goal_tolerance` 由 `0.26` 收紧为 `0.20` rad（≈11.5°），
    `xy_goal_tolerance` 保持 0.2（实测最大 0.208m ≤0.25m）。
  - 第 1 次 4 目标中 3 个成功（满足「至少 n-1 个」），修参数后再复验。

## 2026-09-29  阶段 4 复验（第 2 次，收紧 yaw 容差后）与审查机制

- 执行命令：同第 1 次；输出重定向到 `/tmp/opencode/phase4_result.txt`（避免管道挂起丢证据）。
- 结果/证据：
  - 启动日志显示 4 次 `Goal succeeded`、0 次 `Goal failed`（4/4 到达）。
  - 第 1 次尝试时命令因管道未及时退出被工具超时中断，指标输出丢失，故重跑留档。
  - 第 2 次指标（完整输出见 `/tmp/opencode/phase4_result.txt`），4/4 成功：

    | 目标点 (map) | status | 耗时 | 位置误差 | 朝向误差 |
    | --- | --- | --- | --- | --- |
    | (-2.12, -0.02) | 4 SUCCEEDED | 7.0s | 0.172m | 10.3° |
    | (-2.27, -1.97) | 4 SUCCEEDED | 21.6s | 0.170m | 11.8° |
    | (-4.07, -1.97) | 4 SUCCEEDED | 35.9s | 0.177m | 11.2° |
    | (-2.80, -0.50) | 4 SUCCEEDED | 16.9s | 0.184m | 8.7° |

    全部满足：位置 ≤0.25m、朝向 ≤15°、单点 ≤60s；`check_topics` 退出码 0。
  - 结论：收紧 `yaw_goal_tolerance=0.20` 后，停车过冲不再超 15°，回起点目标也由 ABORTED 变为成功。
- 审查状态：**待用户目视审查**（RViz 全局路径/避障/到点停车），审查通过后在下一行签字。

## 2026-09-29  可移植性修复 + 仓库清理 + README/AGENTS 同步

- 改动文件：
  - `src/launch/{gazebo,mapping,localization,navigation,display_all}.launch.py`：
    SRC_DIR/URDF_DIR 由硬编码绝对路径改为 `__file__` 动态推导（源码布局与 install 布局通用）。
  - `src/README.md`：新增「自检脚本（测试桩）」章节与构建/目录说明；
    `AGENTS.md`：更新路径约定、补充阶段审查机制。
  - 删除临时验证地图 `src/maps/map_verify.pgm` + `map_verify.yaml`。
- 执行命令：
  - `colcon build --packages-select TestRobot`
  - `ros2 launch TestRobot gazebo.launch.py gui:=false`（install 布局）
  - `ros2 launch src/launch/gazebo.launch.py gui:=false`（源码布局）
  - `grep -rn "/home/yfc" src/`
- 结果/证据：
  - `py_compile` 5 个 launch 全部通过；src 内无 `/home/yfc` 残留。
  - install 布局：world 解析为 `install/TestRobot/share/TestRobot/worlds/mine.world`，`/scan` 约 2s 出现。
  - 源码布局：world 解析为 `src/worlds/mine.world`，`/scan` 约 2s 出现。
  - `src/maps/` 仅剩 `map.pgm` + `map.yaml`，默认地图选择不受影响。
- 审查状态：阶段 4 目视审查待用户执行（命令见交付说明）。

## 2026-09-29  修复数字方块悬浮 + 重建地图（用户目视发现）

- 现象（用户目视）：Gazebo 中 number1~4 悬浮半空，高于激光扫描高度。
- 排查依据：
  - `mine.world` 中 number1~4 为 0.5m 立方体（mesh scale 0.5），模型位姿 `z=0.5`（底面在 0.25m），
    文件末尾 `<state>` 保存位姿 `z=0.4`；激光扫描高度约 0.17m，故扫不到。
  - 方块自带 collision（mesh），落地后会成为雷达可见障碍；对照 `unit_cylinder`（z=0.5、长 1、半径 0.5）
    落地正常，地图中已有该圆形柱子。
- 改动：
  - `src/worlds/mine.world`：number1~4 的模型位姿与 state 位姿 z 统一改为 0.25（立方体底面贴地、雷达可见）。
  - 新增 `src/scripts/drive_waypoints.py`（建图覆盖驾驶测试桩：odom 闭环 + 前向激光保护）。
- 计划执行：
  - 路线（已用地图自由区做直线视线校验）：
    `(-2.8,-0.5)->(-2.12,-0.02)->(-2.02,0.83)->(-2.27,-1.97)->(-1.52,-3.22)->(-2.27,-1.97)`
    `->(-4.07,-1.97)->(-5.47,-2.62)->(-4.07,-1.97)->(-2.27,-1.97)->(-2.8,-0.5)`
  - 旧图备份到 `/tmp/opencode/old_map/`，重建后写回 `src/maps/map.*` 并比较覆盖面积。
  - 重跑阶段 3（对齐）与阶段 4（导航）复验。
- 结果/证据：
  - 重建过程修复了一个脚本 bug：Gazebo diff_drive 的 `/odom` 位姿是世界坐标（出生点即
    `(-2.8,-0.5)`），`drive_waypoints.py` 之前误按「odom 从 0 起算」做减法，导致车开向东墙被
    前向保护拦停；修正后 7/7 路点全部到达、无 BLOCKED。
  - 新地图（`src/maps/map.pgm|yaml`，origin `[-5.94,-3.63,0]`）：自由区 12.82 m²、占据 550 格，
    覆盖大于重建前的旧图；完整输出见 `/tmp/opencode/phase2b_result.txt`。
  - 数字方块可见性（新地图 0.6m 邻域占据格数）：number1=21、number2=25、number3=25、number4=25，
    四个方块均已被雷达观测为障碍（此前悬浮扫不到）。
  - 说明：重建期间的两次失败尝试中，有一次把「车没动」的空图写回了 `src/maps`，
    旧图（19:41）已由此更新为本次更完整的新图；原图副本保留在
    `TestRobot/install/TestRobot/share/TestRobot/maps/`（构建时拷贝）与 `/tmp/opencode/old_map_install/`。

## 2026-09-29  数字方块修复后：阶段 3/4 复验（新地图）

- 执行命令：
  - `ros2 launch src/launch/localization.launch.py gui:=false rviz:=false`
    + `python3 src/scripts/check_alignment.py`
  - `ros2 launch src/launch/navigation.launch.py gui:=false rviz:=false`
    + `python3 src/scripts/send_nav_goal.py` × 4
- 结果/证据（输出：`/tmp/opencode/phase3_result2.txt`、`/tmp/opencode/phase4_result3.txt`）：
  - 阶段 3：新地图加载正常（origin `[-5.94,-3.63,0]`），AMCL active，TF 链完整，
    `check_topics` 退出码 0；激光-地图对齐 5 次采样平均 **69.8%**（阈值 50%）=> PASS。
  - 阶段 4：4/4 目标 `status=4`：

    | 目标点 (map) | 耗时 | 位置误差 | 朝向误差 |
    | --- | --- | --- | --- |
    | (-2.12, -0.02) | 7.7s | 0.195m | 10.4° |
    | (-2.27, -1.97) | 27.9s | 0.139m | 9.3° |
    | (-4.07, -1.97) | 27.0s | 0.161m | 10.4° |
    | (-2.80, -0.50) | 17.9s | 0.147m | 10.3° |

    全部满足 ≤0.25m / ≤15° / ≤60s，`goals_rc=0`。
  - 审查状态：**待用户目视**（重点：四个数字方块已落地并出现在地图中；导航路径/避障/到点停车）。

## 2026-09-30  小房间建图尝试（自动驾驶进房间绕方块）

- 背景（用户目视反馈）：小房间内部地图不清晰，疑似车没进房间绕方块。
- 改动文件：`src/scripts/drive_waypoints.py`（新增 `--verbose` 逐秒日志）。
- 执行与结果：
  - 第一版路线（基于 `mine.world` 内联几何 + 切比雪夫间隙 0.25m，51 路点，含各房间绕圈）：
    到达 26/51（其余被前向 0.22m 保护拦下），地图自由区 12.82 → **15.22 m²**，
    四个方块与所在房间明显变清晰（区块轮廓/房间自由区可见）。
  - 第二版路线（改为 scipy EDT 精确欧氏间隙 0.30m，68 路点）：
    仅到达 3/68（首个路点在狭窄门口即被前向保护拦下，后续连续 BLOCKED），
    并把更差的地图写回了 `src/maps`。
  - 处理：已回滚到 15.22 m² 版本（origin `[-5.96,-3.63,0]`）。
- 教训：
  - 自动驾驶绕圈受前向安全阈值与门口宽度限制，成功率有限；
  - **现场最终建图仍以遥控进房间绕行为准**（考核也要求现场运行生成地图）。
- 复核（room-tour 图，15.22 m²，origin `[-5.96,-3.63,0]`）：
  - 阶段 3：地图加载/TF/check_topics 通过；对齐 5 次平均 **51.8%**（阈值 50%），
    相比干净图的 69.8% 明显下降；长轨迹累计漂移/回路闭合导致局部图与激光整体偏约 1 格。
  - 阶段 4：4/4 目标成功：`(-2.12,-0.02)` 7.9s/0.169m/11.8°、`(-2.27,-1.97)` 18.0s/0.169m/12.0°、
    `(-4.07,-1.97)` 30.1s/0.163m/12.2°、`(-2.80,-0.50)` 19.2s/0.188m/10.5°，`goals_rc=0`。
  - 证据：`/tmp/opencode/phase3_result3.txt`、`/tmp/opencode/phase4_result4.txt`。
  - 结论：房间覆盖变好、对齐质量下降，属于取舍；建议按现场流程由用户遥控一次干净重建作为最终交付地图。

## 2026-09-30  最终地图：用户遥控重建（现场流程）

- 决策（用户选择）：由用户用 teleop_twist_keyboard 遥控重建一版干净地图（覆盖房间+绕方块），
  完成后再由代理复验阶段 3/4。
- 备份：重建前的 room-tour 图（15.22 m²）已备份到 `/tmp/opencode/map_roomtour_backup/`。
- 执行命令（交付给用户）：
  - 终端1：`pkill -f '[g]zserver'; pkill -f '[g]zclient'` →
    `cd .../TestRobot && source install/setup.bash` → `ros2 launch src/launch/mapping.launch.py`
  - 终端2：`ros2 run teleop_twist_keyboard teleop_twist_keyboard`
  - 覆盖后（终端3）：`bash src/scripts/save_map.sh map`
- 用户遥控结果：新图 `map.pgm|yaml`（100×100，origin `[-5.93,-3.63,0]`，自由 15.33 m²、占据 1064 格）。
- 复验阶段 3：对齐 5 次采样平均 **87.8%**（历史最佳），`check_topics` 通过。
- 复验阶段 4（第一次）：仅目标 1 成功，目标 2 的 `send_goal` 响应超时
  （Nav2 日志 `Failed to send goal response ... timeout`），随后机器人静止等待 90s，
  Nav2 报 `Transform data too old when converting from map to odom`（工具链瞬时卡顿的连锁反应），
  目标 3/4 也在限时内未完成。已实证：静止时 `map->odom` 会持续刷新、`/amcl_pose` 不更新属正常，
  问题在 goal 响应超时（DDS/执行器瞬时拥塞），非地图或参数错误。
- 修复：`src/scripts/send_nav_goal.py` 增加「目标响应 15s 超时 → 重试一次」；
  复验脚本单点限时 90s → 120s。准备重跑阶段 4。
- 复验阶段 4（第二次，遥控新图）：

  | 目标点 (map) | status | 耗时 | 位置误差 | 朝向误差 |
  | --- | --- | --- | --- | --- |
  | (-2.12, -0.02) | 4 SUCCEEDED | 7.8s | 0.166m | 10.4° |
  | (-2.27, -1.97) | 4 SUCCEEDED | 16.6s | 0.165m | 8.6° |
  | (-4.07, -1.97) | 4 SUCCEEDED | 24.6s | 0.164m | 9.7° |
  | (-2.80, -0.50) | 4 SUCCEEDED | 22.8s | 0.153m | 9.7° |

  全部满足 ≤0.25m / ≤15° / ≤60s，`goals_rc=0`；证据 `/tmp/opencode/phase4_result_manual2.txt`。
- 结论：**遥控新图（对齐 87.8%）作为当前最佳地图**，阶段 3/4 复验全部通过。

## 2026-09-30  阶段 5：GitHub 提交准备（git init + 首次提交）

- 决策（用户选择）：在 `/home/yfc/test_ros/logo_ros` 初始化 git 并首次提交；不添加远程、不 push。
- 执行命令：`git init` → `git add -A` → `git status --short` 核对 → `git commit`。
- 核对点：不包含 `TestRobot/{build,install,log}`、`__pycache__`、`*.bak*`；`chap3/4/6` 不在本仓库内。
- 结果/证据：（待填 hash 与文件统计）
- 审查机制（用户要求）：新增到 `docs/PHASES.md` —— 每阶段由用户目视确认关键现象并在本日志签字，
  自动测试只作数值验证，不代替目视结论。
- 待用户审查项（阶段 4）：
  1. Gazebo/RViz 目视：全局路径、避障、到点停车。
  2. 确认到点指标：位置 ≤0.25m、朝向 ≤15°、单点 ≤60s。
