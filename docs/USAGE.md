# 使用与配置

本文覆盖安装、凭据、运行方式、浏览器叠加层、控制字段、运行文件和常见故障。战术行为本身见 [STRATEGY.md](STRATEGY.md)。

## 1. 前置条件

- Python 3.11 或更高版本。
- Arena Hero API Key。
- 需要叠加层时使用 Chrome 或 Edge 111+。
- Windows 一键脚本需要 PowerShell 7 或 Windows PowerShell 5.1。

项目只依赖官方 `arena-hero>=0.2.9,<0.3` SDK。SDK 负责 WebSocket、HTTP、模型验证和幂等重试，启动器在一次传输会话彻底中断后以 0.5 秒起、最多 5 秒的退避间隔持续重连；战术记忆保存在本地文件中，不会因新会话丢失。

## 2. Windows 安装

```powershell
.\setup.ps1
```

脚本会：

1. 检查 Python 版本是否至少为 3.11。
2. 在 `.venv` 中创建隔离环境。
3. 升级 `pip`。
4. 安装 `requirements.txt`。
5. 输出已安装的 Arena Hero SDK 版本。

已有虚拟环境时脚本会复用它。跳过 `pip` 自身升级：

```powershell
.\setup.ps1 -SkipPipUpgrade
```

指定 Python 可执行文件：

```powershell
.\setup.ps1 -Python "C:\Python311\python.exe"
```

## 3. 凭据

### Windows DPAPI（推荐）

```powershell
.\set_key.ps1
```

Key 会保存到 `.arena_hero_api_key.dpapi`，只能由当前 Windows 用户在当前机器上解密。该文件已被 Git 忽略，但仍应像凭据一样保护，不应发送给他人。

重新设置 Key 时再次运行 `set_key.ps1`。

### 环境变量或 `.env`

`arena_hero_tactic.py` 也支持：

```text
ARENA_HERO_API_KEY=your-key
```

可以临时设置环境变量，或以 `.env.example` 为模板创建本地 `.env`。`.env` 是明文文件，只适合受控环境，并已被 Git 忽略。Windows 启动脚本发现明文 `.env` Key 后会将它迁移到 DPAPI 并从 `.env` 删除该行。

程序不会把 Key 写入遥测、中文事件日志或叠加层响应。

## 4. 运行 Agent

### 前台运行

Windows：

```powershell
.\start_arena_hero.ps1
```

直接运行 Python：

```powershell
.\.venv\Scripts\python.exe .\arena_hero_tactic.py
```

前台模式会逐 Tick 输出资源、人口、敌人数、动作数、上个 Tick 的事件和前几条战术决策。按 `Ctrl+C` 可正常停止。

### 后台运行 Agent 与叠加层

```powershell
.\start_all.ps1
```

该脚本只停止并替换当前仓库路径下旧的 `arena_hero_tactic.py` 和 `arena_hero_route_overlay_server.py` 进程，不会匹配其他 Python 项目。输出写入：

- `agent.log`
- `agent_err.log`

`start_all.ps1` 重启前会把非空输出日志滚存为带毫秒时间戳的 `arena_hero_agent_*.log`，避免上一会话的异常现场被输出重定向覆盖。

叠加层服务地址为 `http://127.0.0.1:8765`。健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
```

### 停止

```powershell
.\stop_all.ps1
```

### 限定 Tick 数

适合短时间试运行：

```powershell
.\.venv\Scripts\python.exe .\arena_hero_tactic.py --max-turns 10
```

## 5. 跨平台运行

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
export ARENA_HERO_API_KEY='your-key'
python arena_hero_tactic.py
```

不要在共享 shell 历史、CI 日志或截图中暴露真实 Key。生产环境应使用平台自己的 secret store 注入环境变量。

叠加层服务可以独立启动：

```bash
python arena_hero_route_overlay_server.py --port 8765
```

浏览器扩展目前固定连接 `127.0.0.1:8765`。

