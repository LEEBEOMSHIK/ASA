"use client";
import { useEffect, useId, useRef, useState } from "react";
import { api } from "../lib/registry";
import { Button, StatusBadge } from "./ui";

type Kind = "script" | "image" | "audio";
type Worker = { kind: Kind; state: string; enabled: boolean; busy: boolean };
type WorkerStatus = { online: boolean; image_online: boolean; can_manage: boolean; workers: Worker[] };
const names: Record<Kind, string> = { script: "에이전트 워커", image: "이미지 워커", audio: "오디오 워커" };
const labels: Record<string, string> = {
  stopped: "중지됨", starting: "시작 중", running: "온라인", stopping: "중지 예약됨",
  offline: "연결 끊김", failed: "실행 오류", external: "기존 프로세스 실행 중",
};

export function AgentWorkerStatus() {
  const [status, setStatus] = useState<WorkerStatus | null>(null);
  const [pending, setPending] = useState<Kind | null>(null);
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
  return <section className="workspace-worker-panel" aria-label="워커 상태 및 제어">
    <div className="workspace-worker-strip">
      <strong>작업 공간 상태</strong>
      {(["script", "image", "audio"] as Kind[]).map(kind => {
        const worker = status?.workers.find(item => item.kind === kind);
        const badge = <StatusBadge tone={!unavailable && worker?.state === "running" ? "success" : "neutral"}>
          {names[kind]} {unavailable ? "상태 미확인" : worker ? labels[worker.state] ?? "상태 미확인" : "확인 중"}
        </StatusBadge>;
        return status?.can_manage ? <button key={kind} type="button" className="worker-status-trigger"
          aria-haspopup="dialog" aria-controls={dialogId}
          aria-label={`${names[kind]} ${unavailable ? "상태 미확인" : labels[worker?.state ?? ""] ?? "확인 중"} · 워커 관리 열기`}
          onClick={event => { trigger.current = event.currentTarget; dialog.current?.showModal(); }}>
          {badge}
        </button> : <span key={kind}>{badge}</span>;
      })}
    </div>
    {status?.can_manage && <dialog ref={dialog} id={dialogId} className="worker-controls-dialog"
      aria-labelledby={`${dialogId}-title`} onClose={() => trigger.current?.focus()}>
      <div className="worker-controls-heading">
        <h2 id={`${dialogId}-title`}>워커 관리</h2>
        <Button variant="secondary" autoFocus onClick={() => dialog.current?.close()}>닫기</Button>
      </div>
      <div className="worker-controls">
      <p className="worker-controls-help">시작하면 대기 요청을 처리하며 AI 사용료가 발생할 수 있습니다. 중지 예약 시 진행 중인 작업을 마친 후 멈추고, 대기 요청은 보존합니다.</p>
      <div className="worker-controls-grid">
        {status.workers.map(worker => {
          const active = ["starting", "running"].includes(worker.state);
          const waiting = worker.state === "stopping";
          return <div className="worker-control" key={worker.kind}>
            <div className="worker-control-heading">
              <strong>{names[worker.kind]}</strong>
              <span role="status">{unavailable ? "상태 미확인" : labels[worker.state]}</span>
            </div>
            <p>{waiting ? "현재 작업 완료 후 중지합니다." : worker.state === "external" ? "기존 워커를 최신 실행 명령으로 다시 시작해야 제어할 수 있습니다." : !worker.enabled ? "서버에서 AI 생성이 비활성화되어 있습니다." : active ? "접수된 작업을 순서대로 처리합니다." : "시작하면 대기 중인 작업을 처리합니다."}</p>
            <Button variant="secondary" disabled={unavailable || pending !== null || waiting || worker.state === "external" || (!active && !worker.enabled)}
              aria-label={`${names[worker.kind]} ${waiting ? "중지 대기 중" : active ? "현재 작업 완료 후 중지" : "시작"}`}
              onClick={() => void change(worker.kind, active ? "stop" : "start")}>
              {pending === worker.kind ? "요청 중…" : waiting ? "중지 대기 중" : active ? "작업 완료 후 중지" : "시작"}
            </Button>
          </div>;
        })}
      </div>
      {unavailable && <p role="alert">상태를 확인할 수 없습니다. 연결이 복구되면 자동으로 갱신합니다.</p>}
      {error && <p role="alert">{error}</p>}
      </div>
    </dialog>}
  </section>;
}
