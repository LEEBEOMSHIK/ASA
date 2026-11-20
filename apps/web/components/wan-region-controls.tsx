"use client";
import {useId,useState} from "react";
import {connectionAuthenticated,connectionLabel,videoTimestamp,type VideoConnectionCheck} from "../lib/video-connection";
import {canApplyWanRegion,type WanRegionProof,type WanRegionState} from "../lib/wan-region";
import {ActionIcon,Button,Field,StatusBadge} from "./ui";
import "./wan-region-controls.css";

const configurationLabels:Record<string,string>={configured:"연결 설정 있음",missing_key:"API 키 미설정",missing_workspace:"작업 공간 ID 미설정",unsupported:"지원되지 않는 리전"};

export function WanRegionControls({state,canManage,busy,onCheck,onApply}:{
  state:WanRegionState; canManage:boolean; busy:boolean;
  onCheck:(region:string)=>Promise<VideoConnectionCheck|undefined>;
  onApply:(region:string,revision:number)=>void;
}) {
  const id=useId();
  const [target,setTarget]=useState(state.active_region);
  const [proof,setProof]=useState<WanRegionProof|null>(null);
  const selected=state.regions.find(item=>item.region===target);
  const active=state.regions.find(item=>item.region===state.active_region);
  const check=proof?.region===target&&proof.revision===state.revision?proof.check:selected?.connection_check;
  const eligible=canApplyWanRegion(state,target,proof);
  async function authenticate(){
    setProof(null);
    const revision=state.revision;
    const result=await onCheck(target);
    if(result)setProof({region:target,revision,check:result});
  }
  return <section className="video-management-section wan-region-controls" aria-labelledby={`${id}-title`}>
    <div className="video-management-row"><h3 id={`${id}-title`}>WAN 리전</h3><StatusBadge>현재 · {active?.label??state.active_region}</StatusBadge></div>
    <p className="helper-text">리전 변경은 새 영상 요청부터 적용됩니다. 기존 요청은 접수 당시 리전에서 계속 처리됩니다.</p>
    <Field id={`${id}-target`} label="사용할 리전" hint="선택 후 인증을 확인하고 적용해 주세요. 인증 확인은 5분 동안 유효합니다.">
      {props=><select {...props} value={target} disabled={busy||!canManage} onChange={event=>{setTarget(event.target.value);setProof(null);}}>
        {state.regions.map(item=><option key={item.region} value={item.region}>{item.label}</option>)}
      </select>}
    </Field>
    <div className="wan-region-status">
      <div className="video-management-row"><strong>{selected?.label??target}</strong><StatusBadge tone={connectionAuthenticated(check)?"success":"warning"}>{connectionLabel(check)}</StatusBadge></div>
      <p className="helper-text">{configurationLabels[selected?.connection_state??""]??"설정 상태 미확인"} · 마지막 인증 확인 {videoTimestamp(check?.checked_at)}</p>
      {selected?.connection_state!=="configured"&&<p className="helper-text">이 리전의 API 키·작업 공간 ID를 서버 환경 설정에 먼저 등록해 주세요.</p>}
    </div>
    <div className="video-management-actions">
      <Button variant="secondary" disabled={busy||!canManage||selected?.connection_state!=="configured"} onClick={()=>void authenticate()}><ActionIcon kind="refresh"/>선택 리전 인증 확인</Button>
      <Button disabled={busy||!canManage||!eligible} onClick={()=>{if(canApplyWanRegion(state,target,proof))onApply(target,state.revision);}}><ActionIcon kind="confirm"/>리전 적용</Button>
    </div>
    <p className="helper-text">{target===state.active_region?"현재 사용 중인 리전입니다.":eligible?"인증을 확인했습니다. 리전 적용을 누르면 새 요청에 사용합니다.":"다른 리전을 적용하려면 선택한 리전의 인증을 먼저 확인해 주세요."}</p>
    <p className="helper-text">리전별 연결 정보는 서버에서 별도로 관리합니다. 인증 확인은 영상 생성 권한·무료 할당량·잔액을 보장하지 않습니다.</p>
  </section>;
}
