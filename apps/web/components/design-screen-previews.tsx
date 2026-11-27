"use client";

import type { ReactNode } from "react";
import {
  AgentCardPreview, AutomationPreview, PermissionMatrixPreview, StudioNavigationPreview,
  VideoCostPreview, WorkerStatusPreview,
} from "./design-interactive-previews";
import { WorkspaceStartSteps } from "./workspace-agent-card";
import { VideoJobProgress } from "./video-clip-manager";

export type CatalogEntry = {
  title: string;
  preview?: ReactNode;
  wide?: boolean;
  href?: string;
  parts: string;
  usage: string;
  screen: string;
};

function VideoProgressSpecimen() {
  return <VideoJobProgress job={{
    id: "design-preview", clip_id: "S01", status: "review", progress_stage: "review",
    created_at: "2026-11-01T12:00:00Z", updated_at: "2026-11-01T12:00:42Z",
    finished_at: "2026-11-01T12:00:42Z", estimate: null,
  }} />;
}

export const startStepsEntry: CatalogEntry =
{ title: "작업 시작 단계", preview: <WorkspaceStartSteps />, href: "/", parts: "단계 번호·현재 위치", usage: "작업의 다음 위치를 안내할 때", screen: "작업 공간" };

export const navigationEntries: CatalogEntry[] = [
  { title: "에이전트 선택 카드", preview: <AgentCardPreview />, href: "/", parts: "이름·하는 일·실행 상태", usage: "실행할 에이전트를 고를 때", screen: "작업 공간·에이전트 목록" },
  { title: "보관함 썸네일 선택", href: "/characters", parts: "미리보기·자료명·선택 표시", usage: "이미지를 보면서 작업 자료를 선택할 때", screen: "보관함·확정 씬 이미지 가져오기" },
  { title: "사이드바 탐색", preview: <StudioNavigationPreview />, href: "/agents", parts: "메뉴 아이콘·현재 위치", usage: "스튜디오 영역을 오갈 때", screen: "공통 탐색·모바일 메뉴" },
  { title: "자동화 연결 캔버스", preview: <AutomationPreview />, href: "/automations", parts: "블록·입력점·출력점·방향 연결선", usage: "앞 단계의 결과를 다음 작업에 전달하거나, 조건에 따라 실행 흐름이 달라질 때", screen: "자동화 빌더" },
  { title: "최근 작업과 결과 상태", href: "/", parts: "작업명·종류·시간·상태", usage: "기존 작업을 찾고 결과 검토를 이어갈 때", screen: "작업 공간 → 최근 작업·작업 관리" },
  { title: "입력 항목 편집", href: "/agents/new", parts: "필드 이름·자료형·필수 여부", usage: "에이전트가 받을 항목을 구성할 때", screen: "에이전트 편집·도구 설정" },
  { title: "필터와 선택 수", href: "/", parts: "검색 결과·선택 수·필터 밖 선택", usage: "필터 변경 후에도 기존 선택 범위를 확인할 때", screen: "확정 씬 이미지 가져오기·보관함" },
];

export const productionEntries: CatalogEntry[] = [
  { title: "답변 버전·이력", href: "/", parts: "버전·변경 내용·최신 표시", usage: "이전 답변과 최신 결과를 구별할 때", screen: "대본·씬·비디오의 AI 답변 이력" },
  { title: "영상 생성 단계", preview: <VideoProgressSpecimen />, href: "/", parts: "현재 단계·경과·후속 단계", usage: "영상의 대기, 생성, 저장을 구분할 때", screen: "클립·영상 생성 진행" },
  { title: "영상 결과·검토 배치", href: "/", parts: "영상 프레임·비율·검수·확정", usage: "영상을 보면서 결과를 확인할 때", screen: "비디오 프롬프트·편집 합성 결과" },
  { title: "생성 당시 참조 자료", href: "/", parts: "시작 이미지·추가 참조·대본 버전", usage: "결과에 사용된 입력을 확인할 때", screen: "비디오 프롬프트 영상 결과" },
  { title: "편집 구간 목록", href: "/", parts: "순서·사용 구간·전환", usage: "영상과 이미지가 이어지는 순서를 확인할 때", screen: "영상 편집·합성 결과" },
  { title: "화자와 발화 카드", href: "/", parts: "화자·대사·배정 시간·음성", usage: "발화별 목소리와 시간을 확인할 때", screen: "음성 제작" },
  { title: "영상 타이밍 참고", href: "/", parts: "영상 검수 근거·발화 시작점·함께 재생", usage: "영상 동작에 음성을 맞출 때", screen: "음성 제작 → 영상 타이밍 참고" },
  { title: "항목별 검수 결과", href: "/", parts: "검토 항목·판정·근거", usage: "확인된 항목과 미검증 항목을 비교할 때", screen: "AI 이미지·영상 검수" },
];

export const adminEntries: CatalogEntry[] = [
  { title: "백그라운드 상태", preview: <WorkerStatusPreview />, wide: true, href: "/admin/workers", parts: "전체 상태·작업별 실행 여부", usage: "일부 작업만 멈췄는지 확인할 때", screen: "백그라운드 작업 관리" },
  { title: "모델 참조 지원표", href: "/admin/video", parts: "모델 상태·참조 유형별 지원", usage: "선택 모델이 받을 수 있는 자료를 확인할 때", screen: "영상 생성 관리·모델 비교" },
  { title: "비용 차이 요약", preview: <VideoCostPreview />, wide: true, href: "/video-comparison", parts: "기준 모델·최저 예상 비용·클립 조건", usage: "모델별 비용 차이를 한눈에 볼 때", screen: "영상 AI 비교·비용 표" },
  { title: "음성 비교 미리듣기", href: "/video-comparison/audio", parts: "화자 이름·말투·재생 제어", usage: "같은 대사를 여러 목소리로 비교할 때", screen: "음성 AI 비교" },
  { title: "권한 체크 매트릭스", preview: <PermissionMatrixPreview />, wide: true, href: "/admin/access", parts: "메뉴·권한 열·사용 불가 상태", usage: "역할별로 여러 메뉴의 권한을 설정할 때", screen: "사용자·권한 관리 → 역할·메뉴" },
  { title: "브랜드 적용 미리보기", href: "/admin/branding", parts: "로고·브랜드 이름·적용 위치", usage: "브랜드 설정이 노출되는 위치를 확인할 때", screen: "브랜드 설정·로그인" },
];
