"use client";
import { useState, type ComponentProps } from "react";
import { CharacterBatch } from "./character-batch";
import { ImageBatchApproval } from "./image-batch-approval";
import { ReviewDashboard } from "./review-dashboard";
import { itemStateLabel } from "../lib/work-progress";
import "./character-studio.css";

type BatchProps = ComponentProps<typeof CharacterBatch>;
type ApprovalProps = ComponentProps<typeof ImageBatchApproval>;
type Props = {
  title: string; unit: string;
  project: {id:string;characters:BatchProps["characters"];jobs:ApprovalProps["jobs"];excluded:string[];blocked?:Record<string,string[]>;approved:ApprovalProps["approved"];reviews:ApprovalProps["reviews"];work_progress:ApprovalProps["progress"]};
  options: {models:string[];enabled:boolean};
  currentId?:string; onSelect:(id:string)=>void;
  getDraft:BatchProps["getDraft"]; refresh:()=>Promise<void>;
};

/** Shared manager for image-producing workflows; task adapters supply labels and data. */
export function ImageTaskManager({title,unit,project,options,currentId,onSelect,getDraft,refresh}:Props) {
  const [batchMode,setBatchMode]=useState<"generate"|"approve"|null>(null);
  function imagePicker(selection?:{eligible:string[];selected:string[];toggle:(id:string)=>void;busy:boolean;images?:Record<string,{id:string;version:number}>}) {
    return <nav className={`character-picker scene-manager-picker${selection?.images ? " image-review-picker" : ""}`} aria-label={selection?`작업할 ${unit} 선택`:`작업할 ${unit}`}>{project.characters.map(c=>{
      const state=project.work_progress.items.find(i=>i.id===c.id)?.state || "pending";
      const image=selection?.images?.[c.id];
      const selectable=!selection || selection.eligible.includes(c.id);
      const selected=selection?selection.selected.includes(c.id):currentId===c.id;
      const review=image && project.reviews?.find(r=>r.image_id===image.id && r.status==="succeeded");
      return <div className="scene-manager-card" key={c.id}><button type="button" aria-pressed={selected} disabled={!!selection && (selection.busy || !selectable || (batchMode==="generate" && !selected && selection.selected.length>=12))} onClick={()=>selection?selection.toggle(c.id):onSelect(c.id)}>
        {image && <img src={`/api/v1/characters/images/${image.id}/asset`} alt={`${c.name} 검토 이미지 v${image.version}`} loading="lazy"/>}
        <strong>{c.name}</strong><span>{image?`v${image.version} · `:""}{project.blocked?.[c.id]?.length && state==="pending"?"자료 확인 필요":itemStateLabel(state,"scene_images")}</span>
        {selection && <small>{!selectable?"선택 대상 아님":selected?"✓ 선택됨":"선택 가능"}</small>}
      </button>{review && <details><summary>AI 검수 의견 보기</summary><ReviewDashboard value={review.result}/></details>}</div>;
    })}</nav>;
  }
  return (
      <div className="image-batch-tools" role="region" aria-label={title}>
      <h3 className="image-batch-tools-title">{title} · {project.characters.length}개</h3>
      <CharacterBatch renderPicker={(eligible,selected,toggle,busy)=>imagePicker({eligible,selected,toggle,busy})} controlledOpen={batchMode==="generate"} onToggle={()=>setBatchMode(v=>v==="generate"?null:"generate")} unit={unit} blocked={project.blocked} key={project.id} projectId={project.id} characters={project.characters} excluded={project.excluded} jobs={project.jobs} models={options.models} enabled={options.enabled} getDraft={getDraft} refresh={refresh}/>
      <ImageBatchApproval renderPicker={(candidates,selected,toggle,busy)=>imagePicker({eligible:candidates.map(c=>c.job.character_id),selected:candidates.filter(c=>selected.includes(c.job.id)).map(c=>c.job.character_id),toggle:id=>{const c=candidates.find(c=>c.job.character_id===id);if(c)toggle(c.job.id);},busy,images:Object.fromEntries(candidates.map(c=>[c.job.character_id,c.job]))})} controlledOpen={batchMode==="approve"} onToggle={()=>setBatchMode(v=>v==="approve"?null:"approve")} key={`approval-${project.id}`} characters={project.characters} jobs={project.jobs} approved={project.approved} excluded={project.excluded} progress={project.work_progress} reviews={project.reviews || []} refresh={refresh}/>
      <div className="scene-status-summary" role="status" aria-label={`${title} 상태 요약`}>{([
        ["pending","미생성"],["queued","생성 대기"],["running","생성 중"],["review","검토 필요"],["approved","확정"],["failed","실패"],["unknown","결과 확인 필요"],["excluded","제외"]
      ] as const).filter(([key])=>["pending","running","review","approved"].includes(key) || project.work_progress.counts[key]>0).map(([key,label])=><span key={key} className={project.work_progress.counts[key]>0?`scene-count scene-count--${key}`:"scene-count"}>{label} <strong>{project.work_progress.counts[key] || 0}</strong></span>)}</div>
      {!batchMode && imagePicker()}
      </div>
  );
}
