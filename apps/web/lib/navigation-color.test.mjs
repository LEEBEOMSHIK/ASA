import test from 'node:test';
import assert from 'node:assert/strict';
import { customNavigationPalette, navigationAccent, normalizeNavigationHex } from './navigation-color.ts';

function luminance(hex) {
  const channels=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255)
    .map(v=>v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4);
  return channels.reduce((sum,c,i)=>sum+c*[0.2126,0.7152,0.0722][i],0);
}
function contrast(a,b) {
  const values=[luminance(a),luminance(b)].sort((x,y)=>x-y);
  return (values[1]+0.05)/(values[0]+0.05);
}

test('normalizes hex without permitting arbitrary CSS and preserves named colors',()=>{
  assert.equal(normalizeNavigationHex(' #3B82F6 '),'#3b82f6');
  for(const value of ['#fff','#12345678','#zzzzzz','red; background:url(x)','']) {
    assert.equal(customNavigationPalette(value),null);
    assert.equal(navigationAccent(value)['data-nav-color'],undefined);
  }
  for(const value of ['red','orange','green','blue','purple','pink']) {
    assert.deepEqual(navigationAccent(value),{'data-nav-color':value});
  }
});

test('rendered rounded palette meets 4.5:1 in both themes, including extreme colors',()=>{
  const levels=[0,1,32,64,128,192,254,255];
  for(const r of levels)for(const g of levels)for(const b of levels) {
    const source='#'+[r,g,b].map(v=>v.toString(16).padStart(2,'0')).join('');
    const p=customNavigationPalette(source);
    for(const theme of ['light','dark']) {
      const foreground=p[theme+'Foreground'],background=p[theme+'Background'];
      assert.match(foreground,/^#[0-9a-f]{6}$/);
      assert.match(background,/^#[0-9a-f]{6}$/);
      assert.ok(contrast(foreground,background)>=4.5,`${source} ${theme}`);
    }
    assert.equal(navigationAccent(source)['data-nav-color'],'custom');
  }
});
