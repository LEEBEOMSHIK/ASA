export type BackgroundWorker = {kind:string;state:string;enabled:boolean};
export function targets<T extends BackgroundWorker>(workers:T[],action:'start'|'stop'):T[]{
  return workers.filter(w=>action==='start'
    ? w.enabled&&['stopped','failed','offline'].includes(w.state)
    : ['running','starting'].includes(w.state));
}
export function summary(workers:BackgroundWorker[]):{text:string;detail:string;tone:'neutral'|'success'|'warning'}{
  const running=workers.filter(w=>w.state==='running').length;
  const detail=`${workers.length}개 중 ${running}개 실행 중`;
  if(workers.some(w=>['failed','offline','external'].includes(w.state)))return {text:'상태 확인 필요',detail,tone:'warning'};
  if(workers.some(w=>['starting','stopping'].includes(w.state)))return {text:'상태 변경 중',detail,tone:'neutral'};
  if(running===workers.length&&running>0)return {text:'실행 중',detail,tone:'success'};
  return {text:running?'일부 중지':'중지됨',detail,tone:running?'warning':'neutral'};
}
