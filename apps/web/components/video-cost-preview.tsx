"use client";
import {useEffect,useId,useState} from "react";
import {api} from "../lib/registry";
import {videoCostLabel,type VideoEstimate} from "../lib/video-cost";
import {DisclosureSummary,Field} from "./ui";

export function VideoCostPreview({modelKey,revision,durations,modelLabel,supportsVideoReference=true,rate,videoRate,initialSeconds}:{initialSeconds?:number;modelKey:string;revision:string;durations:number[];modelLabel:string;supportsVideoReference?:boolean;rate?:number|null;videoRate?:number|null}) {
  const id=useId();
  const [seconds,setSeconds]=useState(initialSeconds&&durations.includes(initialSeconds)?initialSeconds:durations.includes(5)?5:durations[0]);
  const [video,setVideo]=useState(false);
  const [estimate,setEstimate]=useState<VideoEstimate|null>(null);
  const [state,setState]=useState<"loading"|"ready"|"error">("loading");
  useEffect(()=>{
    let live=true;
    setState("loading");setEstimate(null);
    void api<VideoEstimate>("/video-planning/estimate","POST",{model_key:modelKey,model_revision:revision,duration_seconds:seconds,reference_video:supportsVideoReference&&video})
      .then(value=>{if(live){setEstimate(value);setState("ready");}})
      .catch(()=>{if(live)setState("error");});
    return()=>{live=false;};
  },[modelKey,revision,seconds,video,supportsVideoReference]);
  return <section className="video-cost-summary" aria-label="예상 요금">
    <p className="helper-text">공개 요금 · 출력 1초당 {rate==null?"미확인":`$${rate} USD`}{supportsVideoReference&&` · 영상 참조 포함 ${videoRate==null?"미확인":`$${videoRate} USD/초`}`} · 실제 청구액과 다를 수 있음</p>
    <details className="video-model-guidance video-cost-calculator">
    <DisclosureSummary>{modelLabel} 요금 계산기</DisclosureSummary><div className="video-cost-calculator-body">
    <p className="helper-text">실제 클립 길이는 적용된 길이 설정에 따라 계획합니다. 자동 판단을 선택하면 AI가 대본·씬과 모델 지원 범위를 바탕으로 정합니다. 생성 전에 클립 계획의 길이와 예상 비용을 확인하고 확정하세요. 길이를 바꾸려면 클립 계획 수정에서 요청할 수 있습니다.</p>
    <Field id={`${id}-duration`} label="계산 예시 길이" hint="계산 예시이며 실제 영상 계획이나 저장된 설정을 변경하지 않습니다.">{props=><select {...props} value={seconds} onChange={event=>setSeconds(Number(event.target.value))}>{durations.map(duration=><option key={duration} value={duration}>{duration}초</option>)}</select>}</Field>
    {supportsVideoReference&&<label className="checkbox video-cost-reference"><input type="checkbox" checked={video} onChange={event=>setVideo(event.target.checked)}/><span>계산 예시에 참조 영상 포함</span></label>}
    <p role="status">{state==="loading"?"예상 비용 확인 중…":videoCostLabel(estimate?.amount_usd)}</p>
    {state==="error"&&<p className="helper-text">비용 정보를 불러오지 못했습니다. 모델을 다시 선택하거나 잠시 후 확인해 주세요.</p>}
    <p className="helper-text">선택한 모델이 지원하는 참조 파일은 영상 생성을 요청할 때 서버가 자동으로 업로드합니다. 모델 선택과 비용 확인만으로 업로드하거나 생성하지 않습니다.</p>
  </div></details></section>;
}
