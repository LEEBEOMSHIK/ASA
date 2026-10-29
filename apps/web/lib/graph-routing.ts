export type Point = {x: number; y: number};

/** Keep the socket relative to the same snapshot used to route its wire. */
export function inputSocketOffset(route: {targetPoint: Point; target: Point}): number {
  return route.targetPoint.y - route.target.y;
}

function roundedRoute(points: Point[], maxRadius = 20): string {
  let path = `M ${points[0].x} ${points[0].y}`;
  for (let i = 1; i < points.length - 1; i++) {
    const previous = points[i - 1], corner = points[i], next = points[i + 1];
    const incoming = Math.hypot(corner.x - previous.x, corner.y - previous.y);
    const outgoing = Math.hypot(next.x - corner.x, next.y - corner.y);
    if (!incoming || !outgoing) continue;
    const radius = Math.min(maxRadius, incoming / 2, outgoing / 2);
    const before = {x: corner.x + (previous.x - corner.x) * radius / incoming, y: corner.y + (previous.y - corner.y) * radius / incoming};
    const after = {x: corner.x + (next.x - corner.x) * radius / outgoing, y: corner.y + (next.y - corner.y) * radius / outgoing};
    path += ` L ${before.x} ${before.y} Q ${corner.x} ${corner.y} ${after.x} ${after.y}`;
  }
  const end = points[points.length - 1];
  return `${path} L ${end.x} ${end.y}`;
}

export type Rect = Point & {width: number; height: number};
export type ConnectionRoute = {path: string; points?: Point[]; blocked: boolean};

function intersects(a: Point, b: Point, r: Rect): boolean {
  return Math.max(a.x, b.x) > r.x && Math.min(a.x, b.x) < r.x + r.width &&
    Math.max(a.y, b.y) > r.y && Math.min(a.y, b.y) < r.y + r.height;
}

function compact(points: Point[]): Point[] {
  const result: Point[] = [];
  for (const p of points) {
    const last = result.at(-1);
    if (last?.x === p.x && last.y === p.y) continue;
    const before = result.at(-2);
    if (before && last && ((before.x === last.x && last.x === p.x) || (before.y === last.y && last.y === p.y))) result.pop();
    result.push(p);
  }
  return result;
}

/** Port-aware routing. Rounded corners stay inside the obstacle clearance envelope.
 * The finite coordinate grid is bounded by the editor's 50-card limit; no pixel scan.
 * blocked is explicit when overlapping cards enclose a port or no safe lane exists.
 */
export function routeConnection(source: Rect, target: Rect, a: Point, b: Point, allRects: Rect[], occupied: Point[][] = [], orthogonal = false): ConnectionRoute {
  const rects = [...allRects, source, target];
  if (![a.x, a.y, b.x, b.y, ...rects.flatMap(r => [r.x, r.y, r.width, r.height])].every(Number.isFinite)) {
    return {path: '', blocked: true};
  }
  const clear = (p: Point, q: Point, obstacles: Rect[]) => !obstacles.some(r => intersects(p, q, r));
  const segments=occupied.flatMap(ps=>ps.slice(1).map((q,i)=>[ps[i],q]));
  const freeLane=(p:Point,q:Point)=>!segments.some(([u,v])=>{
    if(p.y===q.y && u.y===v.y) return Math.abs(p.y-u.y)<12 && Math.min(Math.max(p.x,q.x),Math.max(u.x,v.x))-Math.max(Math.min(p.x,q.x),Math.min(u.x,v.x))>0.1;
    if(p.x===q.x && u.x===v.x) return Math.abs(p.x-u.x)<12 && Math.min(Math.max(p.y,q.y),Math.max(u.y,v.y))-Math.max(Math.min(p.y,q.y),Math.min(u.y,v.y))>0.1;
    return false;
  });
  // A cubic stays inside its control hull, so this is a conservative exact safety check.
  if (!orthogonal && b.x > a.x && clear(a, b, rects)) return {path: wirePath(a, b, 0), blocked: false};
  for (const margin of [24, 2]) {
    const obstacles = rects.map(r => ({x: r.x-margin, y: r.y-margin, width: r.width+2*margin, height: r.height+2*margin}));
    const start = {x: Math.max(a.x, source.x+source.width+margin), y: a.y};
    const end = {x: Math.min(b.x, target.x-margin), y: b.y};
    if (!clear(a, start, rects) || !clear(end, b, rects) || !freeLane(a,start) || !freeLane(end,b)) continue;
    const safe = (ps: Point[]) => ps.slice(1).every((p, i) => clear(ps[i], p, obstacles) && freeLane(ps[i],p));
    const finish = (ps: Point[]): ConnectionRoute => {
      const points = compact([a, ...ps, b]);
      return {path: roundedRoute(points, Math.min(orthogonal?6:20, margin)), points, blocked: false};
    };
    const ys = [...new Set([start.y, end.y, ...segments.filter(([p,q])=>p.y===q.y).flatMap(([p])=>[p.y-12,p.y+12]), ...obstacles.flatMap(r => [r.y, r.y+r.height])])].sort((x,y) => x-y);
    const xs = [...new Set([start.x, end.x, ...segments.filter(([p,q])=>p.x===q.x).flatMap(([p])=>[p.x-12,p.x+12]), ...obstacles.flatMap(r => [r.x, r.x+r.width])])].sort((x,y) => x-y);
    const candidates = ys.map(y => [start, {x:start.x,y}, {x:end.x,y}, end]);
    candidates.sort((p,q) => length(p)-length(q));
    for (const ps of candidates) if (safe(ps)) return finish(ps);

    // A* on obstacle boundary coordinates handles staggered/maze-like layouts.
    const width = xs.length, size = width*ys.length;
    const index = (p: Point) => ys.indexOf(p.y)*width+xs.indexOf(p.x);
    const point = (id: number): Point => ({x: xs[id%width], y: ys[Math.floor(id/width)]});
    const first = index(start), goal = index(end);
    const costs = new Float64Array(size).fill(Infinity);
    const previous = new Int32Array(size).fill(-1);
    const heap: {id:number; score:number}[] = [];
    const push = (id: number, score: number) => {
      let i = heap.length; heap.push({id,score});
      while(i>0) { const parent = (i-1)>>1; if(heap[parent].score<=score) break; heap[i]=heap[parent]; i=parent; }
      heap[i]={id,score};
    };
    const pop = () => {
      const top=heap[0], tail=heap.pop()!;
      if(heap.length) {
        let i=0;
        while(i*2+1<heap.length) { let child=i*2+1; if(child+1<heap.length && heap[child+1].score<heap[child].score) child++;
          if(heap[child].score>=tail.score) break; heap[i]=heap[child]; i=child; }
        heap[i]=tail;
      }
      return top;
    };
    costs[first]=0; push(first,0);
    const visited = new Uint8Array(size);
    while(heap.length) {
      const {id}=pop(); if(visited[id]) continue; visited[id]=1;
      if(id===goal) {
        const ps: Point[]=[]; for(let at=goal; at!==-1; at=previous[at]) ps.push(point(at));
        return finish(ps.reverse());
      }
      const p=point(id), x=id%width, y=Math.floor(id/width);
      const adjacent=[x>0?id-1:-1, x+1<width?id+1:-1, y>0?id-width:-1, y+1<ys.length?id+width:-1];
      for(const next of adjacent) {
        if(next<0 || visited[next]) continue;
        const q=point(next), prev=previous[id]>=0?point(previous[id]):null;
        const turn=prev && ((prev.x===p.x)!==(p.x===q.x))?24:0;
        const cost=costs[id]+Math.abs(p.x-q.x)+Math.abs(p.y-q.y)+turn;
        if(cost>=costs[next] || !clear(p,q,obstacles) || !freeLane(p,q)) continue;
        costs[next]=cost; previous[next]=id;
        push(next,cost+Math.abs(q.x-end.x)+Math.abs(q.y-end.y));
      }
    }
  }
  return {path: wirePath(a,b,Math.max(...rects.map(r => r.y+r.height))), blocked:true};
}

