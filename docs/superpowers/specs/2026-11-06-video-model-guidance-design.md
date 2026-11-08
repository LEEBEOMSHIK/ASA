# 영상 스타일 기반 모델 안내

사용자 승인: 스타일을 먼저 선택하고 모델 선택란에 공식 자료 기반 안내 표시. 간격·정렬 검증.

기존 선택 화면의 안내를 확장한다. 별도 비교 화면만 사용하는 대안보다 선택 시점에 설명을 제공하는 방식을 채택했다. 공통 inputEntries에서 영상 스타일을 첫 영상 모델 바로 앞으로 이동하되 그 외 순서와 입력값을 보존한다. AgentRunPreview의 선택 스타일을 VideoModelInput에 전달한다.

활성 카탈로그는 Runway Gen-4.5 1개. 정확한 provider/model 조합으로 안내를 찾는다. 2D/3D/실사 활용 제안, 공식 확인 특성, 주의점, 출처와 확인 날짜를 제공한다. 우열·품질 보장이나 자동 모델 변경은 하지 않는다. 미등록 안내는 미확인으로 표시한다. 현재 서버 설정 기반 모델 카탈로그를 유지하며 안내 편집용 별도 관리자 화면은 이번 범위에 추가하지 않는다.

공식 자료: https://help.runwayml.com/hc/en-us/articles/46974685288467-Creating-with-Gen-4-5 및 https://help.runwayml.com/hc/en-us/articles/48324313115155-Image-to-Video-Prompting-Guide (2026-11-06 확인).
