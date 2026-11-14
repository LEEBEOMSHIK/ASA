import type {Tool} from './registry';
import type {WorkTab} from './work-tabs';
import type {WorkProgress} from './work-progress';

export type WorkTabItem = {id:WorkTab;label:string;description:string};
export function workTabItems(agent:Partial<Tool>):WorkTabItem[] {
  const p=agent.output_schema?.properties || {};
  const characters=p.characters?.type==='array', scenes=p.shots?.type==='array';
  const result:WorkTabItem=characters
    ? {id:'images',label:'캐릭터 설정·이미지',description:'외형·목소리 설정과 이미지 생성·확정'}
    : scenes ? {id:'images',label:'씬 설정·이미지',description:'씬별 이미지 생성·수정·확정'}
    : agent.after_tasks?.scene_timing ? {id:'images',label:'장면 구성·시간 확인',description:'장면 구성과 시간 배분, 전체 미리듣기'}
    : p.clips?.type==='array' && p.model_key ? {id:'images',label:'클립·영상 생성',description:'클립 연결과 영상 생성·확정'}
    : p.narration || p.script || p['대본'] ? {id:'images',label:'대본 확인',description:'대본 내용을 확인하고 필요한 답변 확정'}
    : {id:'images',label:'결과 확인',description:'에이전트 결과와 후속 작업 확인'};
  return [
    ...(characters ? [{id:'common' as const,label:'화풍·나레이션',description:'작품 전체에 적용할 영상 유형과 표현 설정'}] : []),
    result,
    {id:'history',label:'AI 답변·수정 요청',description:'원문·이력 확인, AI 수정 요청과 새 작업'},
  ];
}

export function workNextStep(status:string,p:WorkProgress|null|undefined):{label:string;tone:'danger'|'warning'|'primary'|'neutral'|'success';tab:WorkTab} {
  if(status==='running'||status==='queued')return {label:status==='running'?'답변 작성 중':'답변 생성 대기 중',tone:'neutral',tab:'images'};
  if(status==='failed')return {label:'답변 생성 오류 확인',tone:'danger',tab:'history'};
  if(status==='saved'||status==='cancelled')return {label:'답변 생성 필요',tone:'primary',tab:'history'};
  if(status!=='succeeded')return {label:'작업 상태 확인 필요',tone:'warning',tab:'history'};
  if(!p)return {label:'답변 확인',tone:'neutral',tab:'images'};
  const group=p.groups?.find(g=>!['complete','not_required'].includes(g.status))||p;
  const counts=group.counts;
  const states=[['unknown','결과 확인 필요','danger'],['failed','오류 확인','danger'],['review','검토 필요','warning'],['pending','작업 필요','primary'],['running','진행 중','neutral'],['queued','대기 중','neutral']] as const;
  for(const [state,label,tone] of states)if(counts[state]>0)return {label:`${group.label} · ${label}${counts[state]>1?` ${counts[state]}개`:''}`,tone,tab:'images'};
  return {label:p.status==='complete'?'작업 완료':'답변 확인',tone:p.status==='complete'?'success':'neutral',tab:p.status==='complete'?'history':'images'};
}
