export type VideoTiming = {status:string;created_at:string;updated_at:string;finished_at?:string|null};
export function videoJobTime(job:VideoTiming,now:number):{label:string;text:string;active:boolean} {
  const active=["queued","submitting","running"].includes(job.status);
  const completed=["review","approved"].includes(job.status);
  const end=active?now:Date.parse(job.finished_at??(job.status==="approved"?"":job.updated_at));
  const start=Date.parse(job.created_at);
  const label=active?"요청 후 경과":completed?"완료까지 소요":"추적된 시간";
  if(!Number.isFinite(start)||!Number.isFinite(end)||end<start)return {label,text:"기록 없음",active};
  const seconds=Math.floor((end-start)/1000),hours=Math.floor(seconds/3600),minutes=Math.floor(seconds%3600/60);
  return {label,text:`${hours?`${hours}시간 `:""}${minutes?`${minutes}분 `:""}${seconds%60}초`,active};
}
export function videoOrientation(ratio:string):"portrait"|"landscape"|"square" {
  const [w,h]=ratio.split(":").map(Number);
  return w>0&&h>0?(w<h?"portrait":w>h?"landscape":"square"):"landscape";
}
