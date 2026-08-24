"use strict";

const assert = require("node:assert/strict");
const overlay = require("./overlay-core.js");

const camera = { x: 10.5, y: -4.25, cell: 32 };
const screen = overlay.gridToScreen([13, -2], camera, 1000, 600);
assert.deepEqual(screen, { x: 580, y: 372 });
assert.deepEqual(
  overlay.screenToGrid(screen.x, screen.y, camera, 1000, 600),
  [13, -2],
);
assert.equal(overlay.gridDistance([13, -2], [10, 4]), 9);
assert.equal(overlay.gridDistance([13, -2], null), null);
assert.equal(overlay.estimateTravelMinutes(12, 5), 1);
assert.equal(overlay.estimateTravelMinutes(0, 5), 0);

assert.deepEqual(
  overlay.pathTurnPoints([
    [0, 0],
    [0, -1],
    [0, -2],
    [1, -2],
    [2, -2],
    [2, -1],
  ]),
  [
    [0, 0],
    [0, -2],
    [2, -2],
    [2, -1],
  ],
);

const canvas = { parentElement: null };
Object.defineProperty(canvas, "__reactFiber$overlayTest", {
  value: {
    memoizedState: {
      memoizedState: { x: -34.5, y: 85.25, cell: 28 },
      baseState: null,
      queue: null,
      next: null,
    },
    memoizedProps: null,
    pendingProps: null,
    stateNode: null,
    return: null,
    alternate: null,
  },
});
assert.deepEqual(overlay.findCameraState(canvas), {
  x: -34.5,
  y: 85.25,
  cell: 28,
});

let centeredCamera = null;
const focusCanvas = { parentElement: null };
Object.defineProperty(focusCanvas, "__reactFiber$focusTest", {
  value: {
    memoizedState: {
      memoizedState: { width: 800, height: 600 },
      baseState: null,
      queue: { dispatch: () => {} },
      next: {
        memoizedState: { x: 8, y: -3, cell: 44 },
        baseState: null,
        queue: {
          dispatch: (update) => {
            centeredCamera = update({ x: 8, y: -3, cell: 44 });
          },
        },
        next: null,
      },
    },
    memoizedProps: null,
    pendingProps: null,
    stateNode: null,
    return: null,
    alternate: null,
  },
});
assert.equal(overlay.centerCameraOn(focusCanvas, [-52, -210]), true);
assert.deepEqual(centeredCamera, { x: -52, y: -210, cell: 44 });
assert.equal(overlay.centerCameraOn({}, [-52, -210]), false);

// 资源识别按游戏数据契约精确读取：
//   props.state.objects 里 kind==="RESOURCE" 的 TerrainView（坐标在复数 positions）
//   props.explored 缓存里 kind==="RESOURCE" 的格（工人看过、当前已离开视野的水晶）
const resourceCanvas = { parentElement: null };
const exploredCache = new Map([
  ["-40,20", { position: [-40, 20], kind: "EMPTY" }],
  ["-41,20", { position: [-41, 20], kind: "OBSTACLE" }],
  ["-23,86", { position: [-23, 86], kind: "RESOURCE" }],
  // value 里没有 position 时回退用 "x,y" 形式的键
  ["-90,120", { kind: "RESOURCE" }],
]);
Object.defineProperty(resourceCanvas, "__reactFiber$resourceTest", {
  value: {
    memoizedProps: {
      state: {
        objects: [
          { kind: "RESOURCE", positions: [[-62, 68], [-61, 76]] },
          { kind: "OBSTACLE", positions: [[-10, 10], [-11, 10]] },
          { kind: "CORE", position: [0, 0], hp: 5 },
          { kind: "UNIT", position: [1, 0] },
        ],
      },
      explored: exploredCache,
    },
    memoizedState: null,
    pendingProps: null,
    stateNode: null,
    child: null,
    sibling: null,
    return: null,
    alternate: null,
  },
});
assert.deepEqual(
  overlay.findResourceCells(resourceCanvas).sort((a, b) => a[0] - b[0] || a[1] - b[1]),
  [
    [-90, 120],
    [-62, 68],
    [-61, 76],
    [-23, 86],
  ].sort((a, b) => a[0] - b[0] || a[1] - b[1]),
  "只取 RESOURCE，OBSTACLE/EMPTY/CORE/UNIT 一律忽略",
);

