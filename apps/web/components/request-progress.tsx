"use client";
import { useEffect, useState } from "react";
import { StatusBadge } from "./ui";

export function RequestProgress({ status, createdAt, queueAhead, online, instructions, model, receiving }: {
  status: string; createdAt: string; queueAhead: number; online: boolean;
  instructions: string; model?: string; receiving?: boolean;
}) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const seconds = Math.max(0, Math.floor((now - Date.parse(createdAt)) / 1000));
  return <div className="request-progress">
    <div className="card-heading"><h3>요청을 접수했어요</h3><StatusBadge tone="warning">{status === "queued" ? "대기 중" : "AI 작성 중"}</StatusBadge></div>
    <p role="status">{status === "queued" ? online ? (queueAhead ? `앞선 작업 ${queueAhead}건이 처리되면 시작합니다.` : "작성을 시작할 준비를 하고 있습니다.") : "실행 서비스가 연결되지 않아 아직 AI 요청을 시작하지 못했습니다. 요청은 저장되어 있으며 서비스가 복구되면 자동으로 시작합니다. 다시 요청하지 않아도 됩니다." : receiving ? "모델의 응답이 도착하고 있습니다. 작성 안내와 답변을 실시간으로 표시합니다." : "AI에 요청을 보냈습니다. 모델의 첫 응답을 기다리고 있습니다."}</p>
    <ol className="request-progress-steps" aria-label="답변 생성 진행"><li>접수 완료</li><li aria-current={status === "queued" ? "step" : undefined}>실행 대기</li><li aria-current={status === "running" ? "step" : undefined}>AI 작성</li><li>결과 확인</li></ol>
    <p className="muted">접수 후 {Math.floor(seconds / 60)}분 {seconds % 60}초{model ? ` · ${model}` : ""}</p>
    <details className="advanced"><summary>적용할 에이전트 지침 확인</summary><p className="run-entered-value">{instructions}</p></details>
    {seconds >= 45 && (status !== "queued" || online) && <p className="helper-text">응답 시간이 길어지고 있습니다. 중복 실행하지 않아도 상태를 자동으로 확인합니다. 다른 작업으로 이동했다가 최근 작업에서 다시 확인할 수 있습니다.</p>}
  </div>;
}
