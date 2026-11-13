import {test} from 'node:test';
import assert from 'node:assert/strict';
import {workTabKey,parseWorkTab,entryWorkTab,initialWorkTab} from './work-tabs.ts';
test('tab keys isolate work and user and reject missing scopes',()=>{
 assert.notEqual(workTabKey('ws:user','a'),workTabKey('ws:user','b'));
 assert.notEqual(workTabKey('ws:user','a'),workTabKey('ws:other','a'));
 assert.equal(workTabKey('','a'),null);
});
test('only supported tabs restore, otherwise work is default',()=>{
 for(const t of ['common','images','history']) assert.equal(parseWorkTab(t),t);
 for(const t of [null,'','bad','__proto__']) assert.equal(parseWorkTab(t),'images');
});
test('entry prioritizes unfinished image work and completed work opens answer',()=>{
 for(const state of ['pending','queued','running','review','failed','unknown'])
  assert.equal(entryWorkTab('succeeded',{status:'review',counts:{[state]:1}}),'images');
 for(const status of ['complete','not_required'])
  assert.equal(entryWorkTab('succeeded',{status,counts:{approved:2,excluded:1}}),'history');
 assert.equal(entryWorkTab('failed',{status:'review',counts:{review:2}}),'history');
 assert.equal(entryWorkTab('succeeded',null),'history');
});
test('saved tab only takes precedence on reload, not a fresh entry',()=>{
 assert.equal(initialWorkTab('images','history',false),'images');
 assert.equal(initialWorkTab('history','images',false),'history');
 for(const saved of ['common','images','history'])assert.equal(initialWorkTab('images',saved,true),saved);
 assert.equal(initialWorkTab('history',null,true),'history');
 assert.equal(initialWorkTab('history','bad',true),'history');
});