## 6. 命令行参数

`arena_hero_tactic.py` 支持：

| 参数 | 默认值 | 作用 |
|---|---|---|
| `--max-turns N` | 不限制 | 成功提交 N 个 Turn 后退出 |
| `--base-url URL` | `https://api.arenahero.io` | HTTP API 根地址 |
| `--websocket-url URL` | SDK 从 HTTP 地址推导 | WebSocket 地址 |
| `--memory-file PATH` | `.arena_hero_memory.json` | 持久战术记忆 |
| `--telemetry-file PATH` | `arena_hero_telemetry.jsonl` | 每 Tick 决策遥测 |
| `--stats-file PATH` | `.arena_hero_stats.json` | 叠加层统计快照 |
| `--event-log-file PATH` | `arena_hero_events_zh.jsonl` | 中文事件日志 |

对应环境变量：

| 环境变量 | 作用 |
|---|---|
| `ARENA_HERO_API_KEY` | API Key |
| `ARENA_HERO_BASE_URL` | HTTP API 根地址 |
| `ARENA_HERO_WEBSOCKET_URL` | WebSocket 地址 |
| `ARENA_HERO_MEMORY_FILE` | 战术记忆路径 |
| `ARENA_HERO_TELEMETRY_FILE` | 遥测路径 |
| `ARENA_HERO_STATS_FILE` | 统计路径 |
| `ARENA_HERO_EVENT_LOG_FILE` | 中文日志路径 |
| `ARENA_HERO_CONTROL_FILE` | 控制 JSON 路径 |
| `ARENA_HERO_BROWSER_INTEL_FILE` | 浏览器资源提示路径 |
| `ARENA_HERO_RECOVERY_TARGETS_FILE` | 人工恢复目标列表路径 |

## 7. 浏览器叠加层

### 安装

1. 打开 `chrome://extensions` 或 `edge://extensions`。
2. 启用开发者模式。
3. 选择“加载已解压的扩展程序”。
4. 选择 `arena_hero_route_overlay` 目录。
5. 保持本地叠加层服务运行，并打开 `https://app.arenahero.io/arena`。

叠加层会读取本地路线、统计和中文事件；它也会把浏览器当前地图中的资源格作为短期、低置信提示发送给 Agent。Agent 会验证时效、距离、当前视野和资源配额合理性，不会把浏览器提示当作服务器真相。

### 控件

| 控件 | 作用 |
|---|---|
| 模式 | 在发育、侵略、抢信标之间循环 |
| 一键召回 | 所有战斗单位回 Core 防守；再次点击解除 |
| 偷袭 | 启用独立 Core 搜索/斩首编组 |
| 偷袭召回 | 只召回独立偷袭编组 |
| 统计 | 显示资源、人口、成功/失败事件和长期计数 |
| 定位 | 按单位或事件坐标聚焦地图 |
| 日志 | 显示脱敏中文事件流 |
| 设置 | 调整目标距离、偷袭编组数量和侵略编组数量 |
| 全局最优生产 | 补编制缺口时按兵种基础价降序生产，降低同一串产兵的总耗 |
| 优先给工人让路 | 挡住工人去路的自己人主动闪避一步，解开走廊拥堵 |
| 通行调度 | 沿工人整条通路清障 + 递归推挤，处理单步让路解决不了的深度拥堵 |
| 容量够就先攒满 | 囤积改看仓库容量而不是人口门槛 |
| 30 之后的攒资源目标 | 人口过 30 后的通用水位，所有模式生效 |
| 禁止头程侦察 | develop 模式下不再主动派 1 先锋 + 1 游侠去信标方向打头阵 |
| 工人探索半径 | 视野内没有资源时，工人螺旋外扩找矿的半径上限（默认 160 格，0 = 用默认值） |

快捷键：

