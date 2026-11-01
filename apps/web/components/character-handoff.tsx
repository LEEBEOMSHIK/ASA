"use client";
import { useState } from "react";
import { api, message } from "../lib/registry";
import { Button, StatusBadge } from "./ui";
import type { WorkProgress } from "../lib/work-progress";

type Props = { project: {id:string; excluded:string[]; approved:Record<string,string>;
  characters:{id:string;name:string}[]; work_progress:WorkProgress;
  jobs:{id:string;version:number;character:{name:string};status:string}[] } };

export function CharacterHandoff({project}:Props) {
  const [notice,setNotice]=useState("");
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const active=project.characters.filter(c=>!project.excluded.includes(c.id));
  const ready=project.work_progress.status==="complete" || project.work_progress.status==="not_required";
  async function copy(kind:"id"|"data") {
    setBusy(true);setError("");setNotice("");
    try {
      const value=kind==="id"?project.id:JSON.stringify(await api(`/characters/projects/${project.id}/handoff`),null,2);
      await navigator.clipboard.writeText(value);
      setNotice(kind==="id"?"프로젝트 ID를 복사했습니다.":"확정 캐릭터 전달 데이터를 복사했습니다. 이미지 파일은 자동화 실행 시 첨부됩니다.");
    } catch(e) {setError(message(e));} finally {setBusy(false);}
  }
  return <details className="character-edit character-handoff"><summary>다음 단계에 전달할 캐릭터 · {active.length}명</summary>
    <div className="character-form">
      <div className="character-heading"><strong>확정 설정과 기준 이미지</strong><StatusBadge tone={ready?"success":"warning"}>{ready?"전달 준비 완료":"확정 필요"}</StatusBadge></div>
      <p className="muted">사용하는 캐릭터가 모두 확정되면 전달할 수 있습니다. 확정 이미지에 저장된 설정·수정 요청과 해당 이미지 버전을 사용합니다. 저장하지 않은 편집 내용과 제외한 캐릭터는 전달하지 않습니다.</p>
      <ul>{active.map(c=>{
        const job=project.jobs.find(j=>j.id===project.approved[c.id] && j.status==="succeeded");
        const state=project.work_progress.items.find(i=>i.id===c.id)?.state;
        return <li key={c.id}>{job?.character.name || c.name} · {state==="approved" && job?`확정 이미지 v${job.version}`:"이미지 확정 필요"}</li>;
      })}</ul>
      {!active.length && <p>전달할 캐릭터가 없습니다. 빈 캐릭터 목록을 전달합니다.</p>}
      {project.excluded.length>0 && <p className="muted">전달 제외: {project.characters.filter(c=>project.excluded.includes(c.id)).map(c=>c.name).join(", ")}</p>}
      <p>자동화에서 ‘확정 캐릭터 가져오기’ 도구에 아래 프로젝트 ID를 입력하고, <strong>전체 결과</strong>를 다음 에이전트의 객체 입력에 연결하세요. 이미지 입력 지원 모델을 선택해야 합니다.</p>
      <p className="muted">대본과 장면은 변경하거나 이 목록에 합치지 않습니다. 필요한 경우 별도 입력에 원문을 연결하세요. 전달 준비 완료는 자동 실행을 뜻하지 않습니다.</p>
      <label className="character-field">프로젝트 ID<input readOnly value={project.id}/></label>
      <div className="button-row"><Button variant="secondary" disabled={busy} onClick={()=>void copy("id")}>프로젝트 ID 복사</Button><Button variant="secondary" disabled={busy || !ready} onClick={()=>void copy("data")}>전달 데이터 복사</Button></div>
      {notice && <p role="status">{notice}</p>}{error && <p role="alert">{error}</p>}
    </div>
  </details>;
}
