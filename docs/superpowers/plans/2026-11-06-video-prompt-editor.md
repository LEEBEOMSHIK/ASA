# Video Prompt Editor Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 에이전트 편집에서 스타일 지침과 관리자 전용 공통 지침을 저장하고 실행에 적용한다.
**Architecture:** AgentDraft JSON/version에 본문을 저장하고 기존 catalog/bundle snapshot 경로를 재사용한다. Repository create/update에서 권한을 검사한다.
**Tech Stack:** FastAPI/Pydantic/PostgreSQL, Next.js/React.
**Spec:** docs/superpowers/specs/2026-11-06-video-prompt-editor-design.md

## Global Constraints
- 사용자 지침 보존, 작업 공간 경계, 기존 요청 snapshot 유지, 유료 호출 없음.
- 현재 checkout의 기존 변경 보존. 이번 요청에서 커밋/푸시하지 않는다.

## Review Focus
- 일반 사용자의 직접 API 공통 지침 변경/삭제/신규 생성 차단.
- stale revision 덮어쓰기 방지 및 같은 workspace 한정.
- 스타일 전환 시 미저장 본문 보존.
- 공통/선택 스타일이 비어 있거나 자동 매핑이 삭제된 경우 안내.
- 기존 파일 모듈 및 이미 접수한 작업과의 호환.

## Tasks
- [x] backend: 저장 본문 합성/스타일 선택/고정 snapshot red→green, VideoPromptModules와 freeze_module_catalog 확장.
- [x] backend: repository 권한 및 service 검증, 격리 DB member 차단/허용·revision 충돌 확인.
- [x] frontend: VideoPromptEditor, Definition, AgentEditor 및 RegistryShell 역할 context 연결.
- [x] 검증 실행: pytest380, mypy/typecheck/build 통과. 전체 Ruff 기존97건. 브라우저 임시 초안 확인, 모바일 이미지 미확보는 WORKBOARD에 기록.
- [x] 전체 변경 검토와 문서/WORKBOARD에 실제 검증·미검증 기록.

## Execution ledger
- 최종 사용자 정정 반영: opt-in UI/수동 모드 제거, 영상 모델 입력 계약 기반 기본 selection_required/필수 video_style 추가. 설정은 스타일 본문만 관리, 실행 입력으로 선택. 기존 저장 설정은 임의 저장하지 않고 새 계약 저장 필요를 안내한다. 전체383·보완회귀32·typecheck/build/mypy 통과, Ruff 기존97. WORKBOARD의 최신 항목이 최초 계획의 수동/선택적 모드보다 우선한다.
- 설계 승인 대화에 따라 즉시 진행. 별도 저장 승인 반복 없음.
- 검토 보완: agent 요청4MiB(한글/JSON escape), 잘못된 properties/boolean 매핑 검증. 긴 한글 저장413 red→green. 최종 일반 사용자 API 회귀 통과. UI 실제 grid gap16+기존 field margin24 중복은 지역 grid에서 margin0으로 해소.
