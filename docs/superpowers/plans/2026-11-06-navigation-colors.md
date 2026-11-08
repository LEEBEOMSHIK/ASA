# Navigation Colors Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 사용자별 메뉴 강조색을 여러 기기에서 유지한다.
**Architecture:** 인증된 profile 하위 API, 전용 DB 테이블, 공통 client provider/dialog와 NavigationLink.
**Tech Stack:** FastAPI, PostgreSQL, React, CSS 토큰.
**Spec:** ../specs/2026-11-06-navigation-colors-design.md

- [x] 격리 DB에서 인증/입력 제한/두 세션 동기화/사용자·workspace 격리/충돌/초기화 회귀 테스트 작성 후 API 구현.
- [x] 공통 메뉴 계약과 palette 토큰, provider와 편집 dialog, 링크·설정 진입 연결. 기존 60px 폭 유지.
- [x] 전체 backend pytest/ruff/mypy, frontend typecheck/build 및 실제 브라우저 PC·좁은 화면·테마·키보드·오류/취소 확인. 실제 사용자 저장값은 변경하지 않는다.
- [x] 리뷰 및 WORKBOARD/설계 문서에 결과·미검증 기록.

실행 결과: 구현·서버 검증 완료. 실제 저장은 사용자 설정 보존을 위해 격리 DB의 두 세션에서만 수행했다. 모바일 DOM 검증 이후 브라우저 URL 확인 실패로 UI 제어가 중단돼 시각 검증과 원복 확인에 제한이 있다. 세부 미검증은 WORKBOARD 참조.
