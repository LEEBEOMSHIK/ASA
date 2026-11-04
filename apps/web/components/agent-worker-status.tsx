"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/registry";
import { StatusBadge } from "./ui";

export function AgentWorkerStatus() {
  const [online,setOnline]=useState<boolean|null>(null);
  useEffect(()=>{
    let live=true, pending=false;
    async function update(){
      if(pending || document.hidden)return;
      pending=true;
      try {const data=await api<{online:boolean}>("/agent-worker/status");if(live)setOnline(data.online);}
      catch {if(live)setOnline(null);}
      finally {pending=false;}
    }
    void update();
    const timer=window.setInterval(update,30000);
    document.addEventListener("visibilitychange",update);
    return ()=>{live=false;clearInterval(timer);document.removeEventListener("visibilitychange",update);};
  },[]);
  return <div className="workspace-worker-strip" role="status">
    <strong>작업 공간 상태</strong>
    <StatusBadge tone={online===null?"neutral":online?"success":"warning"}>{online===null?"워커 상태 미확인":online?"에이전트 워커 온라인":"에이전트 워커 오프라인"}</StatusBadge>
    {online===false && <span>접수된 에이전트 요청은 워커가 연결되면 순서대로 시작합니다.</span>}
  </div>;
}
