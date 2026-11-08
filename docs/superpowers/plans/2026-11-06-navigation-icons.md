# Navigation Icons Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 현재 메뉴 폭을 유지하면서 목적지를 즉시 식별한다.
**Architecture:** 공통 탐색의 고유 SVG와 client NavigationLink의 portal 안내를 사용한다.
**Tech Stack:** Next.js, React, 기존 CSS 토큰.
**Spec:** ../specs/2026-11-06-navigation-icons-design.md

- [x] ui.tsx에 목적지별 고유 SVG를 적용하고 navigation-link.tsx를 추가한다. sidebar-toggle.tsx의 홈에도 재사용한다.
- [x] globals.css에 토큰 기반 안내 스타일을 추가한다. 기존 레일 폭과 overflow는 유지한다.
- [x] 실제 브라우저에서 사용자/관리 메뉴, hover/focus/Escape, 밝음/어두움, 접힘/펼침, 좁은 화면과 경계를 검증한다. 임시 UI 상태를 복원한다.
- [x] backend pytest/ruff/mypy와 frontend typecheck/build, diff-check를 실행하고 WORKBOARD에 실제 결과와 한계를 기록한다.

검증 결과와 모바일 캡처 미확보 한계는 WORKBOARD의 접힌 메뉴 구분 개선 항목을 참조한다. 별도 자동화 UI 테스트 도입 없이 실제 브라우저의 상호작용과 DOM 경계를 확인했다.
