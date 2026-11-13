"use client";
import { useEffect, useRef, useState } from "react";
import { api, message } from "../lib/registry";
import { elapsedTime } from "../lib/image-job-time";
import { ReviewDashboard as ReviewAnswer } from "./review-dashboard";
import { ActionIcon, Button, StatusBadge } from "./ui";

type Character = {id:string;name:string;facts:string;proposed:string;appearance:string;scene_ids:string;image_prompt:string};
export type AssetReview = {id:string;image_id:string;name:string;agent_ref:string;character:Character;status:string;result:unknown;created_at:string;finished_at:string|null};
export function ImageReviewPanel({imageId, version, character, reviews, configured, online, enqueueError, refresh, scene=false, onBusyChange}: {
  scene?:boolean;onBusyChange?:(busy:boolean)=>void;
  imageId:string;version:number;character:Character;reviews:AssetReview[];configured:boolean;online:boolean;enqueueError?:string|null;refresh:()=>Promise<void>;
}) {
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  useEffect(()=>{onBusyChange?.(busy);},[busy,onBusyChange]);
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
    <div className="character-heading"><h4>AI 이미지 검수 · v{version}</h4><StatusBadge tone={latest?.status==="failed"?"danger":latest && ["succeeded","unknown"].includes(latest.status)?"warning":"neutral"}>{latest ? ({queued:"검수 대기",running:"검수 중",succeeded:"검수 의견 도착",failed:"검수 실패",unknown:"호출 확인 필요"}[latest.status] || "확인 필요") : "검수 전"}</StatusBadge></div>
    {!configured && <p className="muted">{latest ? "이전에 실행한 검수 의견입니다. 이 작업에는 재검수 연결이 설정되어 있지 않습니다." : "이 작업에는 검수 에이전트가 연결되어 있지 않습니다. 직접 확인한 뒤 확정할 수 있습니다."} 에이전트 설정의 ‘답변 이후 작업’에서 연결하고 저장하면 이후 새 작업에 적용됩니다.</p>}
    {active && <p role="status">{online?"백그라운드에서 검수를 진행합니다. 다른 화면으로 이동해도 계속됩니다.":"이미지 워커 연결을 기다리고 있습니다."} · 경과 {elapsedTime(latest.created_at,now)}</p>}
    {changed && <p className="notice">검수 이후 {scene?"씬 설정":"캐릭터 설정"}을 변경했습니다. 기존 의견은 아래 기록 당시의 설정 기준입니다. 다시 검수해 주세요.</p>}
    {latest?.status==="succeeded" && <><p className="helper-text">{new Date(latest.finished_at || latest.created_at).toLocaleString("ko-KR")} · AI의 검토 의견이며 최종 확정은 직접 해 주세요.</p><ReviewAnswer value={latest.result}/></>}
    {(latest?.status==="failed" || latest?.status==="unknown" || (!latest && enqueueError)) && <p role="alert">검수를 완료하지 못했습니다. 이미지와 확정 상태는 유지됩니다. 모델의 이미지 입력 지원 및 관리자 사용량 기록을 확인한 뒤 다시 요청하세요. 자동 재시도하지 않습니다.</p>}
    {configured && <><Button variant="secondary" disabled={busy || !!active} onClick={()=>void request()}><ActionIcon kind="ai"/>{busy?"접수 중…":active?"검수 진행 중":latest?"AI 다시 검수":"AI 검수 요청"}</Button><p className="helper-text">현재 이미지와 편집한 {scene?"씬 설정":"캐릭터 설정"}으로 검토합니다. 별도 AI 비용이 발생하며 설정은 검수 기록에만 보관됩니다. 이미지 재생성·사용자 확정은 자동으로 하지 않습니다.</p></>}
    {error && <p role="alert">{error}</p>}
    {history.length>0 && <details className="character-edit"><summary>검수 실행 이력 · {history.length}회</summary><div className="character-form"><p className="helper-text">이 이미지 버전에 AI 검수를 요청한 내역입니다. 발견한 문제의 개수가 아닙니다. 실행 시각과 당시 전달한 설정을 확인할 수 있습니다.</p>{history.map((r,i)=><div className="review-history-entry" key={r.id}><strong>{history.length-i}번째 검수 · {new Date(r.created_at).toLocaleString("ko-KR")}</strong><StatusBadge>{r.status==="succeeded"?"검수 완료":r.status==="queued"?"대기":r.status==="running"?"진행 중":"확인 필요"}</StatusBadge><details className="character-edit"><summary>당시 전달한 {scene?"씬 설정":"캐릭터 설정"}</summary><dl className="review-settings">{[["외형·의상",r.character.appearance],["제작 지침",r.character.image_prompt],["대본 정보",r.character.facts],["AI 제안",r.character.proposed]].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value || "없음"}</dd></div>)}</dl></details>{i===0 && r.result!=null ? <p className="helper-text">최신 검수 의견은 위에 표시되어 있습니다.</p> : r.result!=null && <details className="character-edit"><summary>이전 검수 의견 보기</summary><ReviewAnswer value={r.result}/></details>}</div>)}</div></details>}
  </section>;
}
