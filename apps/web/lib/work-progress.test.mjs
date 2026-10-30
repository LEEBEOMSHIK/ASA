import test from 'node:test';
import assert from 'node:assert/strict';
import {progressLabel, progressCounts, itemStateLabel} from './work-progress.ts';

test('generic progress labels do not describe audio as images',()=>{
  const p={kind:'voice', status:'running', counts:{running:1,review:2,pending:1,approved:0,excluded:0,failed:0,unknown:0,queued:0}};
  assert.equal(progressLabel(p),'작업 진행 중');
  assert.equal(progressCounts(p),'진행 중 1 · 검토 필요 2 · 미진행 1');
  assert.equal(itemStateLabel('pending','character_images'),'미생성');
  assert.equal(progressLabel({...p,status:'not_required'}),'대상 없음');
});
