import test from 'node:test';
import assert from 'node:assert/strict';
import { inputEntries } from './input-requirements.ts';
import { modelStyleGuidance } from './video-model-guidance.ts';

test('video style precedes model without disturbing other fields or source schema',()=>{
  const schema={type:'object',properties:{script:{type:'string'},model:{type:'string','x-video-model':true},note:{type:'string'},video_style:{type:'string'}},required:['script','model','video_style']};
  const before=JSON.stringify(schema);
  assert.deepEqual(inputEntries(schema).map(([key])=>key),['script','video_style','model','note']);
  assert.equal(JSON.stringify(schema),before);
  const ordinary={type:'object',properties:{note:{type:'string'},model:{type:'string'}},required:['model']};
  assert.deepEqual(inputEntries(ordinary).map(([key])=>key),['model','note']);
});

test('guidance matches exact provider/model/style, never a similar name or missing style',()=>{
  for(const style of ['animation_2d','animation_3d','live_action']) {
    const info=modelStyleGuidance('runway','gen4.5',style);
    assert.ok(info?.suggestion);
    assert.ok(info.sources.every(s=>s.url.startsWith('https://help.runwayml.com/')));
  }
  for(const args of [['other','gen4.5','live_action'],['runway','gen4.5-new','live_action'],['runway','gen4.5',''],['runway','gen4.5','unknown']]) assert.equal(modelStyleGuidance(...args),null);
});

test('WAN guidance is isolated from Runway and other versions',()=>{
  for(const style of ['animation_2d','animation_3d','live_action']) {
    const info=modelStyleGuidance('alibaba','wan3.0-video',style);
    assert.ok(info?.confirmed.includes('2~30초'));
    assert.ok(info.sources.every(s=>s.url.includes('alibabacloud.com')));
  }
  assert.equal(modelStyleGuidance('alibaba','wan3.0-video-prime','live_action'),null);
  assert.equal(modelStyleGuidance('runway','wan3','live_action'),null);
});
