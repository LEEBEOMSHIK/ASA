"use client";

import { useState } from "react";
import { targets } from "../lib/background-workers";
import { AgentFavoriteButton } from "./agent-groups";
import { AccessPermissionMatrix, toggleAccessPermission, type AccessMenu } from "./access-permission-matrix";
import { WorkerManagementPanel, type WorkerStatus } from "./agent-worker-status";
import { Modal } from "./character-library";
import type { EditSource } from "./editing-source-input";
import { EditingUpload } from "./editing-upload";
import { GraphIcon } from "./graph-icon";
import { ActionIcon, Button, StudioNavigation } from "./ui";
import { useVideoCostComparison, VideoCostControls, VideoCostSummary } from "./video-comparison";
import { WorkspaceAgentCard } from "./workspace-agent-card";
import styles from "./design-system-preview.module.css";
import "./editing.css";

const exampleAgent = "샘플 · 채널 대본 작가";
export function AgentCardPreview() {
  const [favorite, setFavorite] = useState(false);
  const [selected, setSelected] = useState(false);
  return <>
    <WorkspaceAgentCard name={exampleAgent} icon="bot" available onSelect={() => setSelected(true)}
      description="주제와 분위기를 바탕으로 쇼츠 대본을 작성합니다."
      favorite={<AgentFavoriteButton name={exampleAgent} selected={favorite} onToggle={() => setFavorite(value => !value)} />} />
    {selected && <p role="status">대본 작성 에이전트를 선택했습니다.</p>}
  </>;
}

export function AutomationPreview() {
  return <>
    <div className={`${styles.automationCanvas} graph-canvas-surface`} role="img"
      aria-label="시작에서 직접 AI를 거쳐 결과로 이어지는 흐름">
      <div className={`${styles.automationNode} graph-node-surface`}>
        <span className="graph-kind-icon"><GraphIcon kind="start" /></span>
        <strong>시작</strong>
        <span className={`graph-socket-mark is-output ${styles.automationOutput}`} />
      </div>
      <span className={styles.automationWire} />
      <div className={`${styles.automationNode} graph-node-surface graph-node-surface--ai`}>
        <span className={`graph-socket-mark ${styles.automationInput}`} />
        <span className="graph-kind-icon"><GraphIcon kind="ai" /></span>
        <strong>직접 AI</strong>
        <span className={`graph-socket-mark is-output ${styles.automationOutput}`} />
      </div>
      <span className={styles.automationWire} />
      <div className={`${styles.automationNode} graph-node-surface`}>
        <span className={`graph-socket-mark ${styles.automationInput}`} />
        <span className="graph-kind-icon"><GraphIcon kind="end" /></span>
        <strong>결과</strong>
      </div>
    </div>
    <dl className={styles.automationParts}>
      <div><dt>블록</dt><dd>작업 단계마다 배치</dd></div>
      <div><dt>입력점·출력점</dt><dd>데이터를 받는 곳과 보내는 곳</dd></div>
      <div><dt>방향 연결선</dt><dd>다음에 실행할 단계 표시</dd></div>
    </dl>
  </>;
}

export function StudioNavigationPreview() {
  const [active, setActive] = useState("");
  return <div className={styles.navigationExample}>
    <StudioNavigation active={active} includeAdmin label="사이드바 탐색 예시" onSelect={setActive} />
  </div>;
}

const exampleWorkers: WorkerStatus = {
  online: true, image_online: true, can_manage: true,
  workers: [
    { kind: "script", state: "running", enabled: true, busy: false },
    { kind: "image", state: "running", enabled: true, busy: false },
    { kind: "audio", state: "stopped", enabled: true, busy: false },
    { kind: "video", state: "running", enabled: true, busy: false },
  ],
};

export function WorkerStatusPreview() {
  const [status, setStatus] = useState(exampleWorkers);
  function change(action: "start" | "stop", kind?: WorkerStatus["workers"][number]["kind"]) {
    setStatus(value => {
      const eligible = targets(value.workers, action);
      return { ...value, workers: value.workers.map(worker => eligible.includes(worker) && (!kind || worker.kind === kind)
        ? { ...worker, state: action === "start" ? "running" : "stopped" }
        : worker) };
    });
  }
  return <WorkerManagementPanel status={status} preview onChange={(kind, action) => change(action, kind)} onChangeAll={change} />;
}

export function VideoCostPreview() {
  const cost = useVideoCostComparison();
  return <><VideoCostControls cost={cost} /><VideoCostSummary cost={cost} /></>;
}

const exampleMenus: AccessMenu[] = [
  { id: "agents", label: "에이전트", actions: ["view", "generate"] },
  { id: "characters", label: "보관함", actions: ["view", "edit", "review", "approve", "delete"] },
  { id: "admin-agents", label: "에이전트 관리", actions: ["view", "edit"] },
];

export function PermissionMatrixPreview() {
  const [permissions, setPermissions] = useState(["agents.view", "agents.generate"]);
  return <AccessPermissionMatrix catalog={exampleMenus} permissions={permissions} editable
    onToggle={(menu, action) => setPermissions(current => toggleAccessPermission(current, menu, action))} />;
}

const exampleVideo: EditSource = { id: "example-video", kind: "video", title: "예시 영상.mp4" };

async function previewUpload(file: File): Promise<EditSource> {
  return { id: crypto.randomUUID(), title: file.name, kind: "video" };
}

export function FileUploadPreview() {
  const [files, setFiles] = useState<EditSource[]>([]);
  const [browse, setBrowse] = useState(false);
  const [busy, setBusy] = useState(false);
  const limit = 32;
  const hasExample = files.some(file => file.id === exampleVideo.id);
  function addFile(file: EditSource) { setFiles(current => [...current, file]); }
  return <>
    <EditingUpload selectedCount={files.length} remaining={limit - files.length} uploadFile={previewUpload}
      onAdd={addFile} onBusy={setBusy} onBrowse={() => setBrowse(true)} />
    {!!files.length && <ul aria-label="선택한 예시 영상" className={styles.exampleFiles}>
      {files.map(file => <li key={file.id}><span>{file.title}</span><Button variant="secondary" disabled={busy}
        onClick={() => setFiles(current => current.filter(item => item.id !== file.id))}><ActionIcon kind="close" /> 제외</Button></li>)}
    </ul>}
    {browse && <Modal title="이전에 올린 영상" onClose={() => setBrowse(false)}>
      <Button variant="secondary" disabled={hasExample || files.length >= limit} onClick={() => { addFile(exampleVideo); setBrowse(false); }}>
        <ActionIcon kind="add" /> {exampleVideo.title}
      </Button>
    </Modal>}
  </>;
}
