import type { CSSProperties } from "react";

export function normalizeNavigationHex(value: string): `#${string}` | null {
  return /^#[0-9a-f]{6}$/i.test(value.trim()) ? value.trim().toLowerCase() as `#${string}` : null;
}

type RGB = [number, number, number];
const rgb = (hex: string): RGB => [1,3,5].map(index=>parseInt(hex.slice(index,index+2),16)) as RGB;
const hex = (channels: RGB) => `#${channels.map(channel=>Math.round(channel).toString(16).padStart(2,"0")).join("")}`;
function blend(from:RGB,to:RGB,amount:number):RGB {
  return from.map((channel,index)=>Math.round(channel+(to[index]-channel)*amount)) as RGB;
}
function luminance(channels:RGB) {
  const linear=channels.map(channel=>{const v=channel/255;return v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4;});
  return linear[0]*0.2126+linear[1]*0.7152+linear[2]*0.0722;
}
function ratio(a:RGB,b:RGB) {
  const x=luminance(a),y=luminance(b);
  return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05);
}
function foreground(base:RGB,background:RGB,target:RGB):RGB {
  // Evaluate rounded output colors, so the actual rendered values meet text contrast.
  for(let step=0;step<=100;step++) {
    const candidate=blend(base,target,step/100);
    if(ratio(candidate,background)>=4.5)return candidate;
  }
  return target;
}

export function customNavigationPalette(value:string) {
  const normalized=normalizeNavigationHex(value);
  if(!normalized)return null;
  const base=rgb(normalized),white:RGB=[255,255,255],black:RGB=[0,0,0];
  const lightBackground=blend(base,white,0.9);
  const darkBackground=blend([25,33,50],base,0.15);
  return {
    lightForeground:hex(foreground(base,lightBackground,black)),lightBackground:hex(lightBackground),
    darkForeground:hex(foreground(base,darkBackground,white)),darkBackground:hex(darkBackground),
  };
}

export function navigationAccent(value:string|null|undefined): {"data-nav-color"?:string;style?:CSSProperties} {
  const palette=value?customNavigationPalette(value):null;
  if(palette)return {"data-nav-color":"custom",style:{
    "--nav-custom-light-fg":palette.lightForeground,"--nav-custom-light-bg":palette.lightBackground,
    "--nav-custom-dark-fg":palette.darkForeground,"--nav-custom-dark-bg":palette.darkBackground,
  } as CSSProperties};
  return {"data-nav-color":value&&/^(red|orange|green|blue|purple|pink)$/.test(value)?value:undefined};
}
