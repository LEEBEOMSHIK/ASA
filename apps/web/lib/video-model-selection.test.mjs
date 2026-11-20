import {test} from 'node:test';
import assert from 'node:assert/strict';
import {videoModelChoices,videoModelName,videoModelFamilies,sameVideoModel,appliedVideoModel} from './video-model-selection.ts';

test('resolution variants stay in one model family without changing stored keys',()=>{
  const catalog=[
    {key:'hf-wan3',provider:'higgsfield',model:'alibaba/wan-3.0',label:'WAN 3.0',resolution:'720p'},
    {key:'hf-wan3-1080p',provider:'higgsfield',model:'alibaba/wan-3.0',label:'WAN 3.0',resolution:'1080p'},
    {key:'wan3',provider:'alibaba',model:'wan3.0-video',label:'WAN 3.0',resolution:'720p'},
  ];
  const before=JSON.stringify(catalog);
  assert.deepEqual(videoModelFamilies(catalog).map(m=>m.key),['hf-wan3','wan3']);
  assert.equal(sameVideoModel(catalog[0],catalog[1]),true);
  assert.equal(sameVideoModel(catalog[0],catalog[2]),false);
  assert.equal(JSON.stringify(catalog),before);
  const defaults={'higgsfield:alibaba/wan-3.0':{model_key:'hf-wan3-1080p',duration_seconds:5}};
  assert.equal(appliedVideoModel(catalog,'hf-wan3',true,defaults).key,'hf-wan3');
  assert.equal(appliedVideoModel(catalog,'hf-wan3',false,defaults).key,'hf-wan3-1080p');
  assert.equal(appliedVideoModel(catalog,'hf-wan3-1080p',false,{}).key,'hf-wan3');
});

test('models remain scoped to their provider and schema while retaining saved selection',()=>{
  const catalog=[
    {key:'wan3',provider:'alibaba',label:'WAN 3.0 · Alibaba'},
    {key:'hf-wan3',provider:'higgsfield',label:'WAN 3.0 - Higgsfield'},
    {key:'hf-other',provider:'higgsfield',label:'Other model'},
    {key:'restricted',provider:'higgsfield',label:'Restricted'},
  ];
  const options=videoModelChoices(['wan3','hf-wan3','hf-other'],catalog,'retired');
  assert.deepEqual(options.filter(m=>m.provider==='higgsfield').map(m=>m.key),['hf-wan3','hf-other']);
  assert.equal(options.find(m=>m.key==='retired').provider,'unavailable');
  assert.equal(videoModelName(options[1]),'WAN 3.0');
  assert.equal(videoModelName(options[2]),'Other model');
  assert.equal(catalog[1].label,'WAN 3.0 - Higgsfield');
});
test('loading or failed catalog retains existing model and provider without changing stored key',()=>{
  const options=videoModelChoices(['wan3','hf-wan3'],[],'hf-wan3');
  assert.equal(options.find(m=>m.key==='hf-wan3').provider,'higgsfield');
  assert.equal(options.length,2);
});
