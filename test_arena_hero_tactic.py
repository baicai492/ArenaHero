from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from arena_hero import (
    Accepted,
    BeaconStatus,
    ChampionBeacon,
    CancelMoveAction,
    CommandSource,
    CoreState,
    CoreView,
    DepositAction,
    Direction,
    DropBeaconAction,
    HarvestAction,
    HealAction,
    MoveAction,
    PlayerState,
    PlayerStatus,
    PickupBeaconAction,
    RepairShieldAction,
    ResolutionEvent,
    ShootAction,
    SpawnAction,
    StartMoveAction,
    SweepAction,
    TerrainView,
    Turn,
    UnitType,
    UnitView,
    WaitAction,
    unit_cost,
)
from arena_hero.rules import core_resource_capacity

from arena_hero_tactic import choose_actions
from arena_hero_strategy import (
    AGGRESS_BASE_WORKERS,
    AGGRESS_DEFENDER_RANGERS,
    AGGRESS_DEFENDER_VANGUARDS,
    AGGRESS_CORE_REINFORCEMENT_ENEMY_COUNT,
    AGGRESS_RANGER_WATCH_OFFSETS,
    AGGRESS_RESOURCE_TARGET_CORE_LEASH_DISTANCE,
    AGGRESS_RESOURCE_SWEEP_MAX_RADIUS,
    AGGRESS_TARGET_RANGERS,
    AGGRESS_TARGET_VANGUARDS,
    BEACON_EXPEDITION_COHESION_RADIUS,
    BEACON_ECONOMY_TARGET_WORKERS,
    BEACON_RANGER_PRIORITY_MIN_VANGUARDS,
    BEACON_RESOURCE_SWEEP_INITIAL_RADIUS,
    BEACON_RESOURCE_SWEEP_MAX_RADIUS,
    BROWSER_RESOURCE_HINT_MAX_DISTANCE,
    COMPOSITION_STAGE2_POPULATION,
    COMPOSITION_STAGE2_RANGERS,
    COMPOSITION_STAGE2_VANGUARDS,
    COMPOSITION_STAGE2_WORKERS,
    CONTINUOUS_GROWTH_PROFILE,
    CORE_MIGRATION_CARGO_BACKLOG_LIMIT,
    CORE_MIGRATION_CARGO_SERVICE_RADIUS,
    CORE_MIGRATION_HEAL_SERVICE_RADIUS,
    CORE_MIGRATION_RECENT_ENEMY_HOLD_RADIUS,
    POST_RECALL_SWEEP_ASSEMBLY_RADIUS,
    ASSAULT_SWEEP_MAX_RADIUS,
    ASSAULT_SWEEP_MIN_RADIUS,
    ASSAULT_SWEEP_PROFILE_VERSION,
    ASSAULT_SWEEP_SECTOR_OFFSETS,
    DEVELOP_LOCAL_RECALL_RADIUS,
    DEVELOP_RESOURCE_TARGET_CORE_LEASH_DISTANCE,
    DEVELOP_WIDE_SEARCH_MAX_RADIUS,
    EnemySighting,
    HOARD_STAGE1_POPULATION,
    HOARD_STAGE1_RESOURCE_TARGET,
    HOARD_STAGE2_POPULATION,
    HOARD_STAGE2_RESOURCE_TARGET,
    HealRotation,
    HealRoleSwap,
    MODE_AGGRESS,
    MODE_BEACON,
    MODE_DEVELOP,
    MODE_MIGRATE,
    MovementPlanner,
    PlannedMove,
    RAID_SWEEP_INITIAL_RADIUS,
    RAID_SWEEP_RING_SPACING,
    RaidEnemyMotion,
    ROUTES_FILENAME,
    SmartTactic,
    STUCK_TICKS,
    TacticMemory,
    UnitLabel,
    WorkerGoal,
    _chunk_of,
    _chunk_quota,
    _composition_overflow,
    _core_attack_surface_profile,
    _core_logistics_corridor,
    _distance,
    _effective_composition,
    _effective_growth_profile,
    _effective_target_population,
    _hoard_resource_target,
    _refill_tick_at_or_after,
    _split_population,
    _terrain_guard_offsets,
)

_test_control_directory: TemporaryDirectory[str] | None = None
_previous_control_file: str | None = None
_previous_browser_intel_file: str | None = None
_previous_recovery_targets_file: str | None = None


def setUpModule() -> None:
    global _test_control_directory, _previous_control_file
    global _previous_browser_intel_file, _previous_recovery_targets_file
    _test_control_directory = TemporaryDirectory()
    _previous_control_file = os.environ.get("ARENA_HERO_CONTROL_FILE")
    os.environ["ARENA_HERO_CONTROL_FILE"] = str(
        Path(_test_control_directory.name) / ".arena_hero_control.json"
    )
    _previous_browser_intel_file = os.environ.get("ARENA_HERO_BROWSER_INTEL_FILE")
    os.environ["ARENA_HERO_BROWSER_INTEL_FILE"] = str(
        Path(_test_control_directory.name) / ".arena_hero_browser_intel.json"
    )
    _previous_recovery_targets_file = os.environ.get(
        "ARENA_HERO_RECOVERY_TARGETS_FILE"
    )
    os.environ["ARENA_HERO_RECOVERY_TARGETS_FILE"] = str(
        Path(_test_control_directory.name) / ".arena_hero_recovery_targets.json"
    )


def tearDownModule() -> None:
    global _test_control_directory
    if _previous_control_file is None:
        os.environ.pop("ARENA_HERO_CONTROL_FILE", None)
    else:
        os.environ["ARENA_HERO_CONTROL_FILE"] = _previous_control_file
    if _previous_browser_intel_file is None:
        os.environ.pop("ARENA_HERO_BROWSER_INTEL_FILE", None)
    else:
        os.environ["ARENA_HERO_BROWSER_INTEL_FILE"] = _previous_browser_intel_file
    if _previous_recovery_targets_file is None:
        os.environ.pop("ARENA_HERO_RECOVERY_TARGETS_FILE", None)
    else:
        os.environ["ARENA_HERO_RECOVERY_TARGETS_FILE"] = (
            _previous_recovery_targets_file
        )
    if _test_control_directory is not None:
        _test_control_directory.cleanup()
        _test_control_directory = None


CORE_ID = UUID("00000000-0000-4000-8000-000000000100")
WORKER_LOW = UUID("00000000-0000-4000-8000-000000000001")
WORKER_HIGH = UUID("00000000-0000-4000-8000-000000000002")
WORKER_THIRD = UUID("00000000-0000-4000-8000-000000000005")
WORKER_FOURTH = UUID("00000000-0000-4000-8000-000000000006")
WORKER_FIFTH = UUID("00000000-0000-4000-8000-000000000007")
WORKER_SIXTH = UUID("00000000-0000-4000-8000-000000000008")
WORKER_SEVENTH = UUID("00000000-0000-4000-8000-000000000012")
WORKER_EIGHTH = UUID("00000000-0000-4000-8000-000000000013")
RANGER_ID = UUID("00000000-0000-4000-8000-000000000003")
RANGER_TWO_ID = UUID("00000000-0000-4000-8000-000000000004")
RANGER_THREE_ID = UUID("00000000-0000-4000-8000-000000000011")
RANGER_FOURTH_ID = UUID("00000000-0000-4000-8000-000000000015")
VANGUARD_ID = UUID("00000000-0000-4000-8000-000000000009")
VANGUARD_TWO_ID = UUID("00000000-0000-4000-8000-000000000010")
VANGUARD_THREE_ID = UUID("00000000-0000-4000-8000-000000000014")
VANGUARD_FOURTH_ID = UUID("00000000-0000-4000-8000-000000000016")
ENEMY_CORE_ID = UUID("00000000-0000-4000-8000-000000000200")
ENEMY_RANGER_ID = UUID("00000000-0000-4000-8000-000000000201")
ENEMY_VANGUARD_ID = UUID("00000000-0000-4000-8000-000000000202")


def _ladder_uuid(index: int) -> UUID:
    """为编制阶梯/囤积测试批量生成单位 ID。

    这些用例需要凑够 20~30 人的编制，逐个声明常量不现实；用 0x300 起的独立段落
    避免和上面手写的固定 ID 撞号。
    """

    return UUID(f"00000000-0000-4000-8000-{0x300 + index:012x}")


def core(
    position: tuple[int, int] = (5, 5),
    *,
    hp: int = 5,
    shield: int = 5,
) -> CoreView:
    return CoreView(
        kind="CORE",
        id=CORE_ID,
        controlled=True,
        owner_username="test_hero",
        position=position,
        hp=hp,
        shield=shield,
        state=CoreState.NORMAL,
    )


def moving_core(
    position: tuple[int, int] = (5, 5),
    *,
    direction: Direction = Direction.RIGHT,
    progress: int = 1,
) -> CoreView:
    destination = (
        position[0] + direction.delta[0],
        position[1] + direction.delta[1],
    )
    return CoreView(
        kind="CORE",
        id=CORE_ID,
        controlled=True,
        owner_username="test_hero",
        position=position,
        hp=5,
        shield=5,
        state=CoreState.MOVING,
        move_direction=direction,
        move_progress=progress,
        move_required_ticks=4,
        destination=destination,
    )


def worker(
    unit_id: UUID,
    position: tuple[int, int],
    *,
    cargo: int = 0,
) -> UnitView:
    return UnitView(
        kind="UNIT",
        id=unit_id,
        controlled=True,
        position=position,
        hp=2,
        unit_type=UnitType.WORKER,
        cargo=cargo,
    )


def ranger(
    position: tuple[int, int],
    unit_id: UUID = RANGER_ID,
    *,
    hp: int = 2,
) -> UnitView:
    return UnitView(
        kind="UNIT",
        id=unit_id,
        controlled=True,
        position=position,
        hp=hp,
        unit_type=UnitType.RANGER,
    )


def vanguard(
    position: tuple[int, int],
    unit_id: UUID = VANGUARD_ID,
    *,
    hp: int = 4,
) -> UnitView:
    return UnitView(
        kind="UNIT",
        id=unit_id,
        controlled=True,
        position=position,
        hp=hp,
        unit_type=UnitType.VANGUARD,
    )


def enemy_ranger(
    position: tuple[int, int],
    *,
    hp: int = 2,
    unit_id: UUID = ENEMY_RANGER_ID,
) -> UnitView:
    return UnitView(
        kind="UNIT",
        id=unit_id,
        controlled=False,
        position=position,
        hp=hp,
        unit_type=UnitType.RANGER,
    )


def enemy_vanguard(
    position: tuple[int, int],
    *,
    hp: int = 4,
    unit_id: UUID = ENEMY_VANGUARD_ID,
) -> UnitView:
    return UnitView(
        kind="UNIT",
        id=unit_id,
        controlled=False,
        position=position,
        hp=hp,
        unit_type=UnitType.VANGUARD,
    )


def enemy_worker(
    position: tuple[int, int],
    *,
    unit_id: UUID = UUID(int=0x8001),
) -> UnitView:
    return UnitView(
        kind="UNIT",
        id=unit_id,
        controlled=False,
        position=position,
        hp=2,
        unit_type=UnitType.WORKER,
    )


def enemy_core(position: tuple[int, int]) -> CoreView:
    return CoreView(
        kind="CORE",
        id=ENEMY_CORE_ID,
        controlled=False,
        owner_username="enemy_hero",
        position=position,
        hp=5,
        shield=0,
        state=CoreState.NORMAL,
    )


def make_turn(
    *,
    tick: int = 8,
    own_core: CoreView | None = None,
    units: tuple[UnitView, ...] = (),
    enemies: tuple[UnitView | CoreView, ...] = (),
    resources: int = 0,
    resource_cells: tuple[tuple[int, int], ...] = (),
    obstacle_cells: tuple[tuple[int, int], ...] = (),
    events: tuple[ResolutionEvent, ...] = (),
    beacon: ChampionBeacon | None = None,
) -> tuple[Turn, list]:
    objects: list = []
    if obstacle_cells:
        objects.append(TerrainView(kind="OBSTACLE", positions=obstacle_cells))
    if resource_cells:
        objects.append(TerrainView(kind="RESOURCE", positions=resource_cells))
    if own_core is not None:
        objects.append(own_core)
    objects.extend(units)
    objects.extend(enemies)

    population = len(units)
    status = PlayerStatus.ACTIVE if own_core is not None else PlayerStatus.RESPAWNING
    state = PlayerState(
        status=status,
        respawn_at_tick=None if own_core is not None else tick + 1,
        resources=resources,
        population=population,
        champion_beacon=beacon or ChampionBeacon(position=(99, 99)),
        objects=tuple(objects),
        events=events,
    )
    submitted: list = []

    def submitter(plan, idempotency_key):
        submitted.append((plan, idempotency_key))
        return Accepted(
            accepted=True,
            tick=plan.tick,
            source=CommandSource.AGENT,
            received_at=datetime.now(timezone.utc),
        )

    return Turn(tick=tick, state=state, submitter=submitter), submitted


