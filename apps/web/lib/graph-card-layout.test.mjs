import test from 'node:test';
import assert from 'node:assert/strict';
import { cardSize, cardPortY } from './graph-card-layout.ts';
import { routeConnections } from './graph-routing.ts';
test('single ports align to card centres and split ports stay inside',()=>{
 for(const kind of ['start','end','ai','tool','map','condition','repeat']) {
  const size=cardSize(kind);
  assert.equal(size.inputY,size.height/2);
  if(kind==='condition'||kind==='repeat') {
   assert.ok(cardPortY(kind,0)<cardPortY(kind,1));
   assert.ok(cardPortY(kind,1)<size.height);
  } else assert.equal(cardPortY(kind,0),size.height/2);
 }
});
test('router respects the visible central input socket',()=>{
 const nodes=[{id:'s',x:0,y:100,...cardSize('start')},{id:'ai',x:450,y:36,...cardSize('ai')}];
 const [route]=routeConnections(nodes,[{id:'e',source:'s',target:'ai',port:'next'}],n=>({x:n.x+n.width,y:n.y+n.height/2}));
 assert.equal(route.targetPoint.y,nodes[1].y+nodes[1].height/2);
 assert.equal(route.blocked,false);
});

test('spacing resolves enlarged cards without changing input data or node order',async()=>{
 const {spaceCards}=await import('./graph-card-layout.ts');
 const nodes=[{id:'a',kind:'ai',x:0,y:0},{id:'b',kind:'condition',x:320,y:0},{id:'c',kind:'end',x:640,y:0}];
 const spaced=spaceCards(nodes);
 assert.deepEqual(spaced.map(n=>n.id),['a','b','c']);
 assert.ok(spaced[1].x>=408);
 assert.ok(spaced[2].x>=spaced[1].x+328);
 assert.equal(nodes[1].x,320);
 assert.deepEqual(spaceCards(spaced),spaced);
});

test('dropping onto mixed cards finds a nearby free position without moving neighbours',async()=>{
 const {placeCard}=await import('./graph-card-layout.ts');
 const nodes=[{id:'ai',kind:'ai',x:100,y:100},{id:'tool',kind:'tool',x:500,y:100},{id:'end',kind:'end',x:500,y:400}];
 const before=JSON.stringify(nodes);
 const result=placeCard({id:'new',kind:'tool',x:120,y:120},nodes);
 for(const n of nodes){const a=cardSize(n.kind),b=cardSize(result.kind);assert.ok(result.x+b.width+24<=n.x||result.x>=n.x+a.width+24||result.y+b.height+24<=n.y||result.y>=n.y+a.height+24);}
 assert.equal(JSON.stringify(nodes),before);
 assert.deepEqual(placeCard(result,nodes),result);
 assert.deepEqual(placeCard(nodes[0],nodes),nodes[0]);
});
