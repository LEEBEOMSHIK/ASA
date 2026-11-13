import {test} from 'node:test';
import assert from 'node:assert/strict';
import {workActionTone,characterNextStep} from './work-progress.ts';
const progress=(counts,status='review')=>({status,counts});
test('action prioritizes errors and uncertain results over review and ungenerated images',()=>{
 assert.equal(workActionTone(progress({failed:1,review:2,pending:3})), 'danger');
 assert.equal(workActionTone(progress({unknown:1,review:2})), 'danger');
 assert.equal(workActionTone(progress({review:2,pending:3})), 'warning');
 assert.equal(workActionTone(progress({pending:3},'pending')), 'primary');
});
test('completed and in-flight work do not show an action-needed warning',()=>{
 assert.equal(workActionTone(progress({},'complete')), 'success');
 assert.equal(workActionTone(progress({running:1},'running')), 'neutral');
 assert.equal(workActionTone(progress({},'not_required')), 'neutral');
});

test('completed AI answer shows only the next human task, not overall completion',()=>{
 assert.deepEqual(characterNextStep('succeeded',progress({review:2,pending:1})),{label:'이미지 검토 필요 · 2개',tone:'warning',tab:'images'});
 assert.equal(characterNextStep('succeeded',progress({},'complete')).label,'작업 완료');
 assert.equal(characterNextStep('succeeded',progress({},'not_required')).label,'작업 대상 없음');
});
test('new AI attempt routes to answer and image errors route to images',()=>{
 for(const state of ['running','queued','failed','saved','cancelled','unknown']) assert.equal(characterNextStep(state,progress({review:2})).tab,'history');
 assert.deepEqual(characterNextStep('succeeded',progress({failed:1,review:2})),{label:'이미지 생성 오류 확인 · 1개',tone:'danger',tab:'images'});
 assert.equal(characterNextStep('succeeded',progress({unknown:1,failed:2})).label,'이미지 생성 결과 확인 필요 · 1개');
});
