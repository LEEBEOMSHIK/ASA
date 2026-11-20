"use client";
import {useState} from 'react';
import {reviewKinds,reviewPhrases,type ReviewKind,type ReviewAnnotation} from '../lib/video-review-highlights';
import {ActionIcon,Button} from './ui';
import './video-review-text.css';

export function VideoReviewText({text,clipId,annotations=[],validation,sections=[]}:{text:string;clipId:string;annotations?:ReviewAnnotation[];validation?:{complete:boolean;covered_sections:number;total_sections:number}|null;sections?:{title:string;text:string;key:string}[]}) {
  const [highlight,setHighlight]=useState(true);
  const [focused,setFocused]=useState<ReviewKind|null>(null);
  const available=new Set([{text,key:'prompt'},...sections].flatMap(s=>reviewPhrases(s.text,annotations,`${clipId}:${s.key}`).flatMap(p=>p.kind?[p.kind]:[])));
  const active=focused&&available.has(focused)?focused:null;
  const [notice,setNotice]=useState('');
  async function copy() {
    try {await navigator.clipboard.writeText(text);setNotice('원문을 복사했습니다.');}
    catch {setNotice('복사하지 못했습니다. 본문을 선택해 복사해 주세요.');}
  }
  function prose(value:string,key:string) {
    return <p className="video-review-prose">{highlight?reviewPhrases(value,annotations,`${clipId}:${key}`).map((part,i)=>{
      const matches=!!active&&part.kind===active;
      const kind=matches?active:part.kind;
      const label=reviewKinds.find(k=>k.id===kind)?.label;
      return kind?<mark key={i} className={`review-mark review-mark--${kind}${active?(matches?' review-focused':' review-dimmed'):''}`} title={label} aria-label={`${label}: ${part.text}`}>{part.text}</mark>:<span key={i} className={active?'review-dimmed':undefined}>{part.text}</span>;
    }):value}</p>;
  }
  return <div className="video-review-text">
    <div className="video-review-toolbar"><h4>영상 제작 지시</h4><div className="video-review-actions">
      <Button variant="secondary" aria-pressed={highlight} onClick={()=>{setHighlight(v=>!v);setFocused(null);}}><ActionIcon kind="document"/>연출 구분 {highlight?'켜짐':'꺼짐'}</Button>
      <Button variant="secondary" onClick={()=>void copy()}><ActionIcon kind="copy"/>원문 복사</Button>
    </div></div>
    {highlight&&<><ul className="video-review-legend" aria-label="연출 하이라이트 범례">{reviewKinds.map(k=><li key={k.id}><Button variant="secondary" className={`review-legend-button review-mark review-mark--${k.id}`} disabled={!available.has(k.id)} title={!available.has(k.id)?`${k.label} 구절이 검출되지 않았습니다.`:k.label} aria-pressed={active===k.id} onClick={()=>setFocused(current=>current===k.id?null:k.id)}><ActionIcon kind={k.id}/>{k.label}</Button></li>)}</ul><p className="helper-text">범례를 누르면 해당 구절에 집중합니다. 다시 누르면 전체 표시로 돌아갑니다. 검출된 구절이 없는 항목은 비활성화됩니다.</p></>}
    {highlight&&active&&<p className="helper-text" role="status">{reviewKinds.find(k=>k.id===active)!.label} 집중 보기</p>}
    {!available.size&&<p className="helper-text">이 본문과 일치하는 AI 분류 정보가 없어 원문으로 표시합니다.</p>}
    {validation&&!validation.complete&&<p className="helper-text" role="status">AI 구절 분류를 일부 확인하지 못했습니다. 원문은 유지되며, 검증된 구절만 표시합니다. ({validation.covered_sections}/{validation.total_sections}개 본문 확인)</p>}
    {prose(text,'prompt')}
    {sections.map(section=><section className="video-review-section" key={section.title}><h4>{section.title}</h4>{prose(section.text,section.key)}</section>)}
    {notice&&<p className="helper-text" role="status">{notice}</p>}
  </div>;
}
