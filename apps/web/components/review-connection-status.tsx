"use client";
import { useEffect, useState } from "react";
import { api, message } from "../lib/registry";
import { Button, StatusBadge } from "./ui";

type Check = {compatible:boolean;model:string;provider:string};
export function ReviewConnectionStatus({agentRef}:{agentRef:string}) {
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
    <p>생성된 이미지와 캐릭터 설정을 함께 전달합니다. 수정 이미지라면 이전 기준 이미지도 전달합니다. 별도의 용도 지정이나 이미지 입력 항목 추가는 필요하지 않습니다.</p>
    {result && <p>{result.provider} · {result.model} · 공식 문서에서 이미지 입력 지원 확인</p>}
    {error && <><p>{error}</p><Button variant="secondary" onClick={()=>setRetry(retry+1)}>다시 확인</Button></>}
    <p className="helper-text">검수에는 선택한 에이전트의 지침과 답변 형식을 사용합니다. 일반 실행용 입력 양식 대신 위 자료를 전달하며, 저장·등록·실행할 때 다시 검증합니다.</p>
  </div>;
}