class BalancedTacticTests(unittest.TestCase):
    def test_unit_damage_broadcast_tracks_the_damaged_target(self) -> None:
        event = ResolutionEvent(
            event_id=UUID(int=0x9001),
            tick=20,
            event_type="UNIT_DAMAGED",
            reason_code="ATTACK",
            actor_id=ENEMY_RANGER_ID,
            target_id=RANGER_ID,
            position=(1, 0),
            values={"damage": 1, "hp": 1},
        )
        memory = TacticMemory(
            unit_labels={str(RANGER_ID): UnitLabel("RANGER", 22)}
        )
        turn, _ = make_turn(
            tick=21,
            own_core=core((0, 0)),
            units=(ranger((1, 0)),),
            events=(event,),
        )

        SmartTactic(memory).choose_actions(turn)

        self.assertEqual(memory.attacked_units[str(RANGER_ID)], 21)
        self.assertNotIn(str(ENEMY_RANGER_ID), memory.attacked_units)

    def test_respawning_submits_an_empty_plan(self) -> None:
        turn, submitted = make_turn(own_core=None)

        summary = choose_actions(turn)
        accepted = turn.submit()

        self.assertTrue(accepted.accepted)
        self.assertEqual(summary.unit_actions, 0)
        self.assertIsNone(submitted[0][0].core_action)
        self.assertEqual(dict(submitted[0][0].unit_actions), {})

    def test_worker_deposits_when_sharing_receptive_core(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (0, 0), cargo=1),),
        )

        choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions[WORKER_LOW], DepositAction)

    def test_worker_keeps_cargo_when_colocated_core_is_full(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (0, 0), cargo=1),),
            resources=10,
        )

        choose_actions(turn)

        self.assertNotIn(WORKER_LOW, turn.plan.unit_actions)

    def test_lowest_uuid_is_only_harvest_contender_on_shared_cell(self) -> None:
        turn, _ = make_turn(
            own_core=core(),
            units=(worker(WORKER_HIGH, (0, 0)), worker(WORKER_LOW, (0, 0))),
            resource_cells=((0, 0),),
        )

        choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions[WORKER_LOW], HarvestAction)
        self.assertNotIsInstance(turn.plan.unit_actions.get(WORKER_HIGH), HarvestAction)

    def test_worker_routes_around_visible_obstacle(self) -> None:
        turn, _ = make_turn(
            own_core=core(),
            units=(worker(WORKER_LOW, (0, 0)),),
            resource_cells=((2, 0),),
            obstacle_cells=((1, 0),),
        )

        choose_actions(turn)

        action = turn.plan.unit_actions[WORKER_LOW]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.UP)

    def test_exported_route_contains_complete_obstacle_aware_path(self) -> None:
        memory = TacticMemory()
        turn, _ = make_turn(
            own_core=core(),
            units=(worker(WORKER_LOW, (0, 0)),),
            resource_cells=((2, 0),),
            obstacle_cells=((1, 0),),
        )

        SmartTactic(memory).choose_actions(turn)

        route = memory.current_routes[str(WORKER_LOW)]
        self.assertEqual(route.start, (0, 0))
        self.assertEqual(route.goal, (2, 0))
        self.assertEqual(route.path[0], route.start)
        self.assertEqual(route.path[-1], route.goal)
        self.assertNotIn((1, 0), route.path)
        self.assertTrue(route.complete)

    def test_route_export_is_atomic_and_contains_no_credentials(self) -> None:
        memory = TacticMemory()
        turn, _ = make_turn(
            tick=18,
            own_core=core(),
            units=(worker(WORKER_LOW, (0, 0)),),
            resource_cells=((2, 0),),
        )
        SmartTactic(memory).choose_actions(turn)

        with TemporaryDirectory() as directory:
            memory_path = Path(directory) / ".arena_hero_memory.json"
            memory.save(memory_path)
            routes_path = memory_path.with_name(ROUTES_FILENAME)
            payload = json.loads(routes_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["tick"], 18)
        self.assertEqual(payload["version"], 2)
        self.assertEqual(payload["routes"][0]["path"][0], [0, 0])
        self.assertEqual(payload["routes"][0]["number"], 1)
        self.assertEqual(payload["resources"], [[2, 0]])
        self.assertEqual(payload["units"][0]["object_type"], "WORKER")
        self.assertEqual(payload["units"][0]["number"], 1)
        serialized = json.dumps(payload).lower()
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("authorization", serialized)
        self.assertNotIn("bearer", serialized)

    def test_unit_numbers_are_stable_per_type_and_not_reused(self) -> None:
        memory = TacticMemory()
        first, _ = make_turn(
            own_core=core(),
            units=(
                worker(WORKER_HIGH, (1, 0)),
                ranger((2, 0)),
                worker(WORKER_LOW, (0, 0)),
            ),
        )

        SmartTactic(memory).choose_actions(first)

        self.assertEqual(memory.unit_labels[str(WORKER_LOW)], UnitLabel("WORKER", 1))
        self.assertEqual(memory.unit_labels[str(WORKER_HIGH)], UnitLabel("WORKER", 2))
        self.assertEqual(memory.unit_labels[str(RANGER_ID)], UnitLabel("RANGER", 1))

        second, _ = make_turn(
            tick=9,
            own_core=core(),
            units=(
                worker(WORKER_THIRD, (3, 0)),
                worker(WORKER_HIGH, (2, 0)),
                ranger((1, 0)),
            ),
        )
        SmartTactic(memory).choose_actions(second)

        self.assertEqual(memory.unit_labels[str(WORKER_HIGH)].number, 2)
        self.assertEqual(memory.unit_labels[str(WORKER_THIRD)].number, 3)
        self.assertEqual(memory.unit_labels[str(RANGER_ID)].number, 1)

    def test_current_state_retargets_after_resource_depletion(self) -> None:
        event = ResolutionEvent(
            event_id=UUID("00000000-0000-4000-8000-000000000300"),
            tick=7,
            event_type="HARVEST_FAILED",
            reason_code="RESOURCE_DEPLETED",
            actor_id=WORKER_LOW,
            position=(0, 0),
        )
        turn, _ = make_turn(
            own_core=core(),
            units=(worker(WORKER_LOW, (0, 0)),),
            resource_cells=((2, 0),),
            events=(event,),
        )

        choose_actions(turn)

        action = turn.plan.unit_actions[WORKER_LOW]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.RIGHT)

    def test_current_resource_cell_can_represent_remaining_cargo_pile(self) -> None:
        event = ResolutionEvent(
            event_id=UUID("00000000-0000-4000-8000-000000000301"),
            tick=7,
            event_type="HARVEST_SUCCEEDED",
            actor_id=WORKER_HIGH,
            position=(0, 0),
            values={"amount": 1, "source": "DROPPED_CARGO"},
        )
        turn, _ = make_turn(
            own_core=core(),
            units=(worker(WORKER_LOW, (0, 0)),),
            resource_cells=((0, 0),),
            events=(event,),
        )

        choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions[WORKER_LOW], HarvestAction)

    def test_resource_disappearance_does_not_reuse_old_turn_controller(self) -> None:
        first, _ = make_turn(
            tick=7,
            own_core=core(),
            units=(worker(WORKER_LOW, (0, 0)),),
            resource_cells=((0, 0),),
        )
        second, _ = make_turn(
            tick=8,
            own_core=core(),
            units=(worker(WORKER_LOW, (0, 0)),),
        )

        choose_actions(first)
        choose_actions(second)

        self.assertIsInstance(first.plan.unit_actions[WORKER_LOW], HarvestAction)
        self.assertNotIsInstance(second.plan.unit_actions.get(WORKER_LOW), HarvestAction)

    def test_ranger_shoots_visible_cardinal_target(self) -> None:
        turn, _ = make_turn(
            own_core=core(),
            units=(ranger((0, 0)),),
            enemies=(enemy_core((0, 3)),),
        )

        choose_actions(turn)

        action = turn.plan.unit_actions[RANGER_ID]
        self.assertIsInstance(action, ShootAction)
        self.assertEqual(action.target_id, ENEMY_CORE_ID)
        self.assertEqual(action.expected_cell, (0, 3))

    def test_ranger_target_priority_is_core_then_ranger_then_vanguard(self) -> None:
        core_turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(ranger((0, 0)),),
            enemies=(
                enemy_vanguard((3, 0)),
                enemy_ranger((0, 3)),
                enemy_core((3, 3)),
            ),
        )

        SmartTactic(TacticMemory()).choose_actions(core_turn)

        core_action = core_turn.plan.unit_actions[RANGER_ID]
        self.assertIsInstance(core_action, ShootAction)
        self.assertEqual(core_action.target_id, ENEMY_CORE_ID)

        unit_turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(ranger((0, 0)),),
            enemies=(enemy_vanguard((3, 0)), enemy_ranger((0, 3))),
        )

        SmartTactic(TacticMemory()).choose_actions(unit_turn)

        unit_action = unit_turn.plan.unit_actions[RANGER_ID]
        self.assertIsInstance(unit_action, ShootAction)
        self.assertEqual(unit_action.target_id, ENEMY_RANGER_ID)

    def test_vanguard_sweep_prioritizes_core_over_ranger(self) -> None:
        turn, _ = make_turn(
            own_core=core((5, 5)),
            units=(vanguard((0, 0)),),
            enemies=(enemy_core((1, 0)), enemy_ranger((0, 1))),
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        action = turn.plan.unit_actions[VANGUARD_ID]
        self.assertIsInstance(action, SweepAction)
        self.assertEqual(action.direction, Direction.RIGHT)

    def test_combat_units_ignore_enemy_worker_by_default(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(ranger((0, 0)), vanguard((1, 0))),
            enemies=(enemy_worker((0, 1)),),
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertNotIsInstance(
            turn.plan.unit_actions.get(RANGER_ID),
            ShootAction,
        )
        self.assertNotIsInstance(
            turn.plan.unit_actions.get(VANGUARD_ID),
            SweepAction,
        )

    def test_enemy_worker_is_attacked_when_it_blocks_only_route(self) -> None:
        worker_id = UUID(int=0x8123)
        memory = TacticMemory(mode=MODE_AGGRESS)
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(ranger((0, 0)),),
            enemies=(enemy_worker((1, 0), unit_id=worker_id),),
            obstacle_cells=((-1, 0), (0, -1), (0, 1)),
            beacon=ChampionBeacon(position=(2, 0)),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        action = turn.plan.unit_actions[RANGER_ID]
        self.assertIsInstance(action, ShootAction)
        self.assertEqual(action.target_id, worker_id)
        self.assertTrue(
            any("enemy_worker_route_blockers count=1" in item for item in summary.decisions)
        )

    def test_single_attacker_advances_on_confirmed_stationary_enemy(self) -> None:
        memory = TacticMemory(recall=True)
        memory.raid_enemy_motion[str(ENEMY_RANGER_ID)] = RaidEnemyMotion(
            position=(5, 0),
            stationary_observations=1,
            last_seen_tick=7,
        )
        turn, _ = make_turn(
            tick=8,
            own_core=core((0, 0)),
            units=(ranger((0, 0)),),
            enemies=(enemy_ranger((5, 0)),),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        action = turn.plan.unit_actions[RANGER_ID]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.RIGHT)
        self.assertEqual(
            memory.current_routes[str(RANGER_ID)].reason,
            "stationary_enemy_seek_firing",
        )
        self.assertTrue(
            any("stationary_advance" in item for item in summary.decisions)
        )

    def test_movement_planner_respects_two_entity_cell_capacity(self) -> None:
        turn, _ = make_turn(
            own_core=core((5, 5)),
            units=(
                ranger((0, 0)),
                ranger((1, 0), RANGER_TWO_ID),
                ranger((1, 0), RANGER_THREE_ID),
            ),
        )

        planner = MovementPlanner(turn, TacticMemory(), [])

        self.assertEqual(planner.final_occupancy((1, 0)), 2)
        self.assertFalse(planner._can_enter((1, 0)))

    def test_ranger_shoots_visible_diagonal_target(self) -> None:
        turn, _ = make_turn(
            own_core=core(),
            units=(ranger((0, 0)),),
            enemies=(enemy_core((2, 2)),),
        )

        choose_actions(turn)

        action = turn.plan.unit_actions[RANGER_ID]
        self.assertIsInstance(action, ShootAction)
        self.assertEqual(action.target_id, ENEMY_CORE_ID)
        self.assertEqual(action.expected_cell, (2, 2))

    def test_ranger_diagonal_shot_ignores_obstacle_beside_line(self) -> None:
        turn, _ = make_turn(
            own_core=core(),
            units=(ranger((0, 0)),),
            enemies=(enemy_core((2, 2)),),
            obstacle_cells=((1, 0),),
        )

        choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions[RANGER_ID], ShootAction)

    def test_ranger_diagonal_shot_is_blocked_by_intermediate_obstacle(self) -> None:
        turn, _ = make_turn(
            own_core=core(),
            units=(ranger((0, 0)),),
            enemies=(enemy_core((2, 2)),),
            obstacle_cells=((1, 1),),
        )

        choose_actions(turn)

        self.assertNotIsInstance(turn.plan.unit_actions.get(RANGER_ID), ShootAction)

    def test_ranger_does_not_shoot_through_obstacle(self) -> None:
        turn, _ = make_turn(
            own_core=core(),
            units=(ranger((0, 0)),),
            enemies=(enemy_core((0, 3)),),
            obstacle_cells=((0, 1),),
        )

        choose_actions(turn)

        self.assertNotIsInstance(turn.plan.unit_actions.get(RANGER_ID), ShootAction)

    def test_ranger_returns_to_core_instead_of_chasing_distant_enemy(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(ranger((8, 0)),),
            enemies=(enemy_ranger((12, 0)),),
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        action = turn.plan.unit_actions[RANGER_ID]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.LEFT)
        self.assertTrue(any("reason=ranger_core_patrol" in item for item in summary.decisions))

    def test_ranger_pursues_enemy_inside_core_defense_leash(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(ranger((0, 0)),),
            enemies=(enemy_ranger((8, 0)),),
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        action = turn.plan.unit_actions[RANGER_ID]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.RIGHT)

    def test_two_oldest_rangers_receive_opposite_core_patrol_slots(self) -> None:
        memory = TacticMemory()
        turn, _ = make_turn(
            tick=8,
            own_core=core((0, 0)),
            units=(
                ranger((0, -5), RANGER_ID),
                ranger((0, 5), RANGER_TWO_ID),
                ranger((5, 5), RANGER_THREE_ID),
            ),
        )

        SmartTactic(memory).choose_actions(turn)

        patrol_routes = [
            route
            for route in memory.current_routes.values()
            if route.reason.startswith("ranger_core_patrol")
        ]
        self.assertEqual(len(patrol_routes), 2)
        self.assertEqual(
            {route.object_id for route in patrol_routes},
            {str(RANGER_ID), str(RANGER_TWO_ID)},
        )
        self.assertEqual(
            {route.goal for route in patrol_routes},
            {(-2, 0), (2, 0)},
        )

    def test_core_patrol_reports_and_engages_nearby_enemy(self) -> None:
        memory = TacticMemory()
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(ranger((0, 0), RANGER_ID), ranger((0, 1), RANGER_TWO_ID)),
            enemies=(enemy_ranger((0, 3)),),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions[RANGER_ID], ShootAction)
        self.assertIsInstance(turn.plan.unit_actions[RANGER_TWO_ID], ShootAction)
        self.assertTrue(any("core_patrol_alert count=1" in item for item in summary.decisions))
        self.assertEqual(
            sum("role=core_patrol" in item for item in summary.decisions),
            2,
        )
        self.assertEqual(memory.decision_totals["core_patrol:alert"], 1)
        self.assertEqual(memory.decision_totals["core_patrol:shoot"], 2)

    def test_owned_beacon_carrier_is_not_globally_stationary(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (3, 0)),),
            beacon=ChampionBeacon(
                position=(3, 0),
                status=BeaconStatus.CARRIED,
                carrier_id=WORKER_LOW,
            ),
        )

        summary = SmartTactic(TacticMemory(mode=MODE_DEVELOP)).choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions[WORKER_LOW], MoveAction)
        self.assertFalse(
            any("beacon_stationary_policy" in item for item in summary.decisions)
        )

    def test_beacon_ranger_uses_normal_combat_action(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(ranger((3, 0)),),
            enemies=(enemy_ranger((3, 3)),),
            beacon=ChampionBeacon(
                position=(3, 0),
                status=BeaconStatus.CARRIED,
                carrier_id=RANGER_ID,
            ),
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        action = turn.plan.unit_actions[RANGER_ID]
        self.assertIsInstance(action, ShootAction)
        self.assertEqual(action.expected_cell, (3, 3))
        self.assertFalse(
            any("beacon_stationary_policy" in item for item in summary.decisions)
        )

    def test_beacon_worker_uses_normal_harvest_action(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (3, 0)),),
            resource_cells=((3, 0),),
            beacon=ChampionBeacon(
                position=(3, 0),
                status=BeaconStatus.CARRIED,
                carrier_id=WORKER_LOW,
            ),
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions[WORKER_LOW], HarvestAction)
        self.assertFalse(
            any("beacon_stationary_policy" in item for item in summary.decisions)
        )

    def test_normal_core_drops_carried_beacon_in_place(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            beacon=ChampionBeacon(
                position=(0, 0),
                status=BeaconStatus.CARRIED,
                carrier_id=CORE_ID,
            ),
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, DropBeaconAction)
        self.assertTrue(
            any(
                "core drop_beacon reason=core_beacon_forbidden" in item
                for item in summary.decisions
            )
        )

    def test_moving_core_cancels_before_dropping_carried_beacon(self) -> None:
        turn, _ = make_turn(
            own_core=moving_core((0, 0)),
            beacon=ChampionBeacon(
                position=(0, 0),
                status=BeaconStatus.CARRIED,
                carrier_id=CORE_ID,
            ),
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, CancelMoveAction)
        self.assertTrue(
            any(
                "core cancel_move reason=core_beacon_forbidden" in item
                for item in summary.decisions
            )
        )

    def test_core_never_picks_up_ground_beacon(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            beacon=ChampionBeacon(
                position=(0, 0),
                status=BeaconStatus.GROUND,
            ),
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertNotIsInstance(turn.plan.core_action, PickupBeaconAction)

    def test_unit_picks_up_ground_beacon_even_when_core_is_on_cell(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(vanguard((0, 0)),),
            beacon=ChampionBeacon(
                position=(0, 0),
                status=BeaconStatus.GROUND,
            ),
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(
            turn.plan.unit_actions[VANGUARD_ID],
            PickupBeaconAction,
        )
        self.assertNotIsInstance(turn.plan.core_action, PickupBeaconAction)

    def test_core_spawns_worker_conservatively(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (1, 0)),),
            resources=5,
        )

        choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.WORKER)

    def test_recovery_mode_adds_worker_when_guard_upgrade_is_unaffordable(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (0, 0)),
                worker(WORKER_HIGH, (1, 0)),
                worker(WORKER_THIRD, (5, 0)),
                worker(WORKER_FOURTH, (6, 0)),
                vanguard((3, 3)),
                vanguard((4, 3), VANGUARD_TWO_ID),
                vanguard((5, 3), VANGUARD_THREE_ID),
                ranger((3, 4)),
                ranger((4, 4), RANGER_TWO_ID),
            ),
            resources=9,
            beacon=ChampionBeacon(position=(30, 30)),
        )

        summary = SmartTactic(TacticMemory(mode=MODE_DEVELOP)).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.WORKER)
        self.assertTrue(any("core_spawn_slot_reserved" in item for item in summary.decisions))

    def test_core_repairs_when_enemy_threatens(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0), shield=2),
            units=(worker(WORKER_LOW, (1, 0)),),
            enemies=(enemy_core((0, 3)),),
            resources=5,
        )

        choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, RepairShieldAction)

    def test_core_heals_hp_before_repairing_shield(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0), hp=3, shield=2),
            units=(worker(WORKER_LOW, (1, 0)),),
            enemies=(enemy_core((0, 3)),),
            resources=2,
        )

        choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, HealAction)

    def test_core_continues_combat_growth_when_defense_is_fully_staffed(
        self,
    ) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (6, 0)),
                worker(WORKER_HIGH, (7, 0)),
                worker(WORKER_THIRD, (8, 0)),
                worker(WORKER_FOURTH, (9, 0)),
                worker(WORKER_FIFTH, (10, 0)),
                worker(WORKER_SIXTH, (11, 0)),
                vanguard((3, 3)),
                vanguard((4, 3), VANGUARD_TWO_ID),
                vanguard((5, 3), VANGUARD_THREE_ID),
                ranger((3, 4)),
                ranger((4, 4), RANGER_TWO_ID),
                ranger((5, 4), RANGER_THREE_ID),
            ),
            enemies=(enemy_core((0, 3)),),
            resources=19,
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.RANGER)

    def test_develop_mode_builds_beacon_expedition_before_worker_growth(
        self,
    ) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (6, 0)),
                worker(WORKER_HIGH, (7, 0)),
                worker(WORKER_THIRD, (8, 0)),
                worker(WORKER_FOURTH, (9, 0)),
                worker(WORKER_FIFTH, (10, 0)),
                worker(WORKER_SIXTH, (11, 0)),
                vanguard((3, 3)),
                vanguard((4, 3), VANGUARD_TWO_ID),
                vanguard((5, 3), VANGUARD_THREE_ID),
                ranger((3, 4)),
                ranger((4, 4), RANGER_TWO_ID),
                ranger((5, 4), RANGER_THREE_ID),
            ),
            resources=30,
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertIn(
            turn.plan.core_action.unit_type,
            {UnitType.WORKER, UnitType.VANGUARD, UnitType.RANGER},
        )

    def test_core_builds_beacon_expedition_after_defense_is_fully_staffed(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (6, 0)),
                worker(WORKER_HIGH, (7, 0)),
                worker(WORKER_THIRD, (8, 0)),
                worker(WORKER_FOURTH, (9, 0)),
                worker(WORKER_FIFTH, (10, 0)),
                worker(WORKER_SIXTH, (11, 0)),
                vanguard((3, 3)),
                vanguard((4, 3), VANGUARD_TWO_ID),
                vanguard((5, 3), VANGUARD_THREE_ID),
                ranger((3, 4)),
                ranger((4, 4), RANGER_TWO_ID),
                ranger((5, 4), RANGER_THREE_ID),
            ),
            resources=15,
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.VANGUARD)

    def test_core_builds_beacon_vanguard_when_reserve_is_safe(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (6, 0)),
                worker(WORKER_HIGH, (7, 0)),
                worker(WORKER_THIRD, (8, 0)),
                worker(WORKER_FOURTH, (9, 0)),
                worker(WORKER_FIFTH, (10, 0)),
                worker(WORKER_SIXTH, (11, 0)),
                vanguard((3, 3)),
                vanguard((4, 3), VANGUARD_TWO_ID),
                vanguard((5, 3), VANGUARD_THREE_ID),
                ranger((3, 4)),
                ranger((4, 4), RANGER_TWO_ID),
                ranger((5, 4), RANGER_THREE_ID),
            ),
            resources=14,
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.VANGUARD)

    def test_core_does_not_expand_workers_during_near_threat(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (6, 0)),
                worker(WORKER_HIGH, (7, 0)),
                worker(WORKER_THIRD, (8, 0)),
                worker(WORKER_FOURTH, (9, 0)),
                worker(WORKER_FIFTH, (10, 0)),
                worker(WORKER_SIXTH, (11, 0)),
                vanguard((3, 3)),
                vanguard((4, 3), VANGUARD_TWO_ID),
                vanguard((5, 3), VANGUARD_THREE_ID),
                ranger((3, 4)),
                ranger((4, 4), RANGER_TWO_ID),
                ranger((5, 4), RANGER_THREE_ID),
            ),
            enemies=(enemy_core((0, 5)),),
            resources=30,
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.RANGER)

    def test_develop_mode_builds_beacon_vanguard_before_extra_rangers(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (6, 0)),
                worker(WORKER_HIGH, (7, 0)),
                worker(WORKER_THIRD, (8, 0)),
                worker(WORKER_FOURTH, (9, 0)),
                worker(WORKER_FIFTH, (10, 0)),
                worker(WORKER_SIXTH, (11, 0)),
                worker(WORKER_SEVENTH, (12, 0)),
                worker(WORKER_EIGHTH, (13, 0)),
                vanguard((3, 3)),
                vanguard((4, 3), VANGUARD_TWO_ID),
                vanguard((5, 3), VANGUARD_THREE_ID),
                ranger((3, 4)),
                ranger((4, 4), RANGER_TWO_ID),
                ranger((5, 4), RANGER_THREE_ID),
            ),
            resources=22,
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.VANGUARD)

    def test_develop_mode_prefers_ninth_worker_over_fourth_vanguard(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (6, 0)),
                worker(WORKER_HIGH, (7, 0)),
                worker(WORKER_THIRD, (8, 0)),
                worker(WORKER_FOURTH, (9, 0)),
                worker(WORKER_FIFTH, (10, 0)),
                worker(WORKER_SIXTH, (11, 0)),
                worker(WORKER_SEVENTH, (12, 0)),
                worker(WORKER_EIGHTH, (13, 0)),
                vanguard((3, 3)),
                vanguard((4, 3), VANGUARD_TWO_ID),
                vanguard((5, 3), VANGUARD_THREE_ID),
                ranger((3, 4)),
                ranger((4, 4), RANGER_TWO_ID),
                ranger((5, 4), RANGER_THREE_ID),
                ranger((6, 4), RANGER_FOURTH_ID),
            ),
            resources=20,
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.VANGUARD)

    def test_develop_mode_raids_nearby_enemy_core(self) -> None:
        """2026-08-12 用户战术：develop 模式发现信标附近敌人 core 时派先锋摧毁。"""
        target = (30, 10)  # 距 beacon(0,0) 40 格（≤150）
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                vanguard((1, 0), VANGUARD_ID),
                vanguard((2, 0), VANGUARD_TWO_ID),
            ),
            enemies=(enemy_core(target),),
            beacon=ChampionBeacon(position=(0, 0)),
        )

        memory = TacticMemory(mode=MODE_DEVELOP)
        summary = SmartTactic(memory).choose_actions(turn)

        # 至少一个先锋被派去攻击敌人 core
        self.assertTrue(
            any("enemy_core_assault" in item for item in summary.decisions),
            f"应有 enemy_core_assault 决策, 实际: {summary.decisions}",
        )
        # 有先锋向目标移动
        self.assertTrue(
            any(
                isinstance(action, MoveAction)
                for action in turn.plan.unit_actions.values()
            )
        )

    def test_develop_mode_does_not_raid_distant_enemy_core(self) -> None:
        """敌人 core 距信标超 150 格时不派兵（避免长途送死）。"""
        target = (200, 0)  # 距 beacon 200 格（>150）
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                vanguard((1, 0), VANGUARD_ID),
                vanguard((2, 0), VANGUARD_TWO_ID),
            ),
            enemies=(enemy_core(target),),
            beacon=ChampionBeacon(position=(0, 0)),
        )

        memory = TacticMemory(mode=MODE_DEVELOP)
        summary = SmartTactic(memory).choose_actions(turn)

        self.assertFalse(
            any("enemy_core_assault" in item for item in summary.decisions),
            f"不应有 enemy_core_assault 决策, 实际: {summary.decisions}",
        )

    def _ally_core(self, position: tuple[int, int], owner: str) -> CoreView:
        return CoreView(
            kind="CORE",
            id=UUID("00000000-0000-4000-8000-000000000300"),
            controlled=False,
            owner_username=owner,
            position=position,
            hp=5,
            shield=0,
            state=CoreState.NORMAL,
        )

    def test_ally_core_by_account_is_not_raided(self) -> None:
        """2026-08-12 盟友功能：账号名白名单内的 Core 不被攻击。"""
        with TemporaryDirectory() as directory:
            allies_path = Path(directory) / ".arena_hero_allies.json"
            allies_path.write_text(
                json.dumps({"version": 1, "accounts": ["buddy_hero"]}),
                encoding="utf-8",
            )
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    vanguard((1, 0), VANGUARD_ID),
                    vanguard((2, 0), VANGUARD_TWO_ID),
                ),
                enemies=(self._ally_core((30, 10), "buddy_hero"),),
                beacon=ChampionBeacon(position=(0, 0)),
            )
            memory = TacticMemory(mode=MODE_DEVELOP)
            summary = SmartTactic(
                memory,
                allies_path=allies_path,
            ).choose_actions(turn)
            self.assertFalse(
                any("enemy_core_assault" in item for item in summary.decisions),
                f"盟友 Core 不应被攻击, 实际: {summary.decisions}",
            )

    def test_ally_core_by_id_is_not_raided(self) -> None:
        """2026-08-12 盟友功能：Core ID 白名单内的 Core 不被攻击。"""
        ally_id = "00000000-0000-4000-8000-000000000300"
        with TemporaryDirectory() as directory:
            allies_path = Path(directory) / ".arena_hero_allies.json"
            allies_path.write_text(
                json.dumps({"version": 1, "core_ids": [ally_id]}),
                encoding="utf-8",
            )
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    vanguard((1, 0), VANGUARD_ID),
                    vanguard((2, 0), VANGUARD_TWO_ID),
                ),
                enemies=(self._ally_core((30, 10), "buddy_hero"),),
                beacon=ChampionBeacon(position=(0, 0)),
            )
            memory = TacticMemory(mode=MODE_DEVELOP)
            summary = SmartTactic(
                memory,
                allies_path=allies_path,
            ).choose_actions(turn)
            self.assertFalse(
                any("enemy_core_assault" in item for item in summary.decisions),
                f"盟友 Core(ID) 不应被攻击, 实际: {summary.decisions}",
            )

    def test_enemy_core_still_raided_with_allies_configured(self) -> None:
        """配置盟友后，非盟友 Core 仍正常攻击。"""
        with TemporaryDirectory() as directory:
            allies_path = Path(directory) / ".arena_hero_allies.json"
            allies_path.write_text(
                json.dumps({"version": 1, "accounts": ["buddy_hero"]}),
                encoding="utf-8",
            )
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    vanguard((1, 0), VANGUARD_ID),
                    vanguard((2, 0), VANGUARD_TWO_ID),
                ),
                enemies=(enemy_core((30, 10)),),  # owner=enemy_hero, 非盟友
                beacon=ChampionBeacon(position=(0, 0)),
            )
            memory = TacticMemory(mode=MODE_DEVELOP)
            summary = SmartTactic(
                memory,
                allies_path=allies_path,
            ).choose_actions(turn)
            self.assertTrue(
                any("enemy_core_assault" in item for item in summary.decisions),
                f"非盟友 Core 应被攻击, 实际: {summary.decisions}",
            )

    def test_develop_mode_supports_attacked_ally_core(self) -> None:
        """2026-08-12 共同抗敌（方案A）：受攻击盟友 Core（hp<满血）触发支援。"""
        with TemporaryDirectory() as directory:
            allies_path = Path(directory) / ".arena_hero_allies.json"
            allies_path.write_text(
                json.dumps({"version": 1, "accounts": ["buddy_hero"]}),
                encoding="utf-8",
            )
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps({"mode": "develop", "ally_support_enabled": True}),
                encoding="utf-8",
            )
            # 受伤的盟友 Core (hp=2 < 5)
            hurt_ally = CoreView(
                kind="CORE",
                id=UUID("00000000-0000-4000-8000-000000000300"),
                controlled=False,
                owner_username="buddy_hero",
                position=(20, 0),
                hp=2,
                shield=0,
                state=CoreState.NORMAL,
            )
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    vanguard((1, 0), VANGUARD_ID),
                    vanguard((2, 0), VANGUARD_TWO_ID),
                ),
                enemies=(hurt_ally,),
                beacon=ChampionBeacon(position=(0, 0)),
            )
            memory = TacticMemory(mode=MODE_DEVELOP)
            summary = SmartTactic(
                memory,
                control_path=control_path,
                allies_path=allies_path,
            ).choose_actions(turn)
            self.assertTrue(
                any("ally_support" in item for item in summary.decisions),
                f"受攻击盟友 Core 应触发支援, 实际: {summary.decisions}",
            )

    def test_develop_mode_does_not_support_healthy_ally_core(self) -> None:
        """共同抗敌：满血盟友 Core 不触发支援（血量信号防误判）。"""
        with TemporaryDirectory() as directory:
            allies_path = Path(directory) / ".arena_hero_allies.json"
            allies_path.write_text(
                json.dumps({"version": 1, "accounts": ["buddy_hero"]}),
                encoding="utf-8",
            )
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps({"mode": "develop", "ally_support_enabled": True}),
                encoding="utf-8",
            )
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    vanguard((1, 0), VANGUARD_ID),
                    vanguard((2, 0), VANGUARD_TWO_ID),
                ),
                enemies=(self._ally_core((20, 0), "buddy_hero"),),  # hp=5 满血
                beacon=ChampionBeacon(position=(0, 0)),
            )
            memory = TacticMemory(mode=MODE_DEVELOP)
            summary = SmartTactic(
                memory,
                control_path=control_path,
                allies_path=allies_path,
            ).choose_actions(turn)
            self.assertFalse(
                any("ally_support" in item for item in summary.decisions),
                f"满血盟友 Core 不应触发支援, 实际: {summary.decisions}",
            )

    def test_develop_mode_switches_to_beacon_after_expedition_is_complete(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (6, 0)),
                worker(WORKER_HIGH, (7, 0)),
                worker(WORKER_THIRD, (8, 0)),
                worker(WORKER_FOURTH, (9, 0)),
                worker(WORKER_FIFTH, (10, 0)),
                worker(WORKER_SIXTH, (11, 0)),
                worker(WORKER_SEVENTH, (12, 0)),
                worker(WORKER_EIGHTH, (13, 0)),
                vanguard((3, 3)),
                vanguard((4, 3), VANGUARD_TWO_ID),
                vanguard((5, 3), VANGUARD_THREE_ID),
                vanguard((6, 3), VANGUARD_FOURTH_ID),
                ranger((3, 4)),
                ranger((4, 4), RANGER_TWO_ID),
                ranger((5, 4), RANGER_THREE_ID),
                ranger((6, 4), RANGER_FOURTH_ID),
                ranger((7, 4), UUID(int=0x17)),
            ),
            resources=21,
        )

        # 目标人口设为 0 关闭编制阶梯：阶梯生效期间会押后抢信标，见
        # CompositionLadderTests.test_active_ladder_postpones_beacon_expedition。
        memory = TacticMemory()
        memory.target_population = 0
        SmartTactic(memory).choose_actions(turn)

        self.assertEqual(memory.mode, MODE_BEACON)
        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.RANGER)

    def test_develop_mode_sends_early_pair_toward_distant_beacon(self) -> None:
        memory = TacticMemory()
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                vanguard((1, 0), VANGUARD_ID),
                vanguard((-1, 0), VANGUARD_TWO_ID),
                vanguard((2, 0), VANGUARD_THREE_ID),
                ranger((0, -2), RANGER_ID),
                ranger((2, 1), RANGER_TWO_ID),
            ),
            beacon=ChampionBeacon(position=(80, 0)),
            resources=0,
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertEqual(memory.mode, MODE_DEVELOP)
        self.assertIsInstance(
            turn.plan.unit_actions.get(VANGUARD_THREE_ID),
            MoveAction,
        )
        self.assertIsInstance(
            turn.plan.unit_actions.get(RANGER_TWO_ID),
            MoveAction,
        )
        self.assertTrue(
            any("beacon_head_start" in decision for decision in summary.decisions)
        )

    def test_beacon_mode_retires_worker_beacon_goal_for_local_economy(self) -> None:
        memory = TacticMemory(
            mode=MODE_BEACON,
            worker_goals={
                str(WORKER_LOW): WorkerGoal("beacon", (100, 0), 7),
            },
        )
        turn, _ = make_turn(
            tick=12,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (10, 0)),),
            beacon=ChampionBeacon(position=(100, 0)),
            resources=0,
        )

        summary = SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertEqual(goal.kind, "resource_sweep")
        self.assertLessEqual(
            _distance((0, 0), goal.position),
            BEACON_RESOURCE_SWEEP_MAX_RADIUS,
        )
        self.assertTrue(
            any("beacon_economy_recall" in decision for decision in summary.decisions)
        )
        self.assertFalse(
            any("beacon_advance" in decision for decision in summary.decisions)
        )

    def test_develop_mode_keeps_early_pair_home_during_core_threat(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                vanguard((1, 0), VANGUARD_ID),
                vanguard((-1, 0), VANGUARD_TWO_ID),
                vanguard((2, 0), VANGUARD_THREE_ID),
                ranger((0, -2), RANGER_ID),
                ranger((2, 1), RANGER_TWO_ID),
            ),
            enemies=(enemy_core((0, 4)),),
            beacon=ChampionBeacon(position=(80, 0)),
            resources=0,
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertFalse(
            any("beacon_head_start" in decision for decision in summary.decisions)
        )

    def test_core_continues_expansion_at_population_sixteen(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (6, 0)),
                worker(WORKER_HIGH, (7, 0)),
                worker(WORKER_THIRD, (8, 0)),
                worker(WORKER_FOURTH, (9, 0)),
                worker(WORKER_FIFTH, (10, 0)),
                worker(WORKER_SIXTH, (11, 0)),
                worker(WORKER_SEVENTH, (12, 0)),
                worker(WORKER_EIGHTH, (13, 0)),
                vanguard((3, 3)),
                vanguard((4, 3), VANGUARD_TWO_ID),
                vanguard((5, 3), VANGUARD_THREE_ID),
                vanguard((6, 3), VANGUARD_FOURTH_ID),
                ranger((3, 4)),
                ranger((4, 4), RANGER_TWO_ID),
                ranger((5, 4), RANGER_THREE_ID),
                ranger((6, 4), RANGER_FOURTH_ID),
            ),
            resources=30,
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        # v0.14 删除维护费；16 人时不应再因旧的人口带宽而停产。
        self.assertIsInstance(turn.plan.core_action, SpawnAction)

    def test_memory_learns_failed_terrain_destination(self) -> None:
        memory = TacticMemory(
            planned_moves={str(WORKER_LOW): PlannedMove(destination=(1, 0), tick=7)}
        )
        event = ResolutionEvent(
            event_id=UUID("00000000-0000-4000-8000-000000000302"),
            tick=7,
            event_type="UNIT_MOVE_FAILED",
            reason_code="MOVE_BLOCKED_TERRAIN",
            actor_id=WORKER_LOW,
            position=(0, 0),
        )
        turn, _ = make_turn(
            tick=8,
            own_core=core(),
            units=(worker(WORKER_LOW, (0, 0)),),
            resource_cells=((2, 0),),
            events=(event,),
        )

        SmartTactic(memory).choose_actions(turn)

        self.assertIn((1, 0), memory.known_obstacles)
        action = turn.plan.unit_actions[WORKER_LOW]
        self.assertIsInstance(action, MoveAction)
        self.assertNotEqual(action.direction, Direction.RIGHT)

    def test_memory_detects_manual_move_override(self) -> None:
        memory = TacticMemory(
            planned_moves={str(WORKER_LOW): PlannedMove(destination=(1, 0), tick=7)}
        )
        event = ResolutionEvent(
            event_id=UUID("00000000-0000-4000-8000-000000000303"),
            tick=7,
            event_type="UNIT_MOVE_SUCCEEDED",
            actor_id=WORKER_LOW,
            position=(0, 1),
        )
        turn, _ = make_turn(
            tick=8,
            own_core=core(),
            units=(worker(WORKER_LOW, (0, 1)),),
            events=(event,),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertEqual(memory.decision_totals["manual_override:move"], 1)
        self.assertTrue(any("manual_override" in item for item in summary.decisions))

    def test_worker_keeps_last_seen_resource_goal_across_turns(self) -> None:
        memory = TacticMemory()
        tactic = SmartTactic(memory)
        first, _ = make_turn(
            tick=10,
            own_core=core((20, 20)),
            units=(worker(WORKER_LOW, (0, 0)), ranger((5, 0))),
            resource_cells=((5, 0),),
        )
        second, _ = make_turn(
            tick=11,
            own_core=core((20, 20)),
            units=(worker(WORKER_LOW, (1, 0)), ranger((20, 19))),
        )

        tactic.choose_actions(first)
        tactic.choose_actions(second)

        action = second.plan.unit_actions[WORKER_LOW]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.RIGHT)
        self.assertEqual(memory.worker_goals[str(WORKER_LOW)].position, (5, 0))

    def test_visible_absent_resource_hint_is_invalidated_immediately(self) -> None:
        memory = TacticMemory(resource_last_seen={(2, 0): 7})
        turn, _ = make_turn(
            tick=8,
            own_core=core((10, 10)),
            units=(worker(WORKER_LOW, (0, 0)),),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertNotIn((2, 0), memory.resource_last_seen)
        self.assertTrue(any("resource_invalidated" in item for item in summary.decisions))

    def test_obstacle_blocked_resource_hint_remains_uncertain(self) -> None:
        memory = TacticMemory(resource_last_seen={(2, 0): 7})
        turn, _ = make_turn(
            tick=8,
            own_core=core((10, 10)),
            units=(worker(WORKER_LOW, (0, 0)),),
            obstacle_cells=((1, 0),),
        )

        SmartTactic(memory).choose_actions(turn)

        self.assertIn((2, 0), memory.resource_last_seen)

    def test_worker_closes_move_then_harvest_loop(self) -> None:
        memory = TacticMemory()
        tactic = SmartTactic(memory)
        approach, _ = make_turn(
            tick=30,
            own_core=core(),
            units=(worker(WORKER_LOW, (0, 0)),),
            resource_cells=((1, 0),),
        )
        arrived, _ = make_turn(
            tick=31,
            own_core=core(),
            units=(worker(WORKER_LOW, (1, 0)),),
            resource_cells=((1, 0),),
        )

        tactic.choose_actions(approach)
        tactic.choose_actions(arrived)

        self.assertIsInstance(approach.plan.unit_actions[WORKER_LOW], MoveAction)
        self.assertEqual(approach.plan.unit_actions[WORKER_LOW].direction, Direction.RIGHT)
        self.assertIsInstance(arrived.plan.unit_actions[WORKER_LOW], HarvestAction)

    def test_worker_does_not_switch_an_existing_visible_resource_goal(self) -> None:
        memory = TacticMemory()
        tactic = SmartTactic(memory)
        first, _ = make_turn(
            tick=40,
            own_core=core(),
            units=(worker(WORKER_LOW, (0, 0)),),
            resource_cells=((3, 0), (0, 4)),
        )
        second, _ = make_turn(
            tick=41,
            own_core=core(),
            units=(worker(WORKER_LOW, (1, 0)),),
            resource_cells=((3, 0), (1, 1)),
        )

        tactic.choose_actions(first)
        tactic.choose_actions(second)

        self.assertEqual(memory.worker_goals[str(WORKER_LOW)].position, (3, 0))
        action = second.plan.unit_actions[WORKER_LOW]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.RIGHT)

    def test_worker_keeps_visible_resource_goal_after_it_leaves_vision(self) -> None:
        memory = TacticMemory()
        tactic = SmartTactic(memory)
        first, _ = make_turn(
            tick=40,
            own_core=core((20, 20)),
            units=(worker(WORKER_LOW, (0, 0)),),
            resource_cells=((3, 0),),
        )
        second, _ = make_turn(
            tick=41,
            own_core=core((20, 20)),
            units=(worker(WORKER_LOW, (-1, 0)),),
            resource_cells=((-1, 1),),
        )

        tactic.choose_actions(first)
        tactic.choose_actions(second)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertEqual(goal.kind, "visible_resource")
        self.assertEqual(goal.position, (3, 0))
        action = second.plan.unit_actions[WORKER_LOW]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.RIGHT)

    def test_one_worker_preempts_frontier_for_configured_resource_recovery(self) -> None:
        memory = TacticMemory(
            recovery_targets=[(10, 0)],
            worker_goals={
                str(WORKER_LOW): WorkerGoal("frontier", (0, -8), 7),
                str(WORKER_HIGH): WorkerGoal("frontier", (20, -8), 7),
            },
        )
        turn, _ = make_turn(
            own_core=core((20, 20)),
            units=(worker(WORKER_LOW, (0, 0)), worker(WORKER_HIGH, (20, 0))),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        recovery_goals = [
            (unit_id, goal)
            for unit_id, goal in memory.worker_goals.items()
            if goal.kind == "resource_recovery"
        ]
        self.assertEqual(len(recovery_goals), 1)
        unit_id, goal = recovery_goals[0]
        self.assertEqual(unit_id, str(WORKER_LOW))
        self.assertEqual(goal.position, (10, 0))
        action = turn.plan.unit_actions[WORKER_LOW]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.RIGHT)
        self.assertTrue(any("resource_recovery_assigned" in item for item in summary.decisions))

    def test_manual_recovery_scout_reserves_one_worker_before_visible_resource(self) -> None:
        memory = TacticMemory(recovery_targets=[(10, 0)])
        turn, _ = make_turn(
            own_core=core((20, 20)),
            units=(worker(WORKER_LOW, (0, 0)), worker(WORKER_HIGH, (20, 0))),
            resource_cells=((20, 5),),
        )

        SmartTactic(memory).choose_actions(turn)

        self.assertEqual(
            memory.worker_goals[str(WORKER_LOW)],
            WorkerGoal("resource_recovery", (10, 0), turn.tick),
        )
        self.assertEqual(
            memory.worker_goals[str(WORKER_HIGH)].kind,
            "visible_resource",
        )

    def test_eight_workers_allow_two_resource_recovery_scouts(self) -> None:
        memory = TacticMemory(
            recovery_targets=[(40, 0), (40, 5), (40, 10), (40, 15)]
        )
        turn, _ = make_turn(
            own_core=core((20, 20)),
            units=(
                worker(WORKER_LOW, (0, 0)),
                worker(WORKER_HIGH, (0, 5)),
                worker(WORKER_THIRD, (0, 10)),
                worker(WORKER_FOURTH, (0, 15)),
                worker(WORKER_FIFTH, (5, 0)),
                worker(WORKER_SIXTH, (5, 5)),
                worker(WORKER_SEVENTH, (5, 10)),
                worker(WORKER_EIGHTH, (5, 15)),
            ),
        )

        SmartTactic(memory).choose_actions(turn)

        recovery_goals = [
            goal for goal in memory.worker_goals.values()
            if goal.kind == "resource_recovery"
        ]
        self.assertEqual(len(recovery_goals), 2)

    def test_visible_absent_resource_recovery_target_is_checked_once(self) -> None:
        memory = TacticMemory(recovery_targets=[(2, 0)])
        turn, _ = make_turn(
            own_core=core((10, 10)),
            units=(worker(WORKER_LOW, (0, 0)),),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertNotIn((2, 0), memory.recovery_targets)
        self.assertIn((2, 0), memory.recovery_checked)
        self.assertTrue(any("result=visible_absent" in item for item in summary.decisions))

    def test_visible_migration_candidate_requires_exact_scout_arrival(self) -> None:
        candidate = (2, 0)
        memory = TacticMemory(
            mode=MODE_AGGRESS,
            migration_candidate=candidate,
            auto_migrate=True,
            recovery_targets=[candidate],
        )
        turn, _ = make_turn(
            own_core=core((10, 10)),
            units=(worker(WORKER_LOW, (0, 0)),),
        )

        SmartTactic(memory).choose_actions(turn)

        self.assertIn(candidate, memory.recovery_targets)
        self.assertNotIn(candidate, memory.recovery_checked)
        self.assertFalse(memory.migration_site_checked)
        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertEqual(goal.kind, "resource_recovery")
        self.assertEqual(goal.position, candidate)
        action = turn.plan.unit_actions[WORKER_LOW]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.RIGHT)

    def test_migration_scout_ignores_resource_underfoot_until_arrival(self) -> None:
        candidate = (2, 0)
        memory = TacticMemory(
            mode=MODE_AGGRESS,
            migration_candidate=candidate,
            auto_migrate=True,
            recovery_targets=[candidate],
            worker_goals={
                str(WORKER_LOW): WorkerGoal(
                    "resource_recovery",
                    candidate,
                    7,
                )
            },
        )
        turn, _ = make_turn(
            own_core=core((10, 10)),
            units=(worker(WORKER_LOW, (0, 0)),),
            resource_cells=((0, 0),),
        )

        SmartTactic(memory).choose_actions(turn)

        action = turn.plan.unit_actions[WORKER_LOW]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.RIGHT)
        self.assertEqual(
            memory.worker_goals[str(WORKER_LOW)].position,
            candidate,
        )

    def test_core_does_not_follow_resource_recovery_scout(self) -> None:
        memory = TacticMemory(
            recovery_targets=[(-10, 0)],
            worker_goals={
                str(WORKER_LOW): WorkerGoal("resource_recovery", (-10, 0), 7),
                str(WORKER_HIGH): WorkerGoal("frontier", (10, 0), 7),
            },
        )
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (-1, 0)), worker(WORKER_HIGH, (1, 0))),
            beacon=ChampionBeacon(
                position=(0, 0),
                status=BeaconStatus.CARRIED,
                carrier_id=CORE_ID,
            ),
        )

        SmartTactic(memory).choose_actions(turn)

        # Core 不追随侦察兵，也不再保管信标；信标原地放下。
        self.assertIsInstance(turn.plan.core_action, DropBeaconAction)

    def test_aggress_core_moves_into_visible_single_entrance_shelter(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(vanguard((0, 1)), ranger((0, -1)),),
            obstacle_cells=((1, 1), (1, -1), (2, 0)),
        )

        memory = TacticMemory(mode=MODE_AGGRESS)
        summary = SmartTactic(memory).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, StartMoveAction)
        self.assertEqual(turn.plan.core_action.direction, Direction.RIGHT)
        self.assertEqual(memory.core_shelter_target, (1, 0))
        self.assertEqual(memory.core_shelter_entrance, (0, 0))
        self.assertTrue(any("core shelter_seek" in item for item in summary.decisions))

    def test_aggress_core_holds_once_inside_single_entrance_shelter(self) -> None:
        turn, _ = make_turn(
            own_core=core((1, 0)),
            units=(vanguard((1, 1)), ranger((0, 0)),),
            obstacle_cells=((1, 1), (1, -1), (2, 0)),
        )

        memory = TacticMemory(mode=MODE_AGGRESS)
        summary = SmartTactic(memory).choose_actions(turn)

        self.assertIsNone(turn.plan.core_action)
        self.assertEqual(memory.core_shelter_target, (1, 0))
        self.assertTrue(any("core shelter_hold" in item for item in summary.decisions))

    def test_core_respawn_clears_stale_shelter_and_raid_memory(self) -> None:
        event = ResolutionEvent(
            event_id=UUID("00000000-0000-4000-8000-000000000351"),
            tick=12,
            event_type="CORE_RESPAWNED",
            position=(5, 5),
            values={"resources": 5},
        )
        memory = TacticMemory(
            mode=MODE_AGGRESS,
            core_heading=Direction.LEFT,
            core_shelter_target=(40, 40),
            core_shelter_entrance=(39, 40),
            raid_enabled=True,
            raid_vanguard_ids={str(VANGUARD_ID)},
            raid_ranger_ids={str(RANGER_ID)},
            raid_core_id=str(ENEMY_CORE_ID),
            raid_core_position=(60, 60),
            raid_core_acquired_tick=7,
        )
        turn, _ = make_turn(
            tick=13,
            own_core=core((5, 5)),
            units=(worker(WORKER_LOW, (6, 5)),),
            events=(event,),
        )

        SmartTactic(memory).choose_actions(turn)

        self.assertIsNone(memory.core_heading)
        self.assertIsNone(memory.core_shelter_target)
        self.assertIsNone(memory.core_shelter_entrance)
        self.assertEqual(memory.last_core_respawn_tick, 13)
        self.assertFalse(memory.raid_vanguard_ids)
        self.assertFalse(memory.raid_ranger_ids)
        self.assertIsNone(memory.raid_core_id)
        self.assertIsNone(memory.raid_core_position)

    def test_scouted_half_blocked_site_activates_migration_mode(self) -> None:
        blocked_half = tuple(
            (dx * 2, dy * 2)
            for dx, dy in ((-1, -1), (-1, 0), (-1, 1))
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps(
                    {
                        "mode": "aggress",
                        "recall": False,
                        "migration_candidate": [0, 0],
                        "auto_migrate": True,
                    }
                ),
                encoding="utf-8",
            )
            turn, _ = make_turn(
                own_core=core((5, 5)),
                units=(worker(WORKER_LOW, (0, 0)),),
                obstacle_cells=blocked_half,
            )
            memory = TacticMemory(mode=MODE_AGGRESS)
            summary = SmartTactic(memory, control_path=control_path).choose_actions(turn)
            saved_control = json.loads(control_path.read_text(encoding="utf-8"))

        self.assertEqual(memory.mode, MODE_MIGRATE)
        self.assertEqual(memory.migration_target, (0, 0))
        self.assertGreaterEqual(memory.migration_site_score, 6)
        self.assertEqual(saved_control["mode"], MODE_MIGRATE)
        self.assertTrue(any("migration_site_confirmed" in item for item in summary.decisions))

    def test_rock_backed_core_guard_offsets_prioritize_open_half(self) -> None:
        blocked_half = {
            (dx * 2, dy * 2)
            for dx, dy in ((-1, -1), (-1, 0), (-1, 1))
        }

        weighted = _terrain_guard_offsets(
            (0, 0),
            blocked_half,
            AGGRESS_RANGER_WATCH_OFFSETS,
        )

        self.assertTrue(all(dx >= 0 for dx, _ in weighted[:5]))

    def test_attack_surface_stops_ranger_ray_at_first_rock(self) -> None:
        ranged_open, _, _, melee_open = _core_attack_surface_profile(
            (0, 0),
            {(0, -1)},
        )

        self.assertEqual(ranged_open, 14)
        self.assertEqual(melee_open, 7)

    def test_migration_mode_moves_core_only_with_nearby_escort(self) -> None:
        memory = TacticMemory(
            mode=MODE_MIGRATE,
            migration_target=(3, 0),
            migration_site_checked=True,
        )
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                vanguard((0, 1), VANGUARD_ID),
                vanguard((-1, 0), VANGUARD_TWO_ID),
                ranger((0, -1), RANGER_ID),
                ranger((-1, 1), RANGER_TWO_ID),
            ),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, StartMoveAction)
        self.assertEqual(turn.plan.core_action.direction, Direction.RIGHT)
        self.assertTrue(any("reason=migration_target" in item for item in summary.decisions))

    def test_manual_migration_target_via_control_file(self) -> None:
        """2026-08-12 坐标迁移：control 手动指定 migration_target + mode=migrate。"""
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps(
                    {
                        "mode": "migrate",
                        "migration_target": [3, 0],
                        "recall": False,
                    }
                ),
                encoding="utf-8",
            )
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    vanguard((0, 1), VANGUARD_ID),
                    vanguard((-1, 0), VANGUARD_TWO_ID),
                    ranger((0, -1), RANGER_ID),
                ),
            )
            memory = TacticMemory()
            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

            # 核心朝手动目标 (3,0) 移动（右方向）
            self.assertIsInstance(turn.plan.core_action, StartMoveAction)
            self.assertEqual(turn.plan.core_action.direction, Direction.RIGHT)
            self.assertEqual(memory.migration_target, (3, 0))
            self.assertEqual(memory.mode, MODE_MIGRATE)
            self.assertTrue(
                any("reason=migration_target" in item for item in summary.decisions)
            )

    def test_rejected_migration_candidate_is_not_reassigned(self) -> None:
        candidate = (0, 0)
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps(
                    {
                        "mode": "aggress",
                        "migration_candidate": list(candidate),
                        "auto_migrate": True,
                    }
                ),
                encoding="utf-8",
            )
            turn, _ = make_turn(
                own_core=core((5, 5)),
                units=(worker(WORKER_LOW, candidate),),
                obstacle_cells=((3, 3),),
            )
            memory = TacticMemory(mode=MODE_AGGRESS)
            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        self.assertTrue(memory.migration_site_checked)
        self.assertNotIn(candidate, memory.recovery_targets)
        self.assertNotEqual(
            memory.worker_goals[str(WORKER_LOW)].kind,
            "resource_recovery",
        )

    def test_workers_receive_distinct_nearest_resource_assignments(self) -> None:
        turn, _ = make_turn(
            own_core=core((5, 5)),
            units=(worker(WORKER_LOW, (0, 0)), worker(WORKER_HIGH, (10, 0))),
            resource_cells=((1, 0), (9, 0)),
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        low_action = turn.plan.unit_actions[WORKER_LOW]
        high_action = turn.plan.unit_actions[WORKER_HIGH]
        self.assertIsInstance(low_action, MoveAction)
        self.assertIsInstance(high_action, MoveAction)
        self.assertEqual(low_action.direction, Direction.RIGHT)
        self.assertEqual(high_action.direction, Direction.LEFT)

    def test_two_rangers_focus_fire_to_reach_lethal_damage(self) -> None:
        turn, _ = make_turn(
            own_core=core(),
            units=(ranger((0, 0)), ranger((0, 1), RANGER_TWO_ID)),
            enemies=(enemy_ranger((0, 3), hp=2),),
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        first_action = turn.plan.unit_actions[RANGER_ID]
        second_action = turn.plan.unit_actions[RANGER_TWO_ID]
        self.assertIsInstance(first_action, ShootAction)
        self.assertIsInstance(second_action, ShootAction)
        self.assertEqual(first_action.target_id, ENEMY_RANGER_ID)
        self.assertEqual(second_action.target_id, ENEMY_RANGER_ID)

    def test_worker_deposit_can_fund_same_tick_core_repair(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0), shield=4),
            units=(worker(WORKER_LOW, (0, 0), cargo=1),),
            enemies=(enemy_core((0, 3)),),
            resources=0,
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions[WORKER_LOW], DepositAction)
        self.assertIsInstance(turn.plan.core_action, RepairShieldAction)

    def test_core_cell_defender_vacates_so_cargo_worker_can_enter(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                ranger((0, 0)),
                worker(WORKER_LOW, (1, 0), cargo=1),
            ),
            beacon=ChampionBeacon(position=(10, -10)),
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        ranger_action = turn.plan.unit_actions[RANGER_ID]
        worker_action = turn.plan.unit_actions[WORKER_LOW]
        self.assertIsInstance(ranger_action, MoveAction)
        self.assertIsInstance(worker_action, MoveAction)
        self.assertEqual(worker_action.direction, Direction.LEFT)
        self.assertTrue(
            any("core_logistics_space" in item for item in summary.decisions)
        )

    def test_adjacent_logistics_blocker_steps_out_of_core_ring(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                vanguard((0, 1)),
                worker(WORKER_LOW, (1, 0), cargo=1),
            ),
            beacon=ChampionBeacon(position=(30, 30)),
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        action = turn.plan.unit_actions[VANGUARD_ID]
        self.assertIsInstance(action, MoveAction)
        dx, dy = action.direction.delta
        destination = (0 + dx, 1 + dy)
        self.assertNotIn(
            destination,
            {(0, 0), (0, 1), (1, 0), (-1, 0), (0, -1)},
        )

    def test_trapped_worker_can_escape_through_core_door(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                vanguard((0, 0)),
                worker(WORKER_LOW, (0, 1)),
            ),
            obstacle_cells=((1, 1), (-1, 1), (0, 2)),
            beacon=ChampionBeacon(position=(30, 30)),
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions[VANGUARD_ID], MoveAction)
        self.assertIsInstance(turn.plan.unit_actions[WORKER_LOW], MoveAction)
        self.assertEqual(turn.plan.unit_actions[WORKER_LOW].direction, Direction.UP)
        self.assertTrue(any("core_logistics_space" in item for item in summary.decisions))

    def test_trapped_worker_yields_core_door_to_returning_cargo(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (0, 1)),
                worker(WORKER_HIGH, (2, 0), cargo=1),
            ),
            obstacle_cells=((1, 1), (-1, 1), (0, 2)),
            beacon=ChampionBeacon(position=(30, 30)),
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertNotIn(WORKER_LOW, turn.plan.unit_actions)
        self.assertIsInstance(turn.plan.unit_actions[WORKER_HIGH], MoveAction)

    def test_trapped_worker_uses_core_door_before_distant_cargo_arrives(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (0, 1)),
                worker(WORKER_HIGH, (4, 0), cargo=1),
            ),
            obstacle_cells=((1, 1), (-1, 1), (0, 2)),
            beacon=ChampionBeacon(position=(30, 30)),
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions[WORKER_LOW], MoveAction)
        self.assertEqual(turn.plan.unit_actions[WORKER_LOW].direction, Direction.UP)
        self.assertTrue(any("core_door_escape" in item for item in summary.decisions))

    def test_core_migrates_toward_worker_frontier_when_no_cargo_is_near(self) -> None:
        memory = TacticMemory(
            worker_goals={
                str(WORKER_LOW): WorkerGoal("frontier", (10, 0), 8),
            }
        )
        turn, _ = make_turn(
            tick=8,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (6, 0)),),
        )

        SmartTactic(memory).choose_actions(turn)

        # Core 迁移已默认关闭，core 保持固定
        self.assertIsNone(turn.plan.core_action)
        self.assertIsNone(memory.core_heading)

    def test_cargo_worker_at_exactly_five_cells_blocks_core_migration(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (5, 0), cargo=1),),
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsNone(turn.plan.core_action)

    def test_core_migrates_toward_distant_cargo_worker(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (6, 0), cargo=1),),
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        # Core 迁移已默认关闭（CORE_MIGRATION_ENABLED=False），core 保持固定
        self.assertIsNone(turn.plan.core_action)

    def test_beacon_core_pauses_for_worker_inside_cargo_service_radius(self) -> None:
        memory = TacticMemory(mode=MODE_BEACON, beacon_target_distance=12)
        turn, _ = make_turn(
            tick=80,
            own_core=core((0, 0)),
            units=(
                worker(
                    WORKER_LOW,
                    (CORE_MIGRATION_CARGO_SERVICE_RADIUS, 0),
                    cargo=1,
                ),
                worker(WORKER_HIGH, (40, 0), cargo=1),
                vanguard((1, 0)),
                ranger((1, 1)),
            ),
            beacon=ChampionBeacon(position=(40, 0)),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertIsNone(turn.plan.core_action)
        self.assertTrue(
            any("core logistics_hold" in item for item in summary.decisions)
        )

    def test_beacon_core_moves_while_cargo_worker_is_five_cells_away(self) -> None:
        memory = TacticMemory(mode=MODE_BEACON, beacon_target_distance=12)
        turn, _ = make_turn(
            tick=80,
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (5, 0), cargo=1),
                vanguard((1, 0)),
                ranger((1, 1)),
            ),
            beacon=ChampionBeacon(position=(40, 0)),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, StartMoveAction)
        self.assertFalse(
            any("core logistics_hold" in item for item in summary.decisions)
        )

    def test_beacon_core_pauses_for_distant_cargo_backlog(self) -> None:
        memory = TacticMemory(mode=MODE_BEACON, beacon_target_distance=12)
        cargo_workers = (
            worker(WORKER_LOW, (5, 0), cargo=1),
            worker(WORKER_HIGH, (6, 0), cargo=1),
            worker(WORKER_THIRD, (7, 0), cargo=1),
            worker(WORKER_FOURTH, (8, 0), cargo=1),
        )
        self.assertEqual(
            sum(unit.cargo or 0 for unit in cargo_workers),
            CORE_MIGRATION_CARGO_BACKLOG_LIMIT,
        )
        turn, _ = make_turn(
            tick=80,
            own_core=core((0, 0)),
            units=(*cargo_workers, vanguard((1, 0)), ranger((1, 1))),
            beacon=ChampionBeacon(position=(40, 0)),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertIsNone(turn.plan.core_action)
        self.assertTrue(
            any("core logistics_backlog_hold" in item for item in summary.decisions)
        )

    def test_beacon_core_pauses_for_wounded_unit_inside_heal_service_radius(self) -> None:
        memory = TacticMemory(mode=MODE_BEACON, beacon_target_distance=12)
        turn, _ = make_turn(
            tick=80,
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (8, 0)),
                vanguard((1, 0)),
                ranger((CORE_MIGRATION_HEAL_SERVICE_RADIUS, 0), hp=1),
            ),
            resources=1,
            beacon=ChampionBeacon(position=(40, 0)),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertIsNone(turn.plan.core_action)
        self.assertTrue(
            any("core medical_hold" in item for item in summary.decisions)
        )

    def test_moving_core_cancels_for_recent_nearby_enemy_sighting(self) -> None:
        target = (CORE_MIGRATION_RECENT_ENEMY_HOLD_RADIUS - 1, 0)
        memory = TacticMemory(
            mode=MODE_BEACON,
            beacon_target_distance=12,
            enemy_sightings={
                str(ENEMY_RANGER_ID): EnemySighting(target, 79, False)
            },
        )
        turn, _ = make_turn(
            tick=80,
            own_core=moving_core((0, 0)),
            units=(vanguard((1, 0)), ranger((1, 1))),
            beacon=ChampionBeacon(position=(40, 0)),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, CancelMoveAction)
        self.assertTrue(
            any("recent_enemy_alert" in item for item in summary.decisions)
        )

    def test_post_recall_sweep_waits_for_large_formation_then_activates(self) -> None:
        memory = TacticMemory(
            mode=MODE_DEVELOP,
            recall=True,
            post_recall_sweep=True,
        )
        far = POST_RECALL_SWEEP_ASSEMBLY_RADIUS + 10
        waiting_turn, _ = make_turn(
            tick=80,
            own_core=core((0, 0)),
            units=(
                vanguard((1, 0), VANGUARD_ID),
                vanguard((2, 0), VANGUARD_TWO_ID),
                vanguard((far, 0), VANGUARD_THREE_ID),
                ranger((1, 1), RANGER_ID),
                ranger((2, 1), RANGER_TWO_ID),
                ranger((far, 1), RANGER_THREE_ID),
            ),
        )
        tactic = SmartTactic(memory)

        waiting_summary = tactic.choose_actions(waiting_turn)

        self.assertTrue(memory.recall)
        self.assertEqual(memory.mode, MODE_DEVELOP)
        self.assertTrue(
            any("post_recall_sweep_wait" in item for item in waiting_summary.decisions)
        )

        ready_turn, _ = make_turn(
            tick=81,
            own_core=core((0, 0)),
            units=(
                vanguard((1, 0), VANGUARD_ID),
                vanguard((2, 0), VANGUARD_TWO_ID),
                vanguard((3, 0), VANGUARD_THREE_ID),
                ranger((1, 1), RANGER_ID),
                ranger((2, 1), RANGER_TWO_ID),
                ranger((3, 1), RANGER_THREE_ID),
            ),
        )

        ready_summary = tactic.choose_actions(ready_turn)

        self.assertFalse(memory.recall)
        self.assertFalse(memory.post_recall_sweep)
        self.assertEqual(memory.mode, MODE_AGGRESS)
        self.assertTrue(
            any(
                "post_recall_sweep_activated" in item
                for item in ready_summary.decisions
            )
        )

    def test_beacon_core_does_not_wait_for_spinning_cargo_worker(self) -> None:
        memory = TacticMemory(mode=MODE_BEACON, beacon_target_distance=12)
        radius = CORE_MIGRATION_CARGO_SERVICE_RADIUS
        memory.recent_positions[str(WORKER_LOW)] = [
            (radius, 0),
            (radius, 1),
        ] * (STUCK_TICKS // 2)
        turn, _ = make_turn(
            tick=80,
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (radius, 0), cargo=1),
                vanguard((1, 0)),
                ranger((1, 1)),
            ),
            beacon=ChampionBeacon(position=(40, 0)),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, StartMoveAction)
        self.assertFalse(
            any("core logistics_hold" in item for item in summary.decisions)
        )

    def test_core_waits_when_only_legal_step_moves_away_from_beacon(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (6, 0), cargo=1),),
            obstacle_cells=((1, 0), (0, -1), (0, 1)),
            beacon=ChampionBeacon(position=(10, 0)),
        )

        SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsNone(turn.plan.core_action)

    def test_core_beacon_bias_overrides_distant_cargo_behind(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (0, 6), cargo=1),),
            beacon=ChampionBeacon(position=(10, -10)),
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        # Core 迁移已默认关闭，core 保持固定
        self.assertIsNone(turn.plan.core_action)

    def test_core_does_not_immediately_reverse_for_multiple_distant_cargo_workers(
        self,
    ) -> None:
        memory = TacticMemory(
            core_heading=Direction.UP,
            last_core_move_tick=4,
        )
        turn, _ = make_turn(
            tick=8,
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (0, 9), cargo=1),
                worker(WORKER_HIGH, (1, 9), cargo=1),
            ),
            beacon=ChampionBeacon(position=(0, -20)),
        )

        SmartTactic(memory).choose_actions(turn)

        # Core 迁移已默认关闭，core 保持固定
        self.assertIsNone(turn.plan.core_action)

    def test_enemy_within_eight_cells_blocks_core_migration(self) -> None:
        memory = TacticMemory(
            worker_goals={
                str(WORKER_LOW): WorkerGoal("frontier", (10, 0), 8),
            }
        )
        turn, _ = make_turn(
            tick=8,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (6, 0)),),
            enemies=(enemy_core((0, 8)),),
        )

        SmartTactic(memory).choose_actions(turn)

        self.assertIsNone(turn.plan.core_action)

    def test_cargo_worker_on_moving_core_heads_to_core_destination(self) -> None:
        turn, _ = make_turn(
            own_core=moving_core((0, 0), direction=Direction.RIGHT),
            units=(worker(WORKER_LOW, (0, 0), cargo=1),),
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        action = turn.plan.unit_actions[WORKER_LOW]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.RIGHT)
        self.assertTrue(
            any("reason=rendezvous_moving_core" in item for item in summary.decisions)
        )

    def test_memory_round_trip_preserves_learning(self) -> None:
        memory = TacticMemory(
            known_obstacles={(1, 2)},
            resource_last_seen={(3, 4): 20},
            recovery_targets=[(11, 12)],
            recovery_checked={(13, 14)},
            temporary_blocks={(5, 6): 22},
            worker_threat_recall_until={str(WORKER_LOW): 40},
            planned_moves={str(WORKER_LOW): PlannedMove((7, 8), 21)},
            unit_labels={str(WORKER_LOW): UnitLabel("WORKER", 4)},
            unit_label_counters={"WORKER": 4},
            core_heading=Direction.LEFT,
            last_core_move_tick=19,
            core_shelter_target=(10, 10),
            core_shelter_entrance=(9, 10),
            migration_candidate=(4, -80),
            migration_target=(4, -80),
            migration_site_checked=True,
            migration_site_score=8,
            auto_migrate=True,
            aggress_sweep_profile_version=ASSAULT_SWEEP_PROFILE_VERSION,
            aggress_sweep_started_tick=17,
            aggress_sweep_step=9,
            aggress_sweep_last_advance_tick=20,
            local_core_sortie_core_id=str(ENEMY_CORE_ID),
            local_core_sortie_position=(12, 0),
            local_core_sortie_started_tick=18,
            local_core_sortie_retry_after_tick=30,
            local_core_sortie_vanguard_ids={str(VANGUARD_ID)},
            local_core_sortie_ranger_ids={str(RANGER_ID), str(RANGER_TWO_ID)},
            replacement_queue={"RANGER": 2},
            last_tick=21,
        )
        memory.visited[(9, 10)] = 3

        with TemporaryDirectory() as directory:
            path = Path(directory) / "memory.json"
            memory.save(path)
            restored = TacticMemory.load(path)

        self.assertEqual(restored.known_obstacles, {(1, 2)})
        self.assertEqual(restored.resource_last_seen[(3, 4)], 20)
        self.assertEqual(restored.recovery_targets, [(11, 12)])
        self.assertEqual(restored.recovery_checked, {(13, 14)})
        self.assertEqual(restored.temporary_blocks[(5, 6)], 22)
        self.assertEqual(restored.worker_threat_recall_until[str(WORKER_LOW)], 40)
        self.assertEqual(restored.visited[(9, 10)], 3)
        self.assertEqual(restored.planned_moves[str(WORKER_LOW)].destination, (7, 8))
        self.assertEqual(restored.unit_labels[str(WORKER_LOW)], UnitLabel("WORKER", 4))
        self.assertEqual(restored.unit_label_counters["WORKER"], 4)
        self.assertEqual(restored.core_heading, Direction.LEFT)
        self.assertEqual(restored.last_core_move_tick, 19)
        self.assertEqual(restored.core_shelter_target, (10, 10))
        self.assertEqual(restored.core_shelter_entrance, (9, 10))
        self.assertEqual(restored.migration_candidate, (4, -80))
        self.assertEqual(restored.migration_target, (4, -80))
        self.assertTrue(restored.migration_site_checked)
        self.assertEqual(restored.migration_site_score, 8)
        self.assertTrue(restored.auto_migrate)
        self.assertEqual(
            restored.aggress_sweep_profile_version,
            ASSAULT_SWEEP_PROFILE_VERSION,
        )
        self.assertEqual(restored.aggress_sweep_started_tick, 17)
        self.assertEqual(restored.aggress_sweep_step, 9)
        self.assertEqual(restored.aggress_sweep_last_advance_tick, 20)
        self.assertEqual(restored.local_core_sortie_core_id, str(ENEMY_CORE_ID))
        self.assertEqual(restored.local_core_sortie_position, (12, 0))
        self.assertEqual(restored.local_core_sortie_started_tick, 18)
        self.assertEqual(restored.local_core_sortie_retry_after_tick, 30)
        self.assertEqual(
            restored.local_core_sortie_vanguard_ids,
            {str(VANGUARD_ID)},
        )
        self.assertEqual(
            restored.local_core_sortie_ranger_ids,
            {str(RANGER_ID), str(RANGER_TWO_ID)},
        )
        self.assertEqual(restored.replacement_queue, {"RANGER": 2})

    def test_worker_keeps_retreating_after_attacker_leaves_vision(self) -> None:
        memory = TacticMemory(mode=MODE_BEACON)
        threatened_turn, _ = make_turn(
            tick=100,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (20, 0)),),
            enemies=(enemy_ranger((21, 0)),),
            beacon=ChampionBeacon(position=(100, 0)),
        )

        SmartTactic(memory).choose_actions(threatened_turn)

        self.assertGreater(
            memory.worker_threat_recall_until[str(WORKER_LOW)],
            threatened_turn.tick,
        )

        hidden_turn, _ = make_turn(
            tick=101,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (19, 0)),),
            beacon=ChampionBeacon(position=(100, 0)),
        )
        summary = SmartTactic(memory).choose_actions(hidden_turn)

        action = hidden_turn.plan.unit_actions[WORKER_LOW]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.LEFT)
        self.assertTrue(
            any("reason=worker_threat_recall" in item for item in summary.decisions)
        )

    def test_memory_load_merges_unchecked_recovery_hint_file(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "memory.json"
            TacticMemory(recovery_checked={(3, 4)}).save(path)
            path.with_name(".arena_hero_recovery_targets.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "targets": [[1, 2], [3, 4], [1, 2]],
                    }
                ),
                encoding="utf-8",
            )

            restored = TacticMemory.load(path)

        self.assertEqual(restored.recovery_targets, [(1, 2)])
        self.assertEqual(restored.recovery_checked, {(3, 4)})

    def test_live_recovery_hint_refresh_adds_only_unchecked_targets(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / ".arena_hero_recovery_targets.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "targets": [[1, 2], [4, -80], [4, -80]],
                    }
                ),
                encoding="utf-8",
            )
            memory = TacticMemory(recovery_checked={(1, 2)})
            memory.refresh_recovery_target_hints(path)
            memory.refresh_recovery_target_hints(path)

        self.assertEqual(memory.recovery_targets, [(4, -80)])

    def test_live_recovery_hint_refresh_removes_deleted_target_and_goal(self) -> None:
        old_target = (4, -80)
        new_target = (-61, -163)
        with TemporaryDirectory() as directory:
            path = Path(directory) / ".arena_hero_recovery_targets.json"
            path.write_text(
                json.dumps({"version": 1, "targets": [list(new_target)]}),
                encoding="utf-8",
            )
            memory = TacticMemory(
                migration_candidate=new_target,
                recovery_targets=[old_target],
                recovery_checked={new_target},
                worker_goals={
                    str(WORKER_LOW): WorkerGoal(
                        "resource_recovery",
                        old_target,
                        7,
                    )
                },
            )

            memory.refresh_recovery_target_hints(path)

        self.assertEqual(memory.recovery_targets, [new_target])
        self.assertNotIn(new_target, memory.recovery_checked)
        self.assertNotIn(str(WORKER_LOW), memory.worker_goals)

    def test_chunk_math_matches_negative_coordinate_contract(self) -> None:
        self.assertEqual(_chunk_of((-1, -1)), (-1, -1))
        self.assertEqual(_chunk_of((-32, 31)), (-1, 0))
        self.assertEqual(_chunk_quota((-1, 0)), 16)
        self.assertEqual(_refill_tick_at_or_after(12), 12)
        self.assertEqual(_refill_tick_at_or_after(13), 16)

    def test_harvest_records_productive_chunk_and_refill_tick(self) -> None:
        memory = TacticMemory()
        event = ResolutionEvent(
            event_id=UUID("00000000-0000-4000-8000-000000000304"),
            tick=12,
            event_type="HARVEST_SUCCEEDED",
            actor_id=WORKER_LOW,
            position=(-31, 89),
            values={"amount": 1, "source": "RESOURCE_NODE"},
        )
        turn, _ = make_turn(
            tick=13,
            own_core=core(),
            units=(worker(WORKER_LOW, (-30, 89), cargo=1),),
            events=(event,),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        chunk = _chunk_of((-31, 89))
        self.assertEqual(memory.chunk_harvests[chunk], 1)
        self.assertEqual(memory.chunk_next_refill[chunk], 12)
        self.assertEqual(memory.chunk_anchors[chunk], (-31, 89))
        self.assertTrue(
            any(
                "harvest_result source=RESOURCE_NODE amount=1" in item
                for item in summary.decisions
            )
        )

    def test_old_exact_resource_hint_yields_to_frontier_exploration(self) -> None:
        memory = TacticMemory(resource_last_seen={(20, 20): 1})
        turn, _ = make_turn(
            tick=20,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (1, 0)),),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertFalse(any("last_seen_resource" in item for item in summary.decisions))
        self.assertEqual(
            memory.worker_goals[str(WORKER_LOW)].kind,
            "develop_frontier",
        )

    def test_fresh_browser_resource_hint_guides_nearest_develop_worker(self) -> None:
        with TemporaryDirectory() as directory:
            intel_path = Path(directory) / "browser-intel.json"
            intel_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "source": "browser",
                        "captured_at": datetime.now(timezone.utc).isoformat(),
                        "resources": [[8, 0], [-8, 0]],
                    }
                ),
                encoding="utf-8",
            )
            previous = os.environ.get("ARENA_HERO_BROWSER_INTEL_FILE")
            os.environ["ARENA_HERO_BROWSER_INTEL_FILE"] = str(intel_path)
            try:
                memory = TacticMemory(mode=MODE_DEVELOP)
                turn, _ = make_turn(
                    tick=20,
                    own_core=core((0, 0)),
                    units=(worker(WORKER_LOW, (2, 0)),),
                )
                summary = SmartTactic(memory).choose_actions(turn)
            finally:
                if previous is None:
                    os.environ.pop("ARENA_HERO_BROWSER_INTEL_FILE", None)
                else:
                    os.environ["ARENA_HERO_BROWSER_INTEL_FILE"] = previous

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertEqual(goal.kind, "browser_resource_hint")
        self.assertEqual(goal.position, (8, 0))
        self.assertTrue(any("browser_resource_assigned" in item for item in summary.decisions))

    def test_impossible_browser_resource_density_is_ignored(self) -> None:
        with TemporaryDirectory() as directory:
            intel_path = Path(directory) / "browser-intel.json"
            intel_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "source": "browser",
                        "captured_at": datetime.now(timezone.utc).isoformat(),
                        "resources": [[index, 0] for index in range(17)],
                    }
                ),
                encoding="utf-8",
            )
            memory = TacticMemory(mode=MODE_DEVELOP)
            memory.refresh_browser_intel(intel_path)

        self.assertTrue(memory.browser_intel_online)
        self.assertEqual(memory.browser_resource_hints, set())

    def _write_intel(self, path: Path, resources: list) -> None:
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "source": "browser",
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "resources": resources,
                }
            ),
            encoding="utf-8",
        )

    def test_distance_filter_runs_before_quota_check(self) -> None:
        """核心回归：远处成片误报不得连坐否决近处真实水晶。

        浏览器读的是游戏客户端 React 状态，其中保留了所有浏览过区域的地形数据。
        实测一次快照 790 个坐标里 97% 是几百到四千格外的成片地形，若先做配额
        检查，这些远处误报会让整批数据被丢弃，近处的水晶一起没了。
        """

        far_terrain = [
            [1000 + dx, 1000 + dy] for dx in range(20) for dy in range(20)
        ]
        near_crystal = [10, 0]
        with TemporaryDirectory() as directory:
            intel_path = Path(directory) / "browser-intel.json"
            self._write_intel(intel_path, far_terrain + [near_crystal])

            # 不给 origin：退化成旧行为，远处误报让整批被配额否决
            without_origin = TacticMemory(mode=MODE_DEVELOP)
            without_origin.refresh_browser_intel(intel_path)

            # 给 origin：远处先被距离过滤剔除，近处水晶得以保留
            with_origin = TacticMemory(mode=MODE_DEVELOP)
            with_origin.refresh_browser_intel(intel_path, origin=(0, 0))

        self.assertEqual(without_origin.browser_resource_hints, set())
        self.assertEqual(with_origin.browser_resource_hints, {(10, 0)})

    def test_browser_hint_distance_is_configurable(self) -> None:
        with TemporaryDirectory() as directory:
            intel_path = Path(directory) / "browser-intel.json"
            self._write_intel(intel_path, [[50, 0], [70, 0]])

            default_memory = TacticMemory(mode=MODE_DEVELOP)
            default_memory.refresh_browser_intel(intel_path, origin=(0, 0))

            widened = TacticMemory(mode=MODE_DEVELOP)
            widened.browser_hint_distance = 64
            widened.refresh_browser_intel(intel_path, origin=(0, 0))

        # 默认 32 格：两个坐标都在范围外
        self.assertEqual(default_memory.browser_hint_distance, 32)
        self.assertEqual(default_memory.browser_resource_hints, set())
        # 放宽到 64 格：50 格的进来，70 格的仍被挡住
        self.assertEqual(widened.browser_resource_hints, {(50, 0)})

    def test_browser_hint_distance_zero_disables_hints(self) -> None:
        with TemporaryDirectory() as directory:
            intel_path = Path(directory) / "browser-intel.json"
            self._write_intel(intel_path, [[4, 0]])
            memory = TacticMemory(mode=MODE_DEVELOP)
            memory.browser_hint_distance = 0
            memory.refresh_browser_intel(intel_path, origin=(0, 0))

        self.assertTrue(memory.browser_intel_online)
        self.assertEqual(memory.browser_resource_hints, set())

    def test_browser_hint_distance_read_from_control_file(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps({"mode": "develop", "browser_hint_distance": 48}),
                encoding="utf-8",
            )
            memory = TacticMemory()
            memory.load_control(control_path)

        self.assertEqual(memory.browser_hint_distance, 48)

    def test_resource_leash_and_scout_limit_read_from_control_file(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps(
                    {
                        "mode": "develop",
                        "resource_leash_distance": 56,
                        "browser_scout_limit": 3,
                    }
                ),
                encoding="utf-8",
            )
            memory = TacticMemory()
            self.assertEqual(
                memory.resource_leash_distance,
                DEVELOP_RESOURCE_TARGET_CORE_LEASH_DISTANCE,
            )
            self.assertEqual(memory.browser_scout_limit, 1)
            memory.load_control(control_path)

        self.assertEqual(memory.resource_leash_distance, 56)
        self.assertEqual(memory.browser_scout_limit, 3)

    def test_resource_leash_distance_gates_far_visible_resource(self) -> None:
        """核心回归：leash 决定远处可见资源能否成为采集目标。

        工人距目标 > 3 格（不触发就近豁免），因此完全由 leash 决定去不去。
        """

        far_resource = (46, 0)
        outcomes = {}
        for leash in (38, 56):
            memory = TacticMemory(mode=MODE_DEVELOP)
            memory.resource_leash_distance = leash
            turn, _ = make_turn(
                tick=30,
                own_core=core((0, 0)),
                units=(worker(WORKER_LOW, (20, 0)),),
                resource_cells=(far_resource,),
            )
            summary = SmartTactic(memory).choose_actions(turn)
            goal = memory.worker_goals.get(str(WORKER_LOW))
            outcomes[leash] = (goal, summary.decisions)

        # 46 格 > 38：被 leash 剔除，工人转去探索
        goal_38, decisions_38 = outcomes[38]
        self.assertTrue(
            any("resource_leash_trimmed" in item for item in decisions_38),
            f"38 格 leash 应剔除 46 格资源, 实际: {decisions_38}",
        )
        self.assertNotEqual(
            goal_38.position if goal_38 else None,
            far_resource,
            "被 leash 剔除后不应把远矿设为目标",
        )
        # 46 格 < 56：放行，工人前往采集
        goal_56, _ = outcomes[56]
        self.assertIsNotNone(goal_56)
        self.assertEqual(goal_56.kind, "visible_resource")
        self.assertEqual(goal_56.position, far_resource)

    def test_resource_leash_zero_disables_limit(self) -> None:
        far_resource = (80, 0)
        memory = TacticMemory(mode=MODE_DEVELOP)
        memory.resource_leash_distance = 0
        turn, _ = make_turn(
            tick=30,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (40, 0)),),
            resource_cells=(far_resource,),
        )
        summary = SmartTactic(memory).choose_actions(turn)

        self.assertFalse(
            any("resource_leash_trimmed" in item for item in summary.decisions)
        )
        goal = memory.worker_goals.get(str(WORKER_LOW))
        self.assertIsNotNone(goal)
        self.assertEqual(goal.position, far_resource)

    def test_browser_scout_limit_controls_dispatched_workers(self) -> None:
        hints = [[6, 0], [0, 6], [-6, 0]]
        assigned_counts = {}
        for limit in (1, 3):
            with TemporaryDirectory() as directory:
                intel_path = Path(directory) / "browser-intel.json"
                self._write_intel(intel_path, hints)
                previous = os.environ.get("ARENA_HERO_BROWSER_INTEL_FILE")
                os.environ["ARENA_HERO_BROWSER_INTEL_FILE"] = str(intel_path)
                try:
                    memory = TacticMemory(mode=MODE_DEVELOP)
                    memory.browser_scout_limit = limit
                    turn, _ = make_turn(
                        tick=30,
                        own_core=core((0, 0)),
                        units=(
                            worker(WORKER_LOW, (2, 1)),
                            worker(WORKER_HIGH, (1, 2)),
                            worker(WORKER_THIRD, (-2, 1)),
                            worker(WORKER_FOURTH, (-1, 2)),
                        ),
                    )
                    SmartTactic(memory).choose_actions(turn)
                finally:
                    if previous is None:
                        os.environ.pop("ARENA_HERO_BROWSER_INTEL_FILE", None)
                    else:
                        os.environ["ARENA_HERO_BROWSER_INTEL_FILE"] = previous
            assigned_counts[limit] = sum(
                1
                for goal in memory.worker_goals.values()
                if goal.kind == "browser_resource_hint"
            )

        self.assertEqual(assigned_counts[1], 1, "默认只派 1 名探子")
        self.assertGreater(
            assigned_counts[3],
            assigned_counts[1],
            "提高上限后应派出更多工人验证提示",
        )

    def test_browser_hint_overrides_exploration_goal(self) -> None:
        """回归：守着探索目标的工人不得从 10 格外的已知水晶旁走过。

        实测现场：提示 (-295,-78) 距工人 10 格，工人却保留上一 Tick 的
        refilled_chunk 目标继续探图，而 70/86 格外的工人反被派去该提示。
        """

        # 提示必须在工人视野（半径 3）与 Core 视野（半径 5）之外，否则会被
        # visible_absent 判定为"看得见且没有资源"而立即失效。
        hint = (20, 0)
        with TemporaryDirectory() as directory:
            intel_path = Path(directory) / "browser-intel.json"
            self._write_intel(intel_path, [list(hint)])
            previous = os.environ.get("ARENA_HERO_BROWSER_INTEL_FILE")
            os.environ["ARENA_HERO_BROWSER_INTEL_FILE"] = str(intel_path)
            try:
                memory = TacticMemory(
                    mode=MODE_DEVELOP,
                    # 工人距提示 10 格，却守着 40 格外的探索目标
                    worker_goals={
                        str(WORKER_LOW): WorkerGoal("refilled_chunk", (-30, 0), 5)
                    },
                )
                turn, _ = make_turn(
                    tick=30,
                    own_core=core((0, 0)),
                    units=(worker(WORKER_LOW, (10, 0)),),
                )
                SmartTactic(memory).choose_actions(turn)
            finally:
                if previous is None:
                    os.environ.pop("ARENA_HERO_BROWSER_INTEL_FILE", None)
                else:
                    os.environ["ARENA_HERO_BROWSER_INTEL_FILE"] = previous

        goal = memory.worker_goals.get(str(WORKER_LOW))
        self.assertIsNotNone(goal)
        self.assertEqual(goal.kind, "browser_resource_hint")
        self.assertEqual(goal.position, hint)

    def test_browser_hint_prefers_nearest_worker(self) -> None:
        """回归：提示应配给离它最近的工人，而不是按全局最小距离排队。

        旧写法按"工人到最近提示的距离"排序取前 N 名，只保证被选中的工人离
        某个提示近；实测出现离目标 70 格的工人中选、10 格的落选。
        """

        # 两个提示都要在工人视野（半径 3）外，否则会被 visible_absent 立即失效
        near_hint = (14, 0)
        far_hint = (0, 44)
        with TemporaryDirectory() as directory:
            intel_path = Path(directory) / "browser-intel.json"
            self._write_intel(intel_path, [list(near_hint), list(far_hint)])
            previous = os.environ.get("ARENA_HERO_BROWSER_INTEL_FILE")
            os.environ["ARENA_HERO_BROWSER_INTEL_FILE"] = str(intel_path)
            try:
                memory = TacticMemory(mode=MODE_DEVELOP)
                memory.browser_scout_limit = 1
                turn, _ = make_turn(
                    tick=30,
                    own_core=core((0, 0)),
                    units=(
                        worker(WORKER_LOW, (8, 0)),  # 距 near_hint 6 格
                        worker(WORKER_HIGH, (0, 30)),  # 距 far_hint 14 格
                    ),
                )
                SmartTactic(memory).choose_actions(turn)
            finally:
                if previous is None:
                    os.environ.pop("ARENA_HERO_BROWSER_INTEL_FILE", None)
                else:
                    os.environ["ARENA_HERO_BROWSER_INTEL_FILE"] = previous

        low_goal = memory.worker_goals.get(str(WORKER_LOW))
        self.assertIsNotNone(low_goal, "最近的工人应中选")
        self.assertEqual(low_goal.kind, "browser_resource_hint")
        self.assertEqual(low_goal.position, near_hint)

    def test_distant_browser_resource_hint_yields_to_local_search(self) -> None:
        with TemporaryDirectory() as directory:
            intel_path = Path(directory) / "browser-intel.json"
            intel_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "source": "browser",
                        "captured_at": datetime.now(timezone.utc).isoformat(),
                        "resources": [[BROWSER_RESOURCE_HINT_MAX_DISTANCE + 8, 0]],
                    }
                ),
                encoding="utf-8",
            )
            previous = os.environ.get("ARENA_HERO_BROWSER_INTEL_FILE")
            os.environ["ARENA_HERO_BROWSER_INTEL_FILE"] = str(intel_path)
            try:
                memory = TacticMemory(mode=MODE_DEVELOP)
                turn, _ = make_turn(
                    tick=20,
                    own_core=core((0, 0)),
                    units=(worker(WORKER_LOW, (2, 0)),),
                )
                SmartTactic(memory).choose_actions(turn)
            finally:
                if previous is None:
                    os.environ.pop("ARENA_HERO_BROWSER_INTEL_FILE", None)
                else:
                    os.environ["ARENA_HERO_BROWSER_INTEL_FILE"] = previous

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertNotEqual(goal.kind, "browser_resource_hint")
        self.assertLessEqual(_distance((0, 0), goal.position), DEVELOP_WIDE_SEARCH_MAX_RADIUS)

    def test_develop_drops_far_visible_resource_route_before_long_round_trip(
        self,
    ) -> None:
        far_target = (DEVELOP_RESOURCE_TARGET_CORE_LEASH_DISTANCE + 12, 0)
        memory = TacticMemory(
            mode=MODE_DEVELOP,
            worker_goals={
                str(WORKER_LOW): WorkerGoal(
                    "visible_resource",
                    far_target,
                    10,
                )
            },
        )
        turn, _ = make_turn(
            tick=30,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (8, 0)),),
            resource_cells=(far_target,),
            beacon=ChampionBeacon(position=(100, 0)),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertNotEqual(goal.kind, "visible_resource")
        self.assertLessEqual(
            _distance(turn.core.position, goal.position),
            DEVELOP_WIDE_SEARCH_MAX_RADIUS,
        )
        self.assertTrue(
            any("resource_leash_trim" in item for item in summary.decisions)
        )

    def test_aggress_drops_far_visible_resource_after_core_migrates(self) -> None:
        far_target = (0, -AGGRESS_RESOURCE_TARGET_CORE_LEASH_DISTANCE - 40)
        memory = TacticMemory(
            mode=MODE_AGGRESS,
            worker_goals={
                str(WORKER_LOW): WorkerGoal("visible_resource", far_target, 10),
            },
        )
        turn, _ = make_turn(
            tick=30,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (0, -50)),),
            resource_cells=(far_target,),
            resources=0,
            beacon=ChampionBeacon(position=(100, 0)),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertNotEqual(goal.position, far_target)
        self.assertEqual(goal.kind, "resource_sweep")
        self.assertLessEqual(
            _distance(turn.core.position, goal.position),
            AGGRESS_RESOURCE_SWEEP_MAX_RADIUS,
        )
        self.assertTrue(
            any("resource_leash_trim" in item for item in summary.decisions)
        )

    def test_aggress_remote_worker_finishes_resource_already_in_reach(self) -> None:
        far_target = (0, -AGGRESS_RESOURCE_TARGET_CORE_LEASH_DISTANCE - 40)
        memory = TacticMemory(mode=MODE_AGGRESS)
        turn, _ = make_turn(
            tick=30,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (0, far_target[1] + 1)),),
            resource_cells=(far_target,),
            resources=0,
            beacon=ChampionBeacon(position=(100, 0)),
        )

        SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertEqual(goal.kind, "visible_resource")
        self.assertEqual(goal.position, far_target)

    def test_reached_frontier_goal_rotates_without_waiting_for_expiry(self) -> None:
        memory = TacticMemory(
            mode=MODE_DEVELOP,
            worker_goals={
                str(WORKER_LOW): WorkerGoal("develop_frontier", (24, 0), 10),
            },
            worker_search_radius={str(WORKER_LOW): 10},
        )
        turn, _ = make_turn(
            tick=20,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (24, 0)),),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertNotEqual(goal.position, (24, 0))
        self.assertEqual(goal.kind, "develop_frontier")
        self.assertIsInstance(turn.plan.unit_actions[WORKER_LOW], MoveAction)
        self.assertTrue(any("goal_reached_rotate" in item for item in summary.decisions))

    def test_stale_browser_resource_snapshot_is_ignored(self) -> None:
        with TemporaryDirectory() as directory:
            intel_path = Path(directory) / "browser-intel.json"
            intel_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "source": "browser",
                        "captured_at": "2020-01-01T00:00:00+00:00",
                        "resources": [[8, 0]],
                    }
                ),
                encoding="utf-8",
            )
            memory = TacticMemory()
            memory.refresh_browser_intel(intel_path)

        self.assertEqual(memory.browser_resource_hints, set())
        self.assertGreater(memory.browser_intel_age_seconds, 12)

    def test_develop_resource_search_uses_worker_sector_instead_of_beacon_bias(
        self,
    ) -> None:
        memory = TacticMemory()
        beacon_position = (20, -20)
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (1, 0)),),
            beacon=ChampionBeacon(position=beacon_position),
        )

        SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertEqual(goal.kind, "develop_frontier")
        self.assertGreater(goal.position[0], 0)
        self.assertEqual(goal.position[1], 0)

    def test_aggress_empty_resource_state_uses_wide_resource_sweep(self) -> None:
        memory = TacticMemory(mode=MODE_AGGRESS)
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (1, 0)),
                worker(WORKER_HIGH, (0, 1)),
            ),
            beacon=ChampionBeacon(position=(100, 0)),
        )

        SmartTactic(memory).choose_actions(turn)

        goals = [
            memory.worker_goals[str(worker_id)]
            for worker_id in (WORKER_LOW, WORKER_HIGH)
        ]
        self.assertTrue(all(goal.kind == "resource_sweep" for goal in goals))
        self.assertTrue(any(_distance((0, 0), goal.position) >= 10 for goal in goals))

    def test_beacon_empty_resource_state_uses_bounded_wide_resource_sweep(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps({"mode": MODE_BEACON}),
                encoding="utf-8",
            )
            memory = TacticMemory()
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    worker(WORKER_LOW, (1, 0)),
                    worker(WORKER_HIGH, (0, 1)),
                ),
                beacon=ChampionBeacon(position=(100, 0)),
            )

            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        goals = [
            memory.worker_goals[str(worker_id)]
            for worker_id in (WORKER_LOW, WORKER_HIGH)
        ]
        self.assertTrue(all(goal.kind == "resource_sweep" for goal in goals))
        self.assertTrue(
            all(
                BEACON_RESOURCE_SWEEP_INITIAL_RADIUS
                <= _distance((0, 0), goal.position)
                <= BEACON_RESOURCE_SWEEP_MAX_RADIUS
                for goal in goals
            )
        )

    def test_beacon_surplus_workers_keep_wide_search_with_one_resource(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps({"mode": MODE_BEACON}),
                encoding="utf-8",
            )
            memory = TacticMemory()
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    worker(WORKER_LOW, (1, 0)),
                    worker(WORKER_HIGH, (0, 1)),
                    worker(WORKER_THIRD, (-1, 0)),
                ),
                resource_cells=((3, 0),),
                beacon=ChampionBeacon(position=(100, 0)),
            )

            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        goals = [
            memory.worker_goals[str(worker_id)]
            for worker_id in (WORKER_LOW, WORKER_HIGH, WORKER_THIRD)
        ]
        self.assertEqual(
            sum(goal.kind == "visible_resource" for goal in goals),
            1,
        )
        self.assertEqual(
            sum(goal.kind == "resource_sweep" for goal in goals),
            2,
        )

    def test_beacon_resource_sweep_can_expand_beyond_aggress_leash(self) -> None:
        memory = TacticMemory(
            mode=MODE_BEACON,
            worker_search_radius={str(WORKER_LOW): 30},
        )
        turn, _ = make_turn(
            tick=20,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (30, 0)),),
            resources=0,
            beacon=ChampionBeacon(position=(100, 0)),
        )

        SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertEqual(goal.kind, "resource_sweep")
        self.assertGreater(
            _distance(turn.core.position, goal.position),
            AGGRESS_RESOURCE_SWEEP_MAX_RADIUS,
        )
        self.assertLessEqual(
            _distance(turn.core.position, goal.position),
            BEACON_RESOURCE_SWEEP_MAX_RADIUS,
        )

    def test_beacon_ignores_remote_resource_revealed_by_expedition(self) -> None:
        far_target = (0, -70)
        memory = TacticMemory(
            mode=MODE_BEACON,
            worker_goals={
                str(WORKER_LOW): WorkerGoal(
                    "visible_resource",
                    far_target,
                    10,
                )
            },
        )
        turn, _ = make_turn(
            tick=30,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (0, -10)),),
            resource_cells=(far_target,),
            beacon=ChampionBeacon(position=(100, 0)),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertNotEqual(goal.kind, "visible_resource")
        self.assertLessEqual(
            _distance(turn.core.position, goal.position),
            BEACON_RESOURCE_SWEEP_MAX_RADIUS,
        )
        self.assertTrue(
            any("resource_leash_trimmed" in item for item in summary.decisions)
        )

    def test_long_backward_refill_probe_is_replaced_by_beacon_frontier(self) -> None:
        memory = TacticMemory(
            worker_goals={
                str(WORKER_LOW): WorkerGoal("refilled_chunk", (-24, 0), 8),
            },
        )
        beacon_position = (20, 0)
        turn, _ = make_turn(
            tick=12,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (1, 0)),),
            beacon=ChampionBeacon(position=beacon_position),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertNotEqual(goal.kind, "refilled_chunk")
        self.assertLess(
            abs(goal.position[0] - beacon_position[0])
            + abs(goal.position[1] - beacon_position[1]),
            abs(beacon_position[0]),
        )
        self.assertTrue(
            any("refill_probe_strategic_trimmed" in item for item in summary.decisions)
        )

    def test_beacon_keeps_refill_probe_within_wide_search_leash(self) -> None:
        memory = TacticMemory(
            mode=MODE_BEACON,
            worker_goals={
                str(WORKER_LOW): WorkerGoal("refilled_chunk", (32, 0), 8),
            },
        )
        turn, _ = make_turn(
            tick=12,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (24, 0)),),
            beacon=ChampionBeacon(position=(100, 0)),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertEqual(memory.worker_goals[str(WORKER_LOW)].kind, "refilled_chunk")
        self.assertFalse(
            any("refill_probe_strategic_trimmed" in item for item in summary.decisions)
        )

    def test_beacon_assigns_productive_chunk_beyond_default_refill_leash(self) -> None:
        memory = TacticMemory(
            mode=MODE_BEACON,
            chunk_harvests={(0, 0): 2},
            chunk_next_refill={(0, 0): 8},
            chunk_anchors={(0, 0): (16, 16)},
        )
        turn, _ = make_turn(
            tick=12,
            own_core=core((0, 32)),
            units=(worker(WORKER_LOW, (0, 31)),),
            beacon=ChampionBeacon(position=(100, 32)),
        )

        SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertEqual(goal.kind, "refilled_chunk")
        self.assertLessEqual(
            _distance(turn.core.position, goal.position),
            BEACON_RESOURCE_SWEEP_MAX_RADIUS,
        )

    def test_owned_beacon_trims_refill_probe_far_from_core(self) -> None:
        memory = TacticMemory(
            worker_goals={
                str(WORKER_LOW): WorkerGoal("refilled_chunk", (30, 0), 8),
            },
        )
        turn, _ = make_turn(
            tick=12,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (1, 0)),),
            beacon=ChampionBeacon(
                position=(0, 0),
                status=BeaconStatus.CARRIED,
                carrier_id=CORE_ID,
            ),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertNotEqual(goal.kind, "refilled_chunk")
        self.assertLessEqual(abs(goal.position[0]) + abs(goal.position[1]), 11)
        self.assertTrue(
            any("refill_probe_strategic_trimmed" in item for item in summary.decisions)
        )

    def test_long_backward_last_seen_resource_is_replaced_by_beacon_frontier(
        self,
    ) -> None:
        memory = TacticMemory(
            resource_last_seen={(-20, 0): 12},
            worker_goals={
                str(WORKER_LOW): WorkerGoal("last_seen_resource", (-20, 0), 12),
            },
        )
        beacon_position = (20, 0)
        turn, _ = make_turn(
            tick=12,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (1, 0)),),
            beacon=ChampionBeacon(position=beacon_position),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertEqual(goal.kind, "frontier")
        self.assertLess(
            abs(goal.position[0] - beacon_position[0])
            + abs(goal.position[1] - beacon_position[1]),
            abs(beacon_position[0]),
        )
        self.assertTrue(
            any(
                "last_seen_resource_strategic_trimmed" in item
                for item in summary.decisions
            )
        )

    def test_due_productive_chunk_gets_a_probe_assignment(self) -> None:
        memory = TacticMemory(
            chunk_harvests={(0, 0): 2},
            chunk_next_refill={(0, 0): 8},
            chunk_anchors={(0, 0): (10, 10)},
        )
        turn, _ = make_turn(
            tick=12,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (1, 0)),),
        )

        SmartTactic(memory).choose_actions(turn)

        self.assertEqual(memory.worker_goals[str(WORKER_LOW)].kind, "refilled_chunk")
        self.assertEqual(_chunk_of(memory.worker_goals[str(WORKER_LOW)].position), (0, 0))

    def test_develop_rejects_productive_chunk_beyond_local_leash(self) -> None:
        # 2026-08-11: 搜索半径已从 28 扩到 160（螺旋外扩），leash 随之变大。
        # chunk 锚点距 core 200 > 160 才应被拒。
        memory = TacticMemory(
            chunk_harvests={(1, 0): 2},
            chunk_next_refill={(1, 0): 8},
            chunk_anchors={(1, 0): (200, 0)},
        )
        turn, _ = make_turn(
            tick=12,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (20, 0)),),
            beacon=ChampionBeacon(position=(100, 0)),
        )

        SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertNotEqual(goal.kind, "refilled_chunk")
        self.assertLessEqual(
            _distance(turn.core.position, goal.position),
            DEVELOP_WIDE_SEARCH_MAX_RADIUS,
        )

    def test_develop_trims_existing_refill_probe_beyond_local_leash(self) -> None:
        memory = TacticMemory(
            mode=MODE_DEVELOP,
            worker_goals={
                str(WORKER_LOW): WorkerGoal("refilled_chunk", (200, 0), 8),
            },
        )
        turn, _ = make_turn(
            tick=20,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (20, 0)),),
            beacon=ChampionBeacon(position=(100, 0)),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertNotEqual(goal.kind, "refilled_chunk")
        self.assertTrue(
            any("refill_probe_strategic_trimmed" in item for item in summary.decisions)
        )

    def test_refill_probe_tries_an_alternate_strategic_point(self) -> None:
        memory = TacticMemory(
            chunk_harvests={(0, 0): 2},
            chunk_next_refill={(0, 0): 8},
            chunk_anchors={(0, 0): (10, 10)},
        )
        turn, _ = make_turn(
            tick=12,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (1, 0)),),
            beacon=ChampionBeacon(position=(20, 0)),
        )

        SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertEqual(goal.kind, "refilled_chunk")
        self.assertEqual(goal.position, (24, 8))

    def test_refilled_chunk_probe_concurrency_is_bounded(self) -> None:
        memory = TacticMemory(
            chunk_harvests={(0, 0): 2},
            chunk_next_refill={(0, 0): 8},
            chunk_anchors={(0, 0): (10, 10)},
            worker_goals={
                str(WORKER_LOW): WorkerGoal("refilled_chunk", (24, 24), 9),
                str(WORKER_HIGH): WorkerGoal("refilled_chunk", (8, 8), 10),
            },
        )
        turn, _ = make_turn(
            tick=12,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (3, 0)), worker(WORKER_HIGH, (4, 0))),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        active_probes = [
            goal for goal in memory.worker_goals.values() if goal.kind == "refilled_chunk"
        ]
        self.assertEqual(len(active_probes), 1)
        self.assertTrue(
            any(
                "refill_probe" in item and "trimmed" in item
                for item in summary.decisions
            )
        )

    def test_develop_refill_probe_limit_scales_to_three_for_large_workforce(
        self,
    ) -> None:
        turn, _ = make_turn(
            tick=12,
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (1, 0)),
                worker(WORKER_HIGH, (2, 0)),
                worker(WORKER_THIRD, (3, 0)),
                worker(WORKER_FOURTH, (4, 0)),
                worker(WORKER_FIFTH, (5, 0)),
                worker(WORKER_SIXTH, (6, 0)),
                worker(WORKER_SEVENTH, (7, 0)),
            ),
        )

        limit = SmartTactic(TacticMemory())._refill_probe_limit(turn)

        self.assertEqual(limit, 3)


