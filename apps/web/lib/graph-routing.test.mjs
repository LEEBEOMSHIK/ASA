import test from 'node:test';
import assert from 'node:assert/strict';
import { routeConnections, routeConnection, verticalGap, wirePath } from './graph-routing.ts';

const rect = (x, y, height = 134) => ({x, y, width: 232, height});
function route(source, target, obstacles) {
  const a = {x: source.x + source.width, y: source.y + source.height - 28};
  const b = {x: target.x, y: target.y + 40};
  const result = routeConnection(source, target, a, b, obstacles);
  if (result.path) {
    const points = samples(result.path);
    assert.deepEqual(points[0], a);
    assert.deepEqual(points.at(-1), b);
  }
  return result;
}
function samples(path) {
  const tokens = path.match(/[MLQC]|-?\d+(?:\.\d+)?(?:e[+-]?\d+)?/gi);
  const result = []; let current;
  for (let i = 0; i < tokens.length;) {
    const command = tokens[i++];
    const count = {M: 1, L: 1, Q: 2, C: 3}[command];
    const ps = Array.from({length: count}, () => ({x: +tokens[i++], y: +tokens[i++]}));
    if (command === 'M') { current = ps[0]; result.push(current); continue; }
    for (let step = 1; step <= 100; step++) {
      const t = step / 100, u = 1 - t;
      result.push(Object.fromEntries(['x', 'y'].map(k => [k, command === 'L'
        ? u * current[k] + t * ps[0][k] : command === 'Q'
          ? u*u*current[k] + 2*u*t*ps[0][k] + t*t*ps[1][k]
          : u*u*u*current[k] + 3*u*u*t*ps[0][k] + 3*u*t*t*ps[1][k] + t*t*t*ps[2][k]])));
    }
    current = ps.at(-1);
  }
  return result;
}
function assertClear(result, obstacles) {
  assert.equal(result.blocked, false);
  for (const point of samples(result.path)) {
    assert.ok(Number.isFinite(point.x) && Number.isFinite(point.y));
    assert.ok(!obstacles.some(r => point.x > r.x + 1e-7 && point.x < r.x+r.width-1e-7 && point.y > r.y+1e-7 && point.y < r.y+r.height-1e-7), `path intersects a card at ${JSON.stringify(point)}`);
  }
}

test('forward edge avoids an unrelated intervening card, including its curved corners', () => {
  const nodes = [rect(0, 100), rect(700, 100), rect(350, 60, 220)];
  assertClear(route(nodes[0], nodes[1], nodes), nodes);
});

test('obstacle routing keeps unobstructed close forward edges cubic', () => {
  for (const gap of [1, 10, 40, 60, 100]) {
    const nodes = [rect(0, 100), rect(232+gap, 50)];
    const result = route(nodes[0], nodes[1], nodes);
    assert.match(result.path, / C /);
    assertClear(result, nodes);
  }
});

test('vertical neighbours, branches, backward edges and cycles avoid every card', () => {
  const nodes = [rect(100,100), rect(100,290,178), rect(430,90), rect(430,320), rect(780,230,90)];
  for (const [from,to] of [[0,1],[1,0],[0,2],[0,3],[2,4],[3,4],[4,0],[3,2]]) {
    const result=route(nodes[from],nodes[to],nodes);
    assertClear(result,nodes);
    assert.equal(result.path,route(nodes[from],nodes[to],nodes).path, 'deterministic routing');
  }
});

test('narrow two-pixel gaps remain routable', () => {
  const nodes=[rect(100,100),rect(100,236),rect(430,100),rect(430,236)];
  for(const [from,to] of [[0,1],[3,0],[1,2]]) assertClear(route(nodes[from],nodes[to],nodes),nodes);
});

test('overlap enclosing a port is explicitly blocked rather than claiming a safe path', () => {
  const nodes=[rect(100,100),rect(300,100),rect(800,100)];
  const result=route(nodes[0],nodes[2],nodes);
  assert.equal(result.blocked,true);
  assert.ok(!/NaN|Infinity/.test(result.path));
});

