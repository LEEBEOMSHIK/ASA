# 에이전트·자동화 빌더 설계 반영

범위: 상세 설계, 구현 계획, WORKBOARD, 아키텍처·디자인 시스템·README 연결.
새 API·에이전트 레지스트리·빌더 화면·실행 엔진 코드는 이번 작업에서 구현하지 않았다.

사용자 확정: 작업 블록 연결형 빌더, ASA 도구와 사용자 에이전트의 도구 등록.
구현자 선택: 순차 DAG, 버전 고정, root 공유 예산, 제한 스키마, 실행 원장 기준 복구.

독립 검토 후 반영한 사항:
1. intent/응답/도구 제안 목록 저장 순서와 재시작 시 호출 ID 복원.
2. v1 중간 입력 대기 제외, 기획 정보 보완은 검토 후 fork.
3. artifact revision·manifest 일치 조건·후속 승인 무효화.
4. runs/invocations 업무 정본과 jobs queue 역할 분리.
5. 조건 분기 병합 시 진입 edge별 입력 매핑.

검증: 기존 scripts/check.ps1을 재실행하여 pytest 11개, ruff, mypy(7 source files),
TypeScript typecheck, Next.js production build 통과. 문서 상대 링크 확인 통과.
처음 검사는 도구 캐시 접근 제한으로 정상 진행하지 못해 같은 명령을 권한 조정 후 실행했다.
이 결과는 기존 기반의 회귀 확인이며 새 빌더 기능의 동작 검증이 아니다.

실제 AI 호출·DB 변경·Docker 실행·커밋·push 없음.
다음 작업은 ASA-009 등록 계약·권한·버전·UI 구현. DB 통합에는 ASA 전용 DB 설정이 필요하다.