// 回归：字段名含 "ore" 的容器（如 explored）不再被误当资源。
// 旧实现用 /(resource|mine|ore|...)/i 匹配字段名，"expl-ore-d" 命中 ore，
// 导致 2 万多格空地和岩石被当成资源点，实测误报率 100%。
{
  const trapCanvas = { parentElement: null };
  const trapExplored = new Map();
  for (let index = 0; index < 300; index += 1) {
    trapExplored.set(`${-500 + index},-300`, {
      position: [-500 + index, -300],
      kind: index % 2 ? "EMPTY" : "OBSTACLE",
    });
  }
  Object.defineProperty(trapCanvas, "__reactFiber$trapTest", {
    value: {
      memoizedProps: {
        explored: trapExplored,
        // 这些字段名都含资源关键词，但不符合数据契约，必须被忽略
        store: [[1, 1], [2, 2]],
        ignore: { position: [3, 3] },
        resourceSprites: [{ x: 4, y: 4, name: "" }],
      },
      memoizedState: null,
      pendingProps: null,
      stateNode: null,
      child: null,
      sibling: null,
      return: null,
      alternate: null,
    },
  });
  assert.deepEqual(
    overlay.findResourceCells(trapCanvas),
    [],
    "含 ore/resource 字样但非 RESOURCE 契约的数据必须全部忽略",
  );
}

// 兄弟组件里的状态也要能抓到：旧实现只沿 return/alternate 向上，整支 sibling 会漏掉。
{
  const siblingCanvas = { parentElement: null };
  Object.defineProperty(siblingCanvas, "__reactFiber$siblingTest", {
    value: {
      memoizedProps: null,
      memoizedState: null,
      pendingProps: null,
      stateNode: null,
      child: {
        memoizedProps: null,
        memoizedState: null,
        pendingProps: null,
        stateNode: null,
        child: null,
        sibling: {
          memoizedProps: {
            state: { objects: [{ kind: "RESOURCE", positions: [[7, 7]] }] },
          },
          memoizedState: null,
          pendingProps: null,
          stateNode: null,
          child: null,
          sibling: null,
          return: null,
          alternate: null,
        },
        return: null,
        alternate: null,
      },
      sibling: null,
      return: null,
      alternate: null,
    },
  });
  assert.deepEqual(overlay.findResourceCells(siblingCanvas), [[7, 7]]);
}

assert.deepEqual(overlay.findResourceCells({}), [], "无 fiber 时返回空数组");

// 误报兜底过滤仍然生效：万一游戏改数据结构，成片坐标不至于灌进策略。
{
  const dense = [];
  for (let bx = 0; bx < 8; bx += 1) {
    for (let by = 0; by < 8; by += 1) {
      dense.push([-128 + bx, -240 + by]); // 单 8x8 区块 64 格全满
    }
  }
  const fakeCanvas = { parentElement: null };
  Object.defineProperty(fakeCanvas, "__reactFiber$denseTest", {
    value: {
      memoizedProps: {
        state: {
          objects: [
            { kind: "RESOURCE", positions: [...dense, [-62, 68], [-61, 76]] },
          ],
        },
      },
      memoizedState: null,
      pendingProps: null,
      stateNode: null,
      child: null,
      sibling: null,
      return: null,
      alternate: null,
    },
  });
  assert.deepEqual(
    overlay.findResourceCells(fakeCanvas).sort((a, b) => a[0] - b[0]),
    [
      [-62, 68],
      [-61, 76],
    ].sort((a, b) => a[0] - b[0]),
  );
}

assert.deepEqual(
  overlay.normalizeSettings({
    lineWidth: 99,
    opacity: 0,
    workerColor: "#ABCDEF",
    rangerColor: "invalid",
    showRoutes: false,
  }),
  {
    ...overlay.DEFAULT_SETTINGS,
    showRoutes: false,
    lineWidth: 5,
    opacity: 0.1,
    workerColor: "#abcdef",
  },
);

