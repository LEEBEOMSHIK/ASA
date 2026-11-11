# 공통 화풍 예시

UI 전용 예시 자산: `apps/web/public/art-style-examples/*.png`.
2026-11-11 내장 image_gen으로 생성했다. 사용자 작품/캐릭터를 사용하지 않았으며 작품 생성 요청의 참조 이미지로 전달하지 않는다. 실제 생성에는 기존 화풍 설명만 전달한다.

공통 프롬프트: landscape 3:2, a young adult Korean woman with a chin-length black bob, mustard yellow raincoat and blue jeans, sitting on a wooden park bench looking at a small red bird; leafy tree, flowers and garden path; eye-level medium-wide framing, friendly daylight; no text, logo, watermark, collage or UI.

화풍별 지시:
- watercolor: traditional watercolor storybook illustration, pastel washes, cold-pressed paper grain, delicate pencil contours.
- 2d: hand-drawn animation cel, rounded contours, flat pastel fills, restrained cel shadows, no 3D rendering.
- 3d: stylized 3D animated film still, rounded dimensional forms, soft rendered materials and cinematic lighting.
- realistic: live-action photograph, realistic human proportions, authentic skin/fabric, soft daylight and subtle depth of field.
- comic: full-color webtoon, expressive ink lines, crisp cel shading, vibrant contrast; no balloons or panel borders.
- clay: handmade clay stop-motion, sculpted texture, miniature set and warm studio lighting.

원본 이미지는 그대로 보존하고 Next Image가 화면 크기에 맞게 전송한다. 예시 카드와 콤보박스는 같은 선택값을 사용한다. 직접 입력 모드에서는 예시 목록 대신 입력란만 표시한다. 저장/오류/복구 상태를 제외한 장문 구현 안내는 화면에 표시하지 않는다.
