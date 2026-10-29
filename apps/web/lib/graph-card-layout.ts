export function cardSize(kind:string) {
 const width=kind==='ai'?360:280;
 const height=kind==='ai'?248:kind==='condition'||kind==='repeat'?216:120;
 return {width,height,inputY:height/2};
}
export function cardPortY(kind:string,index:number) {
 return kind==='condition'||kind==='repeat'?140+index*48:cardSize(kind).height/2;
}

/** Keep other cards fixed; choose the closest clear position around them. */
export function placeCard<T extends {id:string;x:number;y:number;kind:string}>(node:T,nodes:T[]):T {
 const others=nodes.filter(n=>n.id!==node.id), size=cardSize(node.kind), gap=24;
 const clear=(p:{x:number;y:number})=>others.every(o=>{
  const s=cardSize(o.kind);
  return p.x+size.width+gap<=o.x||p.x>=o.x+s.width+gap||p.y+size.height+gap<=o.y||p.y>=o.y+s.height+gap;
 });
 if(clear(node))return node;
 const xs=new Set([node.x,16]),ys=new Set([node.y,16]);
 for(const o of others){const s=cardSize(o.kind);xs.add(o.x+s.width+gap);xs.add(Math.max(16,o.x-size.width-gap));ys.add(o.y+s.height+gap);ys.add(Math.max(16,o.y-size.height-gap));}
 const candidates=[...xs].flatMap(x=>[...ys].map(y=>({x,y}))).filter(clear);
 candidates.sort((a,b)=>Math.hypot(a.x-node.x,a.y-node.y)-Math.hypot(b.x-node.x,b.y-node.y)||a.y-b.y||a.x-b.x);
 return {...node,...candidates[0]};
}

/** Preserve vertical grouping and input order; move only cards lacking clearance. */
export function spaceCards<T extends {x:number;y:number;kind:string}>(nodes:T[]):T[] {
 const positions=new Map<T,T>();
 const placed:T[]=[];
 for(const node of [...nodes].sort((a,b)=>a.x-b.x||a.y-b.y)) {
  const next={...node};const size=cardSize(node.kind);
  for(const other of placed) {
   const otherSize=cardSize(other.kind);
   if(next.y<other.y+otherSize.height+48&&next.y+size.height+48>other.y&&next.x<other.x+otherSize.width+48&&next.x+size.width+48>other.x) next.x=other.x+otherSize.width+48;
  }
  placed.push(next);placed.sort((a,b)=>a.x-b.x);positions.set(node,next);
 }
 return nodes.map(n=>positions.get(n)!);
}