| 快捷键 | 作用 |
|---|---|
| `Alt+Shift+1` | 发育模式 |
| `Alt+Shift+2` | 侵略模式 |
| `Alt+Shift+3` | 抢信标模式 |
| `Alt+Shift+C` | 切换全军召回 |
| `Alt+Shift+R` | 切换路线显示 |
| `Alt+Shift+L` | 切换中文日志 |
| `Alt+Shift+M` | 在鼠标悬停格设置集结点 |
| `Alt+Shift+U` | 清除集结点 |

### 控制 JSON

叠加层把控制写到 `.arena_hero_control.json`。没有叠加层时也可使用 `.arena_hero_control.example.json` 作为结构参考。

| 字段 | 类型 | 含义 |
|---|---|---|
| `mode` | `develop/aggress/beacon/migrate` | 主模式 |
| `recall` | boolean | 全军召回 |
| `raid_enabled` | boolean | 独立偷袭编组 |
| `raid_recall` | boolean | 只召回偷袭编组 |
| `raid_vanguards` | non-negative integer | 偷袭先锋数 |
| `raid_rangers` | non-negative integer | 偷袭游侠数 |
| `beacon_target_distance` | non-negative integer | Core 希望与信标保持的曼哈顿距离；0 关闭 |
| `rally_point` | `[x,y]` or null | 战斗单位人工集结点 |
| `migration_candidate` | `[x,y]` or null | 工人验证的迁移候选格 |
| `auto_migrate` | boolean | 候选格通过防守面检查后自动进入迁移模式 |
| `aggress_vanguards` | non-negative integer | 指定侵略先锋数量；0 使用自动分配 |
| `aggress_rangers` | non-negative integer | 指定侵略游侠数量；0 使用自动分配 |
| `ally_support_enabled` | boolean | 盟友 Core 被攻击时派兵支援 |
| `hoard_stage1` | boolean | 发育模式人口达 20 后先把资源攒到 95 再产兵 |
| `hoard_stage2` | boolean | 发育模式人口达 30 后先把资源攒到 150 再产兵 |
| `optimal_spawn_order` | boolean | 补编制缺口时改用全局资源最优顺序（游侠→先锋→工人）；关闭时用项目原顺序（先锋→游侠→工人） |
| `yield_path_to_workers` | boolean | 工人地形上有路、却被自己人占满而寻不到路时，挡路单位主动闪避一步 |
| `traffic_control` | boolean | 通行调度：沿工人整条通路清障（往前 12 格）+ 递归推挤（最多 2 层），处理单步让路解决不了的深度拥堵。可与 `yield_path_to_workers` 同时开启 |
| `hoard_on_capacity` | boolean | 囤积档位改用容量判定：仓库装得下水位就开始攒，不等人口门槛，也不受超产顺移影响 |
| `hoard_target_after_30` | non-negative integer | 人口过 30 后的通用囤积水位，**所有模式生效**。0 = develop 下回落两档开关、其它模式无目标；非 0 直接覆盖两档。高于仓库容量时自动夹到容量上限 |
| `disable_beacon_scout` | boolean | develop 模式下禁止头程侦察：不再主动派 1 先锋 + 1 游侠去信标方向打头阵，两名单位留在家走普通防守逻辑 |
| `target_population` | non-negative integer | 发育编制阶梯第一级的目标人口，默认 20；0 关闭阶梯 |
| `composition_workers` | non-negative integer | 阶梯第一级的工人配比，默认 12 |
| `composition_vanguards` | non-negative integer | 阶梯第一级的先锋配比，默认 4 |
| `composition_rangers` | non-negative integer | 阶梯第一级的游侠配比，默认 4 |
| `growth_workers` | non-negative integer | 阶梯用尽后的连续增长工人权重，默认 5 |
| `growth_vanguards` | non-negative integer | 阶梯用尽后的连续增长先锋权重，默认 4 |
| `growth_rangers` | non-negative integer | 阶梯用尽后的连续增长游侠权重，默认 6；三项全 0 回落项目原策略 5:4:6 |
| `browser_hint_distance` | non-negative integer | 浏览器水晶提示的搜索半径（格），默认 32；0 关闭提示。提示来自客户端已探索缓存里标记 `RESOURCE` 的格，含工人已离开视野的水晶；实测近处水晶多在 40~70 格，默认 32 常常用不上 |
| `browser_scout_limit` | non-negative integer | 每 Tick 最多派几名工人验证提示，默认 1；0 不派人 |
| `resource_leash_distance` | non-negative integer | develop 模式采集目标距 Core 的上限（格），默认 38；0 取消上限。必须 ≥ `browser_hint_distance`，否则中间那段是「能发现但采不到」的死区 |
| `worker_search_max_radius` | non-negative integer | develop 模式工人螺旋外扩找矿的半径上限（格），默认 160；0 = 用默认值。管「还没发现水晶时往外铺多大搜索圈」，与 `resource_leash_distance`（管「已发现的水晶值不值得采」）互相独立。refill 复查上限跟随本值 |

