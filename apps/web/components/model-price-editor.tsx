"use client";
import { Button, Field } from './ui';
import { cacheKeys, validPrice, type Price } from '../lib/model-pricing';
export function ModelPriceEditor({price,officialPrice,onChange}:{price:Price|null;officialPrice:Price|null;onChange:(price:Price|null)=>void}) {
 const names={input:'입력',output:'출력',cache_read:'캐시 읽기',cache_creation:'캐시 쓰기',cache_creation_5m:'캐시 쓰기 · 5분',cache_creation_1h:'캐시 쓰기 · 1시간'};
 const manual=!!price&&price.label!=='공식 문서 표준 요율';
 const tier=price?.long_context;
 function field(k:keyof typeof names){return <Field key={k} id={`rate-${k}`} label={`${names[k]} · USD / 100만 토큰`}>{p=><input {...p} type="number" min="0" step="any" value={String(price?.[k]??'')} onChange={e=>onChange({...price!,[k]:e.target.value||null,label:'관리자 수정 요율',long_context:null})}/>}</Field>;}
 return <div className="model-rate-panel">
 <div className="model-rate-heading"><div className="model-rate-heading-copy"><h3>{manual?'직접 설정 요율':'자동 적용 요율'}</h3><span className="muted">USD / 100만 토큰</span></div><Button variant="secondary" onClick={()=>onChange(manual?officialPrice:{...price,label:'관리자 수정 요율',input:price?.input??'',output:price?.output??'',long_context:null})}>{manual?'공식 요율로 복원':'요율 직접 설정'}</Button></div>
 {manual?<div className="settings-content"><p className="muted">직접 설정한 단일 요율을 적용합니다. 공식 요율의 입력 길이별 조건은 적용되지 않습니다. 편집 내용을 저장하면 새 요청부터 반영됩니다.</p><div className="settings-fields model-price-fields">{field('input')}{field('output')}</div><p className="muted">입력·출력 요율은 모두 필요합니다. 모르는 값을 0으로 입력하지 마세요.</p><details className="settings-disclosure"><summary>캐시 요율 · 선택 사항</summary><div className="settings-fields model-price-fields">{cacheKeys.map(field)}</div></details></div>:<>
 {price&&validPrice(price)?<><div className="model-rate-table" role="table" aria-label="적용 요율"><div role="row" className="model-rate-row"><strong role="columnheader">항목</strong><strong role="columnheader">{tier?`입력 ${tier.input_tokens_gt.toLocaleString()} 토큰 이하`:'표준 요율'}</strong>{tier&&<strong role="columnheader">기준 초과 시</strong>}</div>{(['input','output',...cacheKeys] as const).filter(k=>price[k]!=null||tier?.[k]!=null).map(k=><div role="row" className="model-rate-row" key={k}><span role="rowheader">{names[k]}</span><span role="cell">{price[k]!=null?`$${price[k]}`:'미확인'}</span>{tier&&<span role="cell">{tier[k]!=null?`$${tier[k]}`:'미확인'}</span>}</div>)}</div><p className="muted">{tier?'캐시를 포함한 전체 입력 토큰 수로 구간을 선택하고 해당 요청 전체에 적용합니다.':'확인된 요율을 사용량에 자동 적용합니다.'} 검색 도구 등 별도 요금은 포함하지 않은 예상 비용입니다.</p></>:<p className="model-price-explanation">자동으로 적용할 요율을 확인하지 못했습니다. 위 안내를 확인한 뒤 ‘공식 정보 갱신’을 눌러 다시 확인하세요. 그동안 비용은 0원이 아닌 미확인으로 표시됩니다.</p>}
 </>}
 </div>;
}
