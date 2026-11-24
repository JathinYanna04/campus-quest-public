// A* over the campus walk graph (nodes in map px, undirected edges).

export class WalkGraph {
  constructor(graph) {
    this.nodes = graph.nodes.map(([x, y]) => ({ x, y }));
    this.adj = this.nodes.map(() => []);
    for (const [a, b] of graph.edges) {
      const d = Math.hypot(this.nodes[a].x - this.nodes[b].x, this.nodes[a].y - this.nodes[b].y);
      this.adj[a].push([b, d]);
      this.adj[b].push([a, d]);
    }
    this.edges = graph.edges;
  }

  nearestNode(x, y) {
    let best = 0;
    let bd = Infinity;
    for (let i = 0; i < this.nodes.length; i++) {
      const n = this.nodes[i];
      const d = (n.x - x) ** 2 + (n.y - y) ** 2;
      if (d < bd) {
        bd = d;
        best = i;
      }
    }
    return best;
  }

  // Closest point on any edge: lets a re-route start from wherever she is
  // standing mid-edge instead of snapping back to a node behind her.
  nearestEdgePoint(x, y) {
    let best = null;
    let bd = Infinity;
    for (const [a, b] of this.edges) {
      const p = this.nodes[a];
      const q = this.nodes[b];
      const dx = q.x - p.x;
      const dy = q.y - p.y;
      const len2 = dx * dx + dy * dy || 1;
      const t = Math.max(0, Math.min(1, ((x - p.x) * dx + (y - p.y) * dy) / len2));
      const px = p.x + dx * t;
      const py = p.y + dy * t;
      const d = (px - x) ** 2 + (py - y) ** 2;
      if (d < bd) {
        bd = d;
        best = { a, b, x: px, y: py };
      }
    }
    return best;
  }

  astar(starts, goal) {
    // starts: [{ node, cost }]
    const g = new Float64Array(this.nodes.length).fill(Infinity);
    const came = new Int32Array(this.nodes.length).fill(-1);
    const goalN = this.nodes[goal];
    const h = (i) => Math.hypot(this.nodes[i].x - goalN.x, this.nodes[i].y - goalN.y);
    const open = [];
    for (const s of starts) {
      if (s.cost < g[s.node]) {
        g[s.node] = s.cost;
        open.push([s.cost + h(s.node), s.node]);
      }
    }
    const closed = new Uint8Array(this.nodes.length);
    while (open.length) {
      let bi = 0;
      for (let i = 1; i < open.length; i++) if (open[i][0] < open[bi][0]) bi = i;
      const [, cur] = open.splice(bi, 1)[0];
      if (closed[cur]) continue;
      if (cur === goal) break;
      closed[cur] = 1;
      for (const [nb, d] of this.adj[cur]) {
        const ng = g[cur] + d;
        if (ng < g[nb]) {
          g[nb] = ng;
          came[nb] = cur;
          open.push([ng + h(nb), nb]);
        }
      }
    }
    if (!Number.isFinite(g[goal])) return null;
    const path = [];
    for (let c = goal; c !== -1; c = came[c]) path.push(c);
    return path.reverse();
  }

  // Full list of points from (x,y) to the target node, then on to `end`.
  route(x, y, goalNode, end) {
    const e = this.nearestEdgePoint(x, y);
    if (!e) return [end];
    const starts = [
      { node: e.a, cost: Math.hypot(this.nodes[e.a].x - e.x, this.nodes[e.a].y - e.y) },
      { node: e.b, cost: Math.hypot(this.nodes[e.b].x - e.x, this.nodes[e.b].y - e.y) },
    ];
    const nodes = this.astar(starts, goalNode);
    if (!nodes) return null;
    const pts = [];
    // Step onto the path first if she is off it (e.g. standing at a door).
    if (Math.hypot(e.x - x, e.y - y) > 1) pts.push({ x: e.x, y: e.y });
    for (const n of nodes) pts.push({ x: this.nodes[n].x, y: this.nodes[n].y });
    if (end) pts.push({ x: end.x, y: end.y });
    // Drop points that double back over the first edge.
    return simplify(pts);
  }
}

function simplify(pts) {
  const out = [];
  for (const p of pts) {
    const last = out[out.length - 1];
    if (last && Math.hypot(last.x - p.x, last.y - p.y) < 0.5) continue;
    out.push(p);
  }
  return out;
}

export function pointInPolygon(x, y, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
