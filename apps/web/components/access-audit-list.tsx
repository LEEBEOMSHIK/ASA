"use client";
import {useEffect,useState} from "react";
import {api,message} from "../lib/registry";
import {ActionIcon,Button,DisclosureIcon,Field} from "./ui";

type Entry={id:number;event:string;actor_name:string;target_name:string;target_type:string;created_at:string};
type Result={items:Entry[];total:number;filtered_total:number;page:number;pages:number};
const labels:Record<string,string>={role_saved:"역할 저장",role_disabled:"역할 사용 중지",user_saved:"사용자 저장",user_disabled:"계정 사용 중지",test_user_created:"테스트 사용자 생성"};
export function AccessAuditList(){
  const [query,setQuery]=useState("");
  const [event,setEvent]=useState("all");
  const [days,setDays]=useState("0");
  const [page,setPage]=useState(1);
  const [revision,setRevision]=useState(0);
  const [result,setResult]=useState<Result|null>(null);
  const [busy,setBusy]=useState(true);
  const [error,setError]=useState("");
  useEffect(()=>{
    let active=true;
    setBusy(true);setError("");
    const timer=setTimeout(()=>{
      const params=new URLSearchParams({q:query,event,days,page:String(page)});
      api<Result>(`/admin/access/audit?${params}`).then(data=>{if(active)setResult(data);})
        .catch(e=>{if(active){setResult(null);setError(message(e));}})
        .finally(()=>{if(active)setBusy(false);});
    },200);
    return ()=>{active=false;clearTimeout(timer);};
  },[query,event,days,page,revision]);
  function reset(){setQuery("");setEvent("all");setDays("0");setPage(1);}
  return <section className="access-audit-browser" aria-labelledby="audit-title">
    <div className="access-heading"><h2 id="audit-title">변경 이력</h2><Button variant="secondary" disabled={busy} onClick={()=>setRevision(v=>v+1)}><ActionIcon kind="refresh"/>새로고침</Button></div>
    <div className="access-audit-filters compact-filter-fields">
      <Field id="audit-search" label="검색">{props=><input {...props} type="search" maxLength={120} placeholder="대상 또는 작업자 이름" value={query} onChange={e=>{setQuery(e.target.value);setPage(1);}}/>}</Field>
      <Field id="audit-event" label="변경 유형">{props=><select {...props} value={event} onChange={e=>{setEvent(e.target.value);setPage(1);}}><option value="all">전체 유형</option>{Object.entries(labels).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select>}</Field>
      <Field id="audit-period" label="기간">{props=><select {...props} value={days} onChange={e=>{setDays(e.target.value);setPage(1);}}><option value="0">전체 기간</option><option value="7">최근 7일</option><option value="30">최근 30일</option><option value="90">최근 90일</option></select>}</Field>
      <Button variant="secondary" disabled={!query&&event==="all"&&days==="0"} onClick={reset}><ActionIcon kind="undo"/>초기화</Button>
    </div>
    <p className="helper-text" role="status">{busy?"이력을 불러오고 있습니다…":result?`검색 결과 ${result.filtered_total}건 · 전체 ${result.total}건 · 페이지당 10건`:"이력을 표시할 수 없습니다."}</p>
    {error&&<p role="alert" className="field-error">{error}</p>}
    {!busy&&result&&<>
      <div className="access-audit-table"><table><caption className="sr-only">사용자·권한 변경 이력</caption><thead><tr><th scope="col">변경 유형</th><th scope="col">대상</th><th scope="col">작업자</th><th scope="col">변경 일시</th></tr></thead><tbody>
        {result.items.map(entry=><tr key={entry.id}><td data-label="변경 유형"><strong>{labels[entry.event]||"기타 변경"}</strong></td><td data-label="대상"><span>{entry.target_type} · {entry.target_name}</span></td><td data-label="작업자">{entry.actor_name}</td><td data-label="변경 일시"><time dateTime={entry.created_at}>{new Date(entry.created_at).toLocaleString("ko-KR")}</time></td></tr>)}
      </tbody></table>{!result.items.length&&<p className="access-role-empty">{result.total?"조건에 맞는 변경 이력이 없습니다.":"아직 변경 이력이 없습니다."}</p>}</div>
      <nav className="access-role-pagination" aria-label="변경 이력 페이지"><Button variant="secondary" disabled={result.page===1} onClick={()=>setPage(result.page-1)}><span className="access-previous"><DisclosureIcon/></span>이전</Button><span aria-live="polite">{result.page} / {result.pages} 페이지</span><Button variant="secondary" disabled={result.page===result.pages} onClick={()=>setPage(result.page+1)}>다음<DisclosureIcon/></Button></nav>
    </>}
    <p className="helper-text">최신 변경부터 표시합니다. 비밀번호와 접근 키는 기록하지 않습니다.</p>
  </section>;
}