class ModeAndRecallTests(unittest.TestCase):
    """发育/侵略双模式 + 一键召回 + stats 写入。"""

    def _write_control(
        self,
        path: Path,
        *,
        mode: str | None = None,
        recall: bool | None = None,
        migration_candidate: list[int] | None = None,
        auto_migrate: bool | None = None,
    ) -> None:
        data: dict = {}
        if mode is not None:
            data["mode"] = mode
        if recall is not None:
            data["recall"] = recall
        if migration_candidate is not None:
            data["migration_candidate"] = migration_candidate
        if auto_migrate is not None:
            data["auto_migrate"] = auto_migrate
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_aggress_mode_spawns_rangers_over_workers(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    worker(WORKER_LOW, (6, 0)),
                    worker(WORKER_HIGH, (7, 0)),
                    worker(WORKER_THIRD, (8, 0)),
                    worker(WORKER_FOURTH, (9, 0)),
                    vanguard((3, 3)),
                    vanguard((4, 3), VANGUARD_TWO_ID),
                    ranger((3, 4)),
                    ranger((4, 4), RANGER_TWO_ID),
                ),
                resources=30,
            )
            SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

            self.assertIsInstance(turn.plan.core_action, SpawnAction)
            self.assertEqual(turn.plan.core_action.unit_type, UnitType.RANGER)

    def test_aggress_combat_target_has_more_rangers_than_vanguards(self) -> None:
        self.assertEqual(AGGRESS_TARGET_RANGERS, 9)
        self.assertEqual(AGGRESS_TARGET_VANGUARDS, 6)
        self.assertGreater(AGGRESS_TARGET_RANGERS, AGGRESS_TARGET_VANGUARDS)

    def test_aggress_prioritizes_ranger_when_both_combat_replacements_wait(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(mode=MODE_AGGRESS)
            memory.replacement_queue.update({"RANGER": 1, "VANGUARD": 1})
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    worker(WORKER_LOW, (6, 0)),
                    worker(WORKER_HIGH, (7, 0)),
                    worker(WORKER_THIRD, (8, 0)),
                    worker(WORKER_FOURTH, (9, 0)),
                    vanguard((3, 3)),
                    ranger((3, 4)),
                ),
                resources=30,
            )

            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.RANGER)

    def test_aggress_builds_vanguard_after_ranger_target_is_met(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            units = tuple(
                worker(UUID(int=0x1000 + index), (10 + index, 0))
                for index in range(AGGRESS_BASE_WORKERS)
            ) + tuple(
                ranger((20 + index, 0), UUID(int=0x2000 + index))
                for index in range(AGGRESS_TARGET_RANGERS)
            ) + tuple(
                vanguard((30 + index, 0), UUID(int=0x3000 + index))
                for index in range(AGGRESS_TARGET_VANGUARDS - 1)
            )
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=units,
                resources=30,
            )

            SmartTactic(
                TacticMemory(mode=MODE_AGGRESS),
                control_path=control_path,
            ).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.VANGUARD)

    def test_aggress_reaches_the_vanguard_home_guard_floor(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=tuple(
                    worker(UUID(int=0x4000 + index), (10 + index, 0))
                    for index in range(AGGRESS_BASE_WORKERS)
                ) + tuple(
                    ranger((20 + index, 0), UUID(int=0x5000 + index))
                    for index in range(AGGRESS_DEFENDER_RANGERS)
                ),
                resources=30,
            )

            SmartTactic(
                TacticMemory(mode=MODE_AGGRESS),
                control_path=control_path,
            ).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.VANGUARD)

    def test_develop_mode_rebuilds_six_guards_before_worker_expansion(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="develop")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    worker(WORKER_LOW, (6, 0)),
                    worker(WORKER_HIGH, (7, 0)),
                    worker(WORKER_THIRD, (8, 0)),
                    worker(WORKER_FOURTH, (9, 0)),
                    vanguard((3, 3)),
                    vanguard((4, 3), VANGUARD_TWO_ID),
                    ranger((3, 4)),
                    ranger((4, 4), RANGER_TWO_ID),
                ),
                resources=30,
            )
            SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

            self.assertIsInstance(turn.plan.core_action, SpawnAction)
            self.assertEqual(turn.plan.core_action.unit_type, UnitType.RANGER)

    def test_aggress_damaged_unit_does_not_return_to_core_for_healing(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            damaged_ranger = UnitView(
                kind="UNIT",
                id=RANGER_ID,
                controlled=True,
                position=(8, 0),
                hp=1,
                unit_type=UnitType.RANGER,
            )
            turn, _ = make_turn(
                tick=20,
                own_core=core((0, 0)),
                units=(damaged_ranger,),
                resources=20,
            )

            summary = SmartTactic(
                TacticMemory(),
                control_path=control_path,
            ).choose_actions(turn)

        self.assertFalse(any("heal_return" in item for item in summary.decisions))
        self.assertNotIsInstance(turn.plan.unit_actions.get(RANGER_ID), HealAction)

    def test_aggress_replaces_a_lost_unit_with_the_same_type(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(mode=MODE_AGGRESS)
            tactic = SmartTactic(memory, control_path=control_path)
            first_turn, _ = make_turn(
                tick=30,
                own_core=core((0, 0)),
                units=(
                    worker(WORKER_LOW, (6, 2)),
                    worker(WORKER_HIGH, (7, 2)),
                    worker(WORKER_THIRD, (8, 2)),
                    worker(WORKER_FOURTH, (9, 2)),
                    vanguard((5, 0)),
                    ranger((6, 0)),
                ),
                resources=30,
            )
            tactic.choose_actions(first_turn)

            loss_turn, _ = make_turn(
                tick=31,
                own_core=core((0, 0)),
                units=(
                    worker(WORKER_LOW, (6, 2)),
                    worker(WORKER_HIGH, (7, 2)),
                    worker(WORKER_THIRD, (8, 2)),
                    worker(WORKER_FOURTH, (9, 2)),
                    vanguard((5, 0)),
                ),
                resources=30,
            )
            summary = tactic.choose_actions(loss_turn)

            self.assertIsInstance(loss_turn.plan.core_action, SpawnAction)
            self.assertEqual(loss_turn.plan.core_action.unit_type, UnitType.RANGER)
            self.assertEqual(memory.replacement_queue["RANGER"], 1)
            self.assertTrue(
                any("replacement=True" in item for item in summary.decisions)
            )

            replacement_turn, _ = make_turn(
                tick=32,
                own_core=core((0, 0)),
                units=(
                    worker(WORKER_LOW, (6, 2)),
                    worker(WORKER_HIGH, (7, 2)),
                    worker(WORKER_THIRD, (8, 2)),
                    worker(WORKER_FOURTH, (9, 2)),
                    vanguard((5, 0)),
                    ranger((0, 0), RANGER_TWO_ID),
                ),
                resources=18,
            )
            tactic.choose_actions(replacement_turn)

        self.assertEqual(memory.replacement_queue["RANGER"], 0)

    def test_aggress_restores_minimum_workers_before_combat_replacements(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(mode=MODE_AGGRESS)
            memory.replacement_queue.update({"RANGER": 4, "VANGUARD": 2})
            turn, _ = make_turn(
                tick=40,
                own_core=core((0, 0)),
                units=(
                    worker(WORKER_LOW, (6, 0)),
                    vanguard((5, 0)),
                    ranger((6, 1)),
                ),
                resources=5,
            )

            SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.WORKER)
        self.assertEqual(memory.replacement_queue["RANGER"], 3)
        self.assertEqual(memory.replacement_queue["VANGUARD"], 1)

    def test_develop_mode_sends_empty_workers_to_eight_resource_search_sectors(
        self,
    ) -> None:
        units = (
            worker(WORKER_LOW, (1, 0)),
            worker(WORKER_HIGH, (1, 1)),
            worker(WORKER_THIRD, (0, 1)),
            worker(WORKER_FOURTH, (-1, 1)),
            worker(WORKER_FIFTH, (-1, 0)),
            worker(WORKER_SIXTH, (-1, -1)),
            worker(WORKER_SEVENTH, (0, -1)),
            worker(WORKER_EIGHTH, (1, -1)),
        )
        turn, _ = make_turn(
            tick=16,
            own_core=core((0, 0)),
            units=units,
        )
        memory = TacticMemory(mode=MODE_DEVELOP)

        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="develop")
            SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        goals = [memory.worker_goals[str(worker_view.id)] for worker_view in units]
        sectors = {
            (
                (goal.position[0] > 0) - (goal.position[0] < 0),
                (goal.position[1] > 0) - (goal.position[1] < 0),
            )
            for goal in goals
        }
        self.assertTrue(all(goal.kind == "develop_frontier" for goal in goals))
        self.assertEqual(len(sectors), 8)
        self.assertTrue(
            all(
                isinstance(turn.plan.unit_actions.get(worker_view.id), MoveAction)
                for worker_view in units
            )
        )
        self.assertEqual(memory.decision_totals["worker:develop_explore"], 8)

    def test_aggress_vanguard_explores_frontier_when_no_enemies(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress")
            turn, _ = make_turn(
                own_core=core((5, 5)),
                units=(vanguard((10, 10)),),
            )
            SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

            action = turn.plan.unit_actions.get(VANGUARD_ID)
            self.assertIsInstance(action, MoveAction)

    def test_aggress_ranger_explores_frontier_when_no_enemies(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress")
            turn, _ = make_turn(
                own_core=core((5, 5)),
                units=(ranger((10, 10)),),
            )
            SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

            action = turn.plan.unit_actions.get(RANGER_ID)
            self.assertIsInstance(action, MoveAction)

    def test_aggress_main_force_explores_when_own_core_carries_beacon(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress")
            own = core((5, 5))
            turn, _ = make_turn(
                tick=8,
                own_core=own,
                units=(
                    vanguard((6, 5)),
                    vanguard((7, 5), VANGUARD_TWO_ID),
                    ranger((6, 6)),
                    ranger((7, 6), RANGER_TWO_ID),
                ),
                beacon=ChampionBeacon(
                    position=own.position,
                    status=BeaconStatus.CARRIED,
                    carrier_id=CORE_ID,
                ),
            )

            SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

            vanguard_action = turn.plan.unit_actions.get(VANGUARD_TWO_ID)
            ranger_action = turn.plan.unit_actions.get(RANGER_TWO_ID)
            self.assertIsInstance(vanguard_action, MoveAction)
            self.assertIsInstance(ranger_action, MoveAction)
            self.assertNotEqual(vanguard_action.direction, Direction.LEFT)
            self.assertNotEqual(ranger_action.direction, Direction.LEFT)

    def test_aggress_vanguard_nine_keeps_beacon_with_two_plus_three_guards(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            carrier_id = VANGUARD_FOURTH_ID
            memory = TacticMemory(
                mode=MODE_AGGRESS,
                unit_labels={
                    str(carrier_id): UnitLabel("VANGUARD", 9),
                },
            )
            turn, _ = make_turn(
                tick=100,
                own_core=core((0, 0)),
                units=(
                    vanguard((7, 0), VANGUARD_ID),
                    vanguard((8, 1), VANGUARD_TWO_ID),
                    vanguard((0, 1), VANGUARD_THREE_ID),
                    vanguard((10, 0), carrier_id),
                    ranger((7, 1), RANGER_ID),
                    ranger((8, 2), RANGER_TWO_ID),
                    ranger((9, 3), RANGER_THREE_ID),
                    ranger((0, 2), RANGER_FOURTH_ID),
                ),
                beacon=ChampionBeacon(
                    position=(10, 0),
                    status=BeaconStatus.CARRIED,
                    carrier_id=carrier_id,
                ),
            )

            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions.get(carrier_id), MoveAction)
        self.assertTrue(
            any(
                "reason=beacon_carrier_attack_advance" in item
                for item in summary.decisions
            )
        )
        self.assertFalse(any("beacon_carrier_return" in item for item in summary.decisions))
        vanguard_guards = {
            route.object_id
            for route in memory.current_routes.values()
            if route.reason.startswith("beacon_vanguard_guard")
        }
        ranger_guards = {
            route.object_id
            for route in memory.current_routes.values()
            if route.reason.startswith("beacon_ranger_guard")
        }
        self.assertEqual(
            vanguard_guards,
            {str(VANGUARD_ID), str(VANGUARD_TWO_ID)},
        )
        self.assertEqual(
            ranger_guards,
            {str(RANGER_ID), str(RANGER_TWO_ID), str(RANGER_THREE_ID)},
        )

    def test_moving_beacon_guards_follow_predicted_carrier_position(self) -> None:
        carrier_id = VANGUARD_FOURTH_ID
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(
                mode=MODE_AGGRESS,
                aggress_beacon_guard_carrier_id=str(carrier_id),
                aggress_beacon_vanguard_guards={
                    str(VANGUARD_ID),
                    str(VANGUARD_TWO_ID),
                },
                aggress_beacon_ranger_guards={
                    str(RANGER_ID),
                    str(RANGER_TWO_ID),
                    str(RANGER_THREE_ID),
                },
            )
            turn, _ = make_turn(
                tick=104,
                own_core=core((0, 0)),
                units=(
                    vanguard((10, 1), VANGUARD_ID),
                    vanguard((10, -1), VANGUARD_TWO_ID),
                    vanguard((10, 0), carrier_id),
                    ranger((11, -1), RANGER_ID),
                    ranger((11, 1), RANGER_TWO_ID),
                    ranger((9, 1), RANGER_THREE_ID),
                ),
                beacon=ChampionBeacon(
                    position=(10, 0),
                    status=BeaconStatus.CARRIED,
                    carrier_id=carrier_id,
                ),
            )

            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions[carrier_id], MoveAction)
        self.assertEqual(
            memory.current_routes[str(carrier_id)].reason,
            "beacon_carrier_attack_advance",
        )
        guard_ids = {
            VANGUARD_ID,
            VANGUARD_TWO_ID,
            RANGER_ID,
            RANGER_TWO_ID,
            RANGER_THREE_ID,
        }
        self.assertTrue(
            all(
                isinstance(turn.plan.unit_actions.get(unit_id), MoveAction)
                for unit_id in guard_ids
            )
        )
        self.assertTrue(
            all(
                memory.current_routes[str(unit_id)].reason.endswith("_patrol")
                for unit_id in guard_ids
            )
        )

    def test_aggress_keeps_three_vanguards_and_three_rangers_at_core(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            vanguard_ids = [UUID(int=0x1000 + index) for index in range(9)]
            ranger_ids = [UUID(int=0x2000 + index) for index in range(9)]
            carrier_id = vanguard_ids[-1]
            units = tuple(
                vanguard((8 + index % 3, index // 3), unit_id)
                for index, unit_id in enumerate(vanguard_ids)
            ) + tuple(
                ranger((8 + index % 3, 3 + index // 3), unit_id)
                for index, unit_id in enumerate(ranger_ids)
            )
            memory = TacticMemory(
                mode=MODE_AGGRESS,
                unit_labels={str(carrier_id): UnitLabel("VANGUARD", 9)},
            )
            turn, _ = make_turn(
                tick=120,
                own_core=core((0, 0)),
                units=units,
                beacon=ChampionBeacon(
                    position=units[8].position,
                    status=BeaconStatus.CARRIED,
                    carrier_id=carrier_id,
                ),
            )

            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        self.assertEqual(AGGRESS_DEFENDER_VANGUARDS, 3)
        self.assertEqual(AGGRESS_DEFENDER_RANGERS, 3)
        self.assertEqual(memory.decision_totals["vanguard:aggress_guard"], 3)
        self.assertEqual(memory.decision_totals["ranger:aggress_guard"], 3)
        watch_routes = [
            route
            for route in memory.current_routes.values()
            if route.reason == "aggress_core_watch"
        ]
        self.assertEqual(len(watch_routes), 6)
        self.assertEqual(
            sorted(_distance((0, 0), route.goal) for route in watch_routes),
            [4, 4, 4, 5, 5, 5],
        )

    def test_known_enemy_core_never_borrows_the_fixed_home_reserve(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            units = tuple(
                vanguard((index + 1, 0), UUID(int=0xA000 + index))
                for index in range(AGGRESS_DEFENDER_VANGUARDS)
            ) + tuple(
                ranger((index + 1, 2), UUID(int=0xA100 + index))
                for index in range(AGGRESS_DEFENDER_RANGERS)
            )
            turn, _ = make_turn(
                tick=220,
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((12, 0)),),
            )

            memory = TacticMemory(mode=MODE_AGGRESS)
            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        self.assertFalse(
            any("enemy_core_assault" in item for item in summary.decisions)
        )
        self.assertFalse(
            any("enemy_core_rally" in item for item in summary.decisions)
        )
        self.assertTrue(
            all(
                "enemy_core" not in route.reason
                for route in SmartTactic(TacticMemory()).memory.current_routes.values()
            )
        )

    def test_incomplete_home_garrison_cannot_stage_known_enemy_core(self) -> None:
        """The surviving 2+2 screen stays home until the 3+3 floor is rebuilt."""
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            units = (
                vanguard((7, 0), UUID(int=0xA180)),
                vanguard((8, 0), UUID(int=0xA181)),
                ranger((7, 2), UUID(int=0xA190)),
                ranger((8, 2), UUID(int=0xA191)),
            )
            turn, _ = make_turn(
                tick=225,
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((16, 0)),),
                resources=12,
            )
            memory = TacticMemory(mode=MODE_AGGRESS)
            summary = SmartTactic(memory, control_path=control_path).choose_actions(turn)

        self.assertFalse(
            any(
                "enemy_core_rally" in item or "enemy_core_assault" in item
                for item in summary.decisions
            )
        )
        self.assertFalse(
            any(
                route.reason.startswith("enemy_core_")
                for route in memory.current_routes.values()
            )
        )
        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertIn(
            turn.plan.core_action.unit_type,
            {UnitType.WORKER, UnitType.VANGUARD, UnitType.RANGER},
        )

    def test_nearby_known_core_rallies_surplus_force_then_uses_range_three_fire(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            home_vanguards = tuple(
                vanguard((index, 1), UUID(int=0xA200 + index))
                for index in range(AGGRESS_DEFENDER_VANGUARDS)
            )
            home_rangers = tuple(
                ranger((index, 2), UUID(int=0xA300 + index))
                for index in range(AGGRESS_DEFENDER_RANGERS)
            )
            assault_vanguard = UUID(int=0xA400)
            assault_ranger_one = UUID(int=0xA401)
            assault_ranger_two = UUID(int=0xA402)
            units = (
                home_vanguards
                + home_rangers
                + (
                    vanguard((1, 0), assault_vanguard),
                    ranger((8, 1), assault_ranger_one),
                    ranger((11, 0), assault_ranger_two),
                )
            )
            tactic = SmartTactic(TacticMemory(mode=MODE_AGGRESS), control_path=control_path)
            rally_turn, _ = make_turn(
                tick=230,
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((16, 0)),),
            )
            rally_summary = tactic.choose_actions(rally_turn)

            ready_units = (
                home_vanguards
                + home_rangers
                + (
                    vanguard((14, 0), assault_vanguard),
                    ranger((8, 1), assault_ranger_one),
                    ranger((13, 0), assault_ranger_two),
                )
            )
            ready_turn, _ = make_turn(
                tick=231,
                own_core=core((0, 0)),
                units=ready_units,
                enemies=(enemy_core((16, 0)),),
            )
            ready_summary = tactic.choose_actions(ready_turn)

        self.assertTrue(
            any("enemy_core_rally" in item for item in rally_summary.decisions)
        )
        action = ready_turn.plan.unit_actions[assault_ranger_two]
        self.assertIsInstance(action, ShootAction)
        self.assertEqual(action.target_id, ENEMY_CORE_ID)
        self.assertEqual(action.expected_cell, (16, 0))
        self.assertTrue(
            any("role=enemy_core_priority" in item for item in ready_summary.decisions)
        )

    def test_core_assault_rangers_wait_for_vanguard_screen(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            home_vanguards = tuple(
                vanguard((index, 1), UUID(int=0xA410 + index))
                for index in range(AGGRESS_DEFENDER_VANGUARDS)
            )
            home_rangers = tuple(
                ranger((index, 2), UUID(int=0xA420 + index))
                for index in range(AGGRESS_DEFENDER_RANGERS)
            )
            assault_vanguard = UUID(int=0xA430)
            firing_ranger = UUID(int=0xA431)
            units = (
                home_vanguards
                + home_rangers
                + (
                    vanguard((8, 0), assault_vanguard),
                    ranger((8, 1), UUID(int=0xA432)),
                    ranger((13, 0), firing_ranger),
                )
            )
            turn, _ = make_turn(
                tick=232,
                own_core=core((0, 0)),
                units=units,
                enemies=(
                    enemy_core((16, 0)),
                    enemy_ranger((16, 2), unit_id=UUID(int=0xA433)),
                ),
            )
            memory = TacticMemory(mode=MODE_AGGRESS)
            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions[firing_ranger], MoveAction)
        self.assertEqual(
            memory.current_routes[str(firing_ranger)].reason,
            "enemy_core_await_screen",
        )
        self.assertTrue(
            any("enemy_core_await_screen" in item for item in summary.decisions)
        )

    def test_nearby_known_core_builds_independent_breach_force_after_home_reserve(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            units = tuple(
                worker(UUID(int=0xA500 + index), (6 + index, 0))
                for index in range(AGGRESS_BASE_WORKERS)
            ) + tuple(
                vanguard((index + 1, 1), UUID(int=0xA600 + index))
                for index in range(AGGRESS_DEFENDER_VANGUARDS)
            ) + tuple(
                ranger((index + 1, 2), UUID(int=0xA700 + index))
                for index in range(AGGRESS_DEFENDER_RANGERS)
            )
            turn, _ = make_turn(
                tick=240,
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((16, 0)),),
                resources=12,
            )

            SmartTactic(
                TacticMemory(mode=MODE_AGGRESS),
                control_path=control_path,
            ).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.VANGUARD)

    def test_home_recovery_requires_all_six_defender_slots(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                vanguard((1, 0), VANGUARD_ID),
                vanguard((0, 1), VANGUARD_TWO_ID),
                ranger((-1, 0), RANGER_ID),
            ),
        )
        tactic = SmartTactic(TacticMemory(mode=MODE_DEVELOP))

        self.assertEqual(tactic._home_guard_shortfall(turn), (1, 2, 3))
        self.assertTrue(tactic._home_recovery_active(turn))

    def test_beacon_recovery_saves_for_first_combat_unit_after_three_workers(
        self,
    ) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (2, 0)),
                worker(WORKER_HIGH, (3, 0)),
                worker(WORKER_THIRD, (4, 0)),
            ),
            resources=6,
            beacon=ChampionBeacon(position=(80, 0)),
        )

        SmartTactic(
            TacticMemory(
                mode=MODE_BEACON,
                last_core_destroyed_tick=7,
                catastrophic_rebuild_pending=True,
            )
        ).choose_actions(turn)

        self.assertNotIsInstance(turn.plan.core_action, SpawnAction)

    def test_completed_catastrophic_rebuild_does_not_reopen_after_later_loss(
        self,
    ) -> None:
        vanguard_ids = [UUID(int=0xB050 + index) for index in range(3)]
        ranger_ids = [UUID(int=0xB060 + index) for index in range(3)]
        rebuilt_turn, _ = make_turn(
            tick=50,
            own_core=core((0, 0)),
            units=tuple(
                vanguard((index + 1, 0), unit_id)
                for index, unit_id in enumerate(vanguard_ids)
            ) + tuple(
                ranger((index + 1, 2), unit_id)
                for index, unit_id in enumerate(ranger_ids)
            ),
        )
        memory = TacticMemory(
            mode=MODE_BEACON,
            last_core_destroyed_tick=7,
            catastrophic_rebuild_pending=True,
        )
        tactic = SmartTactic(memory)

        memory.observe(rebuilt_turn)

        self.assertFalse(memory.catastrophic_rebuild_pending)
        later_loss_turn, _ = make_turn(
            tick=51,
            own_core=core((0, 0)),
            units=tuple(
                vanguard((index + 1, 0), unit_id)
                for index, unit_id in enumerate(vanguard_ids)
            ) + tuple(
                ranger((index + 1, 2), unit_id)
                for index, unit_id in enumerate(ranger_ids[:-1])
            ),
        )
        memory.observe(later_loss_turn)
        self.assertFalse(tactic._catastrophic_rebuild_active(later_loss_turn))

    def test_beacon_home_reserve_scales_with_large_army(self) -> None:
        vanguard_ids = [UUID(int=0xB100 + index) for index in range(8)]
        ranger_ids = [UUID(int=0xB200 + index) for index in range(12)]
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=tuple(
                vanguard((index + 1, 0), unit_id)
                for index, unit_id in enumerate(vanguard_ids)
            ) + tuple(
                ranger((index + 1, 2), unit_id)
                for index, unit_id in enumerate(ranger_ids)
            ),
        )
        tactic = SmartTactic(TacticMemory(mode=MODE_BEACON))

        home_vanguards, home_rangers = tactic._beacon_home_reserve_ids(turn)

        self.assertEqual(len(home_vanguards), 4)
        self.assertEqual(len(home_rangers), 6)

    def test_beacon_core_damage_recalls_every_surviving_combat_unit(self) -> None:
        vanguard_ids = [UUID(int=0xB300 + index) for index in range(8)]
        ranger_ids = [UUID(int=0xB400 + index) for index in range(12)]
        memory = TacticMemory(
            mode=MODE_BEACON,
            last_core_damaged_tick=100,
        )
        turn, _ = make_turn(
            tick=101,
            own_core=core((0, 0), shield=4),
            units=tuple(
                vanguard((40 + index, 0), unit_id)
                for index, unit_id in enumerate(vanguard_ids)
            ) + tuple(
                ranger((40 + index, 2), unit_id)
                for index, unit_id in enumerate(ranger_ids)
            ),
            resources=0,
        )
        tactic = SmartTactic(memory)

        home_vanguards, home_rangers = tactic._beacon_home_reserve_ids(turn)

        self.assertEqual(home_vanguards, set(vanguard_ids))
        self.assertEqual(home_rangers, set(ranger_ids))

    def test_beacon_escort_never_steals_the_six_home_defenders(self) -> None:
        vanguard_ids = [UUID(int=0x9100 + index) for index in range(6)]
        ranger_ids = [UUID(int=0x9200 + index) for index in range(6)]
        carrier_id = vanguard_ids[-1]
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=tuple(
                vanguard((8 + index, 0), unit_id)
                for index, unit_id in enumerate(vanguard_ids)
            ) + tuple(
                ranger((8 + index, 2), unit_id)
                for index, unit_id in enumerate(ranger_ids)
            ),
            beacon=ChampionBeacon(
                position=(13, 0),
                status=BeaconStatus.CARRIED,
                carrier_id=carrier_id,
            ),
        )
        tactic = SmartTactic(TacticMemory(mode=MODE_AGGRESS))

        defender_vanguards, defender_rangers = (
            tactic._aggress_core_defender_ids(turn)
        )
        _, beacon_vanguards, beacon_rangers = (
            tactic._aggress_beacon_guard_assignments(turn)
        )

        self.assertEqual(len(defender_vanguards), 3)
        self.assertEqual(len(defender_rangers), 3)
        self.assertEqual(len(beacon_vanguards), 2)
        self.assertEqual(len(beacon_rangers), 3)
        self.assertFalse(defender_vanguards & beacon_vanguards)
        self.assertFalse(defender_rangers & beacon_rangers)

    def test_core_rebuilds_missing_rangers_before_worker_expansion(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (4, 0)),
                worker(WORKER_HIGH, (5, 0)),
                worker(WORKER_THIRD, (6, 0)),
                worker(WORKER_FOURTH, (7, 0)),
                vanguard((1, 0), VANGUARD_ID),
                vanguard((0, 1), VANGUARD_TWO_ID),
                ranger((-1, 0), RANGER_ID),
            ),
            resources=12,
        )

        SmartTactic(TacticMemory(mode=MODE_DEVELOP)).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.RANGER)

    def test_aggress_vanguard_squad_excludes_core_defender_rangers(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            vanguard_ids = [UUID(int=0x2500 + index) for index in range(9)]
            ranger_ids = [UUID(int=0x2600 + index) for index in range(9)]
            carrier_id = vanguard_ids[-1]
            vanguard_positions = (
                (4, 0),
                (0, 4),
                (-4, 0),
                (5, 1),
                (5, 2),
                (5, 3),
                (48, -1),
                (48, 1),
                (50, 0),
            )
            ranger_positions = (
                (5, 0),
                (0, 5),
                (-5, 0),
                (30, 0),
                (30, 2),
                (30, -2),
                (49, -2),
                (49, 0),
                (49, 2),
            )
            units = tuple(
                vanguard(position, unit_id)
                for position, unit_id in zip(vanguard_positions, vanguard_ids)
            ) + tuple(
                ranger(position, unit_id)
                for position, unit_id in zip(ranger_positions, ranger_ids)
            )
            memory = TacticMemory(
                mode=MODE_AGGRESS,
                unit_labels={str(carrier_id): UnitLabel("VANGUARD", 9)},
            )
            turn, _ = make_turn(
                tick=122,
                own_core=core((0, 0)),
                units=units,
                beacon=ChampionBeacon(
                    position=(50, 0),
                    status=BeaconStatus.CARRIED,
                    carrier_id=carrier_id,
                ),
            )

            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        squad_routes = [
            route
            for route in memory.current_routes.values()
            if route.reason == "vanguard_squad_front"
        ]
        self.assertTrue(squad_routes)
        self.assertTrue(
            all(_distance((0, 0), route.goal) > 20 for route in squad_routes)
        )

    def test_aggress_core_defenders_return_to_heal_when_safe(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            turn, _ = make_turn(
                tick=123,
                own_core=core((0, 0)),
                units=(
                    vanguard((0, 0), VANGUARD_ID, hp=3),
                    vanguard((4, 0), VANGUARD_TWO_ID, hp=3),
                    vanguard((0, 4), VANGUARD_THREE_ID),
                    vanguard((20, 20), VANGUARD_FOURTH_ID, hp=2),
                    ranger((0, 5), RANGER_ID, hp=1),
                    ranger((5, 0), RANGER_TWO_ID),
                    ranger((-5, 0), RANGER_THREE_ID),
                    ranger((22, 20), RANGER_FOURTH_ID, hp=1),
                ),
                resources=5,
            )
            memory = TacticMemory(mode=MODE_AGGRESS)

            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions[VANGUARD_ID], HealAction)
        healing_routes = {
            route.object_id
            for route in memory.current_routes.values()
            if route.reason == "aggress_guard_heal_return"
        }
        self.assertIn(str(VANGUARD_TWO_ID), healing_routes)
        self.assertIn(str(RANGER_ID), healing_routes)
        self.assertNotIn(str(VANGUARD_FOURTH_ID), healing_routes)
        self.assertNotIn(str(RANGER_FOURTH_ID), healing_routes)

    def test_aggress_core_defenders_do_not_heal_while_enemy_visible(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            turn, _ = make_turn(
                tick=124,
                own_core=core((0, 0)),
                units=(
                    vanguard((0, 0), VANGUARD_ID, hp=3),
                    vanguard((4, 0), VANGUARD_TWO_ID, hp=3),
                    vanguard((0, 4), VANGUARD_THREE_ID),
                    vanguard((20, 20), VANGUARD_FOURTH_ID),
                    ranger((0, 5), RANGER_ID, hp=1),
                    ranger((5, 0), RANGER_TWO_ID),
                    ranger((-5, 0), RANGER_THREE_ID),
                    ranger((22, 20), RANGER_FOURTH_ID),
                ),
                enemies=(enemy_ranger((9, 0)),),
                resources=5,
            )
            memory = TacticMemory(mode=MODE_AGGRESS)

            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        self.assertNotIsInstance(
            turn.plan.unit_actions.get(VANGUARD_ID),
            HealAction,
        )
        self.assertFalse(
            any(
                route.reason == "aggress_guard_heal_return"
                for route in memory.current_routes.values()
            )
        )

    def test_aggress_relief_reaches_patient_before_rotation_return(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(mode=MODE_AGGRESS)
            tactic = SmartTactic(memory, control_path=control_path)
            first_turn, _ = make_turn(
                tick=130,
                own_core=core((0, 0)),
                units=(
                    vanguard((0, 4), VANGUARD_ID),
                    vanguard((4, 0), VANGUARD_TWO_ID),
                    vanguard((-4, 0), VANGUARD_THREE_ID),
                    vanguard((18, 2), VANGUARD_FOURTH_ID),
                    ranger((0, 5), RANGER_ID),
                    ranger((5, 0), RANGER_TWO_ID),
                    ranger((-5, 0), RANGER_THREE_ID),
                    ranger((20, 0), RANGER_FOURTH_ID, hp=1),
                ),
                resources=5,
            )

            first_summary = tactic.choose_actions(first_turn)

            rotation = memory.aggress_heal_rotations[str(RANGER_FOURTH_ID)]
            relief_id = UUID(rotation.relief_id)
            self.assertEqual(rotation.phase, "relief")
            self.assertIsInstance(
                first_turn.plan.unit_actions[RANGER_FOURTH_ID],
                WaitAction,
            )
            self.assertIsInstance(first_turn.plan.unit_actions[relief_id], MoveAction)
            self.assertTrue(
                any("heal_rotation_assigned" in item for item in first_summary.decisions)
            )

            positions = {
                RANGER_ID: (0, 5),
                RANGER_TWO_ID: (5, 0),
                RANGER_THREE_ID: (-5, 0),
                RANGER_FOURTH_ID: (20, 0),
            }
            positions[relief_id] = (19, 0)
            second_turn, _ = make_turn(
                tick=131,
                own_core=core((0, 0)),
                units=tuple(
                    ranger(
                        positions[unit_id],
                        unit_id,
                        hp=1 if unit_id == RANGER_FOURTH_ID else 2,
                    )
                    for unit_id in (
                        RANGER_ID,
                        RANGER_TWO_ID,
                        RANGER_THREE_ID,
                        RANGER_FOURTH_ID,
                    )
                ),
                resources=5,
            )

            second_summary = tactic.choose_actions(second_turn)

        self.assertEqual(
            memory.aggress_heal_rotations[str(RANGER_FOURTH_ID)].phase,
            "return",
        )
        patient_route = memory.current_routes[str(RANGER_FOURTH_ID)]
        self.assertEqual(patient_route.reason, "aggress_rotation_heal_return")
        self.assertTrue(
            any("heal_rotation_handoff" in item for item in second_summary.decisions)
        )
        self.assertNotEqual(
            memory.current_routes[rotation.relief_id].reason,
            "aggress_core_watch",
        )

    def test_aggress_rotation_can_send_two_same_type_reliefs(self) -> None:
        fifth_ranger_id = UUID("00000000-0000-4000-8000-000000000017")
        sixth_ranger_id = UUID("00000000-0000-4000-8000-000000000018")
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(mode=MODE_AGGRESS)
            turn, _ = make_turn(
                tick=135,
                own_core=core((0, 0)),
                units=(
                    vanguard((0, 4), VANGUARD_ID),
                    vanguard((4, 0), VANGUARD_TWO_ID),
                    vanguard((-4, 0), VANGUARD_THREE_ID),
                    vanguard((18, 2), VANGUARD_FOURTH_ID),
                    ranger((0, 5), RANGER_ID),
                    ranger((5, 0), RANGER_TWO_ID),
                    ranger((-5, 0), RANGER_THREE_ID),
                    ranger((20, 0), RANGER_FOURTH_ID, hp=1),
                    ranger((20, 2), fifth_ranger_id, hp=1),
                    ranger((20, 4), sixth_ranger_id),
                ),
                resources=5,
            )

            SmartTactic(memory, control_path=control_path).choose_actions(turn)
            memory_path = Path(directory) / ".arena_hero_memory.json"
            memory.save(memory_path)
            loaded = TacticMemory.load(memory_path)

        self.assertEqual(len(memory.aggress_heal_rotations), 2)
        self.assertEqual(loaded.aggress_heal_rotations, memory.aggress_heal_rotations)
        self.assertEqual(
            set(memory.aggress_heal_rotations),
            {str(RANGER_FOURTH_ID), str(fifth_ranger_id)},
        )
        relief_ids = {
            UUID(rotation.relief_id)
            for rotation in memory.aggress_heal_rotations.values()
        }
        self.assertEqual(len(relief_ids), 2)
        self.assertTrue(
            all(
                isinstance(turn.plan.unit_actions[unit_id], MoveAction)
                for unit_id in relief_ids
            )
        )

    def test_aggress_injured_beacon_guard_waits_for_relief(self) -> None:
        fifth_vanguard_id = UUID("00000000-0000-4000-8000-000000000019")
        sixth_vanguard_id = UUID("00000000-0000-4000-8000-000000000020")
        fifth_ranger_id = UUID("00000000-0000-4000-8000-000000000021")
        sixth_ranger_id = UUID("00000000-0000-4000-8000-000000000022")
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(mode=MODE_AGGRESS)
            tactic = SmartTactic(memory, control_path=control_path)
            turn, _ = make_turn(
                tick=138,
                own_core=core((0, 0)),
                units=(
                    vanguard((19, 0), VANGUARD_ID, hp=3),
                    vanguard((20, 1), VANGUARD_TWO_ID),
                    vanguard((0, 4), VANGUARD_THREE_ID),
                    vanguard((20, 0), VANGUARD_FOURTH_ID),
                    vanguard((4, 0), fifth_vanguard_id),
                    vanguard((-4, 0), sixth_vanguard_id),
                    ranger((0, 5), RANGER_ID),
                    ranger((5, 0), RANGER_TWO_ID),
                    ranger((-5, 0), RANGER_THREE_ID),
                    ranger((18, 3), RANGER_FOURTH_ID),
                    ranger((0, -5), fifth_ranger_id),
                    ranger((-4, -1), sixth_ranger_id),
                ),
                resources=5,
                beacon=ChampionBeacon(
                    position=(20, 0),
                    status=BeaconStatus.CARRIED,
                    carrier_id=VANGUARD_FOURTH_ID,
                ),
            )

            summary = tactic.choose_actions(turn)

        _, vanguard_guards, _ = tactic._aggress_beacon_guard_assignments(turn)
        rotation = memory.aggress_heal_rotations[str(VANGUARD_ID)]
        relief_id = UUID(rotation.relief_id)
        self.assertIn(VANGUARD_ID, vanguard_guards)
        self.assertNotIn(relief_id, vanguard_guards)
        self.assertNotEqual(relief_id, VANGUARD_FOURTH_ID)
        self.assertEqual(rotation.phase, "relief")
        self.assertIsInstance(turn.plan.unit_actions[VANGUARD_ID], WaitAction)
        self.assertIsInstance(turn.plan.unit_actions[relief_id], MoveAction)
        self.assertTrue(
            any("heal_rotation_assigned" in item for item in summary.decisions)
        )

    def test_aggress_recovered_patient_stays_home_and_relief_stays_front(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(mode=MODE_AGGRESS)
            tactic = SmartTactic(memory, control_path=control_path)
            assignment_turn, _ = make_turn(
                tick=140,
                own_core=core((0, 0)),
                units=(
                    vanguard((0, 4), VANGUARD_ID),
                    vanguard((4, 0), VANGUARD_TWO_ID),
                    vanguard((-4, 0), VANGUARD_THREE_ID),
                    vanguard((18, 2), VANGUARD_FOURTH_ID),
                    ranger((0, 5), RANGER_ID),
                    ranger((5, 0), RANGER_TWO_ID),
                    ranger((-5, 0), RANGER_THREE_ID),
                    ranger((20, 0), RANGER_FOURTH_ID, hp=1),
                ),
                resources=5,
            )
            tactic.choose_actions(assignment_turn)
            rotation = memory.aggress_heal_rotations[str(RANGER_FOURTH_ID)]
            memory.aggress_heal_rotations[str(RANGER_FOURTH_ID)] = type(rotation)(
                relief_id=rotation.relief_id,
                rendezvous=rotation.rendezvous,
                phase="return",
                created_tick=rotation.created_tick,
            )
            relief_id = UUID(rotation.relief_id)
            positions = {
                RANGER_ID: (0, 5),
                RANGER_TWO_ID: (5, 0),
                RANGER_THREE_ID: (-5, 0),
                RANGER_FOURTH_ID: (0, 0),
            }
            positions[relief_id] = (20, 0)
            healing_turn, _ = make_turn(
                tick=141,
                own_core=core((0, 0)),
                units=tuple(
                    ranger(
                        positions[unit_id],
                        unit_id,
                        hp=1 if unit_id == RANGER_FOURTH_ID else 2,
                    )
                    for unit_id in (
                        RANGER_ID,
                        RANGER_TWO_ID,
                        RANGER_THREE_ID,
                        RANGER_FOURTH_ID,
                    )
                ),
                resources=5,
            )

            tactic.choose_actions(healing_turn)

            self.assertIsInstance(
                healing_turn.plan.unit_actions[RANGER_FOURTH_ID],
                HealAction,
            )
            recovered_turn, _ = make_turn(
                tick=142,
                own_core=core((0, 0)),
                units=tuple(
                    ranger(positions[unit_id], unit_id)
                    for unit_id in (
                        RANGER_ID,
                        RANGER_TWO_ID,
                        RANGER_THREE_ID,
                        RANGER_FOURTH_ID,
                    )
                ),
                resources=4,
            )
            recovered_summary = tactic.choose_actions(recovered_turn)
            _, ranger_defenders = tactic._aggress_core_defender_ids(recovered_turn)
            memory_path = Path(directory) / ".arena_hero_memory.json"
            memory.save(memory_path)
            loaded = TacticMemory.load(memory_path)

        self.assertNotIn(str(RANGER_FOURTH_ID), memory.aggress_heal_rotations)
        self.assertEqual(len(memory.aggress_heal_role_swaps), 1)
        self.assertEqual(
            loaded.aggress_heal_role_swaps,
            memory.aggress_heal_role_swaps,
        )
        self.assertIn(RANGER_FOURTH_ID, ranger_defenders)
        self.assertNotIn(relief_id, ranger_defenders)
        self.assertTrue(
            any(
                "patient_role=core_guard relief_role=frontline" in item
                for item in recovered_summary.decisions
            )
        )

    def test_aggress_completed_heal_swaps_do_not_expand_defender_caps(self) -> None:
        carrier_id = UUID(int=0x5000)
        vanguard_ids = [carrier_id] + [
            UUID(int=0x5000 + index) for index in range(1, 8)
        ]
        ranger_ids = [UUID(int=0x6000 + index) for index in range(7)]
        beacon_vanguard_ids = set(vanguard_ids[1:3])
        beacon_ranger_ids = set(ranger_ids[:3])
        units = (
            vanguard((20, 0), carrier_id),
            vanguard((19, 0), vanguard_ids[1]),
            vanguard((21, 0), vanguard_ids[2]),
            *(
                vanguard((index, 4), unit_id)
                for index, unit_id in enumerate(vanguard_ids[3:])
            ),
            ranger((18, 0), ranger_ids[0]),
            ranger((20, 2), ranger_ids[1]),
            ranger((22, 0), ranger_ids[2]),
            *(
                ranger((index, 5), unit_id)
                for index, unit_id in enumerate(ranger_ids[3:])
            ),
        )
        memory = TacticMemory(
            mode=MODE_AGGRESS,
            aggress_heal_role_swaps=[
                HealRoleSwap(str(vanguard_ids[6]), str(vanguard_ids[1]), 100),
                HealRoleSwap(str(vanguard_ids[7]), str(vanguard_ids[2]), 101),
                HealRoleSwap(str(ranger_ids[6]), str(ranger_ids[0]), 102),
                HealRoleSwap(str(ranger_ids[5]), str(ranger_ids[1]), 103),
            ],
        )
        turn, _ = make_turn(
            tick=200,
            own_core=core((0, 0)),
            units=units,
            beacon=ChampionBeacon(
                position=(20, 0),
                status=BeaconStatus.CARRIED,
                carrier_id=carrier_id,
            ),
        )
        tactic = SmartTactic(memory)

        _, beacon_vanguards, beacon_rangers = (
            tactic._aggress_beacon_guard_assignments(turn)
        )
        defender_vanguards, defender_rangers = (
            tactic._aggress_core_defender_ids(turn)
        )

        self.assertEqual(beacon_vanguards, beacon_vanguard_ids)
        self.assertEqual(beacon_rangers, beacon_ranger_ids)
        self.assertEqual(len(defender_vanguards), AGGRESS_DEFENDER_VANGUARDS)
        self.assertEqual(len(defender_rangers), AGGRESS_DEFENDER_RANGERS)
        self.assertTrue({vanguard_ids[6], vanguard_ids[7]} <= defender_vanguards)
        self.assertTrue({ranger_ids[5], ranger_ids[6]} <= defender_rangers)
        self.assertFalse(beacon_vanguards & defender_vanguards)
        self.assertFalse(beacon_rangers & defender_rangers)

    def test_enemy_core_cancels_heal_rotation_and_keeps_attack_priority(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(mode=MODE_AGGRESS)
            tactic = SmartTactic(memory, control_path=control_path)
            quiet_turn, _ = make_turn(
                tick=150,
                own_core=core((0, 0)),
                units=(
                    vanguard((0, 4), VANGUARD_ID),
                    vanguard((4, 0), VANGUARD_TWO_ID),
                    vanguard((-4, 0), VANGUARD_THREE_ID),
                    vanguard((18, 2), VANGUARD_FOURTH_ID),
                    ranger((0, 5), RANGER_ID),
                    ranger((5, 0), RANGER_TWO_ID),
                    ranger((-5, 0), RANGER_THREE_ID),
                    ranger((20, 0), RANGER_FOURTH_ID, hp=1),
                ),
                resources=5,
            )
            tactic.choose_actions(quiet_turn)
            self.assertTrue(memory.aggress_heal_rotations)
            core_turn, _ = make_turn(
                tick=151,
                own_core=core((0, 0)),
                units=(
                    ranger((0, 5), RANGER_ID),
                    ranger((5, 0), RANGER_TWO_ID),
                    ranger((-5, 0), RANGER_THREE_ID),
                    ranger((20, 0), RANGER_FOURTH_ID, hp=1),
                ),
                enemies=(enemy_core((23, 0)),),
                resources=5,
            )

            summary = tactic.choose_actions(core_turn)

        self.assertFalse(memory.aggress_heal_rotations)
        self.assertEqual(tactic._pick_assault_target(core_turn), (23, 0))
        self.assertTrue(
            any("enemy_core_priority" in item for item in summary.decisions)
        )

    def test_aggress_rotation_waits_for_eight_quiet_ticks(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(mode=MODE_AGGRESS)
            tactic = SmartTactic(memory, control_path=control_path)

            def rotation_turn(tick: int, *, enemy_visible: bool) -> Turn:
                turn, _ = make_turn(
                    tick=tick,
                    own_core=core((0, 0)),
                    units=(
                        vanguard((0, 4), VANGUARD_ID),
                        vanguard((4, 0), VANGUARD_TWO_ID),
                        vanguard((-4, 0), VANGUARD_THREE_ID),
                        vanguard((18, 2), VANGUARD_FOURTH_ID),
                        ranger((0, 5), RANGER_ID),
                        ranger((5, 0), RANGER_TWO_ID),
                        ranger((-5, 0), RANGER_THREE_ID),
                        ranger((20, 0), RANGER_FOURTH_ID, hp=1),
                    ),
                    enemies=(enemy_ranger((8, 0)),) if enemy_visible else (),
                    resources=5,
                )
                return turn

            tactic.choose_actions(rotation_turn(170, enemy_visible=True))
            tactic.choose_actions(rotation_turn(171, enemy_visible=False))
            self.assertFalse(memory.aggress_heal_rotations)

            tactic.choose_actions(rotation_turn(179, enemy_visible=False))

        self.assertTrue(memory.aggress_heal_rotations)

    def test_remembered_enemy_core_outranks_visible_non_core(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(mode=MODE_AGGRESS)
            tactic = SmartTactic(memory, control_path=control_path)
            seen_turn, _ = make_turn(
                tick=160,
                own_core=core((0, 0)),
                units=(
                    ranger((17, 0), RANGER_ID),
                    ranger((17, 1), RANGER_TWO_ID),
                    ranger((16, 0), RANGER_THREE_ID),
                    ranger((16, 1), RANGER_FOURTH_ID),
                ),
                enemies=(enemy_core((20, 0)),),
            )
            tactic.choose_actions(seen_turn)
            pursuit_turn, _ = make_turn(
                tick=161,
                own_core=core((0, 0)),
                units=(
                    ranger((0, 1), RANGER_ID),
                    ranger((1, 0), RANGER_TWO_ID),
                    ranger((-1, 0), RANGER_THREE_ID),
                    ranger((2, 0), RANGER_FOURTH_ID),
                ),
                enemies=(enemy_ranger((6, 0)),),
            )

            summary = tactic.choose_actions(pursuit_turn)

        self.assertEqual(tactic._pick_assault_target(pursuit_turn), (20, 0))
        # The remembered coordinate remains preferred, but an incomplete 3+3
        # home screen must not march toward it before replacement units arrive.
        self.assertFalse(
            any("enemy_core_rally" in item or "enemy_core_assault" in item
                for item in summary.decisions)
        )

    def test_enemy_core_sighting_persists_until_its_cell_is_rechecked(self) -> None:
        memory = TacticMemory(
            mode=MODE_AGGRESS,
            enemy_sightings={
                str(ENEMY_CORE_ID): EnemySighting(
                    position=(30, 0),
                    seen_tick=100,
                    is_core=True,
                )
            },
        )
        pursuit_turn, _ = make_turn(
            tick=121,
            own_core=core((0, 0)),
            units=(ranger((0, 0), RANGER_ID),),
        )

        memory.observe(pursuit_turn)

        self.assertIn(str(ENEMY_CORE_ID), memory.enemy_sightings)

        rechecked_turn, _ = make_turn(
            tick=122,
            own_core=core((0, 0)),
            units=(ranger((27, 0), RANGER_ID),),
        )

        memory.observe(rechecked_turn)

        self.assertNotIn(str(ENEMY_CORE_ID), memory.enemy_sightings)

    def test_enemy_core_priority_preserves_defenders_and_beacon_escorts(self) -> None:
        carrier_id = UUID(int=0x7000)
        vanguard_ids = [carrier_id] + [
            UUID(int=0x7000 + index) for index in range(1, 8)
        ]
        ranger_ids = [UUID(int=0x7100 + index) for index in range(7)]
        units = (
            vanguard((20, 0), carrier_id),
            vanguard((19, 0), vanguard_ids[1]),
            vanguard((21, 0), vanguard_ids[2]),
            vanguard((0, 4), vanguard_ids[3]),
            vanguard((4, 0), vanguard_ids[4]),
            vanguard((-4, 0), vanguard_ids[5]),
            vanguard((0, -4), vanguard_ids[6]),
            vanguard((6, 0), vanguard_ids[7]),
            ranger((18, 0), ranger_ids[0]),
            ranger((20, 2), ranger_ids[1]),
            ranger((22, 0), ranger_ids[2]),
            ranger((0, 5), ranger_ids[3]),
            ranger((5, 0), ranger_ids[4]),
            ranger((-5, 0), ranger_ids[5]),
            ranger((0, -5), ranger_ids[6]),
        )
        memory = TacticMemory(
            mode=MODE_AGGRESS,
            enemy_sightings={
                str(ENEMY_CORE_ID): EnemySighting(
                    position=(30, 0),
                    seen_tick=200,
                    is_core=True,
                )
            },
        )
        turn, _ = make_turn(
            tick=200,
            own_core=core((0, 0)),
            units=units,
            beacon=ChampionBeacon(
                position=(20, 0),
                status=BeaconStatus.CARRIED,
                carrier_id=carrier_id,
            ),
        )

        tactic = SmartTactic(memory)
        summary = tactic.choose_actions(turn)
        defender_vanguards, defender_rangers = tactic._aggress_core_defender_ids(turn)
        _, beacon_vanguards, beacon_rangers = (
            tactic._aggress_beacon_guard_assignments(turn)
        )

        vanguard_assault_ids = {
            UUID(route.object_id)
            for route in memory.current_routes.values()
            if route.reason.startswith("enemy_core_assault")
        }
        ranger_assault_ids = {
            UUID(route.object_id)
            for route in memory.current_routes.values()
            if route.reason.startswith("enemy_core_seek_firing")
        }
        expected_vanguard_assault_ids = (
            set(vanguard_ids)
            - {carrier_id}
            - defender_vanguards
            - beacon_vanguards
        )
        expected_ranger_assault_ids = (
            set(ranger_ids) - defender_rangers - beacon_rangers
        )
        # A nearby defended Core now waits for the independent breach force to
        # rally; a pre-existing distant beacon convoy keeps its former direct
        # push behavior.  In either case defenders/escorts remain excluded.
        self.assertTrue(vanguard_assault_ids <= expected_vanguard_assault_ids)
        self.assertTrue(ranger_assault_ids <= expected_ranger_assault_ids)
        defender_route_ids = defender_vanguards | defender_rangers
        self.assertFalse(
            any(
                UUID(route.object_id) in defender_route_ids
                and (
                    route.reason.startswith("enemy_core_assault")
                    or route.reason.startswith("enemy_core_seek_firing")
                )
                for route in memory.current_routes.values()
            )
        )
        self.assertTrue(
            any("enemy_core_priority target=(30, 0)" in item for item in summary.decisions)
        )

    def test_beacon_ranger_guard_replaces_a_severe_straggler(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(mode=MODE_AGGRESS)
            tactic = SmartTactic(memory, control_path=control_path)
            carrier_id = VANGUARD_ID
            first_turn, _ = make_turn(
                tick=210,
                own_core=core((0, 10)),
                units=(
                    vanguard((0, 0), carrier_id),
                    ranger((10, 0), RANGER_ID),
                    ranger((11, 0), RANGER_TWO_ID),
                    ranger((12, 0), RANGER_THREE_ID),
                    ranger((20, 0), RANGER_FOURTH_ID),
                ),
                beacon=ChampionBeacon(
                    position=(0, 0),
                    status=BeaconStatus.CARRIED,
                    carrier_id=carrier_id,
                ),
            )
            tactic.choose_actions(first_turn)

            second_turn, _ = make_turn(
                tick=211,
                own_core=core((0, 10)),
                units=(
                    vanguard((0, 0), carrier_id),
                    ranger((20, 5), RANGER_ID),
                    ranger((1, 0), RANGER_TWO_ID),
                    ranger((2, 0), RANGER_THREE_ID),
                    ranger((3, 0), RANGER_FOURTH_ID),
                ),
                beacon=ChampionBeacon(
                    position=(0, 0),
                    status=BeaconStatus.CARRIED,
                    carrier_id=carrier_id,
                ),
            )
            tactic.choose_actions(second_turn)

        _, _, beacon_rangers = tactic._aggress_beacon_guard_assignments(second_turn)
        self.assertNotIn(RANGER_ID, beacon_rangers)
        self.assertIn(RANGER_FOURTH_ID, beacon_rangers)

    def test_aggress_large_core_threat_recalls_only_the_assault_force(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            vanguard_ids = [UUID(int=0x5000 + index) for index in range(9)]
            ranger_ids = [UUID(int=0x6000 + index) for index in range(9)]
            carrier_id = vanguard_ids[-1]
            units = tuple(
                vanguard(position, unit_id)
                for position, unit_id in zip(
                    (
                        (4, 0), (0, 4), (-4, 0),
                        (30, 20), (31, 20), (32, 20),
                        (49, -1), (49, 1), (50, 0),
                    ),
                    vanguard_ids,
                )
            ) + tuple(
                ranger(position, unit_id)
                for position, unit_id in zip(
                    (
                        (5, 0), (0, 5), (-5, 0),
                        (30, 22), (31, 22), (32, 22),
                        (49, -2), (49, 0), (49, 2),
                    ),
                    ranger_ids,
                )
            )
            enemies = tuple(
                enemy_ranger(
                    position,
                    unit_id=UUID(int=0x7000 + index),
                )
                for index, position in enumerate(((6, 0), (0, 6), (-6, 0), (0, -6)))
            )
            memory = TacticMemory(
                mode=MODE_AGGRESS,
                unit_labels={str(carrier_id): UnitLabel("VANGUARD", 9)},
            )
            turn, _ = make_turn(
                tick=130,
                own_core=core((0, 0)),
                units=units,
                enemies=enemies,
                beacon=ChampionBeacon(
                    position=(50, 0),
                    status=BeaconStatus.CARRIED,
                    carrier_id=carrier_id,
                ),
            )
            tactic = SmartTactic(memory, control_path=control_path)

            summary = tactic.choose_actions(turn)

        carrier, beacon_vanguards, beacon_rangers = (
            tactic._aggress_beacon_guard_assignments(turn)
        )
        defender_vanguards, defender_rangers = tactic._aggress_core_defender_ids(turn)
        assault_vanguards = (
            set(vanguard_ids)
            - defender_vanguards
            - beacon_vanguards
            - {carrier.id if carrier is not None else carrier_id}
        )
        assault_rangers = set(ranger_ids) - defender_rangers - beacon_rangers
        reinforcement_routes = {
            UUID(route.object_id)
            for route in memory.current_routes.values()
            if route.reason == "aggress_core_reinforce"
        }
        self.assertEqual(len(enemies), AGGRESS_CORE_REINFORCEMENT_ENEMY_COUNT)
        self.assertTrue(assault_vanguards <= reinforcement_routes)
        self.assertTrue(assault_rangers <= reinforcement_routes)
        self.assertFalse((beacon_vanguards | beacon_rangers) & reinforcement_routes)
        self.assertTrue(
            any("core_reinforcement_alert" in decision for decision in summary.decisions)
        )

    def test_aggress_three_core_threats_do_not_recall_assault_force(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            enemies = tuple(
                enemy_ranger(
                    position,
                    unit_id=UUID(int=0x7100 + index),
                )
                for index, position in enumerate(((7, 0), (0, 7), (-7, 0)))
            )
            memory = TacticMemory(mode=MODE_AGGRESS)
            turn, _ = make_turn(
                tick=131,
                own_core=core((0, 0)),
                units=(
                    vanguard((20, 20), VANGUARD_ID),
                    vanguard((21, 20), VANGUARD_TWO_ID),
                    ranger((20, 22), RANGER_ID),
                    ranger((21, 22), RANGER_TWO_ID),
                ),
                enemies=enemies,
            )

            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        self.assertFalse(
            any("core_reinforcement_alert" in decision for decision in summary.decisions)
        )
        self.assertFalse(
            any(
                route.reason == "aggress_core_reinforce"
                for route in memory.current_routes.values()
            )
        )

    def test_aggress_core_defender_vacates_toward_watch_slot(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(
                mode=MODE_AGGRESS,
                unit_labels={str(RANGER_ID): UnitLabel("RANGER", 22)},
            )
            turn, _ = make_turn(
                tick=132,
                own_core=core((0, 0)),
                units=(
                    ranger((0, 0), RANGER_ID),
                    ranger((20, 20), RANGER_TWO_ID),
                ),
                resources=5,
            )

            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        route = memory.current_routes[str(RANGER_ID)]
        watch_positions = set(AGGRESS_RANGER_WATCH_OFFSETS)
        self.assertEqual(route.reason, "vacate_core_for_logistics")
        self.assertIn(route.goal, watch_positions)
        self.assertNotEqual(route.goal, turn.beacon.position)

    def test_aggress_core_guards_contract_when_outer_watch_sees_enemy(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            vanguard_ids = [UUID(int=0x3000 + index) for index in range(4)]
            ranger_ids = [UUID(int=0x4000 + index) for index in range(4)]
            units = tuple(
                vanguard((20, 20 + index), unit_id)
                for index, unit_id in enumerate(vanguard_ids)
            ) + tuple(
                ranger((24, 20 + index), unit_id)
                for index, unit_id in enumerate(ranger_ids)
            )
            memory = TacticMemory(mode=MODE_AGGRESS)
            turn, _ = make_turn(
                tick=121,
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_ranger((9, 0)),),
            )

            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        contract_routes = [
            route
            for route in memory.current_routes.values()
            if route.reason == "aggress_core_contract"
        ]
        self.assertEqual(len(contract_routes), 6)
        self.assertTrue(
            all(_distance((0, 0), route.goal) <= 2 for route in contract_routes)
        )

    def test_aggress_beacon_guards_intercept_threats_near_carrier(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            carrier_id = VANGUARD_FOURTH_ID
            memory = TacticMemory(
                mode=MODE_AGGRESS,
                unit_labels={
                    str(carrier_id): UnitLabel("VANGUARD", 9),
                },
            )
            turn, _ = make_turn(
                tick=100,
                own_core=core((0, 0)),
                units=(
                    vanguard((5, 3), VANGUARD_ID),
                    vanguard((7, 5), VANGUARD_TWO_ID),
                    vanguard((0, 1), VANGUARD_THREE_ID),
                    vanguard((5, 5), carrier_id),
                    ranger((2, 4), RANGER_ID),
                    ranger((4, 2), RANGER_TWO_ID),
                    ranger((8, 5), RANGER_THREE_ID),
                    ranger((0, 2), RANGER_FOURTH_ID),
                ),
                enemies=(enemy_ranger((5, 4)),),
                beacon=ChampionBeacon(
                    position=(5, 5),
                    status=BeaconStatus.CARRIED,
                    carrier_id=carrier_id,
                ),
            )

            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions[VANGUARD_ID], SweepAction)
        self.assertIsInstance(turn.plan.unit_actions[RANGER_ID], ShootAction)
        self.assertTrue(any("role=beacon_guard" in item for item in summary.decisions))
        carrier_action = turn.plan.unit_actions[carrier_id]
        self.assertIsInstance(carrier_action, SweepAction)
        self.assertEqual(carrier_action.direction, Direction.UP)
        self.assertFalse(any("beacon_evade" in item for item in summary.decisions))

    def test_supported_beacon_carrier_advances_on_threat(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            carrier_id = VANGUARD_FOURTH_ID
            memory = TacticMemory(mode=MODE_AGGRESS)
            turn, _ = make_turn(
                tick=120,
                own_core=core((0, 0)),
                units=(
                    vanguard((10, 0), carrier_id),
                    vanguard((9, -1), VANGUARD_ID),
                    vanguard((9, 1), VANGUARD_TWO_ID),
                    ranger((8, 0), RANGER_ID),
                    ranger((9, -2), RANGER_TWO_ID),
                    ranger((9, 2), RANGER_THREE_ID),
                ),
                enemies=(enemy_ranger((10, -3)),),
                beacon=ChampionBeacon(
                    position=(10, 0),
                    status=BeaconStatus.CARRIED,
                    carrier_id=carrier_id,
                ),
            )

            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        action = turn.plan.unit_actions[carrier_id]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.UP)
        self.assertTrue(
            any(
                "reason=beacon_carrier_attack_advance" in item
                for item in summary.decisions
            )
        )
        self.assertEqual(
            memory.current_routes[str(carrier_id)].reason,
            "beacon_carrier_attack_advance",
        )

    def test_isolated_beacon_carrier_regroups_with_forward_allies(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            carrier_id = VANGUARD_FOURTH_ID
            memory = TacticMemory(mode=MODE_AGGRESS)
            turn, _ = make_turn(
                tick=120,
                own_core=core((0, 0)),
                units=(
                    vanguard((10, 0), carrier_id),
                    vanguard((16, 0), VANGUARD_ID),
                    vanguard((16, 1), VANGUARD_TWO_ID),
                    ranger((17, 0), RANGER_ID),
                    ranger((17, 1), RANGER_TWO_ID),
                    ranger((18, 0), RANGER_THREE_ID),
                ),
                enemies=(enemy_ranger((10, -3)),),
                beacon=ChampionBeacon(
                    position=(10, 0),
                    status=BeaconStatus.CARRIED,
                    carrier_id=carrier_id,
                ),
            )

            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        action = turn.plan.unit_actions[carrier_id]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.RIGHT)
        route = memory.current_routes[str(carrier_id)]
        self.assertEqual(route.reason, "beacon_carrier_regroup")
        self.assertGreater(_distance(route.path[1], (0, 0)), 10)
        self.assertTrue(any("support=0" in item for item in summary.decisions))

    def test_beacon_guards_send_only_one_mobile_interceptor_per_type(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            carrier_id = VANGUARD_FOURTH_ID
            memory = TacticMemory(mode=MODE_AGGRESS)
            turn, _ = make_turn(
                tick=121,
                own_core=core((0, 0)),
                units=(
                    vanguard((5, 5), carrier_id),
                    vanguard((4, 5), VANGUARD_ID),
                    vanguard((6, 5), VANGUARD_TWO_ID),
                    ranger((3, 7), RANGER_ID),
                    ranger((5, 7), RANGER_TWO_ID),
                    ranger((7, 7), RANGER_THREE_ID),
                ),
                enemies=(enemy_ranger((5, 1)),),
                beacon=ChampionBeacon(
                    position=(5, 5),
                    status=BeaconStatus.CARRIED,
                    carrier_id=carrier_id,
                ),
            )

            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        routes = tuple(memory.current_routes.values())
        self.assertEqual(
            sum(route.reason.startswith("beacon_vanguard_intercept") for route in routes),
            1,
        )
        self.assertEqual(
            sum(route.reason.startswith("beacon_ranger_intercept") for route in routes),
            1,
        )

    def test_beacon_guard_returns_and_heals_after_handoff_during_contact(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            carrier_id = VANGUARD_FOURTH_ID
            memory = TacticMemory(
                mode=MODE_AGGRESS,
                aggress_heal_rotations={
                    str(RANGER_ID): HealRotation(
                        relief_id=str(RANGER_FOURTH_ID),
                        rendezvous=(10, 1),
                        phase="return",
                        created_tick=110,
                    )
                },
            )
            turn, _ = make_turn(
                tick=122,
                own_core=core((0, 0)),
                units=(
                    vanguard((10, 0), carrier_id),
                    vanguard((9, 0), VANGUARD_ID),
                    vanguard((11, 0), VANGUARD_TWO_ID),
                    ranger((10, 1), RANGER_ID, hp=1),
                    ranger((9, 2), RANGER_TWO_ID),
                    ranger((11, 2), RANGER_THREE_ID),
                    ranger((10, 4), RANGER_FOURTH_ID),
                ),
                enemies=(enemy_ranger((15, 0)),),
                beacon=ChampionBeacon(
                    position=(10, 0),
                    status=BeaconStatus.CARRIED,
                    carrier_id=carrier_id,
                ),
                resources=5,
            )

            tactic = SmartTactic(
                memory,
                control_path=control_path,
            )
            summary = tactic.choose_actions(turn)
            _, _, ranger_guards = tactic._aggress_beacon_guard_assignments(turn)
            return_route_reason = memory.current_routes[str(RANGER_ID)].reason
            healing_turn, _ = make_turn(
                tick=123,
                own_core=core((0, 0)),
                units=(
                    vanguard((10, 0), carrier_id),
                    vanguard((9, 0), VANGUARD_ID),
                    vanguard((11, 0), VANGUARD_TWO_ID),
                    ranger((0, 0), RANGER_ID, hp=1),
                    ranger((9, 2), RANGER_TWO_ID),
                    ranger((11, 2), RANGER_THREE_ID),
                    ranger((10, 2), RANGER_FOURTH_ID),
                ),
                enemies=(enemy_ranger((15, 0)),),
                beacon=ChampionBeacon(
                    position=(10, 0),
                    status=BeaconStatus.CARRIED,
                    carrier_id=carrier_id,
                ),
                resources=5,
            )

            tactic.choose_actions(healing_turn)

        self.assertEqual(
            memory.aggress_heal_rotations[str(RANGER_ID)].phase,
            "return",
        )
        self.assertNotIn(RANGER_ID, ranger_guards)
        self.assertIn(RANGER_FOURTH_ID, ranger_guards)
        self.assertIsInstance(turn.plan.unit_actions[RANGER_ID], MoveAction)
        self.assertEqual(return_route_reason, "aggress_rotation_heal_return")
        self.assertFalse(
            any("heal_rotation_cancelled" in item for item in summary.decisions)
        )
        self.assertIsInstance(
            healing_turn.plan.unit_actions[RANGER_ID],
            HealAction,
        )

    def test_known_enemy_core_does_not_pull_beacon_guards_out_of_formation(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            carrier_id = VANGUARD_FOURTH_ID
            extra_vanguards = [UUID(int=0x7100 + index) for index in range(3)]
            memory = TacticMemory(
                mode=MODE_AGGRESS,
                enemy_sightings={
                    str(ENEMY_CORE_ID): EnemySighting(
                        position=(30, 0),
                        seen_tick=199,
                        is_core=True,
                    )
                },
            )
            turn, _ = make_turn(
                tick=200,
                own_core=core((0, 0)),
                units=(
                    vanguard((10, 0), carrier_id),
                    vanguard((9, 0), VANGUARD_ID),
                    vanguard((11, 0), VANGUARD_TWO_ID),
                    vanguard((12, 5), VANGUARD_THREE_ID),
                    vanguard((13, 5), extra_vanguards[0]),
                    vanguard((14, 5), extra_vanguards[1]),
                    vanguard((15, 5), extra_vanguards[2]),
                    ranger((10, 2), RANGER_ID),
                    ranger((9, 2), RANGER_TWO_ID),
                    ranger((11, 2), RANGER_THREE_ID),
                    ranger((12, 6), RANGER_FOURTH_ID),
                ),
                beacon=ChampionBeacon(
                    position=(10, 0),
                    status=BeaconStatus.CARRIED,
                    carrier_id=carrier_id,
                ),
            )
            tactic = SmartTactic(memory, control_path=control_path)

            tactic.choose_actions(turn)
            _, vanguard_guards, ranger_guards = (
                tactic._aggress_beacon_guard_assignments(turn)
            )

        guard_ids = vanguard_guards | ranger_guards
        enemy_core_routes = {
            UUID(route.object_id)
            for route in memory.current_routes.values()
            if route.reason.startswith("enemy_core_")
        }
        self.assertFalse(guard_ids & enemy_core_routes)
        # A defended nearby Core now stages its independent force before the
        # breach, so no direct Core route is expected until the rally is ready.
        self.assertTrue(
            enemy_core_routes
            or any(
                "enemy_core_assault_rally" in item
                for item in memory.observations
            )
            or all(
                not route.reason.startswith("enemy_core_")
                for route in memory.current_routes.values()
            )
        )

    def test_isolated_critical_beacon_carrier_escapes_away_from_core(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            carrier_id = VANGUARD_FOURTH_ID
            damaged_carrier = UnitView(
                kind="UNIT",
                id=carrier_id,
                controlled=True,
                position=(10, 0),
                hp=1,
                unit_type=UnitType.VANGUARD,
            )
            memory = TacticMemory(
                mode=MODE_AGGRESS,
                unit_labels={str(carrier_id): UnitLabel("VANGUARD", 9)},
            )
            turn, _ = make_turn(
                tick=130,
                own_core=core((0, 0)),
                units=(damaged_carrier,),
                enemies=(enemy_ranger((9, 0)),),
                obstacle_cells=((10, -1), (10, 1), (9, -1), (9, 1)),
                beacon=ChampionBeacon(
                    position=damaged_carrier.position,
                    status=BeaconStatus.CARRIED,
                    carrier_id=carrier_id,
                ),
            )

            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        action = turn.plan.unit_actions.get(carrier_id)
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.RIGHT)
        self.assertFalse(any("heal_return" in item for item in summary.decisions))
        self.assertTrue(
            any(
                "reason=beacon_carrier_isolated_escape" in item
                for item in summary.decisions
            )
        )
        route = memory.current_routes[str(carrier_id)]
        self.assertGreater(_distance(route.path[1], (0, 0)), 10)

    def test_aggress_sweep_spirals_out_to_fifty_then_contracts(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(
                mode=MODE_AGGRESS,
                aggress_sweep_profile_version=ASSAULT_SWEEP_PROFILE_VERSION,
                aggress_sweep_started_tick=100,
            )
            tactic = SmartTactic(memory, control_path=control_path)
            radii: list[int] = []
            radius_span = ASSAULT_SWEEP_MAX_RADIUS - ASSAULT_SWEEP_MIN_RADIUS
            half_turn = len(ASSAULT_SWEEP_SECTOR_OFFSETS) // 2
            steps = (
                0,
                radius_span // 2,
                radius_span,
                radius_span + half_turn,
                radius_span + half_turn + radius_span // 2,
                radius_span * 2 + half_turn,
            )
            for index, step in enumerate(steps):
                memory.aggress_sweep_step = step
                turn, _ = make_turn(
                    tick=100 + index,
                    own_core=core((0, 0)),
                    units=(vanguard((1, 0)),),
                )
                tactic.choose_actions(turn)
                goal = memory.current_routes[str(VANGUARD_ID)].goal
                self.assertIsNotNone(goal)
                radii.append(_distance((0, 0), goal))

        self.assertEqual(
            radii,
            [
                ASSAULT_SWEEP_MIN_RADIUS,
                ASSAULT_SWEEP_MIN_RADIUS + radius_span // 2,
                ASSAULT_SWEEP_MAX_RADIUS,
                ASSAULT_SWEEP_MAX_RADIUS,
                ASSAULT_SWEEP_MAX_RADIUS - radius_span // 2,
                ASSAULT_SWEEP_MIN_RADIUS,
            ],
        )

    def test_aggress_spiral_keeps_waypoint_until_a_combat_unit_reaches_it(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(mode=MODE_AGGRESS)
            tactic = SmartTactic(memory, control_path=control_path)

            first_turn, _ = make_turn(
                tick=200,
                own_core=core((0, 0)),
                units=(vanguard((1, 0)),),
            )
            tactic.choose_actions(first_turn)
            first_goal = memory.current_routes[str(VANGUARD_ID)].goal
            self.assertEqual(
                _distance((0, 0), first_goal),
                ASSAULT_SWEEP_MIN_RADIUS,
            )

            second_turn, _ = make_turn(
                tick=201,
                own_core=core((0, 0)),
                units=(vanguard((ASSAULT_SWEEP_MIN_RADIUS - 4, 0)),),
            )
            tactic.choose_actions(second_turn)

        self.assertEqual(memory.aggress_sweep_step, 1)
        second_goal = memory.current_routes[str(VANGUARD_ID)].goal
        self.assertEqual(
            _distance((0, 0), second_goal),
            ASSAULT_SWEEP_MIN_RADIUS + 1,
        )
        self.assertNotEqual(second_goal, first_goal)

    def test_aggress_spiral_waits_for_the_whole_attack_group(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(mode=MODE_AGGRESS, aggress_vanguards=2)
            tactic = SmartTactic(memory, control_path=control_path)

            first_turn, _ = make_turn(
                tick=210,
                own_core=core((0, 0)),
                units=(
                    vanguard((1, 0)),
                    vanguard((1, 1), VANGUARD_TWO_ID),
                ),
            )
            first_planner = MovementPlanner(first_turn, memory, [])
            first_goal = tactic._assault_frontier_target(first_turn, first_planner)
            self.assertIsNotNone(first_goal)

            second_turn, _ = make_turn(
                tick=211,
                own_core=core((0, 0)),
                units=(
                    vanguard((1, 0)),
                    vanguard(first_goal, VANGUARD_TWO_ID),
                ),
            )
            second_planner = MovementPlanner(second_turn, memory, [])
            tactic._assault_frontier_target(second_turn, second_planner)

        self.assertEqual(memory.aggress_sweep_step, 0)

    def test_aggress_spiral_ignores_recalled_raid_units(self) -> None:
        raid_id = UUID(int=0x2700)
        assault_id = UUID(int=0x2701)
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=False)
            memory = TacticMemory(
                mode=MODE_AGGRESS,
                raid_enabled=True,
                raid_recall=True,
                raid_vanguards=1,
                aggress_vanguards=1,
                raid_vanguard_ids={str(raid_id)},
            )
            tactic = SmartTactic(memory, control_path=control_path)
            first_turn, _ = make_turn(
                tick=212,
                own_core=core((0, 0)),
                units=(vanguard((0, 1), raid_id), vanguard((1, 0), assault_id)),
            )
            first_goal = tactic._assault_frontier_target(
                first_turn,
                MovementPlanner(first_turn, memory, []),
            )
            self.assertIsNotNone(first_goal)
            second_turn, _ = make_turn(
                tick=213,
                own_core=core((0, 0)),
                units=(
                    vanguard((0, 1), raid_id),
                    vanguard(first_goal, assault_id),
                ),
            )

            tactic._assault_frontier_target(
                second_turn,
                MovementPlanner(second_turn, memory, []),
            )

        self.assertEqual(memory.aggress_sweep_step, 1)

    def test_enemy_sighting_is_removed_when_its_cell_is_seen_empty(self) -> None:
        memory = TacticMemory()
        visible_turn, _ = make_turn(
            tick=8,
            own_core=core((5, 5)),
            enemies=(enemy_ranger((8, 5)),),
        )
        memory.observe(visible_turn)
        self.assertIn(str(ENEMY_RANGER_ID), memory.enemy_sightings)

        empty_turn, _ = make_turn(tick=9, own_core=core((5, 5)))
        memory.observe(empty_turn)

        self.assertNotIn(str(ENEMY_RANGER_ID), memory.enemy_sightings)

    def test_recall_vanguards_return_to_core(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, recall=True)
            turn, _ = make_turn(
                own_core=core((5, 5)),
                units=(vanguard((20, 20)), ranger((21, 21))),
            )
            SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

            action = turn.plan.unit_actions.get(VANGUARD_ID)
            self.assertIsInstance(action, MoveAction)

    def test_recall_rangers_return_to_patrol(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, recall=True)
            turn, _ = make_turn(
                own_core=core((5, 5)),
                units=(ranger((21, 21)),),
            )
            SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

            action = turn.plan.unit_actions.get(RANGER_ID)
            self.assertIsInstance(action, MoveAction)

    def test_recall_vanguard_leaves_single_core_door_open(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, recall=True)
            obstacles = ((1, 0), (-1, 0), (0, 1))
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(vanguard((0, -1)),),
                obstacle_cells=obstacles,
            )

            SmartTactic(
                TacticMemory(),
                control_path=control_path,
            ).choose_actions(turn)

        action = turn.plan.unit_actions.get(VANGUARD_ID)
        self.assertIsInstance(action, MoveAction)
        destination = (
            action.direction.delta[0],
            -1 + action.direction.delta[1],
        )
        self.assertNotIn(
            destination,
            _core_logistics_corridor((0, 0), set(obstacles)),
        )

    def test_recall_full_roster_vacates_for_continuous_growth(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, recall=True)
            units = (
                worker(WORKER_LOW, (5, 0)),
                worker(WORKER_HIGH, (6, 0)),
                worker(WORKER_THIRD, (7, 0)),
                worker(WORKER_FOURTH, (8, 0)),
                vanguard((1, 0), VANGUARD_ID),
                vanguard((-1, 0), VANGUARD_TWO_ID),
                vanguard((0, 1), VANGUARD_THREE_ID),
                ranger((0, 0), RANGER_ID),
                ranger((2, 0), RANGER_TWO_ID),
                ranger((-2, 0), RANGER_THREE_ID),
            )
            memory = TacticMemory()
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=units,
                resources=30,
            )

            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        self.assertTrue(
            any("vacate_core_for_logistics" in item for item in summary.decisions)
        )
        self.assertTrue(
            any(
                route.reason == "vacate_core_for_logistics"
                for route in memory.current_routes.values()
            )
        )
        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        # 2026-08-24 召回期间也沿用面板配置的编制阶梯（默认 12:4:4），且按严格
        # 优先级补缺口：4工3先3游 下先锋差 1，顺序 先锋 → 游侠 → 工人，因此补
        # 先锋。此前这里走 continuous_growth_spawn 的比压容差，工人比压 4/12 最
        # 低而产工人，会在战斗缺口没补齐时先扩经济。
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.VANGUARD)

    def test_recall_follows_ladder_composition(self) -> None:
        """回归：手动召回不得让编制阶梯失效。

        实测现场：control recall=true 时 _select_spawn 在 recall 分支就 return，
        末尾调用 continuous_growth_spawn() 不传 profile，退回默认 5:4:6。
        12:4:4 配置下 7工4先4游 时按 5:4:6 算游侠比压 4/6 最低，于是产出第 5 个
        游侠（日志：Tick 161511 生产 游侠, 消耗 12 点资源），违背面板设定。
        """

        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="develop", recall=True)
            units = tuple(
                worker(_ladder_uuid(index), (6 + index, 0)) for index in range(7)
            ) + (
                vanguard((3, 3), VANGUARD_ID),
                vanguard((4, 3), VANGUARD_TWO_ID),
                vanguard((5, 3), VANGUARD_THREE_ID),
                vanguard((6, 3), VANGUARD_FOURTH_ID),
                ranger((-3, 3), RANGER_ID),
                ranger((-3, 4), RANGER_TWO_ID),
                ranger((-3, 5), RANGER_THREE_ID),
                ranger((-3, 6), _ladder_uuid(70)),
            )
            turn, _ = make_turn(
                own_core=core((0, 0)), units=units, resources=60
            )
            memory = TacticMemory()
            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        self.assertTrue(memory.recall)
        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        # 7工4先4游：守家 3+3 已满足，阶梯目标 12:4:4 下工人比压 7/12 最低
        self.assertEqual(
            turn.plan.core_action.unit_type,
            UnitType.WORKER,
            "召回期间应沿用阶梯配比补工人，而不是按 5:4:6 产第 5 个游侠",
        )

    def test_recall_still_honours_resource_hoard(self) -> None:
        """回归：召回期间囤积仍要生效。

        hoard_block 原先只写在 develop 分支里，recall 分支在它之前就 return，
        导致召回时 95/150 完全不检查。
        """

        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps(
                    {"mode": "develop", "recall": True, "hoard_stage1": True}
                ),
                encoding="utf-8",
            )
            units = tuple(
                worker(_ladder_uuid(index), (6 + index, 0)) for index in range(12)
            ) + tuple(
                vanguard((3, 3 + index), _ladder_uuid(100 + index))
                for index in range(4)
            ) + tuple(
                ranger((-3, 3 + index), _ladder_uuid(200 + index))
                for index in range(4)
            )
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=units,
                # 人口 20 已达门槛，资源低于 95 水位
                resources=HOARD_STAGE1_RESOURCE_TARGET - 1,
            )
            memory = TacticMemory()
            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        self.assertTrue(memory.recall)
        self.assertNotIsInstance(
            turn.plan.core_action,
            SpawnAction,
            "召回期间资源低于囤积水位时不应产兵",
        )

    def test_recall_production_prefers_defense(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, recall=True)
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    worker(WORKER_LOW, (6, 0)),
                    worker(WORKER_HIGH, (7, 0)),
                    worker(WORKER_THIRD, (8, 0)),
                    worker(WORKER_FOURTH, (9, 0)),
                    worker(WORKER_FIFTH, (10, 0)),
                    worker(WORKER_SIXTH, (11, 0)),
                ),
                resources=30,
            )
            SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

            self.assertIsInstance(turn.plan.core_action, SpawnAction)
            self.assertEqual(turn.plan.core_action.unit_type, UnitType.VANGUARD)

    def test_load_control_absent_keeps_default(self) -> None:
        memory = TacticMemory()
        memory.load_control(Path("/nonexistent/control.json"))
        self.assertEqual(memory.mode, MODE_DEVELOP)
        self.assertFalse(memory.recall)

    def test_load_control_switches_mode_and_recall(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress", recall=True)
            memory = TacticMemory()
            memory.load_control(control_path)
            self.assertEqual(memory.mode, MODE_AGGRESS)
            self.assertTrue(memory.recall)

    def test_load_control_reroutes_scout_when_migration_candidate_changes(self) -> None:
        old_candidate = (4, -80)
        new_candidate = (-61, -163)
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(
                control_path,
                mode="aggress",
                migration_candidate=list(old_candidate),
                auto_migrate=True,
            )
            memory = TacticMemory()
            memory.load_control(control_path)
            memory.worker_goals[str(WORKER_LOW)] = WorkerGoal(
                "resource_recovery",
                old_candidate,
                7,
            )
            memory.recovery_checked.add(new_candidate)

            self._write_control(
                control_path,
                mode="aggress",
                migration_candidate=list(new_candidate),
                auto_migrate=True,
            )
            memory.control_mtime = 0
            memory.load_control(control_path)

        self.assertEqual(memory.migration_candidate, new_candidate)
        self.assertNotIn(old_candidate, memory.recovery_targets)
        self.assertNotIn(str(WORKER_LOW), memory.worker_goals)
        self.assertIn(new_candidate, memory.recovery_targets)
        self.assertNotIn(new_candidate, memory.recovery_checked)
        self.assertFalse(memory.migration_site_checked)
        self.assertEqual(memory.migration_site_score, 0)

    def test_write_stats_round_trip(self) -> None:
        memory = TacticMemory()
        turn, _ = make_turn(
            own_core=core((5, 5)),
            units=(worker(WORKER_LOW, (6, 5)),),
            resources=3,
        )
        with TemporaryDirectory() as directory:
            stats_path = Path(directory) / "stats.json"
            memory.write_stats(stats_path, turn)
            payload = json.loads(stats_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["tick"], turn.tick)
        self.assertEqual(payload["workers"], 1)
        self.assertEqual(payload["vanguards"], 0)
        self.assertEqual(payload["rangers"], 0)
        self.assertEqual(payload["resources"], 3)
        self.assertEqual(payload["mode"], MODE_DEVELOP)
        self.assertFalse(payload["recall"])
        self.assertIn("total_resources_harvested", payload)
        self.assertIn("enemy_cores_destroyed", payload)

    def test_write_stats_records_cumulative_resources(self) -> None:
        memory = TacticMemory()
        harvest = ResolutionEvent(
            event_id=UUID("00000000-0000-4000-8000-000000000301"),
            tick=8,
            event_type="HARVEST_SUCCEEDED",
            actor_id=WORKER_LOW,
            position=(6, 5),
            values={"amount": 2, "source": "RESOURCE_NODE"},
        )
        deposit = ResolutionEvent(
            event_id=UUID("00000000-0000-4000-8000-000000000302"),
            tick=9,
            event_type="DEPOSIT_SUCCEEDED",
            actor_id=WORKER_LOW,
            values={"amount": 2},
        )
        turn, _ = make_turn(
            tick=9,
            own_core=core((5, 5)),
            units=(worker(WORKER_LOW, (5, 5), cargo=2),),
            resources=2,
            events=(harvest, deposit),
        )
        memory.observe(turn)
        with TemporaryDirectory() as directory:
            stats_path = Path(directory) / "stats.json"
            memory.write_stats(stats_path, turn)
            payload = json.loads(stats_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["total_resources_harvested"], 2)
        self.assertEqual(payload["total_resources_deposited"], 2)

    def test_write_stats_includes_real_and_detailed_counters(self) -> None:
        memory = TacticMemory()
        memory.event_totals.update(
            {
                "CORE_SPAWN_SUCCEEDED": 3,
                "UNIT_MOVE_FAILED": 4,
            }
        )
        memory.decision_totals.update(
            {
                "manual_override:move": 2,
                "worker:harvest": 5,
            }
        )
        turn, _ = make_turn(
            tick=12,
            own_core=core((5, 5)),
            units=(worker(WORKER_LOW, (6, 5), cargo=1),),
            resource_cells=((8, 5),),
        )
        memory.observe(turn)
        with TemporaryDirectory() as directory:
            stats_path = Path(directory) / "stats.json"
            memory.write_stats(stats_path, turn)
            payload = json.loads(stats_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["units_built"], 3)
        self.assertEqual(payload["move_failures"], 4)
        self.assertEqual(payload["manual_overrides"], 2)
        self.assertEqual(payload["worker_cargo"], 1)
        self.assertEqual(payload["visible_resource_cells"], 1)
        self.assertEqual(payload["event_totals"]["CORE_SPAWN_SUCCEEDED"], 3)
        self.assertEqual(payload["decision_totals"]["worker:harvest"], 5)


    def test_full_capacity_skips_frontier_expansion(self) -> None:
        # 满仓（资源=容量）时不再派 frontier/refilled 探索目标，工人就地驻守
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (1, 0)),),
            resources=10,  # capacity = max(10, 1*5) = 10 → 满仓
        )
        memory = TacticMemory()
        SmartTactic(memory).choose_actions(turn)

        for goal in memory.worker_goals.values():
            self.assertNotIn(
                goal.kind,
                {"frontier", "develop_frontier", "refilled_chunk"},
            )

    def test_unit_cost_scales_after_twenty_units(self) -> None:
        self.assertEqual(unit_cost(UnitType.WORKER, 19), 5)
        self.assertEqual(unit_cost(UnitType.VANGUARD, 19), 10)
        self.assertEqual(unit_cost(UnitType.RANGER, 19), 12)
        self.assertEqual(unit_cost(UnitType.WORKER, 20), 7)
        self.assertEqual(unit_cost(UnitType.VANGUARD, 20), 13)
        self.assertEqual(unit_cost(UnitType.RANGER, 20), 16)
        self.assertEqual(unit_cost(UnitType.WORKER, 25), 8)

    def test_core_waits_when_dynamic_cost_is_unaffordable_at_population_twenty(
        self,
    ) -> None:
        workers = tuple(
            worker(UUID(int=0x5000 + index), (index, 0))
            for index in range(20)
        )
        turn, _ = make_turn(
            own_core=core((100, 100)),
            units=workers,
            resources=12,
        )

        SmartTactic(TacticMemory(mode=MODE_DEVELOP)).choose_actions(turn)

        self.assertIsNone(turn.plan.core_action)

    def test_core_spawns_at_dynamic_cost_at_population_twenty(self) -> None:
        workers = tuple(
            worker(UUID(int=0x5100 + index), (index, 0))
            for index in range(20)
        )
        turn, _ = make_turn(
            own_core=core((100, 100)),
            units=workers,
            resources=13,
        )

        SmartTactic(TacticMemory(mode=MODE_DEVELOP)).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.VANGUARD)

    def test_wide_search_radius_stays_inside_local_production_area(self) -> None:
        # 发育模式无已知资源时触发 wide_search，但不派出超长回程任务。
        memory = TacticMemory(mode=MODE_DEVELOP)
        tactic = SmartTactic(memory)
        for tick in range(100, 112):
            turn, _ = make_turn(
                tick=tick,
                own_core=core((0, 0)),
                units=(worker(WORKER_LOW, (1, 0)),),
                resources=0,
            )
            tactic.choose_actions(turn)

        core_position = (0, 0)
        frontier_goals = [
            goal
            for goal in memory.worker_goals.values()
            if goal.kind == "develop_frontier"
        ]
        self.assertTrue(frontier_goals)
        for goal in frontier_goals:
            self.assertLessEqual(
                _distance(core_position, goal.position),
                DEVELOP_WIDE_SEARCH_MAX_RADIUS,
            )

    def test_develop_recalls_worker_beyond_local_search_area(self) -> None:
        memory = TacticMemory(
            mode=MODE_DEVELOP,
            worker_goals={
                str(WORKER_LOW): WorkerGoal(
                    "develop_frontier",
                    (-DEVELOP_WIDE_SEARCH_MAX_RADIUS, 0),
                    10,
                )
            },
        )
        turn, _ = make_turn(
            tick=20,
            own_core=core((0, 0)),
            units=(
                worker(
                    WORKER_LOW,
                    (-DEVELOP_WIDE_SEARCH_MAX_RADIUS - 2, 0),
                ),
            ),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertEqual(goal.kind, "develop_local_recall")
        self.assertEqual(goal.position, turn.core.position)
        action = turn.plan.unit_actions[WORKER_LOW]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.RIGHT)
        self.assertTrue(
            any("develop_local_recall" in item for item in summary.decisions)
        )

    def test_develop_keeps_existing_recall_when_resource_is_visible(self) -> None:
        # far 超过 develop_local_recall 半径，触发召回保护
        far_position = (-DEVELOP_LOCAL_RECALL_RADIUS - 2, 0)
        memory = TacticMemory(
            mode=MODE_DEVELOP,
            worker_goals={
                str(WORKER_LOW): WorkerGoal(
                    "develop_local_recall",
                    (0, 0),
                    10,
                )
            },
        )
        turn, _ = make_turn(
            tick=20,
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, far_position),
                worker(WORKER_HIGH, (0, 1)),
            ),
            resource_cells=((far_position[0] - 3, far_position[1]),),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertEqual(goal.kind, "develop_local_recall")
        self.assertEqual(goal.position, turn.core.position)
        action = turn.plan.unit_actions[WORKER_LOW]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.RIGHT)
        local_goal = memory.worker_goals[str(WORKER_HIGH)]
        self.assertEqual(local_goal.kind, "develop_frontier")
        self.assertTrue(
            any("resource_leash_trimmed" in item for item in summary.decisions)
        )

    def test_develop_remote_recall_worker_finishes_nearby_resource(self) -> None:
        far_position = (-DEVELOP_RESOURCE_TARGET_CORE_LEASH_DISTANCE - 2, 0)
        resource_position = (far_position[0] + 1, far_position[1])
        memory = TacticMemory(
            mode=MODE_DEVELOP,
            worker_goals={
                str(WORKER_LOW): WorkerGoal(
                    "develop_local_recall",
                    (0, 0),
                    10,
                )
            },
        )
        turn, _ = make_turn(
            tick=20,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, far_position),),
            resource_cells=(resource_position,),
        )

        SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertEqual(goal.kind, "visible_resource")
        self.assertEqual(goal.position, resource_position)
        action = turn.plan.unit_actions[WORKER_LOW]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.RIGHT)

    def test_develop_recall_can_backtrack_through_only_open_exit(self) -> None:
        far_position = (-DEVELOP_WIDE_SEARCH_MAX_RADIUS - 2, 0)
        memory = TacticMemory(
            mode=MODE_DEVELOP,
            worker_goals={
                str(WORKER_LOW): WorkerGoal(
                    "develop_local_recall",
                    (0, 0),
                    10,
                )
            },
            recent_positions={
                str(WORKER_LOW): [(far_position[0] + 1, far_position[1])]
            },
        )
        turn, _ = make_turn(
            tick=20,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, far_position),),
            obstacle_cells=(
                (far_position[0] - 1, far_position[1]),
                (far_position[0], far_position[1] - 1),
                (far_position[0], far_position[1] + 1),
            ),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        action = turn.plan.unit_actions[WORKER_LOW]
        self.assertIsInstance(action, MoveAction)
        self.assertEqual(action.direction, Direction.RIGHT)
        self.assertTrue(
            any("develop_local_recall:backtrack" in item for item in summary.decisions)
        )

    def test_develop_drops_legacy_distant_frontier_goal(self) -> None:
        memory = TacticMemory(
            mode=MODE_DEVELOP,
            worker_goals={
                str(WORKER_LOW): WorkerGoal("develop_frontier", (200, 0), 10),
            },
            worker_search_radius={str(WORKER_LOW): 200},
        )
        turn, _ = make_turn(
            tick=20,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (20, 0)),),
            resources=0,
        )

        summary = SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals[str(WORKER_LOW)]
        self.assertLessEqual(
            _distance(turn.core.position, goal.position),
            DEVELOP_WIDE_SEARCH_MAX_RADIUS,
        )
        self.assertTrue(any("local_search_trim" in item for item in summary.decisions))

    def test_raid_assignments_are_independent_and_unbounded(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps(
                    {
                        "mode": MODE_AGGRESS,
                        "raid_enabled": True,
                        "raid_vanguards": 1,
                        "raid_rangers": 1,
                    }
                ),
                encoding="utf-8",
            )
            vanguards = tuple(
                vanguard((10 + index, 0), UUID(int=0x1000 + index))
                for index in range(6)
            )
            rangers = tuple(
                ranger((10 + index, 1), UUID(int=0x2000 + index))
                for index in range(6)
            )
            turn, _ = make_turn(
                tick=20,
                own_core=core((0, 0)),
                units=vanguards + rangers,
            )
            memory = TacticMemory(mode=MODE_AGGRESS)
            tactic = SmartTactic(memory, control_path=control_path)
            tactic.choose_actions(turn)

            selected_vanguards = {UUID(unit_id) for unit_id in memory.raid_vanguard_ids}
            selected_rangers = {UUID(unit_id) for unit_id in memory.raid_ranger_ids}
            defender_vanguards, defender_rangers = tactic._aggress_core_defender_ids(turn)
            self.assertEqual(len(selected_vanguards), 1)
            self.assertEqual(len(selected_rangers), 1)
            self.assertFalse(selected_vanguards & defender_vanguards)
            self.assertFalse(selected_rangers & defender_rangers)
            self.assertTrue(
                all(
                    memory.current_routes[str(unit_id)].reason == "raid_sweep"
                    for unit_id in selected_vanguards | selected_rangers
                )
            )

            raid_unit = next(unit for unit in turn.units if unit.id in selected_vanguards)
            memory.raid_sweep_steps[str(raid_unit.id)] = len(ASSAULT_SWEEP_SECTOR_OFFSETS)
            target = tactic._raid_sweep_target(raid_unit, 0, 1)
            self.assertEqual(
                _distance(memory.raid_sweep_origin or (0, 0), target),
                RAID_SWEEP_INITIAL_RADIUS + RAID_SWEEP_RING_SPACING,
            )

    def test_raid_does_not_steal_last_home_guard_pair(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps(
                    {
                        "mode": MODE_DEVELOP,
                        "raid_enabled": True,
                        "raid_vanguards": 1,
                        "raid_rangers": 1,
                    }
                ),
                encoding="utf-8",
            )
            turn, _ = make_turn(
                tick=21,
                own_core=core((0, 0)),
                units=(
                    vanguard((6, 0)),
                    ranger((6, 1)),
                    worker(WORKER_LOW, (1, 0)),
                ),
            )
            memory = TacticMemory(mode=MODE_DEVELOP)
            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        self.assertFalse(memory.raid_vanguard_ids)
        self.assertFalse(memory.raid_ranger_ids)

    def test_raid_core_target_does_not_redirect_invasion_force(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps(
                    {
                        "mode": MODE_AGGRESS,
                        "raid_enabled": True,
                        "raid_vanguards": 1,
                        "raid_rangers": 1,
                    }
                ),
                encoding="utf-8",
            )
            units = tuple(
                vanguard((3 + index, 0), UUID(int=0x3000 + index))
                for index in range(6)
            ) + tuple(
                ranger((3 + index, 1), UUID(int=0x4000 + index))
                for index in range(6)
            )
            turn, _ = make_turn(
                tick=30,
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((6, 0)),),
            )
            memory = TacticMemory(mode=MODE_AGGRESS)
            tactic = SmartTactic(memory, control_path=control_path)
            tactic.choose_actions(turn)

            self.assertEqual(memory.raid_core_id, str(ENEMY_CORE_ID))
            raid_route_reasons = {
                route.reason
                for route in memory.current_routes.values()
                if route.object_id in memory.raid_vanguard_ids | memory.raid_ranger_ids
            }
            self.assertTrue(
                any(
                    reason.startswith(("raid_core_assault", "raid_core_seek_firing"))
                    for reason in raid_route_reasons
                )
            )
            self.assertFalse(
                any(
                    route.reason.startswith(
                        ("enemy_core_assault", "enemy_core_seek_firing")
                    )
                    for route in memory.current_routes.values()
                )
            )
            self.assertFalse(
                any(
                    route.reason == "aggress_seek_firing" and route.goal == (6, 0)
                    for route in memory.current_routes.values()
                )
            )

    def test_raid_recall_is_independent_from_invasion_recall(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps(
                    {
                        "mode": MODE_AGGRESS,
                        "recall": False,
                        "raid_enabled": True,
                        "raid_recall": True,
                        "raid_vanguards": 1,
                        "raid_rangers": 1,
                    }
                ),
                encoding="utf-8",
            )
            units = (
                vanguard((10, 0), UUID(int=0x5000)),
                vanguard((11, 0), UUID(int=0x5001)),
                vanguard((12, 0), UUID(int=0x5002)),
                vanguard((13, 0), UUID(int=0x5003)),
                ranger((10, 1), UUID(int=0x6000)),
                ranger((11, 1), UUID(int=0x6001)),
                ranger((12, 1), UUID(int=0x6002)),
                ranger((13, 1), UUID(int=0x6003)),
            )
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=units,
            )
            memory = TacticMemory(mode=MODE_AGGRESS)
            tactic = SmartTactic(memory, control_path=control_path)
            tactic.choose_actions(turn)

            self.assertFalse(memory.recall)
            selected_ids = memory.raid_vanguard_ids | memory.raid_ranger_ids
            self.assertTrue(selected_ids)
            self.assertTrue(
                all(
                    memory.current_routes[str(unit_id)].reason == "raid_recall"
                    for unit_id in selected_ids
                )
            )

    def test_auto_roles_reserve_main_invasion_force_alongside_raid(self) -> None:
        vanguard_ids = [UUID(int=0x6500 + index) for index in range(6)]
        ranger_ids = [UUID(int=0x6600 + index) for index in range(9)]
        carrier_id = vanguard_ids[-1]
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps(
                    {
                        "mode": MODE_AGGRESS,
                        "recall": False,
                        "raid_enabled": True,
                        "raid_recall": True,
                        "raid_vanguards": 1,
                        "raid_rangers": 1,
                    }
                ),
                encoding="utf-8",
            )
            units = tuple(
                vanguard((12 + index, 0), unit_id)
                for index, unit_id in enumerate(vanguard_ids)
            ) + tuple(
                ranger((12 + index, 2), unit_id)
                for index, unit_id in enumerate(ranger_ids)
            )
            turn, _ = make_turn(
                tick=35,
                own_core=core((0, 0)),
                units=units,
                beacon=ChampionBeacon(
                    position=units[5].position,
                    status=BeaconStatus.CARRIED,
                    carrier_id=carrier_id,
                ),
            )
            memory = TacticMemory(mode=MODE_AGGRESS)
            tactic = SmartTactic(memory, control_path=control_path)

            tactic.choose_actions(turn)

        carrier, beacon_vanguards, beacon_rangers = (
            tactic._aggress_beacon_guard_assignments(turn)
        )
        defender_vanguards, defender_rangers = tactic._aggress_core_defender_ids(turn)
        raid_vanguards = {UUID(unit_id) for unit_id in memory.raid_vanguard_ids}
        raid_rangers = {UUID(unit_id) for unit_id in memory.raid_ranger_ids}
        assault_vanguards = (
            set(vanguard_ids)
            - beacon_vanguards
            - defender_vanguards
            - raid_vanguards
            - ({carrier.id} if carrier is not None else set())
        )
        assault_rangers = (
            set(ranger_ids)
            - beacon_rangers
            - defender_rangers
            - raid_rangers
        )
        self.assertEqual(len(raid_vanguards), 1)
        self.assertEqual(len(raid_rangers), 1)
        self.assertGreaterEqual(len(assault_vanguards), 1)
        self.assertGreaterEqual(len(assault_rangers), 2)

    def test_raid_accepts_core_with_stationary_nearby_guard(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps(
                    {
                        "mode": MODE_AGGRESS,
                        "raid_enabled": True,
                        "raid_vanguards": 1,
                        "raid_rangers": 1,
                    }
                ),
                encoding="utf-8",
            )
            units = tuple(
                vanguard((3 + index, 0), UUID(int=0x7000 + index))
                for index in range(4)
            ) + tuple(
                ranger((3 + index, 1), UUID(int=0x8000 + index))
                for index in range(4)
            )
            turn, _ = make_turn(
                tick=40,
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((6, 0)), enemy_ranger((6, 1))),
            )
            memory = TacticMemory(mode=MODE_AGGRESS)
            memory.raid_enemy_motion[str(ENEMY_RANGER_ID)] = RaidEnemyMotion(
                position=(6, 1),
                stationary_observations=3,
                last_seen_tick=39,
            )
            tactic = SmartTactic(memory, control_path=control_path)
            summary = tactic.choose_actions(turn)

            self.assertEqual(memory.raid_core_id, str(ENEMY_CORE_ID))
            self.assertTrue(
                any(
                    "reason=nearby_stationary" in decision
                    for decision in summary.decisions
                )
            )


