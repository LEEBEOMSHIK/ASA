"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/registry";
import { StatusBadge } from "./ui";

type WorkerStatus = { online: boolean; image_online?: boolean };

function WorkerBadge({ name, online }: { name: string; online?: boolean }) {
  return <StatusBadge tone={online === undefined ? "neutral" : online ? "success" : "warning"}>
    {name} {online === undefined ? "상태 미확인" : online ? "온라인" : "오프라인"}
  </StatusBadge>;
}

export function AgentWorkerStatus() {
  const [status,setStatus]=useState<WorkerStatus|null>(null);
  useEffect(()=>{
    let live=true, pending=false;
    async function update(){
      if(pending || document.hidden)return;
      pending=true;
      try {const data=await api<WorkerStatus>("/agent-worker/status");if(live)setStatus(data);}
      catch {if(live)setStatus(null);}
      finally {pending=false;}
    }
    void update();
    const timer=window.setInterval(update,30000);
    document.addEventListener("visibilitychange",update);
    return ()=>{live=false;clearInterval(timer);document.removeEventListener("visibilitychange",update);};
  },[]);
  return <div className="workspace-worker-strip" role="status">
    <strong>작업 공간 상태</strong>
    <WorkerBadge name="에이전트 워커" online={status?.online}/>
    <WorkerBadge name="이미지 워커" online={status?.image_online}/>
    {status?.online===false && <span>접수된 에이전트 요청은 워커가 연결되면 순서대로 시작합니다.</span>}
  </div>;
}
