"use client";
import { useState } from "react";
import { Button, Card } from "./ui";

export type Timing = {
  queued:number;running:number;target:number|null;duration:number;speech_seconds:number;gap_seconds:number;
  shortfall:number|null;overlap_seconds:number;missing:number;excluded:number;overrun:number;preview_ready:boolean;
  gaps:{start:number;end:number}[];
  clips:{id:string;speaker_name:string;start:number;duration:number}[];
};
const seconds=(value:number)=>`${Number(value.toFixed(2))}초`;

export function SceneTimingReview({timing,requestId,version,sourceVersion,busy,error,refresh}:{timing:Timing;requestId:string;version:number;sourceVersion:number|null;busy:boolean;error:string;refresh:()=>void}) {
  const [mediaError,setMediaError]=useState(false);
  const speakers=[...new Set(timing.clips.map(c=>c.speaker_name))];
  const signature=timing.clips.map(c=>`${c.id}:${c.start}:${c.duration}`).join("|")+timing.duration;
  return <Card className="scene-timing-review"><section aria-label="시간 배분 확인">
    <header className="work-speech-heading"><div><h3>시간 배분 확인</h3><p className="muted">시간 측정용 임시 음성 · 답변 v{sourceVersion}{sourceVersion!==version?` → v${version}`:""}</p></div><Button variant="secondary" disabled={busy} onClick={()=>{setMediaError(false);refresh();}}>새로고침</Button></header>
    <dl className="scene-timing-summary">{[[timing.target===null?"마지막 배정 구간 기준":"목표 길이",timing.target??timing.duration],["구성 길이 · 미리듣기",timing.duration],["발화 실측 합계",timing.speech_seconds],["발화 사이·앞뒤 여백",timing.gap_seconds]].map(([label,value])=><div key={String(label)}><dt>{label}</dt><dd>{seconds(Number(value))}</dd></div>)}</dl>
    {timing.shortfall!==null&&timing.shortfall>0&&<p role="status" className="work-speech-warning">목표 대비 {seconds(timing.shortfall)} 부족합니다. 부족한 시간은 무음으로 채우지 않습니다. 행동·반응의 구성을 검토해 주세요.</p>}
    <p className="muted">여백은 행동·반응·쉼에 사용할 수 있는 시간입니다. 실제 영상 동작의 자연스러움까지 검증한 값은 아닙니다.</p>
    {(timing.queued>0||timing.running>0)&&<p role="status">측정 음성 생성 · 대기 {timing.queued}개 · 생성 중 {timing.running}개. 오디오 워커가 처리하면 자동 갱신됩니다.</p>}
    {error&&<p role="alert">{error}</p>}
    {(timing.missing>0||timing.overlap_seconds>0||timing.overrun>0)&&<p role="status" className="work-speech-warning">{timing.missing>0?`측정 누락 ${timing.missing}개. `:""}{timing.overlap_seconds>0?`발화 겹침 ${seconds(timing.overlap_seconds)}. `:""}{timing.overrun>0?`목표 초과 ${seconds(timing.overrun)}. `:""}시간표를 확인해 주세요.</p>}
    <div className="scene-timing-timeline" role="img" aria-label={`발화 타임라인, 전체 ${seconds(timing.duration)}. ${timing.clips.map(c=>`${c.speaker_name} ${seconds(c.start)}부터 ${seconds(c.start+c.duration)}`).join(". ")}`}>
      <div className="scene-timing-axis"><span>0초</span><span>{seconds(timing.duration/2)}</span><span>{seconds(timing.duration)}</span></div>
      {speakers.map(speaker=><div className="scene-timing-row" key={speaker}><strong>{speaker.replace(" · 측정용","")}</strong><div className="scene-timing-track">{timing.clips.filter(c=>c.speaker_name===speaker).map(c=><span key={c.id} className="scene-timing-bar" title={`${speaker} ${seconds(c.start)}–${seconds(c.start+c.duration)}`} style={{left:`${c.start/timing.duration*100}%`,width:`${c.duration/timing.duration*100}%`}}/>)}</div><p className="muted">{timing.clips.filter(c=>c.speaker_name===speaker).map(c=>`${seconds(c.start)}–${seconds(c.start+c.duration)}`).join(" · ")}</p></div>)}
    </div>
    <p className="muted">발화 사이·앞뒤 여백: {timing.gaps.map(g=>`${seconds(g.start)}–${seconds(g.end)} (${seconds(g.end-g.start)})`).join(" · ")||"없음"}</p>
    <div className="scene-timing-player"><h4>간격을 포함한 전체 미리듣기</h4>{timing.preview_ready?<audio key={signature} controls preload="metadata" aria-label="간격을 포함한 시간 측정용 전체 음성" src={`/api/v1/audio/work/${requestId}/${version}/timing-preview`} onError={()=>setMediaError(true)}/>:<p>정상 음성이 모두 준비되고 발화 겹침이 해소되면 전체 미리듣기를 사용할 수 있습니다.</p>}{mediaError&&<p role="alert">전체 음성을 불러오지 못했습니다. 새로고침 후 다시 확인해 주세요.</p>}<p className="muted">기존 음성에 시간표의 무음을 넣어 재생합니다. 추가 AI 호출은 없으며 최종 제작 음성이 아닙니다.{timing.excluded>0?` 오류·이전 결과 ${timing.excluded}개는 제외했습니다.`:""}</p></div>
    <p className="muted">자동 측정이 설정된 씬 구성의 새 요청·다시 요청은 답변 저장 후 측정 음성을 생성합니다. 측정 완료 후 계획의 발화 간격을 유지해 배치하며, 최종 목소리로 제작한 뒤에는 시간을 다시 검증해야 합니다.</p>
  </section></Card>;
}
