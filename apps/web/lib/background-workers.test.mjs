import test from 'node:test';
import assert from 'node:assert/strict';
import {targets, summary} from './background-workers.ts';
const items=[{kind:'script',state:'running',enabled:true},{kind:'image',state:'stopped',enabled:true},
  {kind:'audio',state:'stopped',enabled:false},{kind:'video',state:'external',enabled:true}];
test('bulk actions preserve existing active, disabled and externally managed processes',()=>{
  assert.deepEqual(targets(items,'start').map(w=>w.kind),['image']);
  assert.deepEqual(targets(items,'stop').map(w=>w.kind),['script']);
});
test('summary distinguishes partial availability and failure',()=>{
  assert.equal(summary(items).text,'상태 확인 필요');
  assert.equal(summary(items.map(w=>w.state==='external'?{...w,state:'stopped'}:w)).text,'일부 중지');
  assert.equal(summary(items.map(w=>({...w,state:'stopped'}))).text,'중지됨');
  assert.equal(summary(items.map(w=>({...w,state:'running'}))).text,'실행 중');
  const oneStopped=items.map((w,i)=>({...w,state:i===3?'stopped':'running'}));
  assert.deepEqual(summary(oneStopped),{text:'일부 중지',detail:'4개 중 3개 실행 중',tone:'warning'});
  assert.equal(summary([{kind:'video',state:'failed',enabled:true}]).tone,'warning');
});