后四个字段与两个囤积开关只影响 `develop` 模式，详见 [STRATEGY.md](STRATEGY.md) 的「`develop` 目标编制阶梯与资源囤积」。注意阶梯或囤积生效期间会押后自动抢信标。

控制文件在每个 Turn 开始时按修改时间热读取。浏览器 Manual 动作仍然按服务器规则优先于 Agent 对同一对象的动作。

## 8. 运行文件

| 文件 | 内容 | 是否应提交 |
|---|---|---|
| `.arena_hero_api_key.dpapi` | Windows 加密 Key | 否 |
| `.arena_hero_memory.json` | 地图、敌人、编队、编号和累计战术状态 | 否 |
| `.arena_hero_routes.json` | 当前 Tick 路线和单位快照 | 否 |
| `.arena_hero_stats.json` | 叠加层统计快照 | 否 |
| `.arena_hero_control.json` | 当前人工控制 | 否 |
| `.arena_hero_browser_intel.json` | 短期浏览器地图提示 | 否 |
| `.arena_hero_recovery_targets.json` | 人工资源恢复/迁移侦察点 | 否 |
| `arena_hero_telemetry.jsonl` | 每 Tick 决策和事件摘要 | 否 |
| `arena_hero_events_zh.jsonl` | 脱敏中文事件日志 | 否 |
| `agent.log`, `agent_err.log` | 后台进程输出 | 否 |

记忆、遥测和中文日志会限制文件规模；无需手工轮转即可长期运行。

## 9. 策略热加载

运行中修改 `arena_hero_strategy.py` 后：

1. 第一个观察到修改的 Tick 标记 `strategy_reload_pending=True`。
2. 下一个 Tick 保存记忆并加载候选模块。
3. 候选模块加载和状态恢复成功后才替换旧策略。
4. 新策略运行异常时跳过该 Tick，并在可能时回滚旧策略。

这避免了半写入文件或语法错误直接终止长期进程。修改连接入口 `arena_hero_tactic.py` 时仍需重启。

## 10. 故障排查

### `ProtocolError` 或状态模型字段不匹配

确认虚拟环境中的 SDK 版本：

```powershell
.\.venv\Scripts\python.exe -c "import arena_hero; print(arena_hero.__version__)"
```

本仓库要求 `>=0.2.9,<0.3`。重新运行 `setup.ps1` 或 `pip install -r requirements.txt`，然后重启 Agent。

### 叠加层无数据

