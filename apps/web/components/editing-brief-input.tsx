"use client";
import {ExpandableTextarea} from "./expandable-textarea";
import {Field} from "./ui";
import "./editing.css";

export function EditingBriefInput({id,label,required,value,onChange,maxLength=4000}:{id:string;label:string;required:boolean;value:string;onChange:(v:string)=>void;maxLength?:number}){
  const guide = <div className="editing-guide"><strong>편집 요청 작성 가이드</strong><dl>
      <dt>편집 방향</dt><dd>“차분한 이야기”, “빠르고 경쾌한 소개”처럼 분위기와 목적을 적어 주세요. 특별한 요청이 없으면 원본 흐름을 유지합니다.</dd>
      <dt>순서·사용 구간</dt><dd>“S01 다음 S02”, “첫 영상의 처음 2초는 제외”처럼 적어 주세요. 선택한 자료의 이름을 사용하면 명확합니다.</dd>
      <dt>길이·연결 느낌</dt><dd>“30초 안팎”, “길이는 원본에 맞게”, “이미지는 장당 3초”처럼 적어 주세요. 길이를 정하지 않으면 30초로 강제하지 않습니다. 컷 전환·검정 페이드·이미지 확대축소를 사용할 수 있습니다.</dd>
      <dt>목소리·배경음악</dt><dd>원본 소리 유지 또는 제거 여부를 적어 주세요. 배경음악은 사용할 음원도 함께 선택해 주세요. 서로 다른 목소리를 자동으로 같은 음색으로 바꾸지는 않습니다.</dd>
      <dt>자막</dt><dd>넣을 문구와 표시할 장면을 적어 주세요. 요청하지 않으면 자막을 추가하지 않습니다.</dd>
    </dl><p className="helper-text">장면 연결을 판단할 참고 대본·씬 구성도 함께 넣으면 좋습니다. 현재 AI는 제공된 이름·길이·참고 글을 바탕으로 계획하며 영상을 직접 시청하지 않습니다. 이미지 속 배우의 새 동작을 생성하는 기능은 아닙니다.</p></div>;
  return <section className="editing-brief" aria-label="편집 요청 가이드">
    <ExpandableTextarea id={id} label={label} value={value} required={required} rows={6} className="textarea--compact" maxLength={maxLength} aria-describedby={`${id}-guide`} placeholder="편집 방향, 순서, 목표 길이, 장면 연결, 목소리·배경음악, 자막 중 원하는 내용만 적어 주세요." onChange={e=>onChange(e.target.value)} renderField={(input,action)=><Field id={id} label={label} required={required} help={guide} labelAction={action}>{()=>input}</Field>}/>
    <p id={`${id}-guide`} className="helper-text">필요한 항목만 작성하세요. 빈 항목은 AI에 전달하지 않습니다.</p>

  </section>;
}
