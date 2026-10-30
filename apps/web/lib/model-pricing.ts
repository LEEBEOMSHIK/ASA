export type RateTier = {input_tokens_gt:number;input:number|string;output:number|string;[key:string]:unknown};
export type Price = {long_context?:RateTier|null;label:string;input:number|string;output:number|string;[key:string]:unknown};
export const cacheKeys = ['cache_read','cache_creation','cache_creation_5m','cache_creation_1h'] as const;
export function validPrice(price:Price):boolean {
 const valid=(v:unknown)=>v!==null&&v!==undefined&&String(v).trim()!==''&&Number.isFinite(Number(v))&&Number(v)>=0;
 return valid(price.input)&&valid(price.output)&&cacheKeys.every(k=>price[k]==null||price[k]===''||valid(price[k]));
}
export function priceStatus(price:Price|null):string {
 if(!price||!validPrice(price))return '확인 필요';
 return price.label==='공식 문서 표준 요율'?'자동 확인됨':'직접 수정됨';
}
