"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/registry";
import { DisclosureSummary } from "./ui";
import "./video-source-panel.css";

type SourceImage = {image_id:string;name:string;role:string;url:string};
type Sources = {video_references?:{job_id:string;clip_id?:string;source_answer_version?:number}[];generation_mode:"reference"|"first_frame";audio_reference:{speaker_id?:string;start_seconds?:number;end_seconds?:number;source_answer_version?:number};answer_version:number;inherited:boolean;snapshot_available:boolean;script:string;scenes:string;
  scene_name:string;scene_settings:Record<string,string>;generation_images:SourceImage[];planning_images:SourceImage[]};
function Images({items}:{items:SourceImage[]}) {
  return <div className="video-source-images">{items.map((item,index)=><figure key={`${item.image_id}-${index}`}>
    {/* eslint-disable-next-line @next/next/no-img-element */}
    <img src={item.url} alt={item.name} loading="lazy"/><figcaption>{item.name}</figcaption>
  </figure>)}</div>;
}
export function VideoSourcePanel({requestId,version,clipId,jobId}:{requestId:string;version:number;clipId:string;jobId:string}) {
  const [data,setData]=useState<Sources|null>(null);
  const [error,setError]=useState(false);
  useEffect(()=>{
    let active=true;setData(null);setError(false);
    void api<Sources>(`/video-clips/${requestId}/${version}/sources/${encodeURIComponent(clipId)}?job_id=${encodeURIComponent(jobId)}`)
      .then(value=>{if(active)setData(value);}).catch(()=>{if(active)setError(true);});
    return()=>{active=false;};
  },[requestId,version,clipId,jobId]);
  return <section className="video-source-panel" aria-label="영상 생성 당시 자료">
    <h4>생성 당시 자료</h4>
    {error?<p role="alert">생성 당시 자료를 불러오지 못했습니다. 클립을 다시 열어 주세요.</p>:!data?<p role="status">자료 확인 중…</p>:<>
      <p className="helper-text">답변 {data.answer_version} 기준{data.inherited?" · 이전 답변에서 이어받은 영상":""}. 현재 수정본과 다를 수 있습니다.</p>
      <details open><DisclosureSummary>영상 생성 입력 이미지 · {data.generation_images.length}장</DisclosureSummary>
        <p className="helper-text">{data.generation_mode==="reference"?"참조 기반 생성에 사용된 이미지입니다. 첫 프레임을 고정하지 않습니다.":"저장된 영상 생성 입력의 이미지입니다. 시작 이미지 또는 앞 영상의 마지막 프레임을 사용합니다."}</p>
        {data.generation_images.length?<Images items={data.generation_images}/>:<p className="helper-text">확인 가능한 생성 입력 이미지가 없습니다.</p>}
      </details>
      {data.audio_reference.speaker_id&&<p className="helper-text">음성 참조: {data.audio_reference.speaker_id} · {data.audio_reference.start_seconds}–{data.audio_reference.end_seconds}초 · 답변 {data.audio_reference.source_answer_version}</p>}
      {!!data.video_references?.length&&<div className="video-source-text"><strong>생성 당시 참조 영상</strong>{data.video_references.map((reference,index)=><p className="helper-text" key={reference.job_id}>참조 영상 {index+1}{reference.clip_id?` · 클립 ${reference.clip_id}`:""}{reference.source_answer_version!=null?` · 답변 ${reference.source_answer_version}`:""}</p>)}</div>}
      <details><DisclosureSummary>계획 참고 캐릭터 · {data.planning_images.length}장</DisclosureSummary>
        <p className="helper-text">비디오 계획에 연결된 캐릭터 자료입니다. 이 목록만으로 영상 모델에 직접 전송되었다고 볼 수 없습니다.</p>
        {data.planning_images.length?<Images items={data.planning_images}/>:<p className="helper-text">저장된 참고 캐릭터가 없습니다.</p>}
      </details>
      {!data.snapshot_available&&<p className="notice">당시 원본 자료 스냅샷이 없어 대본·씬을 확인할 수 없습니다.</p>}
      {data.scene_name&&<details><DisclosureSummary>선택 씬 · {data.scene_name}</DisclosureSummary>
        {Object.entries(data.scene_settings).map(([key,value])=><div className="video-source-text" key={key}><strong>{({facts:"원문 사실",proposed:"장면 연출",image_prompt:"이미지 지시"})[key]??key}</strong><pre tabIndex={0}>{value}</pre></div>)}
      </details>}
      {data.script&&<details><DisclosureSummary>대본 원문</DisclosureSummary><pre tabIndex={0}>{data.script}</pre></details>}
      {data.scenes&&<details><DisclosureSummary>씬 구성 원문</DisclosureSummary><pre tabIndex={0}>{data.scenes}</pre></details>}
    </>}
  </section>;
}
