"use client";
import {useId, useRef, useState, useEffect} from "react";
import {api} from "../lib/registry";
import {ActionIcon, Button, StatusBadge, Switch} from "./ui";

type State = {enabled:boolean; revision:number; can_manage:boolean; providers:Record<string,boolean>;
  connections:Record<string,string>; counts:{paused:number;running:number}; worker:{state:string;busy:boolean}};
const providers:Record<string,string>={runway:"Runway",alibaba:"WAN · Alibaba"};
const connectionLabels:Record<string,string>={configured:"연결 설정 있음",missing_key:"API 키 미설정",missing_workspace:"작업 공간 ID 미설정",unsupported:"지원되지 않음"};

export function VideoGenerationManager({onChanged}:{onChanged?:()=>void}) {
  const [open,setOpen]=useState(false),[data,setData]=useState<State|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
  const dialog=useRef<HTMLDialogElement>(null),trigger=useRef<HTMLButtonElement>(null);
  const changing=useRef(false),serial=useRef(0); const id=useId();
  async function refresh(){
    const seq=++serial.current;
    try { const next=await api<State>("/video-management"); if(seq===serial.current){setData(next);setError("");} }
    catch {if(seq===serial.current)setError("상태를 불러오지 못했습니다. 새로고침 후 다시 확인해 주세요.");}
  }
  useEffect(()=>{
    if(!open)return;
    void refresh();
    const timer=setInterval(()=>{if(!changing.current&&!document.hidden)void refresh();},3000);
    return ()=>{clearInterval(timer);serial.current++;};
  },[open]);
  async function act(action:()=>Promise<unknown>,message:string){
    if(changing.current)return;
    changing.current=true;serial.current++;setBusy(true);setError("");setNotice("");
    try {await action();await refresh();setNotice(message);onChanged?.();}
    catch {setError("변경하지 못했습니다. 권한·연결 상태를 확인해 주세요. 다른 화면에서 변경했다면 새로고침 후 다시 시도하세요.");}
    finally {changing.current=false;setBusy(false);}
  }
  function update(enabled:boolean,next=data?.providers){
    if(!data)return;
    void act(()=>api("/video-management","PUT",{enabled,providers:next,revision:data.revision}),
      enabled?"설정을 적용했습니다. 활성화만으로 생성하거나 보류 요청을 재개하지 않습니다.":"새 영상 생성을 중지했습니다. 이미 전송한 요청은 계속 결과를 확인합니다.");
  }
  return <>
    <Button variant="secondary" onClick={event=>{trigger.current=event.currentTarget;setOpen(true);dialog.current?.showModal();}} aria-haspopup="dialog"><ActionIcon kind="settings"/>영상 생성 관리</Button>
    <dialog ref={dialog} className="worker-controls-dialog video-management-dialog" aria-labelledby={id}
      onClose={()=>{setOpen(false);trigger.current?.focus();}}>
      <div className="worker-controls-heading"><h2 id={id}>영상 생성 관리</h2><Button variant="secondary" onClick={()=>dialog.current?.close()}><ActionIcon kind="close"/>닫기</Button></div>
      <div className="worker-controls video-management-content">
        <p className="helper-text">공급자 연결과 보류 요청을 관리합니다. 연결 설정 확인만으로 영상 생성이나 비용이 발생하지 않습니다.</p>
        {data&&<>
          {!data.can_manage&&<p className="helper-text">설정 변경은 로컬 작업 공간의 관리자만 할 수 있습니다.</p>}
          <section className="video-management-section"><h3>공급자 연결</h3>
            <p className="helper-text">기존 서버의 연결 설정을 사용합니다. ‘연결 설정 있음’은 계정 권한·잔액 확인을 의미하지 않습니다. API 키는 표시하지 않습니다.</p>
            {Object.entries(providers).map(([key,name])=><div className="video-management-provider" key={key}>
              <div className="video-management-row"><strong>{name}</strong><StatusBadge tone={data.connections[key]==="configured"?"success":"warning"}>{connectionLabels[data.connections[key]]??"상태 미확인"}</StatusBadge></div>
              <Switch label={`${name} 사용 허용`} checked={data.providers[key]} disabled={busy||!data.can_manage||data.worker.state==="external"} onChange={()=>update(data.enabled,{...data.providers,[key]:!data.providers[key]})}/>
              {data.connections[key]!=="configured"&&<p className="helper-text">{key==="alibaba"?"서버에 WAN API 키·작업 공간 ID·리전을 등록해야 합니다.":"서버에 Runway API 키를 등록해야 합니다."}</p>}
              <Button variant="secondary" disabled={busy} onClick={()=>void act(async()=>{
                if(key==="runway"&&data.connections[key]==="configured"){
                  const result=await api<{status:string}>("/video-planning/runway-connection","POST");
                  if(result.status!=="authenticated")throw new Error("connection_failed");
                }
              },key==="runway"&&data.connections[key]==="configured"?"Runway 계정 인증을 확인했습니다. 영상은 생성하지 않았습니다.":"서버 연결 설정을 다시 확인했습니다. 계정 권한·잔액 검증이나 영상 생성은 수행하지 않았습니다.")}><ActionIcon kind="refresh"/>{key==="runway"?"연결 확인":"연결 설정 확인"}</Button>
            </div>)}
          </section>
          <section className="video-management-section"><h3>영상 요청 상태</h3>
            <p className="helper-text">전송 중·결과 대기 {data.counts.running}개 · 보류 {data.counts.paused}개</p>
            {data.can_manage ? <Switch label="새 영상 생성 허용" checked={data.enabled} disabled={busy||data.worker.state==="external"} onChange={()=>update(!data.enabled)}/> : !data.enabled&&<StatusBadge tone="warning">새 영상 생성 일시 중지 중</StatusBadge>}
            <p className="helper-text">끄면 새 요청을 막고 대기 요청을 보류합니다. 이미 전송한 요청은 계속 처리됩니다.</p>
            <p className="helper-text">켜기만 해서는 영상 생성이나 비용이 발생하지 않습니다. 보류 요청은 별도로 재개해 주세요.</p>
            {data.can_manage&&data.worker.state==="external"&&<p role="alert">기존 영상 프로세스를 종료하고 최신 백그라운드 작업으로 다시 시작해야 설정을 변경할 수 있습니다.</p>}
            {data.counts.paused>0&&<><Button disabled={busy||!data.can_manage||!data.enabled} onClick={()=>void act(()=>api("/video-management/resume","POST",{}),"허용된 공급자의 보류 요청을 재개했습니다.")}><ActionIcon kind="ai"/>보류 요청 재개 · 비용 발생 가능</Button></>}
          </section>
        </>}
        {busy&&<p role="status">처리 중…</p>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
        <Button variant="secondary" disabled={busy} onClick={()=>void refresh()}><ActionIcon kind="refresh"/>상태 새로고침</Button>
      </div>
    </dialog>
  </>;
}
