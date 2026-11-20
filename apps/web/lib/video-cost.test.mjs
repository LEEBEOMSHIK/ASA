import {test} from 'node:test';
import assert from 'node:assert/strict';
import {videoCostLabel,totalVideoCost} from './video-cost.ts';

test('missing and failed estimates never become zero dollar costs',()=>{
  for(const value of [null,undefined,NaN,-1])assert.equal(videoCostLabel(value),'예상 비용 미확인');
  assert.equal(totalVideoCost([]),null);
  assert.equal(totalVideoCost([.375,null]),null);
  assert.equal(totalVideoCost([.375,NaN]),null);
});
test('mixed video-reference rates sum per clip and retain estimate qualification',()=>{
  assert.ok(Math.abs(totalVideoCost([.375,.7465])-1.1215)<1e-10);
  assert.match(videoCostLabel(1.1215),/\$1.12 USD/);
  assert.match(videoCostLabel(1.1215),/카탈로그.*실제 청구액/);
});
