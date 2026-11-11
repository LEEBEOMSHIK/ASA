import assert from 'node:assert/strict';
import {test} from 'node:test';
import {saveThenGenerateSample} from './save-voice-sample.ts';
test('save completes before generation and returned revision is used',async()=>{
 const events=[];
 await saveThenGenerateSample({current:{revision:2},needsSave:true,phase:p=>events.push(p),save:async()=>{events.push('saved');return {revision:3};},generate:async r=>events.push(r)});
 assert.deepEqual(events,['saving','saved','requesting',3]);
});
test('save failure never generates',async()=>{
 let called=false;
 await assert.rejects(saveThenGenerateSample({current:{revision:2},needsSave:true,phase:()=>{},save:async()=>{throw Error('conflict');},generate:async()=>{called=true;}}),/conflict/);
 assert.equal(called,false);
});
test('unchanged settings do not save; generation failure propagates',async()=>{
 let saved=false;
 await assert.rejects(saveThenGenerateSample({current:{revision:4},needsSave:false,phase:()=>{},save:async()=>{saved=true;return {revision:5};},generate:async r=>{assert.equal(r,4);throw Error('unavailable');}}),/unavailable/);
 assert.equal(saved,false);
});
