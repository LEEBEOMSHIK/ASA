"use client";
import { useEffect, useRef, useState } from "react";
import { api, message } from "../lib/registry";
import { elapsedTime } from "../lib/image-job-time";
import { AnswerView } from "./agent-answer";
import { Button, StatusBadge } from "./ui";

type Character = {id:string;name:string;facts:string;proposed:string;appearance:string;scene_ids:string;image_prompt:string};
export type AssetReview = {id:string;image_id:string;name:string;agent_ref:string;character:Character;status:string;result:unknown;created_at:string;finished_at:string|null};
export function ImageReviewPanel({imageId, version, character, reviews, configured, online, enqueueError, refresh}: {
  imageId:string;version:number;character:Character;reviews:AssetReview[];configured:boolean;online:boolean;enqueueError?:string|null;refresh:()=>Promise<void>;
}) {
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  const [now,setNow]=useState(Date.now());
  const dispatch=useRef<{signature:string;id:string}|null>(null);
  const history=reviews.filter(r=>r.image_id===imageId), latest=history[0];
  const active=latest && ["queued","running"].includes(latest.status);
  useEffect(()=>{if(!active)return;const timer=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[active,latest?.id]);
  const changed=latest && Object.keys(character).some(k=>character[k as keyof Character]!==latest.character[k as keyof Character]);
  async function request() {
    setBusy(true);setError("");
    try {
      const signature=JSON.stringify({imageId,character});
      if(dispatch.current?.signature!==signature)dispatch.current={signature,id:crypto.randomUUID()};
      await api(`/characters/images/${imageId}/reviews`,"POST",{id:dispatch.current.id,character});
      dispatch.current=null;await refresh();
    } catch(e) {setError(message(e));} finally {setBusy(false);}
  }
  return <section className="image-review character-form" aria-label={`이미지 v${version} AI 검수`}>
    <div className="character-heading"><h4>AI 이미지 검수 · v{version}</h4><StatusBadge>{latest ? ({queued:"검수 대기",running:"검수 중",succeeded:"검수 의견 도착",failed:"검수 실패",unknown:"호출 확인 필요"}[latest.status] || "확인 필요") : "검수 전"}</StatusBadge></div>
    {!configured && <p className="muted">이 작업에는 검수 에이전트가 연결되어 있지 않습니다. 직접 확인한 뒤 확정할 수 있습니다. 에이전트 설정의 ‘답변 이후 작업’에서 연결하고 새 버전을 등록하면 이후 요청에 적용됩니다.</p>}
    {active && <p role="status">{online?"백그라운드에서 검수를 진행합니다. 다른 화면으로 이동해도 계속됩니다.":"이미지 워커 연결을 기다리고 있습니다."} · 경과 {elapsedTime(latest.created_at,now)}</p>}
    {changed && <p className="notice">검수 이후 캐릭터 설정을 변경했습니다. 기존 의견은 아래 기록 당시의 설정 기준입니다. 다시 검수해 주세요.</p>}
    {latest?.status==="succeeded" && <AnswerView value={latest.result}/>}
    {(latest?.status==="failed" || latest?.status==="unknown" || (!latest && enqueueError)) && <p role="alert">검수를 완료하지 못했습니다. 이미지와 확정 상태는 유지됩니다. 모델의 이미지 입력 지원 및 관리자 사용량 기록을 확인한 뒤 다시 요청하세요. 자동 재시도하지 않습니다.</p>}
    {configured && <><Button variant="secondary" disabled={busy || !!active} onClick={()=>void request()}>{busy?"접수 중…":active?"검수 진행 중":latest?"AI 다시 검수":"AI 검수 요청"}</Button><p className="helper-text">현재 이미지와 편집한 캐릭터 설정으로 검토합니다. 별도 AI 비용이 발생하며 설정은 검수 기록에만 보관됩니다. 이미지 재생성·사용자 확정은 자동으로 하지 않습니다.</p></>}
    {error && <p role="alert">{error}</p>}
    {history.length>0 && <details><summary>검수 기록 · {history.length}건</summary><div className="character-form">{history.map(r=><div key={r.id}><strong>{r.name} · {new Date(r.created_at).toLocaleString("ko-KR")}</strong><p>{r.status==="succeeded"?"검수 완료":r.status==="queued"?"대기":r.status==="running"?"진행 중":"확인 필요"}</p><details><summary>검수에 사용한 설정과 의견</summary><p>외형·의상: {r.character.appearance}</p><p>제작 지침: {r.character.image_prompt}</p><p>대본 정보: {r.character.facts}</p><p>AI 제안: {r.character.proposed}</p>{r.result!=null && <AnswerView value={r.result}/>}</details></div>)}</div></details>}
  </section>;
}
