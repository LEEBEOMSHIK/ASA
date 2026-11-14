import {test} from 'node:test';
import assert from 'node:assert/strict';
import {workTabItems,workNextStep} from './work-layout.ts';
const schema=(properties)=>({type:'object',properties});
test('layout follows output contracts and explicit timing, not agent names',()=>{
 assert.equal(workTabItems({output_schema:schema({characters:{type:'array'}})})[0].id,'common');
 const scene=workTabItems({output_schema:schema({shots:{type:'array'}})});
 assert.deepEqual(scene.map(t=>t.id),['images','history']);
 assert.equal(scene[0].label,'씬 설정·이미지');
 assert.equal(workTabItems({after_tasks:{scene_timing:true}})[0].label,'장면 구성·시간 확인');
 assert.equal(workTabItems({output_schema:schema({clips:{type:'array'},model_key:{type:'string'}})})[0].label,'클립·영상 생성');
 assert.equal(workTabItems({output_schema:schema({narration:{type:'string'}})})[0].label,'대본 확인');
 assert.equal(workTabItems({name:'캐릭터 이미지 에이전트'})[0].label,'결과 확인');
});
test('generic approval is not labelled image generation and absent progress is not complete',()=>{
 const p={kind:'answer',label:'답변',status:'review',counts:{review:1}};
 assert.equal(workNextStep('succeeded',p).label,'답변 · 검토 필요');
 assert.equal(workNextStep('succeeded',p).tab,'images');
 assert.equal(workNextStep('succeeded',null).label,'답변 확인');
 assert.equal(workNextStep('running',null).tab,'images');
 assert.equal(workNextStep('failed',null).tab,'history');
});

test('non-character agents do not expose character common settings',()=>{
 for(const agent of [{after_tasks:{scene_timing:true}},{output_schema:schema({clips:{type:'array'},model_key:{type:'string'}})},{output_schema:schema({narration:{type:'string'}})},{}])assert.equal(workTabItems(agent).some(t=>t.id==='common'),false);
});
