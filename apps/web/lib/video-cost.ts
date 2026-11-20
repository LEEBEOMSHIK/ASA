export type VideoEstimate = {amount_usd:number|null;currency:string;source:string;estimated:boolean};

export function videoCostLabel(value:number|null|undefined):string {
  return value == null || !Number.isFinite(value) || value < 0
    ? "예상 비용 미확인"
    : `카탈로그 기준 예상 비용 $${value.toFixed(2)} USD · 실제 청구액과 다를 수 있음`;
}

export function totalVideoCost(values:(number|null|undefined)[]):number|null {
  return !values.length || values.some(v=>v==null || !Number.isFinite(v) || v<0)
    ? null : values.reduce<number>((total,value)=>total+(value??0),0);
}