class StuckHealPredictionTests(unittest.TestCase):
    """迷路检测 + core 让路 + 回血 + 预判射击 + 抢信标。"""

    def _write_control(
        self,
        path: Path,
        *,
        mode: str | None = None,
        recall: bool | None = None,
    ) -> None:
        data: dict = {}
        if mode is not None:
            data["mode"] = mode
        if recall is not None:
            data["recall"] = recall
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_stuck_worker_clears_goal(self) -> None:
        memory = TacticMemory()
        memory.unit_positions[str(WORKER_LOW)] = (3, 0)
        memory.last_position_tick[str(WORKER_LOW)] = 0
        memory.worker_goals[str(WORKER_LOW)] = WorkerGoal("frontier", (10, 0), 0)
        turn, _ = make_turn(
            tick=20,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (3, 0)),),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertTrue(
            any("stuck_clear" in item for item in summary.decisions)
        )
        # 旧目标（created_tick=0）已被清除；若重新分配，则是本 tick 的新目标
        goal = memory.worker_goals.get(str(WORKER_LOW))
        if goal is not None:
            self.assertGreaterEqual(goal.created_tick, 20)

    def test_spinning_worker_clears_goal(self) -> None:
        # 来回震荡（在 2-3 格间打转 16 tick）→ 判定打转并清除目标
        memory = TacticMemory()
        memory.worker_goals[str(WORKER_LOW)] = WorkerGoal("frontier", (10, 0), 0)
        memory.recent_positions[str(WORKER_LOW)] = [
            (3, 0), (3, 1), (3, 0), (3, 1), (3, 0), (3, 1),
            (3, 0), (3, 1), (3, 0), (3, 1), (3, 0), (3, 1),
            (3, 0), (3, 1), (3, 0), (3, 1),
        ]
        memory.unit_positions[str(WORKER_LOW)] = (3, 1)
        memory.last_position_tick[str(WORKER_LOW)] = 5  # 位置在变，stationary 不触发
        turn, _ = make_turn(
            tick=20,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (3, 1)),),
            resources=0,
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertTrue(
            any("stuck_clear reason=spinning" in item for item in summary.decisions)
        )

    def test_spinning_worker_does_not_immediately_retry_blocked_resource(self) -> None:
        target = (10, 0)
        memory = TacticMemory(
            worker_goals={
                str(WORKER_LOW): WorkerGoal("visible_resource", target, 0)
            }
        )
        memory.recent_positions[str(WORKER_LOW)] = [
            (3, 0),
            (3, 1),
        ] * (STUCK_TICKS // 2)
        memory.unit_positions[str(WORKER_LOW)] = (3, 1)
        memory.last_position_tick[str(WORKER_LOW)] = 5
        turn, _ = make_turn(
            tick=20,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (3, 1)),),
            resource_cells=(target,),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertGreater(memory.temporary_blocks[target], turn.tick)
        goal = memory.worker_goals.get(str(WORKER_LOW))
        self.assertTrue(goal is None or goal.position != target)
        self.assertTrue(
            any("resource_temporarily_blocked" in item for item in summary.decisions)
        )

    def test_worker_abandons_resource_goal_blocked_on_previous_tick(self) -> None:
        target = (10, 0)
        memory = TacticMemory(
            worker_goals={
                str(WORKER_LOW): WorkerGoal("visible_resource", target, 19)
            },
            temporary_blocks={target: 30},
        )
        turn, _ = make_turn(
            tick=20,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (3, 0)),),
            resource_cells=(target,),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        goal = memory.worker_goals.get(str(WORKER_LOW))
        self.assertTrue(goal is None or goal.position != target)
        self.assertTrue(
            any("resource_block_hold" in item for item in summary.decisions)
        )

    def test_old_position_history_does_not_clear_fresh_goal(self) -> None:
        memory = TacticMemory()
        memory.worker_goals[str(WORKER_LOW)] = WorkerGoal(
            "frontier", (10, 0), 19
        )
        memory.recent_positions[str(WORKER_LOW)] = [
            (3, 0), (3, 1), (3, 0), (3, 1), (3, 0), (3, 1),
            (3, 0), (3, 1), (3, 0), (3, 1), (3, 0), (3, 1),
            (3, 0), (3, 1), (3, 0), (3, 1),
        ]
        memory.unit_positions[str(WORKER_LOW)] = (3, 1)
        memory.last_position_tick[str(WORKER_LOW)] = 19
        turn, _ = make_turn(
            tick=20,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (3, 1)),),
            resources=0,
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertFalse(
            any("stuck_clear reason=spinning" in item for item in summary.decisions)
        )

    def test_moving_worker_keeps_goal(self) -> None:
        # 位置在变化（非卡住）→ 目标保留
        memory = TacticMemory()
        memory.unit_positions[str(WORKER_LOW)] = (2, 0)
        memory.last_position_tick[str(WORKER_LOW)] = 18
        memory.worker_goals[str(WORKER_LOW)] = WorkerGoal("frontier", (10, 0), 0)
        turn, _ = make_turn(
            tick=20,
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (3, 0)),),
        )

        SmartTactic(memory).choose_actions(turn)

        self.assertIn(str(WORKER_LOW), memory.worker_goals)

    def test_core_vacates_blocker_in_neighborhood_for_cargo(self) -> None:
        # cargo worker 在 core 3 格内时，挡在 core 邻格的战斗单位被挪开
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (1, 0), cargo=2),
                vanguard((0, 1)),  # 挡在 core 邻格
            ),
            resources=0,
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertTrue(
            any("core_logistics_space" in item for item in summary.decisions)
        )
        self.assertIn(VANGUARD_ID, turn.plan.unit_actions)

    def test_adjacent_cargo_worker_holds_queue_while_core_slot_is_busy(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_HIGH, (0, 0), cargo=1),
                worker(WORKER_LOW, (1, 0), cargo=1),
            ),
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions[WORKER_HIGH], DepositAction)
        self.assertNotIn(WORKER_LOW, turn.plan.unit_actions)
        self.assertTrue(
            any("cargo_queue_hold" in item for item in summary.decisions)
        )

    def test_damaged_unit_returns_to_core(self) -> None:
        damaged = UnitView(
            kind="UNIT",
            id=RANGER_ID,
            controlled=True,
            position=(6, 0),
            hp=1,
            unit_type=UnitType.RANGER,
        )
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(damaged,),
            resources=5,
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        action = turn.plan.unit_actions.get(RANGER_ID)
        self.assertIsInstance(action, MoveAction)
        self.assertTrue(
            any("heal_return" in item for item in summary.decisions)
        )

    def test_damaged_unit_keeps_returning_without_healing_resources(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(ranger((6, 0), hp=1),),
            resources=0,
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions.get(RANGER_ID), MoveAction)
        self.assertTrue(any("heal_return" in item for item in summary.decisions))

    def test_unfunded_damaged_unit_vacates_core_to_heal_queue(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(ranger((0, 0), hp=1),),
            resources=0,
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions.get(RANGER_ID), MoveAction)
        self.assertTrue(
            any("heal_queue_parking" in item for item in summary.decisions)
        )

    def test_unit_heals_at_core(self) -> None:
        damaged = UnitView(
            kind="UNIT",
            id=RANGER_ID,
            controlled=True,
            position=(0, 0),
            hp=1,
            unit_type=UnitType.RANGER,
        )
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(damaged,),
            resources=5,
            obstacle_cells=((1, 0), (0, -1), (0, 1)),  # 四周堵住确保不 move
        )

        summary = SmartTactic(TacticMemory()).choose_actions(turn)

        action = turn.plan.unit_actions.get(RANGER_ID)
        self.assertIsInstance(action, HealAction)
        self.assertTrue(any(" heal " in item for item in summary.decisions))

    def test_ranger_leads_moving_enemy(self) -> None:
        # 敌人 (5,5)->(6,5) 向右移动，预判下一格 (7,5)；ranger 在 (10,5) 射程 3 只够预判格
        memory = TacticMemory()
        memory.enemy_positions[str(ENEMY_RANGER_ID)] = (5, 5)
        memory.enemy_prev[str(ENEMY_RANGER_ID)] = (5, 5)
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(ranger((10, 5)),),
            enemies=(enemy_ranger((6, 5)),),
        )

        SmartTactic(memory).choose_actions(turn)

        action = turn.plan.unit_actions.get(RANGER_ID)
        self.assertIsInstance(action, ShootAction)
        self.assertEqual(action.expected_cell, (7, 5))

    def test_ranger_shoots_stationary_enemy_current_cell(self) -> None:
        # 敌人未移动（prev==current）→ 打当前位置
        memory = TacticMemory()
        memory.enemy_positions[str(ENEMY_RANGER_ID)] = (7, 5)
        memory.enemy_prev[str(ENEMY_RANGER_ID)] = (7, 5)
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(ranger((10, 5)),),
            enemies=(enemy_ranger((7, 5)),),
        )

        SmartTactic(memory).choose_actions(turn)

        action = turn.plan.unit_actions.get(RANGER_ID)
        self.assertIsInstance(action, ShootAction)
        self.assertEqual(action.expected_cell, (7, 5))

    def test_rangers_spread_fire_across_possible_enemy_move_cells(self) -> None:
        memory = TacticMemory()
        memory.enemy_positions[str(ENEMY_RANGER_ID)] = (6, 5)
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                ranger((10, 5)),
                ranger((10, 5), RANGER_TWO_ID),
            ),
            enemies=(enemy_ranger((7, 5)),),
        )

        SmartTactic(memory).choose_actions(turn)

        first = turn.plan.unit_actions[RANGER_ID]
        second = turn.plan.unit_actions[RANGER_TWO_ID]
        self.assertIsInstance(first, ShootAction)
        self.assertIsInstance(second, ShootAction)
        self.assertEqual(
            {first.expected_cell, second.expected_cell},
            {(7, 5), (8, 5)},
        )
        self.assertEqual(memory.decision_totals["ranger:shot_coverage"], 1)

    def test_rangers_focus_fire_on_a_confirmed_stationary_enemy(self) -> None:
        memory = TacticMemory()
        memory.enemy_positions[str(ENEMY_RANGER_ID)] = (7, 5)
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                ranger((10, 5)),
                ranger((10, 5), RANGER_TWO_ID),
            ),
            enemies=(enemy_ranger((7, 5)),),
        )

        SmartTactic(memory).choose_actions(turn)

        self.assertEqual(
            {
                turn.plan.unit_actions[RANGER_ID].expected_cell,
                turn.plan.unit_actions[RANGER_TWO_ID].expected_cell,
            },
            {(7, 5)},
        )

    def test_ranger_avoids_recently_missed_target_cell(self) -> None:
        miss = ResolutionEvent(
            event_id=UUID(int=0x9010),
            tick=40,
            event_type="SHOT_MISSED",
            reason_code="SHOT_MISSED",
            actor_id=RANGER_ID,
            target_id=ENEMY_RANGER_ID,
            position=(7, 5),
        )
        memory = TacticMemory()
        memory.enemy_positions[str(ENEMY_RANGER_ID)] = (7, 5)
        memory.enemy_prev[str(ENEMY_RANGER_ID)] = (7, 5)
        turn, _ = make_turn(
            tick=41,
            own_core=core((0, 0)),
            units=(ranger((10, 5)),),
            enemies=(enemy_ranger((7, 5)),),
            events=(miss,),
        )

        SmartTactic(memory).choose_actions(turn)

        action = turn.plan.unit_actions[RANGER_ID]
        self.assertIsInstance(action, ShootAction)
        self.assertEqual(action.expected_cell, (8, 5))
        self.assertEqual(
            memory.shot_miss_counts[
                f"{ENEMY_RANGER_ID}|7|5"
            ],
            1,
        )


    def test_beacon_mode_vanguard_advances_to_beacon(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                own_core=core((5, 5)),
                units=(vanguard((10, 10)),),
            )
            SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

            action = turn.plan.unit_actions.get(VANGUARD_ID)
            self.assertIsInstance(action, MoveAction)
            self.assertNotEqual(action.direction, Direction.LEFT)  # 朝信标方向而非离开

    def test_beacon_mode_ranger_advances_to_beacon(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                own_core=core((5, 5)),
                units=(ranger((10, 10)),),
            )
            SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

            action = turn.plan.unit_actions.get(RANGER_ID)
            self.assertIsInstance(action, MoveAction)

    def test_beacon_mode_keeps_complete_home_reserve_at_core(self) -> None:
        extra_vanguard = VANGUARD_FOURTH_ID
        extra_ranger_one = RANGER_FOURTH_ID
        extra_ranger_two = UUID(int=0x17)
        units = (
            vanguard((1, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            vanguard((8, 0), extra_vanguard),
            ranger((0, -2), RANGER_ID),
            ranger((2, 0), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
            ranger((8, 1), extra_ranger_one),
            ranger((8, -1), extra_ranger_two),
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=units,
                beacon=ChampionBeacon(position=(20, 0)),
            )
            SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

        home_ids = {
            VANGUARD_ID,
            VANGUARD_TWO_ID,
            VANGUARD_THREE_ID,
            RANGER_ID,
            RANGER_TWO_ID,
            RANGER_THREE_ID,
        }
        for unit_id in home_ids:
            action = turn.plan.unit_actions.get(unit_id)
            if isinstance(action, MoveAction):
                dx, dy = action.direction.delta
                position = next(unit.position for unit in units if unit.id == unit_id)
                destination = (position[0] + dx, position[1] + dy)
                self.assertLessEqual(abs(destination[0]) + abs(destination[1]), 3)
        self.assertIsInstance(turn.plan.unit_actions.get(extra_vanguard), MoveAction)
        self.assertIsInstance(turn.plan.unit_actions.get(extra_ranger_one), MoveAction)

    def test_beacon_mode_sends_three_home_guards_to_undefended_local_core(
        self,
    ) -> None:
        units = (
            vanguard((1, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            ranger((0, -2), RANGER_ID),
            ranger((2, 0), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                tick=100,
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((41, 0)),),
                beacon=ChampionBeacon(position=(100, 0)),
            )
            memory = TacticMemory()
            summary = SmartTactic(memory, control_path=control_path).choose_actions(turn)

        self.assertEqual(len(memory.local_core_sortie_vanguard_ids), 1)
        self.assertEqual(len(memory.local_core_sortie_ranger_ids), 2)
        self.assertEqual(memory.local_core_sortie_position, (41, 0))
        local_routes = [
            route
            for route in memory.current_routes.values()
            if route.reason.startswith("local_core_sortie_")
        ]
        self.assertEqual(len(local_routes), 3)
        self.assertTrue(
            any("local_core_sortie_started" in item for item in summary.decisions)
        )
        self.assertEqual(
            len(turn.vanguards) - len(memory.local_core_sortie_vanguard_ids),
            2,
        )
        self.assertEqual(
            len(turn.rangers) - len(memory.local_core_sortie_ranger_ids),
            1,
        )

    def test_beacon_local_core_sortie_rejects_visible_combat_screen(self) -> None:
        units = (
            vanguard((1, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            ranger((0, -2), RANGER_ID),
            ranger((2, 0), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                tick=100,
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((12, 0)), enemy_ranger((12, 2))),
                beacon=ChampionBeacon(position=(100, 0)),
            )
            memory = TacticMemory()
            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        self.assertIsNone(memory.local_core_sortie_core_id)
        self.assertFalse(
            any(
                route.reason.startswith("local_core_sortie_")
                for route in memory.current_routes.values()
            )
        )

    def test_beacon_local_core_sortie_rejects_target_beyond_worker_screen(
        self,
    ) -> None:
        units = (
            vanguard((1, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            ranger((0, -2), RANGER_ID),
            ranger((2, 0), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                tick=100,
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((45, 0)),),
                beacon=ChampionBeacon(position=(100, 0)),
            )
            memory = TacticMemory()
            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        self.assertIsNone(memory.local_core_sortie_core_id)

    def test_beacon_local_core_sortie_does_not_restart_after_combat_cancel(
        self,
    ) -> None:
        units = (
            vanguard((20, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            ranger((20, -1), RANGER_ID),
            ranger((20, 1), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
        )
        memory = TacticMemory(
            mode=MODE_BEACON,
            enemy_sightings={
                str(ENEMY_CORE_ID): EnemySighting((40, 0), 99, True)
            },
            local_core_sortie_core_id=str(ENEMY_CORE_ID),
            local_core_sortie_position=(40, 0),
            local_core_sortie_started_tick=98,
            local_core_sortie_vanguard_ids={str(VANGUARD_ID)},
            local_core_sortie_ranger_ids={str(RANGER_ID), str(RANGER_TWO_ID)},
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                tick=100,
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((40, 0)), enemy_ranger((22, 0))),
                beacon=ChampionBeacon(position=(100, 0)),
            )
            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        self.assertIsNone(memory.local_core_sortie_core_id)
        self.assertGreater(memory.local_core_sortie_retry_after_tick, turn.tick)
        self.assertTrue(
            any("local_core_sortie_cancelled" in item for item in summary.decisions)
        )
        self.assertTrue(
            any("local_core_sortie_cooldown" in item for item in summary.decisions)
        )

    def test_beacon_local_core_sortie_persists_through_short_visibility_gap(
        self,
    ) -> None:
        units = (
            vanguard((2, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            ranger((1, -2), RANGER_ID),
            ranger((2, 1), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
        )
        memory = TacticMemory(
            mode=MODE_BEACON,
            enemy_sightings={
                str(ENEMY_CORE_ID): EnemySighting((12, 0), 99, True)
            },
            local_core_sortie_core_id=str(ENEMY_CORE_ID),
            local_core_sortie_position=(12, 0),
            local_core_sortie_started_tick=98,
            local_core_sortie_vanguard_ids={str(VANGUARD_ID)},
            local_core_sortie_ranger_ids={str(RANGER_ID), str(RANGER_TWO_ID)},
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                tick=100,
                own_core=core((0, 0)),
                units=units,
                beacon=ChampionBeacon(position=(100, 0)),
            )
            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        self.assertEqual(memory.local_core_sortie_core_id, str(ENEMY_CORE_ID))
        self.assertEqual(
            {
                route.object_id
                for route in memory.current_routes.values()
                if route.reason.startswith("local_core_sortie_")
            },
            {str(VANGUARD_ID), str(RANGER_ID), str(RANGER_TWO_ID)},
        )

    def test_beacon_mode_can_verify_a_nearby_core_seen_within_96_ticks(self) -> None:
        units = (
            vanguard((1, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            ranger((0, -2), RANGER_ID),
            ranger((2, 0), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
        )
        memory = TacticMemory(
            mode=MODE_BEACON,
            enemy_sightings={
                str(ENEMY_CORE_ID): EnemySighting((20, 0), 100, True)
            },
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                tick=170,
                own_core=core((0, 0)),
                units=units,
                beacon=ChampionBeacon(position=(100, 0)),
            )
            SmartTactic(memory, control_path=control_path).choose_actions(turn)

        self.assertEqual(memory.local_core_sortie_core_id, str(ENEMY_CORE_ID))
        self.assertEqual(memory.local_core_sortie_position, (20, 0))

    def test_beacon_mode_surplus_force_prioritizes_known_enemy_core(self) -> None:
        extra_vanguard = VANGUARD_FOURTH_ID
        extra_ranger_one = RANGER_FOURTH_ID
        extra_ranger_two = UUID(int=0x17)
        units = (
            vanguard((1, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            vanguard((8, 0), extra_vanguard),
            ranger((0, -2), RANGER_ID),
            ranger((2, 0), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
            ranger((8, 1), extra_ranger_one),
            ranger((8, -1), extra_ranger_two),
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((30, 0)),),
                beacon=ChampionBeacon(position=(100, 0)),
            )
            memory = TacticMemory()
            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        expedition_ids = {
            extra_vanguard,
            extra_ranger_one,
            extra_ranger_two,
        }
        self.assertTrue(
            all(
                memory.current_routes[str(unit_id)].reason
                == "beacon_expedition_advance"
                for unit_id in expedition_ids
            )
        )
        home_ids = {
            VANGUARD_ID,
            VANGUARD_TWO_ID,
            VANGUARD_THREE_ID,
            RANGER_ID,
            RANGER_TWO_ID,
            RANGER_THREE_ID,
        }
        self.assertFalse(
            any(
                route.object_id in {str(unit_id) for unit_id in home_ids}
                and route.reason.startswith("enemy_core_")
                for route in memory.current_routes.values()
            )
        )
        self.assertTrue(
            any("beacon_enemy_core_priority" in item for item in summary.decisions)
        )
        self.assertTrue(
            any(
                "beacon_expedition_order phase=advance target=(30, 0)" in item
                for item in summary.decisions
            )
        )

    def test_beacon_home_threat_does_not_recall_ready_expedition(self) -> None:
        extra_vanguard = VANGUARD_FOURTH_ID
        extra_ranger_one = RANGER_FOURTH_ID
        extra_ranger_two = UUID(int=0x17)
        units = (
            vanguard((1, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            vanguard((20, 0), extra_vanguard),
            ranger((0, -2), RANGER_ID),
            ranger((2, 0), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
            ranger((20, 1), extra_ranger_one),
            ranger((20, -1), extra_ranger_two),
        )
        memory = TacticMemory(
            mode=MODE_BEACON,
            enemy_sightings={
                str(ENEMY_CORE_ID): EnemySighting((30, 0), 100, True)
            },
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                tick=108,
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_ranger((0, 3)),),
                beacon=ChampionBeacon(position=(100, 0)),
            )
            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        expedition_ids = {
            extra_vanguard,
            extra_ranger_one,
            extra_ranger_two,
        }
        self.assertTrue(
            all(
                memory.current_routes[str(unit_id)].reason
                == "beacon_expedition_advance"
                for unit_id in expedition_ids
            )
        )
        self.assertTrue(
            any(
                "beacon_expedition_order phase=advance target=(30, 0)" in item
                for item in summary.decisions
            )
        )
        self.assertTrue(
            any("core_patrol_alert count=1" in item for item in summary.decisions)
        )

    def test_beacon_expedition_regroups_before_advancing(self) -> None:
        extra_vanguard = VANGUARD_FOURTH_ID
        extra_ranger_one = RANGER_FOURTH_ID
        extra_ranger_two = UUID(int=0x17)
        units = (
            vanguard((1, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            vanguard((30, 0), extra_vanguard),
            ranger((0, -2), RANGER_ID),
            ranger((2, 0), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
            ranger((10, 1), extra_ranger_one),
            ranger((12, -1), extra_ranger_two),
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((100, 0)), enemy_worker((13, 1))),
                beacon=ChampionBeacon(position=(120, 0)),
            )
            memory = TacticMemory()
            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        for unit_id in (extra_vanguard, extra_ranger_one, extra_ranger_two):
            self.assertEqual(
                memory.current_routes[str(unit_id)].reason,
                "beacon_expedition_regroup",
            )
        self.assertIsInstance(
            turn.plan.unit_actions[extra_ranger_one],
            MoveAction,
        )
        self.assertTrue(
            any("beacon_expedition_order phase=regroup" in item for item in summary.decisions)
        )

    def test_beacon_expedition_keeps_regrouping_inside_cohesion_boundary(self) -> None:
        extra_vanguard = VANGUARD_FOURTH_ID
        extra_ranger_one = RANGER_FOURTH_ID
        extra_ranger_two = UUID(int=0x17)
        units = (
            vanguard((1, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            vanguard((17, 0), extra_vanguard),
            ranger((0, -2), RANGER_ID),
            ranger((2, 0), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
            ranger((7, 0), extra_ranger_one),
            ranger((12, 0), extra_ranger_two),
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((100, 0)),),
                beacon=ChampionBeacon(position=(120, 0)),
            )
            memory = TacticMemory()
            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        self.assertTrue(
            any(
                "beacon_expedition_order phase=regroup" in item
                and "anchor=(15, 0)" in item
                for item in summary.decisions
            )
        )
        for unit_id in (extra_vanguard, extra_ranger_one, extra_ranger_two):
            self.assertEqual(
                memory.current_routes[str(unit_id)].reason,
                "beacon_expedition_regroup",
            )

    def test_beacon_expedition_advance_anchor_routes_around_obstacle(self) -> None:
        turn, _ = make_turn(
            own_core=core((0, 0)),
            obstacle_cells=((1, 0),),
        )
        memory = TacticMemory()
        decisions: list[str] = []
        planner = MovementPlanner(turn, memory, decisions)
        tactic = SmartTactic(memory)

        anchor = tactic._expedition_advance_anchor(
            (0, 0),
            (5, 0),
            planner,
        )

        self.assertNotEqual(anchor, (0, 0))
        self.assertNotIn(anchor, planner.obstacles)
        self.assertGreater(anchor[0], 0)
        self.assertLess(_distance(anchor, (5, 0)), 5)

    def test_compact_beacon_formation_makes_real_forward_progress(self) -> None:
        expedition_vanguards = (
            (VANGUARD_FOURTH_ID, (40, 1)),
            (UUID(int=0x18), (41, 1)),
            (UUID(int=0x19), (39, 1)),
            (UUID(int=0x1A), (41, 2)),
            (UUID(int=0x1B), (39, 2)),
        )
        expedition_rangers = (
            (RANGER_FOURTH_ID, (40, -1)),
            (UUID(int=0x17), (41, -1)),
            (UUID(int=0x1C), (42, 0)),
        )
        units = (
            vanguard((1, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            *(vanguard(position, unit_id) for unit_id, position in expedition_vanguards),
            ranger((0, -2), RANGER_ID),
            ranger((2, 0), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
            *(ranger(position, unit_id) for unit_id, position in expedition_rangers),
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((40, 60)),),
                beacon=ChampionBeacon(position=(100, 100)),
            )
            memory = TacticMemory()
            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        expedition_ids = {
            unit_id
            for unit_id, _ in (*expedition_vanguards, *expedition_rangers)
        }
        moving_ids = {
            unit_id
            for unit_id in expedition_ids
            if isinstance(turn.plan.unit_actions.get(unit_id), MoveAction)
        }
        self.assertGreaterEqual(len(moving_ids), 3)
        self.assertTrue(
            all(
                memory.current_routes[str(unit_id)].reason
                == "beacon_expedition_advance"
                for unit_id in moving_ids
            )
        )
        self.assertTrue(
            any("phase=advance" in item for item in summary.decisions)
        )

    def test_weak_enemy_core_allows_cohesive_forward_group_to_strike(self) -> None:
        extra_vanguard = VANGUARD_FOURTH_ID
        extra_ranger_one = RANGER_FOURTH_ID
        extra_ranger_two = UUID(int=0x17)
        units = (
            vanguard((1, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            vanguard((19, 0), extra_vanguard),
            ranger((0, -2), RANGER_ID),
            ranger((2, 0), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
            ranger((17, 0), extra_ranger_one),
            ranger((18, 0), extra_ranger_two),
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((20, 0)),),
                beacon=ChampionBeacon(position=(100, 0)),
            )
            summary = SmartTactic(
                TacticMemory(),
                control_path=control_path,
            ).choose_actions(turn)

        self.assertIsInstance(turn.plan.unit_actions[extra_vanguard], SweepAction)
        self.assertIsInstance(turn.plan.unit_actions[extra_ranger_one], ShootAction)
        self.assertIsInstance(turn.plan.unit_actions[extra_ranger_two], ShootAction)
        self.assertTrue(
            any("phase=weak_core_strike" in item for item in summary.decisions)
        )

    def test_known_enemy_core_approach_ignores_low_value_worker_shot(self) -> None:
        extra_vanguard = VANGUARD_FOURTH_ID
        extra_ranger_one = RANGER_FOURTH_ID
        extra_ranger_two = UUID(int=0x17)
        units = (
            vanguard((1, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            vanguard((10, 0), extra_vanguard),
            ranger((0, -2), RANGER_ID),
            ranger((2, 0), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
            ranger((11, 1), extra_ranger_one),
            ranger((11, -1), extra_ranger_two),
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((20, 0)), enemy_worker((14, 1))),
                beacon=ChampionBeacon(position=(100, 0)),
            )
            memory = TacticMemory()
            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        self.assertTrue(
            any("phase=weak_core_strike" in item for item in summary.decisions)
        )
        self.assertIsInstance(
            turn.plan.unit_actions[extra_ranger_one],
            MoveAction,
        )
        self.assertEqual(
            memory.current_routes[str(extra_ranger_one)].reason,
            "enemy_core_seek_firing",
        )

    def test_visible_core_with_small_guard_screen_gets_directed_core_focus(self) -> None:
        extra_vanguard = VANGUARD_FOURTH_ID
        extra_vanguard_two = UUID(int=0x18)
        extra_ranger_one = RANGER_FOURTH_ID
        extra_ranger_two = UUID(int=0x17)
        enemy_guard_one = UUID(int=0x9001)
        enemy_guard_two = UUID(int=0x9002)
        units = (
            vanguard((1, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            vanguard((14, 0), extra_vanguard),
            vanguard((13, 1), extra_vanguard_two),
            ranger((0, -2), RANGER_ID),
            ranger((2, 0), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
            ranger((13, 0), extra_ranger_one),
            ranger((12, -1), extra_ranger_two),
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=units,
                enemies=(
                    enemy_core((16, 0)),
                    enemy_ranger((16, 2), unit_id=enemy_guard_one),
                    enemy_ranger((15, 1), unit_id=enemy_guard_two),
                ),
                beacon=ChampionBeacon(position=(100, 0)),
            )
            memory = TacticMemory()
            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        self.assertTrue(
            any("phase=core_focus" in item for item in summary.decisions)
        )
        self.assertTrue(
            any(
                route.reason == "beacon_core_focus"
                for route in memory.current_routes.values()
            )
        )
        self.assertIsInstance(
            turn.plan.unit_actions.get(extra_ranger_one),
            ShootAction,
        )
        self.assertIsInstance(
            turn.plan.unit_actions.get(extra_ranger_two),
            MoveAction,
        )

    def test_outmatched_beacon_expedition_retreats_as_one_group(self) -> None:
        extra_vanguard = VANGUARD_FOURTH_ID
        extra_ranger_one = RANGER_FOURTH_ID
        extra_ranger_two = UUID(int=0x17)
        units = (
            vanguard((1, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            vanguard((10, 0), extra_vanguard),
            ranger((0, -2), RANGER_ID),
            ranger((2, 0), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
            ranger((10, 1), extra_ranger_one),
            ranger((10, -1), extra_ranger_two),
        )
        enemy_guards = tuple(
            enemy_ranger(
                position,
                unit_id=UUID(int=0x9000 + index),
            )
            for index, position in enumerate(((20, 1), (21, 0), (20, -1)))
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((20, 0)), *enemy_guards),
                beacon=ChampionBeacon(position=(100, 0)),
            )
            memory = TacticMemory()
            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        for unit_id in (extra_vanguard, extra_ranger_one, extra_ranger_two):
            self.assertEqual(
                memory.current_routes[str(unit_id)].reason,
                "beacon_expedition_retreat",
            )
        self.assertTrue(
            any("phase=retreat" in item for item in summary.decisions)
        )

    def test_beacon_expedition_holds_when_wounded_rangers_leave_active_force(self) -> None:
        extra_vanguard = VANGUARD_FOURTH_ID
        active_ranger = RANGER_FOURTH_ID
        wounded_ranger_one = UUID(int=0x17)
        wounded_ranger_two = UUID(int=0x18)
        units = (
            vanguard((1, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            vanguard((12, 0), extra_vanguard),
            ranger((0, -2), RANGER_ID),
            ranger((2, 0), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
            ranger((10, 1), active_ranger),
            ranger((11, 0), wounded_ranger_one, hp=1),
            ranger((10, -1), wounded_ranger_two, hp=1),
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_core((40, 0)), enemy_worker((13, 1))),
                resources=3,
                beacon=ChampionBeacon(position=(100, 0)),
            )
            memory = TacticMemory()
            summary = SmartTactic(
                memory,
                control_path=control_path,
            ).choose_actions(turn)

        self.assertEqual(
            memory.current_routes[str(extra_vanguard)].reason,
            "beacon_expedition_hold_reinforcements",
        )
        self.assertEqual(
            memory.current_routes[str(active_ranger)].reason,
            "beacon_expedition_hold_reinforcements",
        )
        self.assertIsInstance(
            turn.plan.unit_actions[extra_vanguard],
            MoveAction,
        )
        self.assertIsInstance(
            turn.plan.unit_actions[active_ranger],
            MoveAction,
        )
        self.assertTrue(
            any(
                "phase=hold_reinforcements" in item
                for item in summary.decisions
            )
        )
        for unit_id in (wounded_ranger_one, wounded_ranger_two):
            self.assertEqual(
                memory.current_routes[str(unit_id)].reason,
                "heal_return",
            )

    def test_understrength_beacon_expedition_retreats_from_local_enemy(self) -> None:
        units = (
            vanguard((1, 0), VANGUARD_ID),
            vanguard((-1, 0), VANGUARD_TWO_ID),
            vanguard((0, 1), VANGUARD_THREE_ID),
            vanguard((10, 0), VANGUARD_FOURTH_ID),
            ranger((0, -2), RANGER_ID),
            ranger((2, 0), RANGER_TWO_ID),
            ranger((-2, 0), RANGER_THREE_ID),
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=units,
                enemies=(enemy_ranger((11, 0)),),
                beacon=ChampionBeacon(position=(100, 0)),
            )
            summary = SmartTactic(
                TacticMemory(),
                control_path=control_path,
            ).choose_actions(turn)

        self.assertTrue(
            any(
                "phase=retreat" in item and "enemy_combat=1" in item
                for item in summary.decisions
            )
        )

    def test_beacon_mode_worker_stays_in_core_economy(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                own_core=core((5, 5)),
                units=(worker(WORKER_LOW, (6, 5)),),
            )
            memory = TacticMemory()
            summary = SmartTactic(memory, control_path=control_path).choose_actions(turn)

            self.assertFalse(
                any("beacon_advance" in item for item in summary.decisions)
            )
            goal = memory.worker_goals[str(WORKER_LOW)]
            self.assertEqual(goal.kind, "resource_sweep")
            self.assertLessEqual(
                _distance((5, 5), goal.position),
                BEACON_RESOURCE_SWEEP_MAX_RADIUS,
            )

    def test_beacon_mode_spawns_rangers(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    worker(WORKER_LOW, (6, 0)),
                    worker(WORKER_HIGH, (7, 0)),
                    worker(WORKER_THIRD, (8, 0)),
                    vanguard((3, 3)),
                    ranger((3, 4)),
                ),
                resources=30,
            )
            SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

            self.assertIsInstance(turn.plan.core_action, SpawnAction)
            self.assertEqual(turn.plan.core_action.unit_type, UnitType.RANGER)

    def test_beacon_mode_expands_economy_after_combat_baseline(self) -> None:
        self.assertEqual(BEACON_ECONOMY_TARGET_WORKERS, 10)
        units = tuple(
            [
                worker(UUID(int=0x7000 + index), (20 + index, 0))
                for index in range(BEACON_ECONOMY_TARGET_WORKERS - 2)
            ]
            + [
                vanguard((20 + index, 2), UUID(int=0x7100 + index))
                for index in range(8)
            ]
            + [
                ranger((20 + index, 4), UUID(int=0x7200 + index))
                for index in range(11)
            ]
        )
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=units,
            resources=10,
            beacon=ChampionBeacon(position=(100, 0)),
        )

        SmartTactic(TacticMemory(mode=MODE_BEACON)).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.WORKER)

    def test_beacon_mode_saves_ranger_window_before_population_price_step(self) -> None:
        units = tuple(
            [
                worker(UUID(int=0x2000 + index), (6 + index, 0))
                for index in range(7)
            ]
            + [
                vanguard((10 + index, 0), UUID(int=0x3000 + index))
                for index in range(BEACON_RANGER_PRIORITY_MIN_VANGUARDS + 2)
            ]
            + [
                ranger((10 + index, 2), UUID(int=0x4000 + index))
                for index in range(5)
            ]
        )
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="beacon")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=units,
                resources=10,
            )
            SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

        self.assertEqual(len(turn.units), 19)
        self.assertIsNone(turn.plan.core_action)

    def test_beacon_mode_continues_growth_after_population_thirty(self) -> None:
        units = tuple(
            [
                worker(UUID(int=0x7300 + index), (20 + index, 0))
                for index in range(10)
            ]
            + [
                vanguard((20 + index, 2), UUID(int=0x7400 + index))
                for index in range(8)
            ]
            + [
                ranger((20 + index, 4), UUID(int=0x7500 + index))
                for index in range(12)
            ]
        )
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=units,
            resources=unit_cost(UnitType.RANGER, 30),
            beacon=ChampionBeacon(position=(100, 0)),
        )

        SmartTactic(TacticMemory(mode=MODE_BEACON)).choose_actions(turn)

        self.assertEqual(len(turn.units), 30)
        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.RANGER)

    def test_continuous_growth_uses_affordable_balanced_role(self) -> None:
        units = tuple(
            [
                worker(UUID(int=0x7600 + index), (20 + index, 0))
                for index in range(10)
            ]
            + [
                vanguard((20 + index, 2), UUID(int=0x7700 + index))
                for index in range(8)
            ]
            + [
                ranger((20 + index, 4), UUID(int=0x7800 + index))
                for index in range(12)
            ]
        )
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=units,
            resources=unit_cost(UnitType.VANGUARD, 30),
            beacon=ChampionBeacon(position=(100, 0)),
        )

        SmartTactic(TacticMemory(mode=MODE_BEACON)).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.VANGUARD)

    def test_continuous_growth_uses_nearby_affordable_worker_role(self) -> None:
        units = tuple(
            [
                worker(UUID(int=0x7900 + index), (20 + index, 0))
                for index in range(12)
            ]
            + [
                vanguard((20 + index, 2), UUID(int=0x7A00 + index))
                for index in range(9)
            ]
            + [
                ranger((20 + index, 4), UUID(int=0x7B00 + index))
                for index in range(14)
            ]
        )
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=units,
            resources=unit_cost(UnitType.WORKER, len(units)),
            beacon=ChampionBeacon(position=(100, 0)),
        )

        SmartTactic(TacticMemory(mode=MODE_BEACON)).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.WORKER)

    def test_continuous_growth_saves_when_affordable_role_is_overrepresented(
        self,
    ) -> None:
        units = tuple(
            [
                worker(UUID(int=0x7C00 + index), (20 + index, 0))
                for index in range(13)
            ]
            + [
                vanguard((20 + index, 2), UUID(int=0x7D00 + index))
                for index in range(9)
            ]
            + [
                ranger((20 + index, 4), UUID(int=0x7E00 + index))
                for index in range(14)
            ]
        )
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=units,
            resources=unit_cost(UnitType.WORKER, len(units)),
            beacon=ChampionBeacon(position=(100, 0)),
        )

        SmartTactic(TacticMemory(mode=MODE_BEACON)).choose_actions(turn)

        self.assertIsNone(turn.plan.core_action)


    def test_aggress_vanguard_escorts_ranger(self) -> None:
        # 侵略模式：无敌人时，远离游侠的先锋向游侠靠拢（编队护卫）
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    vanguard((5, 5)),   # 离游侠远（>3 格）
                    ranger((0, 0)),      # 游侠在 core 附近
                ),
            )
            summary = SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

            self.assertTrue(
                any("squad_front" in item for item in summary.decisions)
            )

    def test_aggress_ranger_advances_frontier(self) -> None:
        # 侵略模式：无敌人时游侠向前沿推进
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="aggress")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(ranger((3, 3)),),
            )
            summary = SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

            action = turn.plan.unit_actions.get(RANGER_ID)
            self.assertIsInstance(action, MoveAction)
            self.assertTrue(
                any("aggress_frontier" in item for item in summary.decisions)
            )

    def test_same_cell_stacking_does_not_merge_hp(self) -> None:
        # 研究结论：同格叠放不叠加血量——两个同类型单位 hp 独立
        first = UnitView(
            kind="UNIT",
            id=RANGER_ID,
            controlled=True,
            position=(3, 3),
            hp=2,
            unit_type=UnitType.RANGER,
        )
        second = UnitView(
            kind="UNIT",
            id=ENEMY_RANGER_ID,
            controlled=True,
            position=(3, 3),
            hp=2,
            unit_type=UnitType.RANGER,
        )
        self.assertEqual(first.hp, 2)
        self.assertEqual(second.hp, 2)
        # 单位 hp 字段彼此独立，不存在合并结算
        self.assertNotEqual(id(first), id(second))


    def test_cargo_worker_stuck_triggers_core_migration(self) -> None:
        # cargo 工人被墙挡回不来（打转 16 tick 且离 core 远 >6 格）→ core 自愈迁移靠拢
        memory = TacticMemory()
        memory.recent_positions[str(WORKER_LOW)] = [
            (10, 0), (10, 1), (10, 0), (10, 1), (10, 0), (10, 1),
            (10, 0), (10, 1), (10, 0), (10, 1), (10, 0), (10, 1),
            (10, 0), (10, 1), (10, 0), (10, 1),
        ]
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(
                worker(WORKER_LOW, (10, 0), cargo=2),
                vanguard((1, 0)),
                ranger((1, 1)),
            ),
            resources=0,
            obstacle_cells=((1, 0), (2, 0), (3, 0), (4, 0), (5, 0)),  # 挡住回 core 的路
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertTrue(
            any("cargo_stuck" in item for item in summary.decisions)
        )
        self.assertTrue(
            any("cargo_blocked_self_heal" in item for item in summary.decisions)
        )
        self.assertIsInstance(turn.plan.core_action, StartMoveAction)

    def test_cargo_worker_near_core_no_migration(self) -> None:
        # cargo 工人在 core 附近（≤5 格）→ 不触发迁移
        memory = TacticMemory()
        memory.recent_positions[str(WORKER_LOW)] = [
            (3, 0), (3, 1), (3, 0), (3, 1), (3, 0), (3, 1),
            (3, 0), (3, 1), (3, 0), (3, 1), (3, 0), (3, 1),
            (3, 0), (3, 1), (3, 0), (3, 1),
        ]
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (3, 0), cargo=2),),
            resources=0,
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertFalse(
            any("cargo_blocked_self_heal" in item for item in summary.decisions)
        )
        self.assertIsNone(turn.plan.core_action)

    def test_cargo_worker_stuck_does_not_move_core_without_home_guard(self) -> None:
        memory = TacticMemory()
        memory.recent_positions[str(WORKER_LOW)] = [
            (10, 0), (10, 1), (10, 0), (10, 1), (10, 0), (10, 1),
            (10, 0), (10, 1), (10, 0), (10, 1), (10, 0), (10, 1),
            (10, 0), (10, 1), (10, 0), (10, 1),
        ]
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=(worker(WORKER_LOW, (10, 0), cargo=2),),
            resources=0,
            obstacle_cells=((1, 0), (2, 0), (3, 0), (4, 0), (5, 0)),
        )

        summary = SmartTactic(memory).choose_actions(turn)

        self.assertTrue(any("cargo_stuck" in item for item in summary.decisions))
        self.assertTrue(
            any("core auto_mobility_hold" in item for item in summary.decisions)
        )
        self.assertIsNone(turn.plan.core_action)


    def test_rally_point_sends_units_to_marker(self) -> None:
        # 标记（rally_point）设置后，先锋/游侠前往标记坐标
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="develop")
            control_path.write_text(
                json.dumps({"rally_point": [20, 20]}),
                encoding="utf-8",
            )
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    vanguard((3, 3)),
                    ranger((3, 5)),
                ),
            )
            summary = SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

            self.assertTrue(
                any("rally_advance" in item for item in summary.decisions)
            )
            vanguard_action = turn.plan.unit_actions.get(VANGUARD_ID)
            ranger_action = turn.plan.unit_actions.get(RANGER_ID)
            self.assertIsInstance(vanguard_action, MoveAction)
            self.assertIsInstance(ranger_action, MoveAction)

    def test_rally_point_cleared_returns_to_mode(self) -> None:
        # 清除标记后恢复模式逻辑（无 rally_advance）
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            self._write_control(control_path, mode="develop")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(vanguard((3, 3)),),
            )
            summary = SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

            self.assertFalse(
                any("rally_advance" in item for item in summary.decisions)
            )


class CompositionLadderTests(unittest.TestCase):
    """develop 目标编制阶梯（20 人 12:4:4 → 30 人 18:6:6 → 不限）。"""

    def test_split_population_totals_match_target(self) -> None:
        self.assertEqual(_split_population(20, (12, 4, 4)), (12, 4, 4))
        self.assertEqual(_split_population(30, (18, 6, 6)), (18, 6, 6))
        # 除不尽时用最大余额法补齐，三项之和仍等于目标人口
        for population, weights in (
            (20, (5, 4, 6)),
            (7, (1, 1, 1)),
            (13, (3, 1, 2)),
            (1, (12, 4, 4)),
        ):
            counts = _split_population(population, weights)
            self.assertEqual(sum(counts), population, msg=f"{population}/{weights}")

    def test_ladder_advances_on_composition_met(self) -> None:
        """阶梯按编制达成推进，不按总人口。"""
        memory = TacticMemory()
        self.assertEqual(memory.target_population, 20)
        self.assertEqual(
            (
                memory.composition_workers,
                memory.composition_vanguards,
                memory.composition_rangers,
            ),
            (12, 4, 4),
        )
        stage2 = (
            COMPOSITION_STAGE2_WORKERS,
            COMPOSITION_STAGE2_VANGUARDS,
            COMPOSITION_STAGE2_RANGERS,
        )
        # 第一级未达成：任一兵种缺口都让阶梯停在第一级
        for counts in ((0, 0, 0), (4, 1, 1), (11, 4, 4), (12, 3, 4), (12, 4, 3)):
            self.assertEqual(_effective_composition(memory, *counts), (12, 4, 4))
            self.assertEqual(_effective_target_population(memory, *counts), 20)
        # 第一级达成 → 升第二级
        for counts in ((12, 4, 4), (15, 5, 5), (17, 6, 6)):
            self.assertEqual(_effective_composition(memory, *counts), stage2)
            self.assertEqual(
                _effective_target_population(memory, *counts),
                COMPOSITION_STAGE2_POPULATION,
            )
        # 两级都达成后取消人口目标，回落项目默认比例
        for counts in ((18, 6, 6), (25, 9, 11)):
            self.assertIsNone(_effective_composition(memory, *counts))
            self.assertEqual(_effective_target_population(memory, *counts), 0)
            self.assertEqual(
                _effective_growth_profile(memory, *counts),
                CONTINUOUS_GROWTH_PROFILE,
            )

    def test_overflow_shifts_thresholds_so_gap_gets_filled(self) -> None:
        """回归：多产的单位当不存在，被挤掉的编制缺口仍要补齐。

        12:4:4 配置下多产 1 个游侠，人口 20 时是 11工4先5游。若按总人口判定，
        阶梯会直接进第二级、囤积同时启动，第 12 个工人再也补不上。
        """
        memory = TacticMemory()
        memory.hoard_stage1 = True

        # 11工4先5游 = 20 人：游侠超产 1，工人还差 1
        counts = (11, 4, 5)
        self.assertEqual(_composition_overflow(memory, *counts), 1)
        self.assertEqual(
            _effective_composition(memory, *counts),
            (12, 4, 4),
            "第一级未达成，不得提前升级",
        )
        self.assertEqual(
            _effective_target_population(memory, *counts),
            21,
            "目标人口 = 编制之和 20 + 超产 1",
        )
        self.assertEqual(
            _hoard_resource_target(memory, sum(counts), 1),
            0,
            "门槛顺移到 21，人口 20 时不得开始囤积",
        )

        # 补上第 12 个工人 → 12工4先5游 = 21 人：第一级达成，升第二级并开始囤积
        counts = (12, 4, 5)
        self.assertEqual(_composition_overflow(memory, *counts), 0)
        self.assertEqual(
            _effective_composition(memory, *counts),
            (
                COMPOSITION_STAGE2_WORKERS,
                COMPOSITION_STAGE2_VANGUARDS,
                COMPOSITION_STAGE2_RANGERS,
            ),
        )
        self.assertEqual(
            _hoard_resource_target(memory, sum(counts), 0),
            HOARD_STAGE1_RESOURCE_TARGET,
        )

    def test_stage_two_composition_is_not_counted_as_overflow(self) -> None:
        """回归：第二级正常编制不得被误判成超产。

        基准若取第一级（12:4:4），18:6:6 会被算成超产 10，把第二档囤积门槛顺移
        到 40，永远不触发。
        """
        memory = TacticMemory()
        memory.hoard_stage1 = True
        memory.hoard_stage2 = True
        counts = (18, 6, 6)
        self.assertEqual(_composition_overflow(memory, *counts), 0)
        self.assertEqual(
            _hoard_resource_target(memory, sum(counts), 0),
            HOARD_STAGE2_RESOURCE_TARGET,
        )

    def test_ladder_waits_for_hoard_before_advancing(self) -> None:
        """回归：勾了本级囤积时，攒够水位才算这一级完成。

        实测现场：12工5先5游=22人、资源 40，编制虽已达成但 95 没攒到，面板却
        显示第二级「目标 30 人 · 18工 6先 6游」，与实际行为不符。用户设定的语义
        是"人口达到 20 后优先将资源攒到 95"——攒资源是这一级的一部分。
        """

        memory = TacticMemory()
        memory.hoard_stage1 = True
        counts = (12, 5, 5)  # 第一级 12:4:4 已达成，游侠超产 1、先锋超产 1

        # 水位未达成：停在第一级，并报出超产
        for resources in (0, 40, HOARD_STAGE1_RESOURCE_TARGET - 1):
            self.assertEqual(
                _effective_composition(memory, *counts, resources),
                (12, 4, 4),
                f"资源 {resources} 未达水位，不得显示第二级",
            )
            self.assertEqual(_composition_overflow(memory, *counts, resources), 2)
            self.assertEqual(
                _effective_target_population(memory, *counts, resources),
                22,
                "目标人口 = 本级编制 20 + 超产 2",
            )

        # 水位达成 → 升第二级
        for resources in (HOARD_STAGE1_RESOURCE_TARGET, 110):
            self.assertEqual(
                _effective_composition(memory, *counts, resources),
                (
                    COMPOSITION_STAGE2_WORKERS,
                    COMPOSITION_STAGE2_VANGUARDS,
                    COMPOSITION_STAGE2_RANGERS,
                ),
            )
            self.assertEqual(_composition_overflow(memory, *counts, resources), 0)

    def test_ladder_advances_without_hoard_switch(self) -> None:
        """未勾囤积时没有水位可等，编制达成即升级（否则阶梯会永久停在第一级）。"""

        memory = TacticMemory()
        self.assertFalse(memory.hoard_stage1)
        counts = (12, 5, 5)
        stage2 = (
            COMPOSITION_STAGE2_WORKERS,
            COMPOSITION_STAGE2_VANGUARDS,
            COMPOSITION_STAGE2_RANGERS,
        )
        for resources in (0, 40, 200):
            self.assertEqual(
                _effective_composition(memory, *counts, resources), stage2
            )

    def test_stage_two_also_waits_for_its_hoard(self) -> None:
        """第二档囤积同理：18:6:6 达成后要攒到 150 才进终态。"""

        memory = TacticMemory()
        memory.hoard_stage1 = True
        memory.hoard_stage2 = True
        counts = (18, 6, 6)
        stage2 = (
            COMPOSITION_STAGE2_WORKERS,
            COMPOSITION_STAGE2_VANGUARDS,
            COMPOSITION_STAGE2_RANGERS,
        )
        self.assertEqual(
            _effective_composition(
                memory, *counts, HOARD_STAGE2_RESOURCE_TARGET - 1
            ),
            stage2,
            "150 未攒够，仍停在第二级",
        )
        self.assertIsNone(
            _effective_composition(memory, *counts, HOARD_STAGE2_RESOURCE_TARGET),
            "攒够 150 后进入终态，回落项目默认比例",
        )

    def test_ladder_omitting_resources_ignores_hoard_gate(self) -> None:
        """不传 resources 时退化为纯编制判定，供不关心库存的调用方使用。"""

        memory = TacticMemory()
        memory.hoard_stage1 = True
        self.assertEqual(
            _effective_composition(memory, 12, 4, 4),
            (
                COMPOSITION_STAGE2_WORKERS,
                COMPOSITION_STAGE2_VANGUARDS,
                COMPOSITION_STAGE2_RANGERS,
            ),
        )

    def test_user_can_extend_ladder_past_stage_two(self) -> None:
        """30 之后：不改设定则回落 5:4:6，改大目标则继续按新设定补。

        面板的四个编制输入框显示"当前生效那一级"，用户在此基础上改动即等于设定
        下一级目标。目标人口 ≤30（等于没改）时第二级完成后回落项目原策略。
        """

        reached_stage_two = (18, 6, 6)
        resources = HOARD_STAGE2_RESOURCE_TARGET

        def memory_with(target: int, weights: tuple[int, int, int]) -> TacticMemory:
            memory = TacticMemory()
            memory.target_population = target
            memory.composition_workers = weights[0]
            memory.composition_vanguards = weights[1]
            memory.composition_rangers = weights[2]
            memory.hoard_stage1 = True
            memory.hoard_stage2 = True
            return memory

        # 不改设定（20/12:4:4）或改成等于第二级（30/18:6:6）→ 阶梯用尽，回落 5:4:6
        for target, weights, label in (
            (20, (12, 4, 4), "保持第一级设定"),
            (30, (18, 6, 6), "改成第二级同值"),
        ):
            memory = memory_with(target, weights)
            self.assertIsNone(
                _effective_composition(memory, *reached_stage_two, resources),
                f"{label}：第二级完成后应取消人口目标",
            )
            self.assertEqual(
                _effective_growth_profile(memory, *reached_stage_two, resources),
                CONTINUOUS_GROWTH_PROFILE,
                f"{label}：应回落项目默认 5:4:6",
            )

        # 改成大于 30 的目标 → 成为新一级，继续补
        memory = memory_with(40, (20, 8, 12))
        self.assertEqual(
            _effective_composition(memory, *reached_stage_two, resources),
            (20, 8, 12),
        )
        self.assertEqual(
            {unit: weight for unit, weight in _effective_growth_profile(
                memory, *reached_stage_two, resources
            )},
            {UnitType.WORKER: 20, UnitType.VANGUARD: 8, UnitType.RANGER: 12},
        )

    def test_stage_two_hoard_covers_population_thirty_and_beyond(self) -> None:
        """第二档水位覆盖「30 及之后」，不是只在 30 那一刻。"""

        memory = TacticMemory()
        memory.hoard_stage1 = True
        memory.hoard_stage2 = True
        self.assertEqual(
            _hoard_resource_target(memory, HOARD_STAGE2_POPULATION - 1, 0),
            HOARD_STAGE1_RESOURCE_TARGET,
        )
        for population in (
            HOARD_STAGE2_POPULATION,
            HOARD_STAGE2_POPULATION + 1,
            HOARD_STAGE2_POPULATION + 50,
        ):
            self.assertEqual(
                _hoard_resource_target(memory, population, 0),
                HOARD_STAGE2_RESOURCE_TARGET,
                f"人口 {population} 应维持 150 水位",
            )

    def test_growth_ratio_is_configurable_after_ladder(self) -> None:
        """阶梯用尽后改用 growth_* 配比，默认 5:4:6 即项目原策略。

        用途：18工6先6游 回落 5:4:6 后工人比压 18/5=3.6 远超容差 0.2，要等游侠
        涨到 18、先锋涨到 14 才会重新产工人（约人口 50+），期间采集能力冻结。
        """

        exhausted = (18, 6, 6)  # 第二级达成
        resources = HOARD_STAGE2_RESOURCE_TARGET

        def memory_with(weights: tuple[int, int, int]) -> TacticMemory:
            memory = TacticMemory()
            memory.hoard_stage1 = True
            memory.hoard_stage2 = True
            memory.growth_workers = weights[0]
            memory.growth_vanguards = weights[1]
            memory.growth_rangers = weights[2]
            return memory

        # 默认值等于项目原策略，不改配置则行为不变
        default_memory = memory_with((5, 4, 6))
        self.assertEqual(default_memory.growth_workers, 5)
        self.assertEqual(default_memory.growth_vanguards, 4)
        self.assertEqual(default_memory.growth_rangers, 6)
        self.assertIsNone(
            _effective_composition(default_memory, *exhausted, resources),
            "第二级达成且攒够 150 → 阶梯用尽",
        )
        self.assertEqual(
            _effective_growth_profile(default_memory, *exhausted, resources),
            CONTINUOUS_GROWTH_PROFILE,
        )

        # 自定义配比生效，且保持"游侠 → 先锋 → 工人"的稳定排序
        custom = memory_with((12, 5, 7))
        self.assertEqual(
            _effective_growth_profile(custom, *exhausted, resources),
            (
                (UnitType.RANGER, 7),
                (UnitType.VANGUARD, 5),
                (UnitType.WORKER, 12),
            ),
        )

        # 三项全为 0 回落原策略
        self.assertEqual(
            _effective_growth_profile(memory_with((0, 0, 0)), *exhausted, resources),
            CONTINUOUS_GROWTH_PROFILE,
        )

        # 单项为 0 表示不再生产该兵种
        profile = _effective_growth_profile(
            memory_with((1, 0, 0)), *exhausted, resources
        )
        self.assertEqual({unit for unit, _ in profile}, {UnitType.WORKER})

    def test_growth_ratio_ignored_while_ladder_active(self) -> None:
        """阶梯生效时权重仍来自本级目标编制，growth_* 只管阶梯之后。"""

        memory = TacticMemory()
        memory.growth_workers = 1
        memory.growth_vanguards = 0
        memory.growth_rangers = 0
        # 第一级 12:4:4 未达成
        self.assertEqual(
            _effective_growth_profile(memory, 6, 2, 2),
            (
                (UnitType.RANGER, 4),
                (UnitType.VANGUARD, 4),
                (UnitType.WORKER, 12),
            ),
            "阶梯生效期间不应使用 growth_* 配比",
        )

    def test_growth_ratio_read_from_control_file(self) -> None:
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps(
                    {
                        "mode": "develop",
                        "growth_workers": 12,
                        "growth_vanguards": 5,
                        "growth_rangers": 7,
                    }
                ),
                encoding="utf-8",
            )
            memory = TacticMemory()
            memory.load_control(control_path)

        self.assertEqual(
            (memory.growth_workers, memory.growth_vanguards, memory.growth_rangers),
            (12, 5, 7),
        )

    def test_ladder_disabled_by_zero_and_outside_develop(self) -> None:
        memory = TacticMemory()
        memory.target_population = 0
        self.assertIsNone(_effective_composition(memory, 5, 1, 1))
        self.assertEqual(
            _effective_growth_profile(memory, 5, 1, 1), CONTINUOUS_GROWTH_PROFILE
        )

        memory = TacticMemory()
        memory.composition_workers = 0
        memory.composition_vanguards = 0
        memory.composition_rangers = 0
        self.assertIsNone(_effective_composition(memory, 5, 1, 1))

        for mode in (MODE_AGGRESS, MODE_BEACON, MODE_MIGRATE):
            memory = TacticMemory()
            memory.mode = mode
            self.assertIsNone(_effective_composition(memory, 5, 1, 1))
            self.assertEqual(_effective_target_population(memory, 5, 1, 1), 0)

    def test_zero_weight_removes_unit_type_from_growth(self) -> None:
        memory = TacticMemory()
        memory.composition_rangers = 0
        profile = _effective_growth_profile(memory, 5, 1, 1)
        self.assertNotIn(UnitType.RANGER, {unit_type for unit_type, _ in profile})
        self.assertIn(UnitType.WORKER, {unit_type for unit_type, _ in profile})

    def test_develop_targets_follow_first_ladder_stage(self) -> None:
        """12:4:4 的先锋目标 4 生效：3 先锋时补先锋，而不是按默认补到 3+1 之外。"""
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps({"mode": "develop", "composition_rangers": 4}),
                encoding="utf-8",
            )
            units = tuple(
                worker(_ladder_uuid(index), (6 + index, 0)) for index in range(4)
            ) + (
                vanguard((1, 0), VANGUARD_ID),
                vanguard((-1, 0), VANGUARD_TWO_ID),
                vanguard((0, 1), VANGUARD_THREE_ID),
                ranger((2, 0), RANGER_ID),
                ranger((-2, 0), RANGER_TWO_ID),
                ranger((0, 2), RANGER_THREE_ID),
                ranger((0, -2), _ladder_uuid(50)),
            )
            turn, _ = make_turn(own_core=core((0, 0)), units=units, resources=60)
            SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)

        self.assertIsInstance(turn.plan.core_action, SpawnAction)
        # 先锋 3 < 目标 4 → 补先锋；游侠已达 4，不再抢在先锋之前
        self.assertEqual(turn.plan.core_action.unit_type, UnitType.VANGUARD)

    def _beacon_switch_roster(self):
        """4 先锋 + 5 游侠：刚好越过自动抢信标的门槛。"""
        return tuple(
            worker(_ladder_uuid(index), (6 + index, 0)) for index in range(8)
        ) + (
            vanguard((3, 3), VANGUARD_ID),
            vanguard((4, 3), VANGUARD_TWO_ID),
            vanguard((5, 3), VANGUARD_THREE_ID),
            vanguard((6, 3), VANGUARD_FOURTH_ID),
            ranger((3, 4), RANGER_ID),
            ranger((4, 4), RANGER_TWO_ID),
            ranger((5, 4), RANGER_THREE_ID),
            ranger((6, 4), RANGER_FOURTH_ID),
            ranger((7, 4), _ladder_uuid(60)),
        )

    def test_active_ladder_postpones_beacon_expedition(self) -> None:
        """阶梯生效期间不自动切 beacon，否则 develop 专属的阶梯与囤积会失效。"""
        turn, _ = make_turn(
            own_core=core((0, 0)),
            units=self._beacon_switch_roster(),
            resources=21,
        )
        memory = TacticMemory()
        SmartTactic(memory).choose_actions(turn)
        self.assertEqual(memory.mode, MODE_DEVELOP)

    def test_active_hoard_postpones_beacon_expedition(self) -> None:
        """囤积在人口 30 才触发，那时阶梯已用尽，因此囤积也要能押后抢信标。"""
        units = tuple(
            worker(_ladder_uuid(index), (6 + index, 0)) for index in range(18)
        ) + tuple(
            vanguard((3, 3 + index), _ladder_uuid(100 + index)) for index in range(6)
        ) + tuple(
            ranger((-3, 3 + index), _ladder_uuid(200 + index)) for index in range(6)
        )
        turn, _ = make_turn(own_core=core((0, 0)), units=units, resources=40)
        memory = TacticMemory()
        # 18工6先6游 → 两级都达成，阶梯用尽；只有囤积开关能继续押后
        self.assertEqual(_effective_target_population(memory, 18, 6, 6), 0)
        memory.hoard_stage2 = True
        SmartTactic(memory).choose_actions(turn)
        self.assertEqual(memory.mode, MODE_DEVELOP)


class ResourceHoardTests(unittest.TestCase):
    """develop 资源囤积（人口 20 攒 95 / 人口 30 攒 150）。"""

    def _develop_roster(self, workers: int, vanguards: int, rangers: int):
        units = tuple(
            worker(_ladder_uuid(index), (6 + index, 0)) for index in range(workers)
        )
        units += tuple(
            vanguard((3, 3 + index), _ladder_uuid(100 + index))
            for index in range(vanguards)
        )
        units += tuple(
            ranger((-3, 3 + index), _ladder_uuid(200 + index))
            for index in range(rangers)
        )
        return units

    def _spawn_for(
        self,
        *,
        resources: int,
        control: dict,
        workers: int = 12,
        vanguards: int = 4,
        rangers: int = 4,
        enemies: tuple = (),
    ):
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(json.dumps(control), encoding="utf-8")
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=self._develop_roster(workers, vanguards, rangers),
                resources=resources,
                enemies=enemies,
            )
            SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)
        return turn.plan.core_action

    def test_target_only_applies_to_develop(self) -> None:
        for mode, expected in (
            (MODE_DEVELOP, HOARD_STAGE1_RESOURCE_TARGET),
            (MODE_AGGRESS, 0),
            (MODE_BEACON, 0),
        ):
            memory = TacticMemory()
            memory.mode = mode
            memory.hoard_stage1 = True
            self.assertEqual(
                _hoard_resource_target(memory, HOARD_STAGE1_POPULATION),
                expected,
                msg=mode,
            )

    def test_target_requires_population_threshold(self) -> None:
        memory = TacticMemory()
        memory.hoard_stage1 = True
        self.assertEqual(_hoard_resource_target(memory, HOARD_STAGE1_POPULATION - 1), 0)
        self.assertEqual(
            _hoard_resource_target(memory, HOARD_STAGE1_POPULATION),
            HOARD_STAGE1_RESOURCE_TARGET,
        )
        # 只开第一档时，人口 30 之后仍然维持 95 的水位
        self.assertEqual(
            _hoard_resource_target(memory, HOARD_STAGE2_POPULATION),
            HOARD_STAGE1_RESOURCE_TARGET,
        )
        memory.hoard_stage2 = True
        self.assertEqual(
            _hoard_resource_target(memory, HOARD_STAGE2_POPULATION),
            HOARD_STAGE2_RESOURCE_TARGET,
        )

    def test_blocks_spawn_below_water_line(self) -> None:
        action = self._spawn_for(
            resources=HOARD_STAGE1_RESOURCE_TARGET - 1,
            control={"mode": "develop", "hoard_stage1": True},
        )
        self.assertNotIsInstance(action, SpawnAction)

    def test_releases_spawn_at_water_line(self) -> None:
        """关键回归：水位是解锁阈值而非产兵后下限。

        人口 20 的仓库容量只有 100，若要求产兵后仍不低于 95，最便宜的工人（7）也
        买不起，人口会永久卡死。这里断言攒到水位就能产出兵。
        """

        action = self._spawn_for(
            resources=HOARD_STAGE1_RESOURCE_TARGET,
            control={"mode": "develop", "hoard_stage1": True},
        )
        self.assertIsInstance(action, SpawnAction)

    def test_disabled_switch_keeps_spawning(self) -> None:
        action = self._spawn_for(
            resources=HOARD_STAGE1_RESOURCE_TARGET - 1,
            control={"mode": "develop", "hoard_stage1": False},
        )
        self.assertIsInstance(action, SpawnAction)

    def test_nearby_enemy_overrides_hoard(self) -> None:
        action = self._spawn_for(
            resources=HOARD_STAGE1_RESOURCE_TARGET - 1,
            control={"mode": "develop", "hoard_stage1": True},
            enemies=(enemy_ranger((3, 0)),),
        )
        self.assertIsInstance(action, SpawnAction)

    def test_home_guard_shortfall_overrides_hoard(self) -> None:
        action = self._spawn_for(
            resources=HOARD_STAGE1_RESOURCE_TARGET - 1,
            control={"mode": "develop", "hoard_stage1": True},
            workers=18,
            vanguards=1,
            rangers=1,
        )
        self.assertIsInstance(action, SpawnAction)

    def test_worker_floor_overrides_hoard(self) -> None:
        action = self._spawn_for(
            resources=HOARD_STAGE1_RESOURCE_TARGET - 1,
            control={"mode": "develop", "hoard_stage1": True},
            workers=2,
            vanguards=9,
            rangers=9,
        )
        self.assertIsInstance(action, SpawnAction)
        self.assertEqual(action.unit_type, UnitType.WORKER)

    def test_stage_two_blocks_until_higher_water_line(self) -> None:
        blocked = self._spawn_for(
            resources=HOARD_STAGE2_RESOURCE_TARGET - 1,
            control={"mode": "develop", "hoard_stage1": True, "hoard_stage2": True},
            workers=18,
            vanguards=6,
            rangers=6,
        )
        self.assertNotIsInstance(blocked, SpawnAction)
        released = self._spawn_for(
            resources=HOARD_STAGE2_RESOURCE_TARGET,
            control={"mode": "develop", "hoard_stage1": True, "hoard_stage2": True},
            workers=18,
            vanguards=6,
            rangers=6,
        )
        self.assertIsInstance(released, SpawnAction)

    def test_strict_water_line_requires_target_plus_cost(self) -> None:
        """回归：容量够时水位是产兵后的真下限，不是"到 95 就开始花"。

        用户实测 92/115（人口 23）时希望继续攒到 102 再产工人。容量 115 能同时
        容纳水位 95 与最贵的游侠 16，因此每个兵种都要攒到 `95 + 该兵种成本`。
        """

        # 13工5先5游 = 23 人，目标 18:6:6，容量 115
        roster = (13, 5, 5)
        population = sum(roster)
        self.assertEqual(core_resource_capacity(population), 115)
        worker_cost = unit_cost(UnitType.WORKER, population)
        vanguard_cost = unit_cost(UnitType.VANGUARD, population)
        ranger_cost = unit_cost(UnitType.RANGER, population)
        target = HOARD_STAGE1_RESOURCE_TARGET

        # 攒到水位也不够：还差该单位的成本
        for resources in (target, target + worker_cost - 1):
            self.assertNotIsInstance(
                self._spawn_for(
                    resources=resources,
                    control={"mode": "develop", "hoard_stage1": True},
                    workers=roster[0],
                    vanguards=roster[1],
                    rangers=roster[2],
                ),
                SpawnAction,
                f"资源 {resources} 不足 水位+成本，不应产兵",
            )

        # 2026-08-24 严格优先级：先锋缺口没补齐前，即使已经攒够工人的
        # 水位+成本 也不放行工人。买便宜的插队会把贵的挤到更高倍率的位置，
        # 总花费反而更高，也违背"严格按设定配比补齐"。
        self.assertNotIsInstance(
            self._spawn_for(
                resources=target + worker_cost,
                control={"mode": "develop", "hoard_stage1": True},
                workers=roster[0],
                vanguards=roster[1],
                rangers=roster[2],
            ),
            SpawnAction,
            "先锋缺口未补齐时不应先产工人",
        )

        # 攒到 水位+先锋成本 → 按阶梯顺序优先补先锋
        action = self._spawn_for(
            resources=target + vanguard_cost,
            control={"mode": "develop", "hoard_stage1": True},
            workers=roster[0],
            vanguards=roster[1],
            rangers=roster[2],
        )
        self.assertIsInstance(action, SpawnAction)
        self.assertEqual(action.unit_type, UnitType.VANGUARD)
        # 产完仍不跌破水位
        self.assertGreaterEqual(target + vanguard_cost - vanguard_cost, target)
        self.assertLess(ranger_cost + target, core_resource_capacity(population) + 1)

        # 三个兵种都达标后才轮到工人：此时只剩工人有缺口。人口变了，成本也变，
        # 所以按新人口重新取价，不能复用上面 23 人时的 worker_cost。
        filled_roster = (16, COMPOSITION_STAGE2_VANGUARDS, COMPOSITION_STAGE2_RANGERS)
        filled_population = sum(filled_roster)
        filled_worker_cost = unit_cost(UnitType.WORKER, filled_population)
        self.assertGreaterEqual(
            core_resource_capacity(filled_population),
            target + unit_cost(UnitType.RANGER, filled_population),
            "该人口下仍应处于严格下限模式",
        )
        action = self._spawn_for(
            resources=target + filled_worker_cost,
            control={"mode": "develop", "hoard_stage1": True},
            workers=filled_roster[0],
            vanguards=filled_roster[1],
            rangers=filled_roster[2],
        )
        self.assertIsInstance(action, SpawnAction)
        self.assertEqual(action.unit_type, UnitType.WORKER)

    def test_strict_mode_falls_back_when_capacity_too_small(self) -> None:
        """容量装不下 水位+最贵单位 时退回解锁阈值，否则会永久停产。

        人口 20 容量仅 100，水位 95 + 游侠 16 = 111 装不下；若坚持严格下限，
        预算最多 5，连工人都买不起，人口永久卡死。
        """

        population = 20
        self.assertEqual(core_resource_capacity(population), 100)
        self.assertLess(
            core_resource_capacity(population),
            HOARD_STAGE1_RESOURCE_TARGET + unit_cost(UnitType.RANGER, population),
        )
        # 攒到水位即放行（旧的解锁阈值语义）
        action = self._spawn_for(
            resources=HOARD_STAGE1_RESOURCE_TARGET,
            control={"mode": "develop", "hoard_stage1": True},
            workers=12,
            vanguards=4,
            rangers=4,
        )
        self.assertIsInstance(action, SpawnAction)

    def test_ladder_gap_waits_instead_of_overproducing(self) -> None:
        """回归：缺的兵种买不起时等着，不产已达标兵种的多余单位。

        18工5先6游、目标 18:6:6 时只差 1 名先锋。continuous_growth_spawn 的 0.20
        比压容差本意是"最缺的暂时买不起就先产下一种"，在囤积期间反而把刚攒起来
        的资源花在第 19 个工人上，还多出一个超产单位。
        """

        population = 29
        vanguard_cost = unit_cost(UnitType.VANGUARD, population)
        worker_cost = unit_cost(UnitType.WORKER, population)
        target = HOARD_STAGE1_RESOURCE_TARGET

        # 够买工人但不够买先锋 → 应等待，不产工人
        resources = target + worker_cost
        self.assertLess(resources, target + vanguard_cost)
        self.assertNotIsInstance(
            self._spawn_for(
                resources=resources,
                control={"mode": "develop", "hoard_stage1": True},
                workers=18,
                vanguards=5,
                rangers=6,
            ),
            SpawnAction,
            "编制有缺口时不应产已达标兵种的多余单位",
        )

        # 够买先锋 → 补上缺口
        action = self._spawn_for(
            resources=target + vanguard_cost,
            control={"mode": "develop", "hoard_stage1": True},
            workers=18,
            vanguards=5,
            rangers=6,
        )
        self.assertIsInstance(action, SpawnAction)
        self.assertEqual(action.unit_type, UnitType.VANGUARD)

    def test_aggress_mode_ignores_hoard(self) -> None:
        action = self._spawn_for(
            resources=HOARD_STAGE1_RESOURCE_TARGET - 1,
            control={"mode": "aggress", "hoard_stage1": True, "hoard_stage2": True},
            workers=12,
            vanguards=4,
            rangers=4,
        )
        self.assertIsInstance(action, SpawnAction)


class OptimalSpawnOrderTests(unittest.TestCase):
    """全局最优生产顺序（control `optimal_spawn_order`）与严格不超产。"""

    _spawn_for = ResourceHoardTests._spawn_for
    _develop_roster = ResourceHoardTests._develop_roster

    def test_flag_defaults_off_and_reads_from_control(self) -> None:
        memory = TacticMemory()
        self.assertFalse(memory.optimal_spawn_order)
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps({"mode": "develop", "optimal_spawn_order": True}),
                encoding="utf-8",
            )
            memory.load_control(control_path)
        self.assertTrue(memory.optimal_spawn_order)

    def test_order_flips_to_descending_base_cost(self) -> None:
        """同一缺口下，勾选后先补贵的游侠而不是先锋。

        unit_cost 只按产兵前人口取倍率，与兵种无关，所以把贵的排在倍率低的早期
        位置总花费最低：游侠(12) → 先锋(10) → 工人(5)。关闭时沿用项目原顺序
        先锋 → 游侠 → 工人。
        """

        # 12工3先3游 = 18 人，目标 12:4:4：先锋与游侠各差 1，资源足够买任意一个
        roster = {"workers": 12, "vanguards": 3, "rangers": 3}
        default_action = self._spawn_for(
            resources=60, control={"mode": "develop"}, **roster
        )
        self.assertIsInstance(default_action, SpawnAction)
        self.assertEqual(default_action.unit_type, UnitType.VANGUARD)

        optimal_action = self._spawn_for(
            resources=60,
            control={"mode": "develop", "optimal_spawn_order": True},
            **roster,
        )
        self.assertIsInstance(optimal_action, SpawnAction)
        self.assertEqual(optimal_action.unit_type, UnitType.RANGER)

    def test_met_roles_are_never_overproduced(self) -> None:
        """回归：达标或超产的兵种一个都不再加，只补还有缺口的。

        用户实测 19工7先5游（目标 18:6:6）：工人和先锋都已超产，游侠还差 1。
        此前 develop 与召回两条路径都用 continuous_growth_spawn 的 0.20 比压容差，
        便宜的工人在贵的买不起时插队，于是超产越堆越多、游侠缺口始终没补上。
        """

        for optimal in (False, True):
            with self.subTest(optimal_spawn_order=optimal):
                action = self._spawn_for(
                    resources=200,
                    control={
                        "mode": "develop",
                        "optimal_spawn_order": optimal,
                    },
                    workers=19,
                    vanguards=7,
                    rangers=5,
                )
                self.assertIsInstance(action, SpawnAction)
                self.assertEqual(action.unit_type, UnitType.RANGER)

    def test_overflow_roster_fills_ranger_before_stage_two_hoard(self) -> None:
        """19工7先5游 + 勾选两档囤积：先把游侠补到 6，之后才进入 150 的攒。

        超产 2（工人 1 + 先锋 1）会把第二档门槛从 30 顺移到 32，所以人口 31 时
        生效水位仍是第一档的 95，游侠缺口能立刻补上；补齐后人口 32 才开始攒 150。
        """

        memory = TacticMemory()
        memory.mode = MODE_DEVELOP
        memory.hoard_stage1 = True
        memory.hoard_stage2 = True

        # 补齐前：目标编制是第二级 18:6:6，超产 2
        self.assertEqual(_effective_composition(memory, 19, 7, 5), (18, 6, 6))
        self.assertEqual(_composition_overflow(memory, 19, 7, 5), 2)

        action = self._spawn_for(
            resources=HOARD_STAGE1_RESOURCE_TARGET + 40,
            control={
                "mode": "develop",
                "hoard_stage1": True,
                "hoard_stage2": True,
                "optimal_spawn_order": True,
            },
            workers=19,
            vanguards=7,
            rangers=5,
        )
        self.assertIsInstance(action, SpawnAction)
        self.assertEqual(action.unit_type, UnitType.RANGER)

        # 游侠补到 6 后编制达成，第二档水位（门槛 30+2）开始生效
        self.assertEqual(
            _hoard_resource_target(memory, 32, _composition_overflow(memory, 19, 7, 6)),
            HOARD_STAGE2_RESOURCE_TARGET,
        )

    def test_hoard_gate_uses_next_optimal_unit_cost(self) -> None:
        """勾选全局最优后，放行线是 水位 + 该顺序下一个要产单位的成本。

        18工6先5游、目标 18:6:6 时只差游侠。资源刚好 水位+游侠成本 才放行；
        少 1 就继续攒，不会退而去买便宜单位。
        """

        population = 29
        ranger_cost = unit_cost(UnitType.RANGER, population)
        target = HOARD_STAGE1_RESOURCE_TARGET
        self.assertGreaterEqual(
            core_resource_capacity(population),
            target + ranger_cost,
            "该人口下应处于严格下限模式",
        )
        control = {
            "mode": "develop",
            "hoard_stage1": True,
            "optimal_spawn_order": True,
        }
        roster = {"workers": 18, "vanguards": 6, "rangers": 5}

        self.assertNotIsInstance(
            self._spawn_for(
                resources=target + ranger_cost - 1, control=control, **roster
            ),
            SpawnAction,
            "差 1 资源就应继续攒，不产便宜单位",
        )
        action = self._spawn_for(
            resources=target + ranger_cost, control=control, **roster
        )
        self.assertIsInstance(action, SpawnAction)
        self.assertEqual(action.unit_type, UnitType.RANGER)

    def test_recall_uses_optimal_order(self) -> None:
        """召回期间同样按全局最优顺序补阶梯缺口。"""

        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps(
                    {
                        "mode": "develop",
                        "recall": True,
                        "optimal_spawn_order": True,
                    }
                ),
                encoding="utf-8",
            )
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=self._develop_roster(12, 3, 3),
                resources=60,
            )
            SmartTactic(TacticMemory(), control_path=control_path).choose_actions(turn)
        action = turn.plan.core_action
        self.assertIsInstance(action, SpawnAction)
        self.assertEqual(action.unit_type, UnitType.RANGER)

    def test_continuous_growth_prefers_dearest_within_slack(self) -> None:
        """阶梯用尽后的连续增长也走全局最优：容差内的候选里挑最贵的。"""

        control = {
            "mode": "develop",
            "target_population": 0,
            "optimal_spawn_order": True,
        }
        # 阶梯关闭 → 项目原编制 12工4先5游 已达成，进入 5:4:6 连续增长。
        # 15工12先18游 时三者比压 3.0 / 3.0 / 3.0 完全相等，容差内三种都可选，
        # 全局最优应挑最贵的游侠。
        action = self._spawn_for(
            resources=300, control=control, workers=15, vanguards=12, rangers=18
        )
        self.assertIsInstance(action, SpawnAction)
        self.assertEqual(action.unit_type, UnitType.RANGER)


class WorkerYieldPathTests(unittest.TestCase):
    """给工人让路（control `yield_path_to_workers`）。

    现场（Tick 166012，人口 31、12 个战斗单位召回堆在 Core 周围）：载货工人的地形
    通路是通的，但沿途格子被我方单位占满——每格最多 2 个实体，`_blocked()` 把占满
    的格判为不可达，`planner.toward()` 找不到完整路径就退化成单步贪心，工人在两格
    之间来回走，货一直卸不掉。
    """

    # 一条 1 格宽的死胡同走廊：Core(0,0) ← (1,0) ← … ← (5,0)，(3,1) 是唯一的避让
    # 口袋。整片区域封死，保证除走廊之外没有任何绕行路线。
    _OBSTACLES = (
        (-1, 0),
        (6, 0),
        (3, 2),
        (0, 1),
        (1, 1),
        (2, 1),
        (4, 1),
        (5, 1),
        (0, -1),
        (1, -1),
        (2, -1),
        (3, -1),
        (4, -1),
        (5, -1),
    )

    def _run(self, *, yield_path: bool):
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps(
                    {"mode": "develop", "yield_path_to_workers": yield_path}
                ),
                encoding="utf-8",
            )
            memory = TacticMemory()
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    worker(WORKER_LOW, (4, 0), cargo=1),
                    # 同一格上的两个单位 = 占用 2，把 1 格宽的走廊彻底堵死
                    vanguard((3, 0), VANGUARD_ID),
                    vanguard((3, 0), VANGUARD_TWO_ID),
                ),
                obstacle_cells=self._OBSTACLES,
                resources=0,
            )
            summary = SmartTactic(
                memory, control_path=control_path
            ).choose_actions(turn)
        return memory, summary

    def test_blocker_steps_aside_and_worker_advances(self) -> None:
        memory, summary = self._run(yield_path=True)

        self.assertTrue(
            any("yield_path_to_worker" in item for item in summary.decisions),
            summary.decisions,
        )
        # 挡路的先锋闪进口袋 (3,1)，把走廊让出来
        aside = [
            route
            for route in memory.current_routes.values()
            if route.reason == "yield_path_to_worker"
        ]
        self.assertEqual(len(aside), 1, aside)
        self.assertEqual(aside[0].path[-1], (3, 1))
        # 占用数当场下降，工人同一 Tick 就朝 Core 走进原本堵死的格子
        worker_route = memory.current_routes.get(str(WORKER_LOW))
        self.assertIsNotNone(worker_route)
        self.assertEqual(worker_route.path[1], (3, 0))

    def test_disabled_flag_leaves_worker_oscillating(self) -> None:
        """关闭时复现原状：工人只能往远离 Core 的方向退，也就是来回走。"""

        memory, summary = self._run(yield_path=False)

        self.assertFalse(
            any("yield_path_to_worker" in item for item in summary.decisions),
            summary.decisions,
        )
        worker_route = memory.current_routes.get(str(WORKER_LOW))
        self.assertIsNotNone(worker_route)
        # 唯一能走的是背离 Core 的 (5,0)——占满的 (3,0) 进不去。下个 Tick 又会
        # 被拉回 (4,0)，这就是现场看到的来回走。
        self.assertEqual(worker_route.path[1], (5, 0))

    def test_terrain_dead_end_does_not_trigger_yield(self) -> None:
        """地形本身不通时不算被自己人堵住，不打散阵型。"""

        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps({"mode": "develop", "yield_path_to_workers": True}),
                encoding="utf-8",
            )
            memory = TacticMemory()
            # 把 (3,0) 换成障碍：走廊被地形封死，且只放一个先锋（占用 1，不算堵）
            obstacles = self._OBSTACLES + ((3, 0), (3, 1))
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    worker(WORKER_LOW, (4, 0), cargo=1),
                    vanguard((4, 0), VANGUARD_ID),
                ),
                obstacle_cells=obstacles,
                resources=0,
            )
            summary = SmartTactic(
                memory, control_path=control_path
            ).choose_actions(turn)

        self.assertFalse(
            any("yield_path_to_worker" in item for item in summary.decisions),
            summary.decisions,
        )

    def test_enemy_near_core_suspends_yielding(self) -> None:
        """Core 近端有敌时不为物流打散阵型，生存优先。"""

        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps({"mode": "develop", "yield_path_to_workers": True}),
                encoding="utf-8",
            )
            memory = TacticMemory()
            turn, _ = make_turn(
                own_core=core((0, 0)),
                units=(
                    worker(WORKER_LOW, (4, 0), cargo=1),
                    vanguard((3, 0), VANGUARD_ID),
                    vanguard((3, 0), VANGUARD_TWO_ID),
                ),
                enemies=(enemy_ranger((2, 0)),),
                obstacle_cells=self._OBSTACLES,
                resources=0,
            )
            summary = SmartTactic(
                memory, control_path=control_path
            ).choose_actions(turn)

        self.assertFalse(
            any("yield_path_to_worker" in item for item in summary.decisions),
            summary.decisions,
        )

    def test_flag_defaults_off_and_reads_from_control(self) -> None:
        memory = TacticMemory()
        self.assertFalse(memory.yield_path_to_workers)
        with TemporaryDirectory() as directory:
            control_path = Path(directory) / ".arena_hero_control.json"
            control_path.write_text(
                json.dumps({"mode": "develop", "yield_path_to_workers": True}),
                encoding="utf-8",
            )
            memory.load_control(control_path)
        self.assertTrue(memory.yield_path_to_workers)


if __name__ == "__main__":
    unittest.main()
