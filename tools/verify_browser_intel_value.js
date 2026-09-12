// 验证脚本：精确匹配能抓到的 RESOURCE 坐标 vs 策略自己的视野
//
// 目的：确认 browser intel 是否能提供 API 之外的额外资源信息。
// 只读 props.state.objects 里 kind==="RESOURCE" 的条目（TerrainView.positions），
// 这与 Python 侧 turn.resource_cells 的来源一致。若两者完全相同，说明浏览器旁路
// 拿不到额外信息；若浏览器更多，说明服务端下发范围大于策略采用范围。
//
// 用法：游戏页面按 F12，粘贴本文件全部内容回车。结果自动复制到剪贴板。
(() => {
  const CORE = [-286, -97];
  const dist = (a, b) => Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]);
  const isIntPair = (v) =>
    Array.isArray(v) && v.length === 2 && Number.isInteger(v[0]) && Number.isInteger(v[1]);

  let canvas = null;
  let bestArea = 0;
  for (const item of document.querySelectorAll("canvas")) {
    const rect = item.getBoundingClientRect();
    const area = rect.width * rect.height;
    if (area > bestArea) {
      bestArea = area;
      canvas = item;
    }
  }
  if (!canvas) {
    console.log("[验证] 未找到 canvas");
    return;
  }

  let fiber = null;
  let element = canvas;
  for (let depth = 0; element && depth < 6 && !fiber; depth += 1) {
    for (const key of Object.getOwnPropertyNames(element)) {
      if (key.startsWith("__reactFiber$") || key.startsWith("__reactInternalInstance$")) {
        fiber = element[key];
        break;
      }
    }
    element = element.parentElement;
  }
  if (!fiber) {
    console.log("[验证] 未找到 react fiber");
    return;
  }

  // 找 props.state.objects：服务端下发的当前 turn 视野对象数组
  let stateObjects = null;
  let exploredMap = null;
  let tick = null;
  const queue = [fiber];
  const seen = new Set();
  while (queue.length && seen.size < 3000) {
    const node = queue.shift();
    if (!node || seen.has(node)) continue;
    seen.add(node);
    const props = node.memoizedProps;
    if (props && typeof props === "object") {
      if (!stateObjects && props.state && Array.isArray(props.state.objects)) {
        stateObjects = props.state.objects;
        tick = props.state.tick ?? props.tick ?? null;
      }
      if (!exploredMap && props.explored instanceof Map) {
        exploredMap = props.explored;
      }
    }
    queue.push(node.child, node.sibling, node.return, node.alternate);
  }

  const lines = [];
  const push = (text) => {
    lines.push(text);
    console.log(text);
  };

  push("===== browser intel 价值验证 =====");
  push(`Core=${JSON.stringify(CORE)}  tick=${tick}`);
  if (!stateObjects) {
    push("未找到 props.state.objects，无法验证");
    return;
  }
  // PLACEHOLDER_ANALYSIS

  // ---- 1. 精确匹配：objects 里 kind==="RESOURCE" 的 positions ----
  const resourceCells = [];
  const kindCounts = new Map();
  for (const object of stateObjects) {
    if (!object || typeof object !== "object") continue;
    const kind = String(object.kind ?? "?");
    kindCounts.set(kind, (kindCounts.get(kind) || 0) + 1);
    if (kind !== "RESOURCE") continue;
    // TerrainView 用复数 positions；兼容单数 position 以防结构差异
    if (Array.isArray(object.positions)) {
      for (const position of object.positions) {
        if (isIntPair(position)) resourceCells.push(position);
      }
    } else if (isIntPair(object.position)) {
      resourceCells.push(object.position);
    }
  }
  const unique = [...new Set(resourceCells.map((p) => `${p[0]},${p[1]}`))].map((k) =>
    k.split(",").map(Number),
  );
  unique.sort((a, b) => dist(CORE, a) - dist(CORE, b));

  push("");
  push("【1. props.state.objects 的 kind 构成】");
  for (const [kind, count] of [...kindCounts].sort((a, b) => b[1] - a[1])) {
    push(`  ${String(count).padStart(4)} × ${kind}`);
  }

  push("");
  push(`【2. 精确匹配抓到的 RESOURCE 坐标】共 ${unique.length} 个`);
  if (!unique.length) {
    push("  （当前视野内没有资源格）");
  }
  for (const position of unique.slice(0, 40)) {
    push(`  ${JSON.stringify(position)}  距 Core ${dist(CORE, position)} 格`);
  }
  if (unique.length > 40) push(`  ...另有 ${unique.length - 40} 个`);

  // ---- 2. 距离分布：判断是否超出工人当前视野范围 ----
  if (unique.length) {
    const distances = unique.map((p) => dist(CORE, p)).sort((a, b) => a - b);
    push("");
    push("【3. 距 Core 距离分布】");
    push(
      `  最近 ${distances[0]} / 中位 ${distances[Math.floor(distances.length / 2)]} / 最远 ${distances[distances.length - 1]} 格`,
    );
    const buckets = [
      [0, 16],
      [17, 32],
      [33, 48],
      [49, 64],
      [65, 128],
      [129, 99999],
    ];
    for (const [low, high] of buckets) {
      const count = distances.filter((d) => d >= low && d <= high).length;
      if (count) {
        push(`  ${String(low).padStart(4)}-${high > 9999 ? "∞" : String(high).padEnd(4)} 格: ${count} 个`);
      }
    }
  }

  // ---- 3. explored 缓存里到底有没有 RESOURCE ----
  push("");
  push("【4. props.explored 已探索缓存的 kind 构成】");
  if (!exploredMap) {
    push("  未找到 props.explored");
  } else {
    const exploredKinds = new Map();
    const exploredResources = [];
    let index = 0;
    for (const [key, value] of exploredMap) {
      if (index++ > 20000) break;
      const kind = String((value && value.kind) ?? "?");
      exploredKinds.set(kind, (exploredKinds.get(kind) || 0) + 1);
      if (kind === "RESOURCE") {
        const parts = String(key).split(",").map(Number);
        if (parts.length === 2 && parts.every(Number.isInteger)) {
          exploredResources.push(parts);
        } else if (value && isIntPair(value.position)) {
          exploredResources.push(value.position);
        }
      }
    }
    push(`  缓存总格数 ${exploredMap.size}`);
    for (const [kind, count] of [...exploredKinds].sort((a, b) => b[1] - a[1])) {
      push(`  ${String(count).padStart(5)} × ${kind}`);
    }
    push("");
    push(`【5. 关键判定：explored 里的 RESOURCE】共 ${exploredResources.length} 个`);
    if (!exploredResources.length) {
      push("  → 客户端不缓存资源记忆，browser intel 拿不到 API 之外的资源信息");
    } else {
      exploredResources.sort((a, b) => dist(CORE, a) - dist(CORE, b));
      const visibleKeys = new Set(unique.map((p) => `${p[0]},${p[1]}`));
      const extra = exploredResources.filter((p) => !visibleKeys.has(`${p[0]},${p[1]}`));
      push(`  其中不在当前视野 objects 里的: ${extra.length} 个 ← 这才是额外信息`);
      for (const position of extra.slice(0, 30)) {
        push(`    ${JSON.stringify(position)}  距 Core ${dist(CORE, position)} 格`);
      }
      if (extra.length > 30) push(`    ...另有 ${extra.length - 30} 个`);
    }
  }

  // ---- 4. 对照线上现有实现抓到了什么 ----
  push("");
  push("【6. 对照：线上 findResourceCells 当前抓到的】");
  const overlayCore = globalThis.ArenaHeroOverlayCore;
  if (!overlayCore || typeof overlayCore.findResourceCells !== "function") {
    push("  叠加层未注入（ArenaHeroOverlayCore 不可用），跳过对照");
  } else {
    const captured = overlayCore.findResourceCells(canvas);
    push(`  抓到 ${captured.length} 个坐标`);
    const visibleKeys = new Set(unique.map((p) => `${p[0]},${p[1]}`));
    const hit = captured.filter((p) => isIntPair(p) && visibleKeys.has(`${p[0]},${p[1]}`));
    push(`  其中真的是 RESOURCE 的: ${hit.length} 个`);
    push(
      `  误报率: ${captured.length ? Math.round((100 * (captured.length - hit.length)) / captured.length) : 0}%`,
    );
    const missed = unique.filter(
      (p) => !captured.some((c) => isIntPair(c) && c[0] === p[0] && c[1] === p[1]),
    );
    push(`  漏抓的真 RESOURCE: ${missed.length} 个 ${JSON.stringify(missed.slice(0, 10))}`);
  }

  const report = lines.join("\n");
  try {
    copy(report);
    console.log("%c报告已复制到剪贴板", "color:#9bcbbd");
  } catch (error) {
    console.log("copy() 不可用，请手动全选控制台输出");
  }
  window.__arenaHeroVerify = { resourceCells: unique, report };
})();

