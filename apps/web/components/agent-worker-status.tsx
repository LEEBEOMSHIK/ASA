"use client";
import { useEffect, useId, useRef, useState } from "react";
import { VideoGenerationManager } from "./video-generation-manager";
import { api } from "../lib/registry";
import { summary, targets } from "../lib/background-workers";
import { ActionIcon, Button, StatusBadge } from "./ui";

type Kind = "script" | "image" | "audio" | "video";
type Worker = { kind: Kind; state: string; enabled: boolean; busy: boolean };
type WorkerStatus = { online: boolean; image_online: boolean; can_manage: boolean; workers: Worker[] };
const names: Record<Kind, string> = { script: "AI 답변", image: "이미지 생성", audio: "음성 생성", video:"영상 생성" };
const labels: Record<string, string> = {
  stopped: "중지됨", starting: "시작 중", running: "온라인", stopping: "중지 예약됨",
  offline: "연결 끊김", failed: "실행 오류", external: "기존 프로세스 실행 중",
};

export function AgentWorkerStatus() {
  const [status, setStatus] = useState<WorkerStatus | null>(null);
  const [pending, setPending] = useState<Kind | "all" | null>(null);
  const [error, setError] = useState("");
  const [unavailable, setUnavailable] = useState(false);
  const generation = useRef(0);
  const changing = useRef(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const dialogId = useId();
  useEffect(() => {
    let live = true, fetching = false;
    async function update() {
      if (fetching || changing.current || document.hidden) return;
      fetching = true;
      const version = generation.current;
      try {
        const data = await api<WorkerStatus>("/agent-worker/status");
        if (live && version === generation.current) { setStatus(data); setUnavailable(false); }
      } catch { if (live) setUnavailable(true); }
      finally { fetching = false; }
    }
    void update();
    const timer = window.setInterval(update, 3000);
    document.addEventListener("visibilitychange", update);
    return () => { live = false; clearInterval(timer); document.removeEventListener("visibilitychange", update); };
  }, []);
  async function change(kind: Kind, action: "start" | "stop") {
    if (changing.current) return;
    changing.current = true;
    generation.current++;
    setPending(kind); setError("");
    try {
      setStatus(await api<WorkerStatus>(`/agent-worker/${kind}/${action}`, "POST", {}));
      setUnavailable(false);
    } catch { setError(`${names[kind]} 제어 요청을 처리하지 못했습니다. 상태를 확인한 뒤 다시 시도해 주세요.`); }
    finally { generation.current++; changing.current = false; setPending(null); }
  }
  async function changeAll(action:"start"|"stop") {
    if(changing.current||!status)return;
    changing.current=true;generation.current++;setPending("all");setError("");
    const failures:string[]=[];
    try {
      const fresh=await api<WorkerStatus>("/agent-worker/status");
      for(const worker of targets(fresh.workers,action)){
        try {setStatus(await api<WorkerStatus>(`/agent-worker/${worker.kind}/${action}`,"POST",{}));}
        catch {failures.push(names[worker.kind]);}
      }
      setStatus(await api<WorkerStatus>("/agent-worker/status"));setUnavailable(false);
      if(failures.length)setError(`${failures.join(", ")} 요청을 처리하지 못했습니다. 다른 항목은 적용됐으며 아래 상태를 확인해 주세요.`);
    } catch {setError("최신 상태를 확인하지 못했습니다. 상태를 확인한 뒤 다시 시도해 주세요.");}
    finally {generation.current++;changing.current=false;setPending(null);}
  }
  const aggregate=status?summary(status.workers):null;
  return <section className="workspace-worker-panel" aria-label="백그라운드 작업 상태 및 관리">
    <div className="workspace-worker-strip">
      <strong>백그라운드 작업</strong>
      <StatusBadge tone={unavailable?"warning":aggregate?.tone??"neutral"}>{unavailable?"상태 미확인":aggregate?.text??"확인 중"}</StatusBadge>
      {aggregate&&!unavailable&&<span>{aggregate.detail}</span>}
      <Button variant="secondary" className="background-management-trigger" disabled={!status} aria-haspopup="dialog" aria-controls={dialogId}
        onClick={event=>{trigger.current=event.currentTarget;dialog.current?.showModal();}}><ActionIcon kind="settings"/>작업 관리</Button>
    </div>
    {status && <dialog ref={dialog} id={dialogId} className="worker-controls-dialog background-work-dialog"
      aria-labelledby={`${dialogId}-title`} onClose={() => trigger.current?.focus()}>
      <div className="worker-controls-heading">
        <h2 id={`${dialogId}-title`}>백그라운드 작업 관리</h2>
        <Button variant="secondary" autoFocus onClick={() => dialog.current?.close()}><ActionIcon kind="close"/>닫기</Button>
      </div>
      <div className="worker-controls background-work-content">
      <p className="worker-controls-help">시작하면 대기 요청을 처리하며 AI 사용료가 발생할 수 있습니다. 중지하면 진행 중인 처리 이후 멈추고 대기 요청은 보존합니다. 영상은 현재 통신 이후 결과 조회를 멈춥니다.</p>
      {status.can_manage&&<div className="background-work-actions">
        <Button disabled={unavailable||pending!==null||!targets(status.workers,"start").length} onClick={()=>void changeAll("start")}><ActionIcon kind="play"/>전체 시작</Button>
        <Button variant="secondary" disabled={unavailable||pending!==null||!targets(status.workers,"stop").length} onClick={()=>void changeAll("stop")}><ActionIcon kind="stop"/>전체 중지</Button>
      </div>}
      <p className="helper-text">이미 실행 중인 항목은 유지합니다. 사용 불가·중지 중·기존 프로세스 항목은 전체 시작에서 제외되며 아래에 이유를 표시합니다.</p>
      <div className="worker-controls-grid">
        {status.workers.map(worker => {
          const active = ["starting", "running"].includes(worker.state);
          const waiting = worker.state === "stopping";
          const stopLabel=worker.kind==="video"?"현재 통신 후 중지":"작업 완료 후 중지";
          return <div className="worker-control" key={worker.kind}>
            <div className="worker-control-heading">
              <strong>{names[worker.kind]}</strong>
              <StatusBadge tone={worker.state==="running"?"success":["failed","offline","external"].includes(worker.state)?"warning":"neutral"}>{unavailable ? "상태 미확인" : labels[worker.state]}</StatusBadge>
            </div>
            <p>{worker.state==="external"?"기존 프로세스를 최신 실행 명령으로 다시 시작해야 제어할 수 있습니다.":worker.kind==="video"?"중지하면 현재 통신 이후 결과 조회가 멈춥니다. 공급자 생성은 계속되며 다시 시작하면 결과를 회수합니다.":waiting ? "현재 작업 완료 후 중지합니다." : worker.state === "external" ? "기존 워커를 최신 실행 명령으로 다시 시작해야 제어할 수 있습니다." : !worker.enabled ? "서버에서 AI 생성이 비활성화되어 있습니다." : active ? "접수된 작업을 순서대로 처리합니다." : "시작하면 대기 중인 작업을 처리합니다."}</p>
            <Button variant="secondary" disabled={!status.can_manage || unavailable || pending !== null || waiting || worker.state === "external" || (!active && !worker.enabled)}
              aria-label={`${names[worker.kind]} ${waiting ? "중지 대기 중" : active ? stopLabel : "시작"}`}
              onClick={() => void change(worker.kind, active ? "stop" : "start")}>
              <ActionIcon kind={active?"stop":"play"}/>{pending === worker.kind ? "요청 중…" : waiting ? "중지 대기 중" : active ? stopLabel : "시작"}
            </Button>
          </div>;
        })}
      </div>
      {status.can_manage&&<VideoGenerationManager/>}
      {pending=== "all"&&<p role="status">전체 제어 요청을 처리 중입니다…</p>}
      {unavailable && <p role="alert">상태를 확인할 수 없습니다. 연결이 복구되면 자동으로 갱신합니다.</p>}
      {error && <p role="alert">{error}</p>}
      </div>
    </dialog>}
  </section>;
}
