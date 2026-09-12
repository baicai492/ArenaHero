// 浏览器资源识别诊断脚本（临时工具，不参与 agent 运行时）
//
// 用途：找出游戏 React 状态里真实水晶存放在哪个字段，以及为什么
// overlay-core.js 的 findResourceCells 会漏抓近处水晶、却错抓远处成片地形。
// 与线上代码的关键差异：这里遍历完整 fiber 树（含 child/sibling），而线上只沿
// fiber.return 向上加 fiber.alternate，兄弟组件里的状态会被整支漏掉。
//
// 用法：在游戏页面（app.arenahero.io/arena）按 F12 打开控制台，粘贴本文件全部
// 内容并回车。结果打印到控制台，同时用 copy() 放进剪贴板，直接粘回对话即可。
(() => {
  // Core 当前坐标，取自叠加层左侧 FLEET INDEX 的 Core 条目；移动过就改这里。
  const CORE = [-286, -97];
  const NEAR = 80; // 认为"家附近"的曼哈顿距离
  const FIBER_LIMIT = 3000; // 最多访问多少个 fiber 节点
  const NODE_LIMIT = 400000; // 最多访问多少个对象节点

  const RESOURCE_KEY_RE = /(resource|mine|ore|mineral|crystal|deposit)/i;
  const dist = (a, b) => Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]);
  const isIntPair = (v) =>
    Array.isArray(v) &&
    v.length === 2 &&
    Number.isInteger(v[0]) &&
    Number.isInteger(v[1]);

  // ---- 1. 找面积最大的 canvas，与 overlay 的 findMapCanvas 选法一致 ----
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
    console.log("[诊断] 未找到 canvas，确认当前在游戏画面页");
    return;
  }

  // ---- 2. 从 canvas 向上找 react fiber ----
  let fiber = null;
  let element = canvas;
  for (let depth = 0; element && depth < 6 && !fiber; depth += 1) {
    for (const key of Object.getOwnPropertyNames(element)) {
      if (
        key.startsWith("__reactFiber$") ||
        key.startsWith("__reactInternalInstance$")
      ) {
        fiber = element[key];
        break;
      }
    }
    element = element.parentElement;
  }
  if (!fiber) {
    console.log("[诊断] 未找到 react fiber");
    return;
  }

  const paths = new Map(); // 路径 -> { coords, sample }
  const typeHits = new Map(); // "路径 :: type=值" -> 次数
  const seenObjects = new WeakSet();
  let nodeCount = 0;
  // PLACEHOLDER_WALK

  // ---- 3. 递归下钻任意对象，记录"每个路径下出现的整数坐标" ----
  // 与线上不同：不按资源关键词剪枝，任何路径都记录，这样才能发现真水晶被存在
  // 什么名字的字段里（可能压根不含 resource/crystal 字样）。
  function walk(value, path, depth) {
    if (nodeCount >= NODE_LIMIT || depth > 12) return;
    if (value === null || typeof value !== "object") return;
    if (seenObjects.has(value)) return;
    seenObjects.add(value);
    nodeCount += 1;

    // 整数坐标对：直接记在当前路径下
    if (isIntPair(value)) {
      record(path, value, null);
      return;
    }

    if (value instanceof Map) {
      let index = 0;
      for (const [mapKey, mapValue] of value) {
        if (index++ > 4096) break;
        if (isIntPair(mapValue)) record(path + "[Map]", mapValue, null);
        else if (typeof mapKey === "string" && /^-?\d+,-?\d+$/.test(mapKey)) {
          // 常见形态：Map 的 key 本身就是 "x,y"
          const parts = mapKey.split(",").map(Number);
          if (parts.every(Number.isInteger)) {
            record(path + "[MapKey]", parts, mapValue);
          }
        }
        walk(mapValue, path + "[Map]", depth + 1);
      }
      return;
    }

    if (value instanceof Set) {
      let index = 0;
      for (const item of value) {
        if (index++ > 4096) break;
        if (isIntPair(item)) record(path + "[Set]", item, null);
        else walk(item, path + "[Set]", depth + 1);
      }
      return;
    }

    if (Array.isArray(value)) {
      for (let index = 0; index < Math.min(value.length, 4096); index += 1) {
        const item = value[index];
        if (isIntPair(item)) record(path + "[]", item, null);
        else walk(item, path + "[]", depth + 1);
      }
      return;
    }

    // 普通对象：先看它自身是不是一条"带坐标的记录"
    for (const key of [
      "position",
      "coordinates",
      "coordinate",
      "cell",
      "gridPosition",
      "grid_position",
      "tile",
      "location",
      "pos",
    ]) {
      if (isIntPair(value[key])) {
        record(path + "." + key, value[key], value);
      }
    }
    if (Number.isInteger(value.x) && Number.isInteger(value.y)) {
      record(path + "{x,y}", [value.x, value.y], value);
    }

    let keyCount = 0;
    for (const key of Object.keys(value)) {
      if (keyCount++ > 200) break;
      if (key.startsWith("__react") || key === "stateNode") continue;
      walk(value[key], path + "." + key, depth + 1);
    }
  }

  function record(path, coord, owner) {
    let entry = paths.get(path);
    if (!entry) {
      entry = { coords: [], sample: null };
      paths.set(path, entry);
    }
    if (entry.coords.length < 8192) entry.coords.push(coord);
    if (!entry.sample && owner && typeof owner === "object") {
      // 存一份浅快照，用来判断这条记录是水晶、岩石还是别的东西
      const shallow = {};
      let count = 0;
      for (const key of Object.keys(owner)) {
        if (count++ > 14) break;
        const raw = owner[key];
        shallow[key] =
          raw === null || typeof raw !== "object"
            ? raw
            : Array.isArray(raw)
              ? `[Array ${raw.length}]`
              : `{${Object.keys(raw).slice(0, 6).join(",")}}`;
      }
      entry.sample = shallow;
    }
    // 同时统计 type/kind 之类的判别字段取值，便于区分水晶与地形
    if (owner) {
      for (const key of ["type", "kind", "resourceType", "category", "name", "terrain"]) {
        const raw = owner[key];
        if (raw !== undefined && (typeof raw === "string" || typeof raw === "number")) {
          const mapKey = `${path} :: ${key}=${raw}`;
          typeHits.set(mapKey, (typeHits.get(mapKey) || 0) + 1);
        }
      }
    }
  }

  // ---- 4. 遍历完整 fiber 树（含 child/sibling，这是与线上的关键差异）----
  const queue = [fiber];
  const seenFibers = new Set();
  while (queue.length && seenFibers.size < FIBER_LIMIT) {
    const node = queue.shift();
    if (!node || seenFibers.has(node)) continue;
    seenFibers.add(node);
    const name =
      (node.type &&
        (node.type.displayName || node.type.name || String(node.type).slice(0, 24))) ||
      "anon";
    walk(node.memoizedProps, `<${name}>.props`, 0);
    let hook = node.memoizedState;
    let hookIndex = 0;
    while (hook && typeof hook === "object" && hookIndex < 128) {
      walk(hook.memoizedState, `<${name}>.hook${hookIndex}`, 0);
      if (hook.queue) {
        walk(hook.queue.lastRenderedState, `<${name}>.hook${hookIndex}.queue`, 0);
      }
      hook = hook.next;
      hookIndex += 1;
    }
    queue.push(node.child, node.sibling, node.return, node.alternate);
  }
  // PLACEHOLDER_REPORT

  // ---- 5. 汇总：按"家附近坐标数"排序，家附近多的最可能是真水晶字段 ----
  const rows = [];
  for (const [path, entry] of paths) {
    const coords = entry.coords;
    if (!coords.length) continue;
    const unique = new Set(coords.map((c) => `${c[0]},${c[1]}`));
    const near = coords.filter((c) => dist(CORE, c) <= NEAR);
    const nearUnique = new Set(near.map((c) => `${c[0]},${c[1]}`));
    // 连通块最大尺寸：成片地形会很大，零散水晶接近 1
    const maxCluster = largestCluster(unique);
    rows.push({
      path,
      total: unique.size,
      near: nearUnique.size,
      maxCluster,
      nearSample: [...nearUnique]
        .map((k) => k.split(",").map(Number))
        .sort((a, b) => dist(CORE, a) - dist(CORE, b))
        .slice(0, 6),
      keyword: RESOURCE_KEY_RE.test(path),
      sample: entry.sample,
    });
  }
  rows.sort((a, b) => b.near - a.near || a.maxCluster - b.maxCluster);

  function largestCluster(keySet) {
    const points = new Set(keySet);
    let best = 0;
    const seen = new Set();
    for (const start of points) {
      if (seen.has(start)) continue;
      let size = 0;
      const stack = [start];
      seen.add(start);
      while (stack.length) {
        const key = stack.pop();
        size += 1;
        const [x, y] = key.split(",").map(Number);
        for (let dx = -1; dx <= 1; dx += 1) {
          for (let dy = -1; dy <= 1; dy += 1) {
            const nk = `${x + dx},${y + dy}`;
            if (points.has(nk) && !seen.has(nk)) {
              seen.add(nk);
              stack.push(nk);
            }
          }
        }
      }
      if (size > best) best = size;
    }
    return best;
  }

  const lines = [];
  const push = (text) => {
    lines.push(text);
    console.log(text);
  };

  push("===== ArenaHero 资源识别诊断 =====");
  push(
    `Core=${JSON.stringify(CORE)} | fiber 访问 ${seenFibers.size} 个 | 对象访问 ${nodeCount} 个 | 发现 ${rows.length} 条含坐标的路径`,
  );
  push("");
  push("【A. 家附近有坐标的路径】按家附近数量排序，maxCluster 越小越像零散水晶");
  const nearRows = rows.filter((r) => r.near > 0).slice(0, 25);
  if (!nearRows.length) push("  （无：家附近一个坐标都没抓到）");
  for (const row of nearRows) {
    push(
      `  近${String(row.near).padStart(4)} 总${String(row.total).padStart(5)} 团${String(row.maxCluster).padStart(4)} ${row.keyword ? "[含资源关键词]" : ""} ${row.path}`,
    );
    push(`        近处样例: ${JSON.stringify(row.nearSample)}`);
    if (row.sample) push(`        记录形态: ${JSON.stringify(row.sample)}`);
  }

  push("");
  push("【B. 坐标最多的路径】用于确认成片地形误报来自哪里");
  for (const row of [...rows].sort((a, b) => b.total - a.total).slice(0, 12)) {
    push(
      `  总${String(row.total).padStart(5)} 近${String(row.near).padStart(4)} 团${String(row.maxCluster).padStart(4)} ${row.keyword ? "[含资源关键词]" : ""} ${row.path}`,
    );
    if (row.sample) push(`        记录形态: ${JSON.stringify(row.sample)}`);
  }

  push("");
  push("【C. 判别字段取值统计】看哪个 type/kind 值对应水晶");
  const typeRows = [...typeHits.entries()].sort((a, b) => b[1] - a[1]).slice(0, 30);
  if (!typeRows.length) push("  （无 type/kind 字段）");
  for (const [key, count] of typeRows) push(`  ${String(count).padStart(5)} × ${key}`);

  push("");
  push("【D. 线上代码会命中的路径】含 resource/crystal 等关键词的");
  const keywordRows = rows.filter((r) => r.keyword).slice(0, 15);
  if (!keywordRows.length) push("  （无：说明线上的关键词剪枝可能完全找错了方向）");
  for (const row of keywordRows) {
    push(`  总${String(row.total).padStart(5)} 近${String(row.near).padStart(4)} 团${String(row.maxCluster).padStart(4)} ${row.path}`);
  }

  const report = lines.join("\n");
  try {
    copy(report);
    console.log("%c报告已复制到剪贴板，直接粘贴给 Claude 即可", "color:#9bcbbd");
  } catch (error) {
    console.log("copy() 不可用，请手动全选控制台输出");
  }
  window.__arenaHeroDiagnosis = { rows, typeHits, report };
})();

