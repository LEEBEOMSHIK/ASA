import {test} from 'node:test';
import assert from 'node:assert/strict';
import {videoJobTime,videoOrientation} from './video-job-time.ts';
const base={created_at:'2026-11-16T00:00:00Z',updated_at:'2026-11-16T00:02:01Z'};
test('active elapsed advances, completion freezes even after approval',()=>{
 assert.equal(videoJobTime({...base,status:'running'},Date.parse('2026-11-16T00:03:00Z')).text,'3분 0초');
 assert.equal(videoJobTime({...base,status:'review'},Date.now()).text,'2분 1초');
 assert.equal(videoJobTime({...base,status:'approved',updated_at:'2026-11-16T01:00:00Z',finished_at:base.updated_at},Date.now()).text,'2분 1초');
 assert.equal(videoJobTime({...base,status:'approved'},Date.now()).text,'기록 없음');
 assert.equal(videoJobTime({...base,status:'unknown'},Date.now()).text,'2분 1초');
 assert.equal(videoJobTime({...base,status:'running'},0).text,'기록 없음');
});
test('orientation supports portrait landscape square and unknown ratios',()=>{
 assert.equal(videoOrientation('9:16'),'portrait');assert.equal(videoOrientation('16:9'),'landscape');
 assert.equal(videoOrientation('1:1'),'square');assert.equal(videoOrientation('invalid'),'landscape');
});
