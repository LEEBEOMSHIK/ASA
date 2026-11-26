"use client";

import { useState, type ComponentProps } from "react";
import type { WorkTab } from "../lib/work-tabs";
import type { WorkTabItem } from "../lib/work-layout";
import type { ReviewAnnotation } from "../lib/video-review-highlights";
import { AccessRoleList, type AccessRole } from "./access-role-list";
import { CharacterWorkTabsContext, WorkTabBar } from "./character-work-tabs";
import { Modal } from "./character-library";
import { RequestProgressSteps } from "./request-progress";
import { ActionIcon, Button, DisclosureSummary, DraftNotice, Field, InputRequirement, SelectCombobox, StatusBadge, Switch } from "./ui";
import { VideoReviewText } from "./video-review-text";
import styles from "./design-system-preview.module.css";
import "./access-management.css";

const roles: AccessRole[] = [
  { id: "creator", name: "제작자", enabled: true, permissions: ["home.view", "agents.view"], revision: 1 },
  { id: "reader", name: "열람자", enabled: true, permissions: ["home.view"], revision: 1 },
  { id: "reviewer", name: "검수 담당", enabled: false, permissions: ["home.view", "characters.view"], revision: 1 },
];

const tabs: WorkTabItem[] = [
  { id: "images", label: "클립·영상 생성", description: "클립 연결·영상 확정" },
  { id: "history", label: "AI 답변·수정 요청", description: "원문과 수정 이력" },
];

export function TabsSpecimen() {
  const [tab, select] = useState<WorkTab>("images");
  return <CharacterWorkTabsContext.Provider value={{ tab, select }}>
    <WorkTabBar prefix="catalog-work" items={tabs} />
    <div role="tabpanel" id="catalog-work-panel" aria-labelledby={`catalog-work-${tab}`} className={styles.tabPanel}>
      {tab === "images" ? "선택한 클립의 영상과 진행 상태" : "저장된 답변과 수정 요청 이력"}
    </div>
  </CharacterWorkTabsContext.Provider>;
}

export function DirectorySpecimen() {
  const [selectedId, setSelectedId] = useState("creator");
  return <AccessRoleList roles={roles} selectedId={selectedId} busy={false} pageSize={2}
    onSelect={role => setSelectedId(role.id)} />;
}

export function TextFieldSpecimen() {
  const [title, setTitle] = useState("");
  return <Field id="design-preview-title" label="작품 제목" required hint="입력하면 오류 표시가 해제됩니다."
    error={title.trim() ? undefined : "작품 제목을 입력해 주세요."} help="필수 입력과 오류 표시의 예시입니다.">
    {props => <input {...props} required value={title} onChange={event => setTitle(event.target.value)} />}
  </Field>;
}

const ratios = [
  { id: "vertical", label: "세로형 9:16" },
  { id: "wide", label: "가로형 16:9" },
];

export function ComboSpecimen() {
  const [ratio, setRatio] = useState("vertical");
  return <SelectCombobox label="화면 비율" options={ratios} value={ratio} onChange={setRatio} showId={false}
    hint="검색하거나 화살표 키로 선택하세요." />;
}

export function CheckboxSpecimen() {
  return <fieldset className={styles.choices}>
    <legend className="sr-only">체크박스 예시</legend>
    <label className="checkbox"><input type="checkbox" /> 이 클립을 선택</label>
    <label className="checkbox"><input type="checkbox" defaultChecked disabled /> 선택됨 · 변경 불가</label>
  </fieldset>;
}

export function SwitchSpecimen() {
  const [enabled, setEnabled] = useState(false);
  return <fieldset className={styles.choices}>
    <legend className="sr-only">스위치 예시</legend>
    <Switch label="알림 받기" checked={enabled} onChange={() => setEnabled(value => !value)} />
    <Switch label="설정 잠김" checked onChange={() => {}} disabled />
  </fieldset>;
}

export function DisclosureSpecimen() {
  return <>
    <details open>
      <DisclosureSummary>생성 당시 참고 자료</DisclosureSummary>
      <p className="muted">확정 씬 이미지 v2와 씬 구성 v1을 사용했습니다.</p>
    </details>
    <details>
      <DisclosureSummary>대본과 장면 연결 확인</DisclosureSummary>
      <p className="muted">S01 첫 장면에 대본 도입부를 연결했습니다.</p>
    </details>
  </>;
}

