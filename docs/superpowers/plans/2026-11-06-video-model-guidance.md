# Video model guidance Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans. Steps use checkbox tracking.

**Goal:** 스타일 선택 후 실제 영상 모델 안내 표시.
**Architecture:** 공통 입력 순서와 스타일 전달, 정확한 모델 식별자로 공식 근거 안내 렌더링.
**Tech Stack:** Next.js, React, TypeScript.
**Spec:** docs/superpowers/specs/2026-11-06-video-model-guidance-design.md

## Global Constraints
사용자 초안 저장·AI 호출 금지. 기존 다른 작업 보존. 토큰과 공통 UI 사용.
## Review Focus
일반 입력 순서 유지, 스타일 변경 시 모델 값 보존, 알려지지 않은 모델에 잘못된 안내 금지, 미선택 상태 안내, 좁은 화면과 긴 문구.

## Task 1
- [x] 순서 및 정확한 안내 매칭 회귀 테스트 작성·실패 확인.
- [x] input-requirements.ts 순서, agent-run-preview/agent-input.tsx 스타일 전달.
- [x] video-model-guidance.ts와 VideoModelInput 안내·공통 간격 구현.
- [x] 회귀 테스트 및 브라우저 밝은/어두운·데스크톱/좁은 화면 확인.
- [x] pytest/ruff/mypy/typecheck/build, 최종 리뷰와 WORKBOARD 갱신. 커밋 요청 없음.