assert.deepEqual(
  overlay.normalizeLogs({
    latest_tick: 9,
    entries: [
      {
        tick: 9,
        event_id: "event-9",
        category: "战斗",
        level: "danger",
        title: "单位阵亡",
        message: "先锋#4 阵亡",
        position: [3, -2],
      },
      { tick: "bad", event_id: "ignored", title: "x", message: "y" },
    ],
  }),
  {
    version: 1,
    latest_tick: 9,
    entries: [
      {
        version: 1,
        recorded_at: null,
        tick: 9,
        event_id: "event-9",
        source: "server",
        category: "战斗",
        level: "danger",
        title: "单位阵亡",
        message: "先锋#4 阵亡",
        event_type: null,
        reason_code: null,
        position: [3, -2],
        actor: null,
        target: null,
      },
    ],
  },
);

const desktopLayout = overlay.calculateControlLayout(
  { left: 100, top: 50, width: 1200, height: 700 },
  62,
  900,
);
assert.deepEqual(desktopLayout.dock, {
  left: 110,
  top: 60,
  width: 760,
  height: 62,
});
assert.equal(desktopLayout.stats.top, 130);
assert.equal(desktopLayout.stats.left, 110);
assert.equal(desktopLayout.stats.width, 390);
assert.equal(desktopLayout.stats.maxHeight, 610);

const narrowLayout = overlay.calculateControlLayout(
  { left: 0, top: 0, width: 360, height: 640 },
  112,
  640,
);
assert.deepEqual(narrowLayout.dock, {
  left: 10,
  top: 10,
  width: 340,
  height: 112,
});
assert.equal(narrowLayout.stats.left, 10);
assert.equal(narrowLayout.stats.width, 340);
assert.equal(narrowLayout.settings.left, 10);
assert.equal(narrowLayout.settings.top, 130);
assert.equal(narrowLayout.settings.maxHeight, 500);
for (const panel of [
  narrowLayout.settings,
  narrowLayout.stats,
  narrowLayout.locator,
  narrowLayout.logs,
]) {
  assert.ok(panel.top >= narrowLayout.dock.top + narrowLayout.dock.height + 8);
  assert.ok(panel.left >= 8);
  assert.ok(panel.left + panel.width <= 350);
}
assert.equal(overlay.calculateControlLayout({}, 20, 720), null);

// 资源误报过滤：零散水晶保留，成片地形整块丢弃。
{
  const scattered = [
    [0, 0],
    [40, 40],
    [80, 80],
  ];
  assert.deepEqual(
    overlay.pruneImplausibleResourceCells(scattered),
    scattered,
    "零散单格应原样保留",
  );

  // 紧邻小簇（4 格）保留：真实水晶可能成对或小簇出现。
  const smallCluster = [
    [0, 0],
    [0, 1],
    [1, 0],
    [1, 1],
  ];
  assert.equal(
    overlay.pruneImplausibleResourceCells(smallCluster).length,
    4,
    "4 格小簇应保留",
  );

  // 5 格连通块超过上限，整块丢弃。
  assert.deepEqual(
    overlay.pruneImplausibleResourceCells([
      [0, 0],
      [0, 1],
      [1, 0],
      [1, 1],
      [2, 1],
    ]),
    [],
    "超过 4 格的连通块应整块丢弃",
  );

  // 混合场景：成片地形被清除，远处零散水晶保留。
  const terrain = [];
  for (let x = 0; x < 10; x += 1) {
    for (let y = 0; y < 6; y += 1) {
      terrain.push([x, y]);
    }
  }
  assert.deepEqual(
    overlay
      .pruneImplausibleResourceCells(terrain.concat([[500, 500], [900, 900]]))
      .sort((a, b) => a[0] - b[0]),
    [
      [500, 500],
      [900, 900],
    ],
    "成片地形清除后应只剩零散水晶",
  );

  assert.deepEqual(overlay.pruneImplausibleResourceCells([]), []);
}

console.log("overlay-core tests passed");
