"use client";
import { useState } from "react";
import { voiceLabel } from "../lib/voice-labels";
import { Button, DisclosureSummary } from "./ui";

export type BasicPreview = {ready:boolean;description:string;duration?:number;model?:string;text?:string};
export type BasicPreviews = Record<string,Record<string,BasicPreview>>;

function PreviewAudio({model,voice}:{model:string;voice:string}) {
  const [failed,setFailed]=useState(false);
  return <><audio controls preload="none" aria-label={`${voiceLabel(voice)} 기본 샘플`} src={`/api/v1/audio/previews/${encodeURIComponent(model)}/${encodeURIComponent(voice)}`} onError={()=>setFailed(true)} onPlay={e=>{document.querySelectorAll("audio").forEach(other=>{if(other!==e.currentTarget)other.pause();});}}/>{failed&&<p role="alert">기본 샘플을 불러오지 못했습니다. 연결 상태를 확인하고 화면을 새로고침해 주세요.</p>}</>;
}

export function BasicVoicePreview({model,voice,voices,previews,disabled,onSelect}:{model:string;voice:string;voices:string[];previews:BasicPreviews;disabled:boolean;onSelect:(voice:string)=>void}) {
  const chosen=previews[model]?.[voice];
  return <section className="basic-voice-preview" aria-label="기본 음색 미리듣기">
    <h4>기본 샘플 · 바로 듣기</h4>
    <p className="muted">미리 만든 한국어 음성입니다. 저장·생성 없이 재생하며 추가 생성 비용이 없습니다. 아래의 말투 요청은 적용되지 않은 기본 음색 참고용입니다.</p>
    <strong>{voiceLabel(voice)}</strong><p>{chosen?.description||"이 음색의 기본 샘플은 아직 준비되지 않았습니다."}</p>
    {chosen?.ready?<PreviewAudio key={model+voice} model={model} voice={voice}/>:<p className="muted">관리자가 기본 샘플을 준비하면 여기에서 바로 들을 수 있습니다.</p>}
    <p className="muted">느낌 설명은 이 샘플의 음높이·길이를 기준으로 한 참고 정보입니다. 실제 말투와 언어에 따라 달라질 수 있습니다.</p>
    <details><DisclosureSummary>모든 기본 음색 비교 · {voices.length}개</DisclosureSummary><div className="voice-sample-list">{voices.map(item=>{const preview=previews[model]?.[item];return <article className="voice-sample-card" key={item}><strong>{voiceLabel(item)}</strong><p>{preview?.description||"기본 샘플 준비 전"}</p>{preview?.ready&&<PreviewAudio model={model} voice={item}/>}<Button variant="secondary" disabled={disabled||voice===item} onClick={()=>onSelect(item)}>{voice===item?"현재 기본 음색":"이 기본 음색 사용"}</Button></article>;})}</div></details>
  </section>;
}
