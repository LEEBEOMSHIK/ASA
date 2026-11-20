"use client";

import { useEffect, useId, useRef, useState, type RefObject } from "react";
import { api, ApiError, message } from "../lib/registry";
import { Modal } from "./character-library";
import { ActionIcon, Button, Field } from "./ui";

type Stage = {
  revision: number;
  head_version: number;
  execution_enabled: boolean;
  attempts: {status:string}[];
};
type Operation = {fingerprint:string;id:string};

export function VideoClipRevisionDialog({requestId,version,clipId,title,disabled,operation,onClose,onAccepted}: {
  requestId:string; version:number; clipId:string; title:string; disabled:boolean;
  operation:RefObject<Operation|null>; onClose:()=>void; onAccepted:()=>void;
}) {
  const instructionId=useId();
  const formId=useId();
  const descriptionId=useId();
  const path=`/work-requests/${encodeURIComponent(requestId)}/script`;
  const [stage,setStage]=useState<Stage|null>(null);
  const [instruction,setInstruction]=useState("");
  const [acknowledged,setAcknowledged]=useState(false);
  const [error,setError]=useState("");
  const [stale,setStale]=useState(false);
  const [busy,setBusy]=useState(false);
  const pending=useRef(false);

  useEffect(()=>{
    let live=true;
    api<Stage>(path).then(
      data=>{if(live)setStage(data);},
      reason=>{if(live)setError(message(reason));},
    );
    return()=>{live=false;};
  },[path]);

  const needsAcknowledgment=stage?.attempts.some(attempt=>attempt.status==="unknown");
  const active=stage?.attempts.some(attempt=>["queued","running"].includes(attempt.status));
  const unavailable=stale||stage?.head_version!==version||!stage?.execution_enabled||active||disabled;
  async function submit() {
    if(!stage||pending.current||unavailable||!instruction.trim()||(needsAcknowledgment&&!acknowledged))return;
    const body={
      expected_revision:stage.revision,
      base_version:version,
      clip_id:clipId,
      instruction:instruction.trim(),
      acknowledge_duplicate_cost:acknowledged,
    };
    const fingerprint=JSON.stringify(body);
    if(operation.current?.fingerprint!==fingerprint)operation.current={fingerprint,id:crypto.randomUUID()};
    pending.current=true;
    setBusy(true);
    setError("");
    try {
      await api(path+"/revise-clip","POST",{...body,id:operation.current.id});
      operation.current=null;
      onAccepted();
    } catch(reason) {
      if(reason instanceof ApiError&&["script_revision_conflict","script_busy","script_unknown_ack_required"].includes(reason.code)) {
        setStale(true);
        setError("작업 상태가 바뀌었습니다. 수정 지시를 복사한 뒤 최신 클립 계획에서 다시 열어 주세요.");
      } else if(reason instanceof ApiError&&reason.code==="video_clip_revision_unavailable") {
        setStale(true);
        setError("이 답변은 클립별 AI 수정을 지원하지 않습니다.");
      } else {
        setError(message(reason));
      }
    } finally {
      pending.current=false;
      setBusy(false);
    }
  }

  return <Modal title={`${title} · AI 계획 수정`} className="video-clip-revision-dialog"
    onClose={()=>{if(!pending.current)onClose();}} footer={<>
        <Button variant="secondary" disabled={busy} onClick={onClose}><ActionIcon kind="close"/>취소</Button>
        <Button form={formId} type="submit" disabled={busy||unavailable||!instruction.trim()||Boolean(needsAcknowledgment&&!acknowledged)} aria-describedby={descriptionId}>
          <ActionIcon kind="ai"/>{busy?"이 클립 수정 요청 접수 중…":"AI에게 계획 수정 요청"}
        </Button>
      </>}>
    <form id={formId} className="video-clip-revision-form" onSubmit={event=>{event.preventDefault();void submit();}}>
      <p id={descriptionId}>수정 지시로 새 클립 계획을 만듭니다. 현재 영상 파일을 직접 편집하거나 수정용 영상으로 AI에 전달하지 않습니다.</p>
      <ol className="video-revision-steps"><li>AI가 수정한 새 계획 확인</li><li>클립 계획 확정</li><li>영상 생성을 별도로 요청</li></ol>
      <p className="helper-text">같은 작업에 새 답변 버전이 추가되며 기존 영상·자료·검수 기록은 이전 버전에 유지됩니다. 이어지는 연속 클립은 연결을 다시 확인하세요.</p>
      <p className="helper-text">연출 지시를 수정할 수 있습니다. 길이·기준 이미지·대사·공통 목소리를 변경하려면 전체 답변을 수정하세요.</p>
      <Field label="수정 지시" id={instructionId} required hint="예: 시선이 먼저 문 쪽으로 향하고 카메라는 고정되도록 바꿔 주세요.">
        {props=><textarea {...props} value={instruction} rows={4} maxLength={2000} required disabled={busy} onChange={event=>setInstruction(event.target.value)}/>}
      </Field>
      {needsAcknowledgment&&<label className="video-clip-cost-acknowledgment">
        <input type="checkbox" checked={acknowledged} disabled={busy} onChange={event=>setAcknowledged(event.target.checked)}/>
        <span>이전 AI 호출의 사용량을 확인했고 중복 비용이 발생할 수 있음을 확인했습니다.</span>
      </label>}
      <p className="helper-text">요청을 접수하면 AI 수정 비용이 발생할 수 있습니다.</p>
      {!stage&&!error&&<p className="helper-text" role="status">최신 작업 상태를 확인하고 있습니다.</p>}
      {stage&&(stage.head_version!==version||active||disabled)&&!error&&<p className="helper-text" role="status">진행 중인 작업이 끝나면 최신 클립 계획에서 요청할 수 있습니다.</p>}
      {stage&&!stage.execution_enabled&&<p className="helper-text">AI 답변 실행 설정이 꺼져 있습니다.</p>}
      {error&&<p role="alert" className="field-error">{error}</p>}

    </form>
  </Modal>;
}