export function TextAreaSpecimen() {
  return <Field id="catalog-brief" label="편집 방향" hint="원하는 분위기와 장면 연결을 적으세요.">
    {props => <textarea {...props} rows={2} defaultValue="첫 장면은 천천히 시작하고 다음 장면으로 자연스럽게 연결." />}
  </Field>;
}

export function RequirementsSpecimen() {
  return <div className={styles.requirements}>
    <span>영상 모델 <InputRequirement required /></span>
    <span>추가 요청 <InputRequirement required={false} /></span>
  </div>;
}

export function StatusSpecimen() {
  return <div className={styles.row}>
    <StatusBadge>대기</StatusBadge><StatusBadge tone="success">완료</StatusBadge>
    <StatusBadge tone="warning">확인 필요</StatusBadge><StatusBadge tone="danger">실패</StatusBadge>
  </div>;
}

export function ProgressSpecimen() {
  return <><StatusBadge tone="warning">AI 작성 중</StatusBadge><RequestProgressSteps status="running" /></>;
}

export function DraftSpecimen() {
  const [cleared, setCleared] = useState(false);
  return <DraftNotice message={cleared ? "예시 입력을 초기화했습니다." : "저장한 초안을 불러왔습니다."}
    hint="현재 입력을 확인한 후 이어서 작성할 수 있습니다."
    actionLabel="초안 지우기" onReset={() => setCleared(true)} disabled={cleared} compact />;
}

export function ModalSpecimen() {
  const [open, setOpen] = useState(false);
  return <>
    <Button variant="secondary" onClick={() => setOpen(true)}><ActionIcon kind="document" /> 모달 열기</Button>
    {open && <Modal title="모달 예시" onClose={() => setOpen(false)}
      footer={<Button variant="secondary" onClick={() => setOpen(false)}><ActionIcon kind="close" /> 닫기</Button>}>
      <p className="muted">Esc 또는 닫기 버튼으로 돌아갈 수 있습니다.</p>
    </Modal>}
  </>;
}

const direction = "카메라는 전체를 담는다. 이루리는 살짝 미소를 짓고 문 쪽을 바라본다.";
const phrases = [
  { quote: "카메라는 전체를 담는다", kind: "camera" },
  { quote: "살짝 미소를 짓고", kind: "expression" },
  { quote: "문 쪽을 바라본다", kind: "gaze" },
] as const;
const annotations: ReviewAnnotation[] = phrases.map(phrase => ({ ...phrase, key: "catalog:prompt", source: direction }));

export function HighlightSpecimen() {
  return <VideoReviewText text={direction} clipId="catalog" annotations={annotations} />;
}

export function ButtonsSpecimen() {
  const [notice, setNotice] = useState("");
  return <>
    <div className={styles.row}>
      <Button onClick={() => setNotice("확인 버튼을 눌렀습니다.")}><ActionIcon kind="confirm" /> 확인</Button>
      <Button variant="secondary" onClick={() => setNotice("편집 버튼을 눌렀습니다.")}><ActionIcon kind="edit" /> 편집</Button>
      <Button variant="secondary" onClick={() => setNotice("AI 버튼의 미리보기입니다.")}><ActionIcon kind="ai" /> AI 검수</Button>
      <Button disabled><ActionIcon kind="save" /> 저장 불가</Button>
    </div>
    <p role="status" className={`muted ${styles.notice}`}>{notice}</p>
  </>;
}

const actions: { kind: ComponentProps<typeof ActionIcon>["kind"]; label: string }[] = [
  { kind: "add", label: "추가" }, { kind: "edit", label: "편집" },
  { kind: "save", label: "저장" }, { kind: "confirm", label: "확정" },
  { kind: "ai", label: "AI 요청" }, { kind: "refresh", label: "새로고침" },
  { kind: "copy", label: "복사" }, { kind: "download", label: "다운로드" },
  { kind: "undo", label: "되돌리기" }, { kind: "close", label: "닫기" },
  { kind: "play", label: "재생" }, { kind: "stop", label: "중지" },
];

export function IconsSpecimen() {
  return <ul className={styles.iconList} aria-label="동작 아이콘">
    {actions.map(({ kind, label }) => <li key={kind}><ActionIcon kind={kind} /><span>{label}</span></li>)}
  </ul>;
}