test('invalid numeric geometry is explicitly blocked without an invalid SVG path', () => {
  const nodes=[rect(0,0),rect(Infinity,100)];
  assert.equal(route(nodes[0],nodes[1],nodes).blocked,true);
  assert.ok(!/NaN|Infinity/.test(route(nodes[0],nodes[1],nodes).path));
});

test('supported cap: 50 cards and 100 mixed directional edges stay clear and bounded', t => {
  const nodes=Array.from({length:50},(_,i)=>rect(50+(i%10)*310,50+Math.floor(i/10)*250,90+(i%3)*44));
  const routes=[];
  const began=performance.now();
  for(let i=0;i<100;i++) {
    const from=i%50, to=(from+1+(i*17)%49)%50;
    const source=nodes[from], target=nodes[to];
    routes.push(routeConnection(source,target,{x:source.x+source.width,y:source.y+source.height-28},{x:target.x,y:target.y+40},nodes));
  }
  const elapsed=performance.now()-began;
  t.diagnostic(`100 routes through 50 cards: ${elapsed.toFixed(1)}ms`);
  assert.ok(elapsed<1000, `routing exceeded 1 second: ${elapsed}ms`);
  for(const result of routes) assertClear(result,nodes);
});

test('staggered barriers require several turns without cutting rounded corners', () => {
  const nodes=[rect(0,300),rect(1900,300),rect(350,0,420),rect(680,260,440),rect(1010,0,420),rect(1340,260,440),rect(240,-100,300),rect(240,500,300),rect(1700,-100,300),rect(1700,500,300)];
  const result=route(nodes[0],nodes[1],nodes);
  assertClear(result,nodes);
  assert.ok(result.points.length>=8, 'barriers require more than a single outside lane');
});

test('supported cap with staggered coordinates: 50 cards and 100 edges avoid all cards', t => {
  let seed=8;
  const jitter=() => {
    seed=(Math.imul(seed,1664525)+1013904223)>>>0;
    return seed%70;
  };
  const nodes=Array.from({length:50},(_,i)=>rect(50+(i%10)*310+jitter(),50+Math.floor(i/10)*250+jitter(),90+(i%3)*44));
  const routes=[];
  const began=performance.now();
  for(let i=0;i<100;i++) {
    const source=nodes[i%50], target=nodes[(i%50+1+(i*17)%49)%50];
    routes.push(routeConnection(source,target,{x:source.x+source.width,y:source.y+source.height-28},{x:target.x,y:target.y+40},nodes));
  }
  const elapsed=performance.now()-began;
  // Diagnostic only: shared runners and concurrent builds distort wall-clock budgets.
  t.diagnostic(`100 routes through 50 staggered cards (seed 8): ${elapsed.toFixed(1)}ms`);
  for(const result of routes) assertClear(result,nodes);
});

test('legacy negative coordinates and self-return endpoints stay finite and clear', () => {
  const nodes=[rect(-600,-300),rect(-250,-100),rect(100,-250)];
  for(const [from,to] of [[0,1],[2,0],[1,1]]) assertClear(route(nodes[from],nodes[to],nodes),nodes);
});

