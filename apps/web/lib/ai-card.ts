export function aiCardInfo(node: {instructions?:string;provider?:string;model?:string}, defaultModel:string|null) {
 const summary=node.instructions?.trim().replace(/\s+/g,' ')||'';
 const claude=node.provider==='anthropic';
 const model=node.model||(claude?'':defaultModel);
 return {summary:summary||'작업 내용을 설정해 주세요',
  model:`${claude?'Claude':'OpenAI'} · ${model||(claude?'모델 미선택':'서버 기본 모델')}`,
  warning:!summary?'지시문을 입력하세요':claude&&!model?'모델을 선택하세요':''};
}
