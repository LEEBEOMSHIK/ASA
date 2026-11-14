"use client";
import {createContext,useContext,useEffect,useRef,useState,type ReactNode} from "react";
import {DraftScope} from "../lib/work-draft";
import {initialWorkTab,workTabKey,type WorkTab} from "../lib/work-tabs";
import {workTabItems,type WorkTabItem} from "../lib/work-layout";
import {Button} from "./ui";
export const CharacterWorkTabsContext=createContext<{tab:WorkTab;select:(tab:WorkTab)=>void}|null>(null);
export function useCharacterWorkTabs(){return useContext(CharacterWorkTabsContext);}
const documentEntryPath=typeof window==="undefined"?"":window.location.pathname;
let reloadClaimed=false;
export function useWorkTabSelection(request:string,preferred:WorkTab,ready:boolean,hasCommon=true){
 const scope=useContext(DraftScope),key=workTabKey(scope,request);
 const [selection,setSelection]=useState<{key:string|null;tab:WorkTab}>({key:null,tab:"images"});
 const [warning,setWarning]=useState("");
 const initialized=useRef<string|null>(null);
 useEffect(()=>{
  if(!ready || !key || initialized.current===key)return;
  initialized.current=key;
  const reload=!reloadClaimed && documentEntryPath.startsWith(`/works/${request}`) && (performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming|undefined)?.type==="reload";
  reloadClaimed=true;
  let tab=preferred;
  try{tab=initialWorkTab(preferred,localStorage.getItem(key),reload);if(tab==="common"&&!hasCommon)tab=preferred;localStorage.setItem(key,tab);}catch{setWarning("탭 선택을 저장·복원하지 못했습니다. 남은 작업에 맞는 탭을 표시합니다.");}
  setSelection({key,tab});
 },[key,request,preferred,ready,hasCommon]);
 const savedTab=selection.key===key?selection.tab:preferred;
 const tab=savedTab==="common"&&!hasCommon?"images":savedTab;
 function select(tab:WorkTab){
  if(tab==="common"&&!hasCommon)tab=preferred;
  setSelection({key,tab});
  try{if(key)localStorage.setItem(key,tab);}catch{setWarning("탭 선택을 이 브라우저에 저장하지 못했습니다. 새로고침하면 기본 탭이 열립니다.");}
 }
 return {tab,select,warning};
}
export function WorkTabBar({prefix,items=workTabItems({})}:{prefix:string;items?:WorkTabItem[]}){
 const tabs=useCharacterWorkTabs()!;
 return <div className="work-task-tabs" role="tablist" aria-label="에이전트 작업 영역">{items.map((item,index)=><Button key={item.id} variant="secondary" role="tab" aria-label={item.label} id={`${prefix}-${item.id}`} aria-selected={tabs.tab===item.id} aria-controls={`${prefix}-panel`} aria-describedby={`${prefix}-${item.id}-description`} tabIndex={tabs.tab===item.id?0:-1} onClick={()=>tabs.select(item.id)} onKeyDown={e=>{
 if(e.ctrlKey||e.metaKey||e.altKey)return;
 const next=e.key==="Home"?0:e.key==="End"?items.length-1:e.key==="ArrowRight"?(index+1)%items.length:e.key==="ArrowLeft"?(index+items.length-1)%items.length:-1;
 if(next<0)return;e.preventDefault();tabs.select(items[next].id);document.getElementById(`${prefix}-${items[next].id}`)?.focus();
 }}><span className="work-tab-title">{item.label}</span><span className="work-tab-description" id={`${prefix}-${item.id}-description`}>{item.description}</span></Button>)}</div>;
}
export function WorkTabPart({tab,children,className=""}:{tab:WorkTab;children:ReactNode;className?:string}){
 const tabs=useCharacterWorkTabs();if(!tabs)return <>{children}</>;return <div className={`work-tab-part ${className}`} hidden={!!tabs&&tabs.tab!==tab}>{children}</div>;
}
