# AI Shorts Studio Foundation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for native execution in this session. No per-task delegation.

**Goal:** 외부 AI API를 사용하는 로컬 개발 기반과 설계·협업 규칙을 구축한다.
**Architecture:** 모듈형 모놀리스, web/API/수동 worker 실행 분리. PostgreSQL 체크포인트.
**Tech Stack:** Next.js, TypeScript, FastAPI, Python, LangGraph, LangChain, PostgreSQL, FFmpeg.
**Spec:** ../../architecture.md

## Global Constraints

- 개발에 Docker를 요구하지 않는다. AI는 외부 API.
- 실제 유료 요청은 이번 검증에서 실행하지 않는다.
- 초기 구성과 전체 MVP 구현을 구분한다. 기존 빈 저장소의 사용자 지정 경로에서 작업한다.
- push·공개 배포·DB 관리자 계정 변경은 수행하지 않는다.

## Review Focus

- 승인 재개 시 대본 재생성 → graph 테스트의 생성 호출 수 검증.
- 거절을 승인으로 잘못 처리 → rejected 결과 검증.
- 잘못된 승인값을 bool로 강제 변환 → ValidationError 검증.
- DB 없이 ready 표시 → health 503 테스트.
- 외부 호출이 구성 누락으로 조용히 대체됨 → 누락 설정의 명시 실패 테스트.

## Task 1 — 설계와 협업 기준

- [x] docs/architecture.md, docs/design-system.md, WORKBOARD.md, AGENTS.md 작성.
- [x] README와 로컬 실행 가이드에 현재 구현·미구현 범위를 구분.

## Task 2 — API와 승인 그래프

Files: services/backend/pyproject.toml, src/asa/{api,config,models,providers,workflow,worker}.py,
tests/test_api.py, tests/test_workflow.py, tests/test_providers.py.
Interfaces: Script(title,narration), build_graph(generator,checkpointer), Settings, create_app(settings).

- [x] pytest에서 승인 전 interrupt, 승인·거절, 재개 중복 생성 방지, 잘못된 승인·입력, DB 503을 먼저 검증해 실패 확인.
- [x] FastAPI health와 LangGraph/LangChain 어댑터, PostgreSQL 수동 worker 구현.
- [x] uv run pytest / ruff check . / mypy src 통과 확인.

## Task 3 — Next.js와 공통 UI

Files: apps/web/app/{page,layout}.tsx, {tokens,globals}.css, components/ui.tsx, package.json.
Interfaces: Button, Card, StatusBadge, Field; 의미 기반 CSS custom properties.

- [x] 초기 상태를 정직하게 보여주는 화면과 공통 컴포넌트 구현.
- [x] npm run typecheck / npm run build 확인. 브라우저 검증 가능 여부 기록.

## Task 4 — 실행·운영 구성 및 마감

Files: scripts/{setup,run,check}.ps1, deploy/{backend,web}.Dockerfile, compose.production.yml.

- [x] 로컬 setup은 의존성 설치만 수행, DB 생성·비밀값 설정은 명시 절차로 제공.
- [x] 운영 이미지·볼륨·health·수동 worker 프로파일과 비밀값 예시 작성.
- [x] 가능한 실행 검사 후 WORKBOARD와 docs/verification.md에 범위·제약 기록.
- [x] 전체 변경을 검토하고 사용자에게 로컬 파일 상태 전달. 커밋·push는 이번 범위에서 제외.

## 실행 결과

2026-10-26: 초기 구성 완료. 상세 검증과 미완료 범위는 ../../verification.md.
Ruling: 사용자 지정 빈 저장소를 직접 사용, 커밋·push 없음.
Ruling: 기본 ARM64 대신 기존 x64 Python 3.13 사용, 설치 호환 문제 해결.
Ruling: 초기 워커는 승인 그래프 CLI까지만 구현. 상시 큐·영상 제작은 MVP 후속 작업.
