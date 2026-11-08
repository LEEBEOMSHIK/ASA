# Navigation Custom Colors Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 팔레트·HEX 사용자 메뉴색과 일관된 간격.
**Architecture:** 기존 색 계약에 검증된 HEX를 확장하고 공통 색상 유틸리티에서 모드별 대비를 계산한다.
**Tech Stack:** React/Next.js, CSS tokens, FastAPI/PostgreSQL.
**Spec:** ../specs/2026-11-06-navigation-custom-colors-design.md

- [x] HEX 정규화/거부 및 기존 DB 제약에서 마이그레이션·두 세션 저장 조회 테스트 후 API 확장.
- [x] 공통 대비 계산, 기본/직접 선택·팔레트/HEX·미리보기 및 탐색 링크 연결. 오류·disabled·간격 유지.
- [x] 대비 경계 검증, 필수 backend/frontend 검사, 실제 브라우저 밝음/어두움·360px·키보드·취소·간격 검증.
- [x] 리뷰 및 실제 검증/미검증 결과를 WORKBOARD에 기록.

완료: 최종 리뷰 차단 이슈 없음. 결과/화면 증거와 실기기 OS 팝업 미검증은 WORKBOARD 기록을 참조한다.
