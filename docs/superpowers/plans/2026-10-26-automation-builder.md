# Automation Builder Implementation Plan

**Goal:** 사용자 요청에 따라 자동화 구성 화면을 실행 엔진보다 먼저 제공한다.
**Architecture:** 기존 등록 버전 카탈로그·owner 인증·workspace DB를 재사용. 순서 있는 블록과 명시 입력 매핑을 저장한다.
**Tech Stack:** Next.js, FastAPI, PostgreSQL. 개발은 로컬 프로세스.

기존 agent-automation-design의 빌더를 먼저 구현한다. 자유 캔버스 대신 키보드로 조작 가능한
순차 블록 편집기를 첫 범위로 선택한다. 복잡한 분기·조건·병렬·게시/실행 manifest는 후속이다.
시작 입력은 요청 문자열 하나, 각 블록은 고정 도구 버전과 입력 필드별 출처(시작 입력/이전 결과/직접 값)를 갖는다.
최종 결과는 마지막 블록 출력이다. 매핑은 문자열 코드 실행 없이 서버가 해석한다.
연결 테스트는 실제 AI 호출 없이 사용자가 입력한 샘플 결과를 전달한다. 길이 검사 도구는 실제 로컬 계산한다.
샘플과 실측 도구 결과를 구분하며 실행 엔진 완성이나 실제 AI 품질 검증으로 표시하지 않는다.

- [x] 실패 테스트: 누락/미래 참조/형식 불일치, 샘플 전달, 저장 충돌·격리·CSRF.
- [x] automation 모듈과 DB 초안 저장, 검증·연결 테스트 API 구현.
- [x] 목록/편집 화면, 카탈로그 그룹, 순서 변경, 입력 출처 설정, 테스트 패널 구현.
- [x] 전체 필수 검사·실제 브라우저 검증·문서와 보드 갱신.

변경 파일: registry/automations.py, registry/migration.sql, api.py, test_automation.py,
test_registry_db.py, components/automation-builder.tsx, app/automations/page.tsx, 공통 탐색·CSS.
커밋/push 없음. 기존 대본 화면·자료 보존.