依次检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
Invoke-RestMethod http://127.0.0.1:8765/stats
```

确认扩展已启用、页面域名为 `app.arenahero.io`，并在扩展更新后点击“重新加载”。

### 资源增长慢

先看统计中的 `worker_cargo`、`visible_resource_cells`、`known_resource_cells`、`exploring_workers`、`move_failures` 和 `worker:cargo_stuck`。资源为 0 可能只是刚产兵；载货正在回仓也不等于卡住。不要只根据 Core 当前库存增加工人，必须同时考虑动态人口价格和回本周期。

### Core 门口拥堵

短暂 `cargo_queue_hold` 是主动排队。真正异常通常伴随连续 `UNIT_MOVE_FAILED`、`worker:cargo_stuck` 或载货距离长期不下降。策略会让占据 Core 的单位腾位，并在近端载货进入服务半径时暂停 Core 迁移。

### 工人来回走、货卸不掉

先分清两类原因，处理方式完全不同。看决策日志里该工人的 `reason`：

**带 `:fallback`（例如 `return_cargo:fallback`）= 完整寻路失败，退化成单步贪心。** 这类打转已在策略里修掉三个成因，无需开关，升级策略即可：加权 A\*（`PATHFINDING_HEURISTIC_WEIGHT`）解决启发式与 `visited` 代价尺度不匹配导致的搜索爆炸（实测最坏展开量 33133 超过 30000 硬上限，注定寻不到路）；贪心分支加了反打转，不再走回上一个 Tick 待过的格；`_blocked()` 补上本 Tick 已计划移入的格。细节见 [STRATEGY.md 2.1.4](STRATEGY.md#214-寻路退化与打转)。如果升级后仍然看到大量 `:fallback`，那是真的没路（地形死路或临时封锁），不是寻路缺陷。

**不带 `:fallback` 但位置长期不下降 = 寻到路了，被自己人占满的走廊卡住。** 每格最多 2 个实体，人口一多（尤其召回把战斗单位堆在 Core 附近）走廊会被占满。两个开关按拥堵深度递进：

- `yield_path_to_workers`（面板「优先给工人让路」）：让通路上第一个满格的挡路单位闪避一步。适合浅拥堵。
- `traffic_control`（面板「通行调度」）：沿整条通路往前 12 格逐个清障，挡路单位四周也满时递归把外层单位推开腾出落脚点（最多 2 层）。防守单位一多，相邻格普遍都是满的，单步让路会当场失败——这时才需要它。

判断是否生效：`yield_path_to_worker_total`、`traffic_control_total`、`traffic_yield_chain_total` 与 `cargo_stuck_total` 一起看。让路/疏通次数上升、打转次数停止增长即为对症。`traffic_yield_chain_total` 占比高说明拥堵已经深到单步让路根本处理不了。

### 水晶被自己人占住采不了

采集要求工人**站在水晶格上**，而每格最多容纳 2 个实体。一颗水晶被两个采不了的单位占住（两个战斗单位，或战斗单位 + 已载货工人）时就**永久采不到**：摆位规则只看地形与威胁、不认水晶格，游侠的射击位或召回阵位一旦落在水晶上，再来第二个单位这颗水晶就废了。

策略里已内置自动让开，无需开关，日志会打 `resource_cell_vacated at=(x, y)`。触发条件是「格子已满 + 上面没有空载工人 + 水晶 5 格内无敌」三条同时满足，即确认这颗水晶这一 Tick 铁定采不了；有敌时按战斗优先不动。腾位会递归推挤，所以挡路单位四周也满时依然能让开。细节见 [STRATEGY.md 2.1.3](STRATEGY.md#213-让开水晶格)。

摆位那边也做了源头规避：召回位、警戒位与 Core 巡逻位现在会把落在水晶上的阵位排到最后（只降优先级，水晶多时仍可站，否则单位无处可去）。所以正常情况下 `vacate_resource_cell_total` 应该维持在很低的水平。

看 `vacate_resource_cell_total`：若仍持续增长，说明单位是被别的规则（射击位、追击、护送）带到水晶上的，顺着决策日志找那条规则。某颗水晶长期没有采集记录、又没出现 `resource_cell_vacated`，那更可能是采集距离上限（`resource_leash_distance`）、临时封锁未解除或空载工人不够，不是被占住。

### API Key 无法解密

DPAPI 文件与 Windows 用户绑定。切换账号或机器后运行：

```powershell
.\set_key.ps1
```

不要尝试把旧 DPAPI 文件复制到新机器。