function yCoordinates(path) {
  return path.match(/-?\d+(?:\.\d+)?/g).map(Number).filter((_, i) => i % 2 === 1);
}
test('close right-hand target stays between endpoints even with a lower unrelated card', () => {
  for (const distance of [1, 20, 40, 60, 61, 100]) {
    const path = wirePath({x: 280, y: 203}, {x: 280 + distance, y: 130}, 600);
    assert.ok(Math.max(...yCoordinates(path)) <= 203);
    assert.ok(Math.min(...yCoordinates(path)) >= 130);
    const xs = path.match(/-?\d+(?:\.\d+)?/g).map(Number).filter((_, i) => i % 2 === 0);
    assert.ok(Math.min(...xs) >= 280 && Math.max(...xs) <= 280 + distance);
  }
});
test('return route rounds each direction change', () => {
  const path = wirePath({x: 632, y: 263}, {x: 80, y: 460}, 510, 340);
  assert.equal((path.match(/Q /g) || []).length, 4);
  assert.ok(!path.includes('NaN'));
});
test('lower overlapping neighbour does not loop below the result card', () => {
  const gap = verticalGap({y: 160, height: 134}, {y: 320, height: 90});
  const path = wirePath({x: 632, y: 263}, {x: 570, y: 360}, 410, gap);
  assert.ok(Math.max(...yCoordinates(path)) <= 360);
  assert.ok(Math.min(...yCoordinates(path)) >= 263);
});
test('upper neighbour uses the gap above rather than the bottom of both cards', () => {
  const gap = verticalGap({y: 400, height: 134}, {y: 180, height: 90});
  const path = wirePath({x: 632, y: 503}, {x: 570, y: 220}, 534, gap);
  assert.ok(Math.max(...yCoordinates(path)) <= 503);
  assert.ok(Math.min(...yCoordinates(path)) >= 220);
});
test('same-row return retains an outside lane', () => {
  const gap = verticalGap({y: 160, height: 134}, {y: 180, height: 90});
  assert.equal(gap, undefined);
  assert.ok(Math.max(...yCoordinates(wirePath({x: 632,y: 263},{x: 200,y: 220},294,gap))) > 294);
});

function assertSeparate(routes) {
  for(let i=0;i<routes.length;i++) for(let j=0;j<i;j++) {
    const a=routes[i].points,b=routes[j].points;
    assert.ok(a && b);
    for(let x=1;x<a.length;x++) for(let y=1;y<b.length;y++) {
      const p=a[x-1],q=a[x],u=b[y-1],v=b[y];
      if(p.y===q.y && u.y===v.y && Math.abs(p.y-u.y)<.01)
        assert.ok(Math.min(Math.max(p.x,q.x),Math.max(u.x,v.x))-Math.max(Math.min(p.x,q.x),Math.min(u.x,v.x))<=.01,'shared horizontal lane');
      if(p.x===q.x && u.x===v.x && Math.abs(p.x-u.x)<.01)
        assert.ok(Math.min(Math.max(p.y,q.y),Math.max(u.y,v.y))-Math.max(Math.min(p.y,q.y),Math.min(u.y,v.y))<=.01,'shared vertical lane');
    }
  }
}
const batchOutput=(n,e)=>({x:n.x+n.width,y:n.y+103+(['no','done'].includes(e.port)?44:0)});
test('batch routes separate parallel returns and fan-in, independent of input order',()=>{
  const nodes=[['start',40,80,134],['ideas',360,80,134],['loop',680,340,178],['cat',1000,80,178],['dog',1000,400,178],['end',40,660,90],['cat_check',1320,80,134],['dog_check',1320,360,134],['other_check',1320,640,134],['merge',680,660,134]].map(([id,x,y,height])=>({id,x,y,height,width:232}));
  const edges=[['start','ideas','next'],['ideas','loop','next'],['loop','cat','item'],['loop','end','done'],['cat','cat_check','yes'],['cat','dog','no'],['dog','dog_check','yes'],['dog','other_check','no'],['cat_check','merge','next'],['dog_check','merge','next'],['other_check','merge','next'],['merge','loop','next']].map(([source,target,port],i)=>({id:String(i).padStart(2,'0'),source,target,port}));
  const rs=routeConnections(nodes,edges,batchOutput);
  for(const r of rs){assertClear(r,nodes);assert.equal(r.crowded,false);}
  assertSeparate(rs);
  assert.deepEqual(rs,routeConnections([...nodes].reverse(),[...edges].reverse(),batchOutput));
  const joins=rs.filter(r=>r.edge.target==='merge');
  assert.equal(new Set(joins.map(r=>r.targetPoint.y)).size,3);
});
test('batch congestion is explicit and never silently drops an edge',()=>{
  const nodes=[{id:'a',...rect(0,0)},{id:'b',...rect(400,0)}];
  const edges=[{id:'1',source:'a',target:'b',port:'next'},{id:'2',source:'a',target:'b',port:'next'}];
  const rs=routeConnections(nodes,edges,batchOutput);
  assert.equal(rs.length,2);assert.equal(rs[1].crowded,true);
  for(const r of rs) assertClear(r,nodes);
});
test('batch cap of 50 nodes and 98 distinct output ports stays finite',t=>{
  const nodes=Array.from({length:50},(_,i)=>({id:String(i),...rect(50+(i%10)*370,50+Math.floor(i/10)*300,178)}));
  const edges=Array.from({length:98},(_,i)=>({id:String(i).padStart(3,'0'),source:String(Math.floor(i/2)),target:String((Math.floor(i/2)+1+i%2*11)%50),port:i%2?'no':'yes'}));
  const began=performance.now();const rs=routeConnections(nodes,edges,batchOutput);
  t.diagnostic(`batch 50 cards / 98 edges: ${(performance.now()-began).toFixed(1)}ms; crowded ${rs.filter(r=>r.crowded).length}`);
  assert.equal(rs.length,98);for(const r of rs) assertClear(r,nodes);
  assertSeparate(rs.filter(r=>!r.crowded));
});

