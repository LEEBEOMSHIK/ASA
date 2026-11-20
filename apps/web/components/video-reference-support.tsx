import {StatusBadge} from './ui';

export type ReferenceSupport={image:boolean;audio:boolean;video:boolean};
export function VideoReferenceSupport({support}:{support?:ReferenceSupport}){
  if(!support)return <p className="helper-text">참조 파일 지원 정보를 확인하는 중입니다.</p>;
  return <section className="video-reference-support" aria-label="모델별 참조 파일 지원">
    <strong>참조 파일 지원</strong>
    <div className="video-reference-support-list">{([
      ['image','이미지'],['audio','음성'],['video','영상'],
    ] as const).map(([key,label])=><span key={key}>{label} <StatusBadge tone={support[key]?'success':'neutral'}>{support[key]?'지원':'미지원'}</StatusBadge></span>)}</div>
    <p className="helper-text">시작 이미지 1장과 추가 참조는 구분됩니다. 참조 기반 모드는 첫 프레임을 완전히 고정하지 않습니다. 지원하지 않는 참조를 자동으로 제외하지 않습니다.</p>
  </section>;
}
