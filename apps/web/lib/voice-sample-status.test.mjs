import assert from 'node:assert/strict';
import {test} from 'node:test';
import {voiceSampleStatus} from './voice-sample-status.ts';
const base={changed:false,saved:true,selected:false};
test('sample lifecycle is distinct from saved settings',()=>{
  for(const [status,label] of [['queued','맞춤 샘플 생성 대기'],['running','맞춤 샘플 생성 중'],['review','맞춤 샘플 듣고 선택'],['approved','맞춤 샘플 듣고 선택'],['failed','맞춤 샘플 생성 실패'],['unknown','맞춤 샘플 호출 결과 확인 필요']]) assert.equal(voiceSampleStatus({...base,sample:{status,error_code:null}}).label,label);
  assert.equal(voiceSampleStatus(base).label,'설정 저장됨 · 맞춤 샘플 없음');
  assert.equal(voiceSampleStatus({...base,saved:false}).label,'맞춤 샘플 생성 전 · 설정 저장 필요');
  assert.equal(voiceSampleStatus({...base,selected:true}).label,'목소리 선택 완료');
  assert.equal(voiceSampleStatus({...base,selected:true,changed:true}).label,'저장 전 변경');
  assert.equal(voiceSampleStatus({...base,sample:{status:'review',error_code:'audio_transcript_mismatch'}}).label,'맞춤 샘플 생성 실패');
});