test('compact socket cards route from visible ports and split fan-in without card collisions', () => {
  const nodes=[{id:'start',...rect(0,100,90)},{id:'branch',...rect(370,100,166)},
    {id:'upper',...rect(760,0,90)},{id:'lower',...rect(760,320,90)},
    {id:'end',...rect(1120,130,90)}];
  const edges=[['start','branch','next'],['branch','upper','yes'],['branch','lower','no'],
    ['upper','end','next'],['lower','end','next']].map(([source,target,port],i)=>({id:String(i),source,target,port}));
  const output=(n,e)=>({x:n.x+232,y:n.y+(n.id==='branch'?(e.port==='yes'?100:144):40)});
  const routes=routeConnections(nodes,edges,output);
  assert.equal(routes.length,5);
  for(const route of routes){
    assert.equal(route.blocked,false);
    assertClear(route,nodes);
    assert.deepEqual(samples(route.path)[0],output(nodes.find(n=>n.id===route.edge.source),route.edge));
    assert.deepEqual(samples(route.path).at(-1),route.targetPoint);
  }
  const incoming=routes.filter(r=>r.edge.target==='end');
  assert.notEqual(incoming[0].targetPoint.y,incoming[1].targetPoint.y);
});

test('input sockets retain fan-in offsets while their target moves', async () => {
  const { inputSocketOffset } = await import('./graph-routing.ts');
  const target = {id:'end',...rect(700,200,90)};
  const nodes = [{id:'a',...rect(0,0,90)},{id:'b',...rect(0,400,90)},target];
  const edges = ['a','b'].map(id=>({id,source:id,target:'end',port:'next'}));
  const routes = routeConnections(nodes,edges,n=>({x:n.x+232,y:n.y+40})).map(r=>({...r,target:nodes.find(n=>n.id===r.edge.target)}));
  for (const moved of [{x:700,y:360},{x:400,y:40},{x:1200,y:700}]) {
    for (const r of routes) {
      const offset = inputSocketOffset(r);
      assert.ok(offset >= 0 && offset <= target.height);
      const endpoint = {x:moved.x,y:moved.y+(r.targetPoint.y-r.target.y)};
      assert.deepEqual({x:moved.x,y:moved.y+offset},endpoint);
    }
    assert.notEqual(inputSocketOffset(routes[0]),inputSocketOffset(routes[1]));
  }
});

test('expanded AI cards keep wire endpoints clear of their full bounds',()=>{
 const nodes=[{id:'start',...rect(48,100,90)},{id:'ai',x:360,y:100,width:280,height:216},{id:'end',...rect(760,100,90)}];
 const edges=[{id:'a',source:'start',target:'ai',port:'next'},{id:'b',source:'ai',target:'end',port:'next'}];
 const output=n=>({x:n.x+n.width,y:n.y+40});
 for(const r of routeConnections(nodes,edges,output)){
  assertClear(r,nodes);
  assert.deepEqual(samples(r.path)[0],output(nodes.find(n=>n.id===r.edge.source)));
  assert.deepEqual(samples(r.path).at(-1),r.targetPoint);
 }
});
