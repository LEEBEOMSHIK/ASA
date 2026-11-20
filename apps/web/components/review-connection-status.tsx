"use client";
import { useEffect, useState } from "react";
import { api, message } from "../lib/registry";
import { ActionIcon, Button, StatusBadge } from "./ui";

type Check = {compatible:boolean;model:string;provider:string};
export function ReviewConnectionStatus({agentRef,kind="image"}:{agentRef:string;kind?:"image"|"video"}) {
  const [result,setResult]=useState<Check|null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(true);
  const [retry,setRetry]=useState(0);
  useEffect(()=>{
    let active=true; setLoading(true); setResult(null); setError("");
    api<Check>(`/review-connection?agent_ref=${encodeURIComponent(agentRef)}`)
      .then(value=>{if(active)setResult(value);})
      .catch(e=>{if(active)setError(message(e));})
      .finally(()=>{if(active)setLoading(false);});
    return ()=>{active=false;};
  },[agentRef,retry]);
  return <div className="review-connection-status" role="status">
    <StatusBadge tone={error?"warning":result?"success":"neutral"}>{loading?"연결 확인 중":error?"연결 확인 필요":"이미지 입력 연결 가능"}</StatusBadge>
    <p>{kind==="video"?"생성된 영상의 샘플 프레임과 생성 당시 제작 지시를 함께 전달합니다. 오디오·대사·음색·립싱크 및 샘플 사이 움직임은 미검증입니다.":"생성된 이미지와 캐릭터 설정을 함께 전달합니다. 수정 이미지라면 이전 기준 이미지도 전달합니다. 별도의 용도 지정이나 이미지 입력 항목 추가는 필요하지 않습니다."}</p>
    {result && <p>{result.provider} · {result.model} · 공식 문서에서 이미지 입력 지원 확인</p>}
    {error && <><p>{error}</p><Button variant="secondary" onClick={()=>setRetry(retry+1)}><ActionIcon kind="refresh"/>다시 확인</Button></>}
    <p className="helper-text">{kind==="video"?"선택한 에이전트의 지침과 표준 영상 검수 보고서 형식을 사용합니다. 요약·항목별 관찰·문제·미검증·한계를 기록하며 영상 생성이나 확정을 자동 실행하지 않습니다.":"검수에는 선택한 에이전트의 지침과 답변 형식을 사용합니다. 일반 실행용 입력 양식 대신 위 자료를 전달하며, 저장·등록·실행할 때 다시 검증합니다."}</p>
  </div>;
}
