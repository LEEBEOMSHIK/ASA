"use client";

import { useId } from "react";
import { ExternalLink } from "./ui";
import { HelpText } from "./help-text";

const models: Record<string, { name: string; focus: string; description: string }> = {
  "gpt-image-2.5-sunburst": {
    name: "GPT Image 2.5 Sunburst", focus: "품질 우선",
    description: "복잡한 외형·의상 지침과 세밀한 수정의 품질을 먼저 확인하고 싶을 때 선택하세요.",
  },
  "gpt-image-2.5-flare": {
    name: "GPT Image 2.5 Flare", focus: "속도 우선",
    description: "여러 이미지 후보를 빠르게 비교하고 싶을 때 선택하세요. 원하는 품질이 유지되는지 결과를 확인해 주세요.",
  },
};

export function ImageModelSelect({ label, value, options, onChange, disabled = false }: {
  label: string; value: string; options: string[]; onChange: (value: string) => void; disabled?: boolean;
}) {
  const id = useId();
  const selected = models[value];
  return <div className="image-model-select">
    <div className="image-model-heading">
      <label htmlFor={id}>{label}</label>
      <HelpText label="모델 차이와 비용">
      <div className="image-model-details">
        <dl>{Object.entries(models).map(([key, model]) => <div key={key}><dt>{model.name} · {model.focus}</dt><dd>{model.description}</dd></div>)}</dl>
        <p>두 모델의 표준 API 토큰 단가는 같습니다. 100만 토큰당 텍스트 입력 $5 · 이미지 입력 $8 · 이미지 출력 $30입니다. 실제 비용은 지침, 참고 이미지와 생성 결과의 토큰 사용량에 따라 달라집니다.</p>
        <p>현재 생성 설정은 1024 × 1024 · 보통 품질 · 1장입니다. 속도와 결과 품질은 요청에 따라 달라지며, 수정 후에는 얼굴·의상 등 유지할 특징을 확인하세요.</p>
        <div className="image-model-sources muted"><span>공식 정보 확인: 2026. 10. 31.</span><ExternalLink href="https://developers.openai.com/api/docs/guides/image-prompting#migrate-an-existing-workflow">모델 선택 안내</ExternalLink><ExternalLink href="https://developers.openai.com/api/docs/pricing">공식 요금표</ExternalLink></div>
      </div>
      </HelpText>
    </div>
    <div className="character-field"><select id={id} value={value} onChange={e => onChange(e.target.value)} disabled={disabled} aria-describedby={`${id}-help`}>
      {options.map(model => <option key={model} value={model}>{models[model] ? `${models[model].name} · ${models[model].focus}` : model}</option>)}
    </select></div>
    <p id={`${id}-help`} className="muted" aria-live="polite">{selected?.description || "이 모델의 비교 정보는 아직 등록되지 않았습니다. 공급자의 안내를 확인해 주세요."}</p>
  </div>;
}
