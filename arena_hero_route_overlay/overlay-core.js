(function installArenaHeroOverlayCore(root, factory) {
  "use strict";

  const api = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.ArenaHeroOverlayCore = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, () => {
  "use strict";

  const DEFAULT_SETTINGS = Object.freeze({
    showRoutes: true,
    showUnitLabels: true,
    showResources: true,
    lineWidth: 1.2,
    opacity: 0.42,
    workerColor: "#4f9f8a",
    vanguardColor: "#bd8754",
    rangerColor: "#6689ad",
    resourceColor: "#c5a54d",
  });

  function clamp(value, minimum, maximum) {
    return Math.min(maximum, Math.max(minimum, value));
  }

  function color(value, fallback) {
    return typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value)
      ? value.toLowerCase()
      : fallback;
  }

  function normalizeSettings(value) {
    const source = value && typeof value === "object" ? value : {};
    const lineWidth = Number(source.lineWidth);
    const opacity = Number(source.opacity);
    return {
      showRoutes:
        typeof source.showRoutes === "boolean"
          ? source.showRoutes
          : DEFAULT_SETTINGS.showRoutes,
      showUnitLabels:
        typeof source.showUnitLabels === "boolean"
          ? source.showUnitLabels
          : DEFAULT_SETTINGS.showUnitLabels,
      showResources:
        typeof source.showResources === "boolean"
          ? source.showResources
          : DEFAULT_SETTINGS.showResources,
      lineWidth: Number.isFinite(lineWidth)
        ? clamp(lineWidth, 0.5, 5)
        : DEFAULT_SETTINGS.lineWidth,
      opacity: Number.isFinite(opacity)
        ? clamp(opacity, 0.1, 1)
        : DEFAULT_SETTINGS.opacity,
      workerColor: color(source.workerColor, DEFAULT_SETTINGS.workerColor),
      vanguardColor: color(source.vanguardColor, DEFAULT_SETTINGS.vanguardColor),
      rangerColor: color(source.rangerColor, DEFAULT_SETTINGS.rangerColor),
      resourceColor: color(source.resourceColor, DEFAULT_SETTINGS.resourceColor),
    };
  }

  function normalizePosition(value) {
    if (!Array.isArray(value) || value.length !== 2) {
      return null;
    }
    const x = Number(value[0]);
    const y = Number(value[1]);
    return Number.isFinite(x) && Number.isFinite(y) ? [x, y] : null;
  }

  function calculateControlLayout(rect, dockHeight, viewportHeight) {
    const left = Number(rect && rect.left);
    const top = Number(rect && rect.top);
    const width = Number(rect && rect.width);
    const height = Number(rect && rect.height);
    if (
      !Number.isFinite(left) ||
      !Number.isFinite(top) ||
      !Number.isFinite(width) ||
      !Number.isFinite(height) ||
      width <= 0 ||
      height <= 0
    ) {
      return null;
    }
    const margin = 10;
    const bottom = top + height;
    const availableWidth = Math.max(1, width - margin * 2);
    const dockWidth = Math.min(760, availableWidth);
    const dockTop = Math.max(8, top + margin);
    const dockBottom = dockTop + Math.max(0, Number(dockHeight) || 0);
    const panelTop = dockBottom + 8;
    const visibleBottom = Math.min(
      bottom - margin,
      Number.isFinite(Number(viewportHeight))
        ? Number(viewportHeight) - 8
        : bottom - margin,
    );
    const maxPanelHeight = Math.max(120, Math.floor(visibleBottom - panelTop));

    const panel = (preferredWidth) => {
      const panelWidth = Math.min(preferredWidth, availableWidth);
      return {
        left: Math.max(8, left + margin),
        top: panelTop,
        width: panelWidth,
        maxHeight: maxPanelHeight,
      };
    };

    return {
      dock: {
        left: Math.max(8, left + margin),
        top: dockTop,
        width: dockWidth,
        height: Math.max(0, Number(dockHeight) || 0),
      },
      settings: panel(300),
      stats: panel(390),
      locator: panel(330),
      logs: panel(520),
    };
  }

  function normalizeLogs(value) {
    const source = value && typeof value === "object" ? value : {};
    const levels = new Set(["debug", "info", "success", "warning", "danger"]);
    const rawEntries = Array.isArray(source.entries) ? source.entries : [];
    const entries = [];
    for (const entry of rawEntries.slice(-250)) {
      if (!entry || typeof entry !== "object") {
        continue;
      }
      const tick = Number(entry.tick);
      if (
        !Number.isInteger(tick) ||
        tick < 0 ||
        typeof entry.event_id !== "string" ||
        typeof entry.title !== "string" ||
        typeof entry.message !== "string"
      ) {
        continue;
      }
      entries.push({
        version: 1,
        recorded_at: typeof entry.recorded_at === "string" ? entry.recorded_at.slice(0, 48) : null,
        tick,
        event_id: entry.event_id.slice(0, 160),
        source: typeof entry.source === "string" ? entry.source.slice(0, 24) : "server",
        category: typeof entry.category === "string" ? entry.category.slice(0, 32) : "系统",
        level: levels.has(entry.level) ? entry.level : "info",
        title: entry.title.slice(0, 96),
        message: entry.message.slice(0, 512),
        event_type: typeof entry.event_type === "string" ? entry.event_type.slice(0, 96) : null,
        reason_code: typeof entry.reason_code === "string" ? entry.reason_code.slice(0, 96) : null,
        position: normalizePosition(entry.position),
        actor: typeof entry.actor === "string" ? entry.actor.slice(0, 96) : null,
        target: typeof entry.target === "string" ? entry.target.slice(0, 96) : null,
      });
    }
    const latest = Number(source.latest_tick);
    return {
      version: 1,
      latest_tick: Number.isInteger(latest) && latest >= 0
        ? latest
        : entries.reduce((maximum, entry) => Math.max(maximum, entry.tick), 0),
      entries,
    };
  }

  function normalizeCamera(value) {
    if (!value || typeof value !== "object") {
      return null;
    }
    const x = Number(value.x);
    const y = Number(value.y);
    const cell = Number(value.cell);
    if (
      !Number.isFinite(x) ||
      !Number.isFinite(y) ||
      !Number.isFinite(cell) ||
      cell < 2 ||
      cell > 512
    ) {
      return null;
    }
    return { x, y, cell };
  }

  function gridToScreen(position, camera, width, height) {
    const point = normalizePosition(position);
    const view = normalizeCamera(camera);
    if (!point || !view) {
      return null;
    }
    return {
      x: width / 2 + (point[0] - view.x) * view.cell,
      y: height / 2 + (point[1] - view.y) * view.cell,
    };
  }

  function screenToGrid(x, y, camera, width, height) {
    const view = normalizeCamera(camera);
    if (!view || !Number.isFinite(x) || !Number.isFinite(y)) {
      return null;
    }
    return [
      Math.floor(view.x + (x - width / 2) / view.cell + 0.5),
      Math.floor(view.y + (y - height / 2) / view.cell + 0.5),
    ];
  }

  function gridDistance(from, to) {
    const origin = normalizePosition(from);
    const target = normalizePosition(to);
    if (!origin || !target) {
      return null;
    }
    return Math.abs(origin[0] - target[0]) + Math.abs(origin[1] - target[1]);
  }

  function estimateTravelMinutes(distance, secondsPerTick = 5) {
    const cells = Number(distance);
    const seconds = Number(secondsPerTick);
    if (!Number.isFinite(cells) || cells < 0 || !Number.isFinite(seconds) || seconds <= 0) {
      return null;
    }
    return (cells * seconds) / 60;
  }

  function pathTurnPoints(path) {
    if (!Array.isArray(path)) {
      return [];
    }
    const points = [];
    for (const value of path) {
      const point = normalizePosition(value);
      if (!point) {
        continue;
      }
      const previous = points[points.length - 1];
      if (!previous || previous[0] !== point[0] || previous[1] !== point[1]) {
        points.push(point);
      }
    }
    if (points.length <= 2) {
      return points;
    }
    const turns = [points[0]];
    for (let index = 1; index < points.length - 1; index += 1) {
      const before = points[index - 1];
      const current = points[index];
      const after = points[index + 1];
      const incoming = [current[0] - before[0], current[1] - before[1]];
      const outgoing = [after[0] - current[0], after[1] - current[1]];
      if (incoming[0] !== outgoing[0] || incoming[1] !== outgoing[1]) {
        turns.push(current);
      }
    }
    turns.push(points[points.length - 1]);
    return turns;
  }

  function reactFiber(element) {
    let current = element;
    for (let depth = 0; current && depth < 6; depth += 1) {
      for (const key of Object.getOwnPropertyNames(current)) {
        if (key.startsWith("__reactFiber$") || key.startsWith("__reactInternalInstance$")) {
          return current[key];
        }
      }
      current = current.parentElement;
    }
    return null;
  }

  function cameraCandidates(value, baseScore, output) {
    const direct = normalizeCamera(value);
    if (direct) {
      output.push({ camera: direct, score: baseScore });
    }
    if (!value || typeof value !== "object") {
      return;
    }
    for (const key of ["current", "camera", "viewport", "view"]) {
      const nested = normalizeCamera(value[key]);
      if (nested) {
        output.push({ camera: nested, score: baseScore - 2 });
      }
    }
  }

  function inspectFiber(fiber, depth, output) {
    let hook = fiber && fiber.memoizedState;
    const seenHooks = new Set();
    let hookIndex = 0;
    while (hook && typeof hook === "object" && !seenHooks.has(hook) && hookIndex < 64) {
      seenHooks.add(hook);
      const score = 100 - depth * 3 - hookIndex * 0.01;
      cameraCandidates(hook.memoizedState, score, output);
      cameraCandidates(hook.baseState, score - 1, output);
      if (hook.queue) {
        cameraCandidates(hook.queue.lastRenderedState, score - 1, output);
      }
      hook = hook.next;
      hookIndex += 1;
    }
    cameraCandidates(fiber && fiber.memoizedProps, 35 - depth, output);
    cameraCandidates(fiber && fiber.pendingProps, 30 - depth, output);
    cameraCandidates(fiber && fiber.stateNode && fiber.stateNode.state, 25 - depth, output);
  }

  function findCameraState(element) {
    const first = reactFiber(element);
    if (!first) {
      return null;
    }
    const queue = [{ fiber: first, depth: 0 }];
    const seenFibers = new Set();
    const candidates = [];
    while (queue.length && seenFibers.size < 160) {
      const { fiber, depth } = queue.shift();
      if (!fiber || seenFibers.has(fiber) || depth > 32) {
        continue;
      }
      seenFibers.add(fiber);
      inspectFiber(fiber, depth, candidates);
      queue.push({ fiber: fiber.return, depth: depth + 1 });
      queue.push({ fiber: fiber.alternate, depth });
    }
    candidates.sort((left, right) => right.score - left.score);
    return candidates.length ? candidates[0].camera : null;
  }

  function centerCameraOn(element, position) {
    const target = normalizePosition(position);
    const first = reactFiber(element);
    if (!target || !first) {
      return false;
    }
    const queue = [{ fiber: first, depth: 0 }];
    const seenFibers = new Set();
    const candidates = [];
    while (queue.length && seenFibers.size < 160) {
      const { fiber, depth } = queue.shift();
      if (!fiber || seenFibers.has(fiber) || depth > 32) {
        continue;
      }
      seenFibers.add(fiber);
      let hook = fiber.memoizedState;
      const seenHooks = new Set();
      let hookIndex = 0;
      while (
        hook &&
        typeof hook === "object" &&
        !seenHooks.has(hook) &&
        hookIndex < 64
      ) {
        seenHooks.add(hook);
        const camera = normalizeCamera(hook.memoizedState);
        const dispatch = hook.queue && hook.queue.dispatch;
        if (camera && typeof dispatch === "function") {
          candidates.push({
            camera,
            dispatch,
            score: 100 - depth * 3 - hookIndex * 0.01,
          });
        }
        hook = hook.next;
        hookIndex += 1;
      }
      queue.push({ fiber: fiber.return, depth: depth + 1 });
      queue.push({ fiber: fiber.alternate, depth });
    }
    candidates.sort((leftCandidate, rightCandidate) =>
      rightCandidate.score - leftCandidate.score
    );
    const candidate = candidates[0];
    if (!candidate) {
      return false;
    }
    try {
      candidate.dispatch((current) => ({
        ...(current && typeof current === "object" ? current : candidate.camera),
        x: target[0],
        y: target[1],
        cell: candidate.camera.cell,
      }));
      return true;
    } catch (error) {
      return false;
    }
  }

  // 2026-08-24 改为按游戏数据契约精确读取，不再用关键词正则猜字段。
  // 旧实现用 /(resource|mine|ore|...)/i 匹配字段名，而 "explored"（已探索地图缓存）
  // 里含有 "ore"，于是 2 万多格空地和岩石被整体当成资源点，实测误报率 100%；
  // 这些数据还会吃光遍历预算，让真正的资源格没机会被访问。
  //
  // 两个数据源（与 arena_hero/models.py 的 TerrainView / 客户端缓存一致）：
  //   props.state.objects  — 服务端当前 Turn 下发的视野对象，kind==="RESOURCE"
  //                          时坐标在复数 positions 数组里。与策略同源。
  //   props.explored       — 客户端已探索缓存 Map，key 为 "x,y"，value.kind 可能是
  //                          EMPTY / OBSTACLE / RESOURCE。其中的 RESOURCE 是工人
  //                          曾经看到、当前已离开视野的水晶，这才是 API 之外的
  //                          增量信息，也是本功能存在的理由。
  const RESOURCE_KIND = "RESOURCE";
  const EXPLORED_SCAN_LIMIT = 60000;

  function integerPosition(value) {
    const point = normalizePosition(value);
    return point && Number.isInteger(point[0]) && Number.isInteger(point[1])
      ? [point[0], point[1]]
      : null;
  }

  // "x,y" 形式的缓存键
  function positionFromKey(key) {
    if (typeof key !== "string") {
      return null;
    }
    const parts = key.split(",");
    if (parts.length !== 2) {
      return null;
    }
    const x = Number(parts[0]);
    const y = Number(parts[1]);
    return Number.isInteger(x) && Number.isInteger(y) ? [x, y] : null;
  }

  function isResourceKind(value) {
    return (
      value !== null &&
      typeof value === "object" &&
      String(value.kind ?? value.type ?? "") === RESOURCE_KIND
    );
  }

  // 服务端下发的视野对象：TerrainView 用复数 positions，其它视图用单数 position。
  function collectStateObjectResources(objects, output) {
    if (!Array.isArray(objects)) {
      return;
    }
    for (const object of objects.slice(0, 4096)) {
      if (!isResourceKind(object)) {
        continue;
      }
      if (Array.isArray(object.positions)) {
        for (const candidate of object.positions.slice(0, 4096)) {
          const point = integerPosition(candidate);
          if (point) {
            output.set(`${point[0]},${point[1]}`, point);
          }
        }
        continue;
      }
      const single = integerPosition(object.position);
      if (single) {
        output.set(`${single[0]},${single[1]}`, single);
      }
    }
  }

  // 客户端已探索缓存：只取标记为 RESOURCE 的格。缓存会随探索持续增长（实测
  // 22010 格），因此按 EXPLORED_SCAN_LIMIT 兜底，避免极端情况下卡住渲染循环。
  function collectExploredResources(explored, output) {
    if (!(explored instanceof Map)) {
      return;
    }
    let scanned = 0;
    for (const [key, value] of explored) {
      if (scanned >= EXPLORED_SCAN_LIMIT) {
        break;
      }
      scanned += 1;
      if (!isResourceKind(value)) {
        continue;
      }
      const point = integerPosition(value.position) || positionFromKey(key);
      if (point) {
        output.set(`${point[0]},${point[1]}`, point);
      }
    }
  }

  function findResourceCells(element) {
    const first = reactFiber(element);
    if (!first) {
      return [];
    }
    const values = new Map();
    const seenFibers = new Set();
    // 完整遍历 fiber 树：旧实现只沿 return/alternate 向上，兄弟组件里的状态会被
    // 整支漏掉。数据实测挂在地图组件的 props 上，补 child/sibling 才稳妥。
    const queue = [first];
    while (queue.length && seenFibers.size < 3000) {
      const fiber = queue.shift();
      if (!fiber || seenFibers.has(fiber)) {
        continue;
      }
      seenFibers.add(fiber);
      for (const props of [fiber.memoizedProps, fiber.pendingProps]) {
        if (!props || typeof props !== "object") {
          continue;
        }
        if (props.state && typeof props.state === "object") {
          collectStateObjectResources(props.state.objects, values);
        }
        collectStateObjectResources(props.objects, values);
        collectExploredResources(props.explored, values);
      }
      queue.push(fiber.child, fiber.sibling, fiber.return, fiber.alternate);
    }
    return pruneImplausibleResourceCells(Array.from(values.values()));
  }

  // 合理性过滤：真实资源点在 8x8 区块内不会成片密集。
  // 误报特征 = 区块内几乎每格都是"资源"（游戏状态里存整片区域的数组被误当资源点）。
  // 8x8 区块 > 32 格（过半）即视为误报，整块丢弃，避免污染策略的 known_resource_cells。
  const RESOURCE_CELL_BLOCK = 8;
  const RESOURCE_CELL_BLOCK_QUOTA = 32;
  // 2026-08-24 第二道过滤：连通块大小。区块配额只能挡住"整块几乎填满"的误报，
  // 挡不住跨区块延伸的成片地形（实测一次快照 790 个坐标里，97% 属于 22 个大于
  // 4 格的连通块，最大的一块 77 格、包围盒 10x21、填充率 37%，正是岩石群的形态）。
  // 天然水晶是零散单格或紧邻的小簇，因此超过此大小的 8 邻域连通块整块丢弃。
  const RESOURCE_CELL_MAX_CLUSTER = 4;

  function pruneImplausibleResourceCells(positions) {
    if (!positions.length) {
      return [];
    }
    const counts = new Map();
    for (const position of positions) {
      const key = `${Math.floor(position[0] / RESOURCE_CELL_BLOCK)},${Math.floor(
        position[1] / RESOURCE_CELL_BLOCK,
      )}`;
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    const denseBlocks = new Set();
    for (const [key, count] of counts) {
      if (count > RESOURCE_CELL_BLOCK_QUOTA) {
        denseBlocks.add(key);
      }
    }
    let pruned = positions;
    if (denseBlocks.size) {
      pruned = positions.filter((position) => {
        const key = `${Math.floor(position[0] / RESOURCE_CELL_BLOCK)},${Math.floor(
          position[1] / RESOURCE_CELL_BLOCK,
        )}`;
        return !denseBlocks.has(key);
      });
    }
    return pruneLargeResourceClusters(pruned);
  }

  // 8 邻域洪泛，丢弃大于 RESOURCE_CELL_MAX_CLUSTER 的连通块。
  function pruneLargeResourceClusters(positions) {
    if (positions.length <= RESOURCE_CELL_MAX_CLUSTER) {
      return positions;
    }
    const index = new Map();
    for (const position of positions) {
      index.set(`${position[0]},${position[1]}`, position);
    }
    const visited = new Set();
    const kept = [];
    for (const [startKey] of index) {
      if (visited.has(startKey)) {
        continue;
      }
      const cluster = [];
      const stack = [startKey];
      visited.add(startKey);
      while (stack.length) {
        const key = stack.pop();
        const cell = index.get(key);
        cluster.push(cell);
        for (let dx = -1; dx <= 1; dx += 1) {
          for (let dy = -1; dy <= 1; dy += 1) {
            if (!dx && !dy) {
              continue;
            }
            const neighbour = `${cell[0] + dx},${cell[1] + dy}`;
            if (index.has(neighbour) && !visited.has(neighbour)) {
              visited.add(neighbour);
              stack.push(neighbour);
            }
          }
        }
      }
      if (cluster.length <= RESOURCE_CELL_MAX_CLUSTER) {
        kept.push(...cluster);
      }
    }
    return kept;
  }

  return {
    DEFAULT_SETTINGS,
    calculateControlLayout,
    centerCameraOn,
    findCameraState,
    findResourceCells,
    gridDistance,
    gridToScreen,
    estimateTravelMinutes,
    normalizeCamera,
    normalizeLogs,
    normalizePosition,
    normalizeSettings,
    pathTurnPoints,
    pruneImplausibleResourceCells,
    screenToGrid,
  };
});