function length(points: Point[]): number {
  return points.slice(1).reduce((sum,p,i) => sum+Math.abs(p.x-points[i].x)+Math.abs(p.y-points[i].y),0);
}

/** Keep vertical neighbours in their shared gap; only return edges need an outer lane. */
export function wirePath(a: Point, b: Point, bottom: number, gap?: number): string {
  if (b.x > a.x) {
    const bend = (b.x - a.x) / 2;
    return `M ${a.x} ${a.y} C ${a.x + bend} ${a.y}, ${b.x - bend} ${b.y}, ${b.x} ${b.y}`;
  }
  const lane = gap ?? bottom + 40;
  return roundedRoute([a, {x: a.x + 24, y: a.y}, {x: a.x + 24, y: lane},
    {x: b.x - 24, y: lane}, {x: b.x - 24, y: b.y}, b]);
}

export function verticalGap(source: {y: number; height: number}, target: {y: number; height: number}): number | undefined {
  const sourceBottom = source.y + source.height;
  const targetBottom = target.y + target.height;
  if (target.y >= sourceBottom) return (sourceBottom + target.y) / 2;
  if (source.y >= targetBottom) return (targetBottom + source.y) / 2;
  return undefined;
}

export type RoutedEdge = {id:string;source:string;target:string;port:string};
export type RoutedNode = Rect & {id:string;inputY?:number};
/** Stable batch routing reserves parallel lanes while allowing transverse crossings. */
export function routeConnections(nodes:RoutedNode[],edges:RoutedEdge[],output:(node:RoutedNode,edge:RoutedEdge)=>Point) {
  const occupied:Point[][]=[];
  const incoming=new Map<string,RoutedEdge[]>();
  const ordered=[...edges].sort((a,b)=>{
    const x=nodes.find(n=>n.id===a.source),y=nodes.find(n=>n.id===b.source);
    return (x?.y||0)-(y?.y||0)||(x?.x||0)-(y?.x||0)||a.port.localeCompare(b.port)||a.id.localeCompare(b.id);
  });
  for(const edge of ordered) incoming.set(edge.target,[...(incoming.get(edge.target)||[]),edge]);
  return ordered.flatMap(edge=>{
    const source=nodes.find(n=>n.id===edge.source),target=nodes.find(n=>n.id===edge.target);
    if(!source||!target)return [];
    const siblings=incoming.get(target.id)!;
    const index=siblings.indexOf(edge);
    const a=output(source,edge),b={x:target.x,y:target.y+(siblings.length===1?(target.inputY??40):20+(target.height-40)*(index+1)/(siblings.length+1))};
    let route=routeConnection(source,target,a,b,nodes,occupied,true);
    const crowded=route.blocked;
    if(crowded) route=routeConnection(source,target,a,b,nodes);
    if(route.points&&!route.blocked) occupied.push(route.points);
    return [{edge,...route,crowded,targetPoint:b}];
  });
}
