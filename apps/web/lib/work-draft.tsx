"use client";
import {createContext,useContext,useEffect,useLayoutEffect,useRef,useState} from "react";
import {DraftSession} from "./work-draft-session";
import {loadDraft,writeDraft,journalDraft,cleanJournal} from "./work-draft-storage";
export const DraftScope=createContext("");
export function useWorkDraft<T>(key:string|undefined,value:T,restore:(value:T)=>void,ready=true,changed=true){
 const scope=useContext(DraftScope),storageKey=scope&&key?`asa-input-draft:v1:${scope}:${key}`:"";
 const session=useRef<{key:string;manager:DraftSession}|null>(null),latest=useRef({value,changed});
 const restoreRef=useRef(restore);restoreRef.current=restore;
 const [notice,setNotice]=useState("");
 useLayoutEffect(()=>{latest.current={value,changed};if(session.current?.key===storageKey)session.current.manager.update(value,changed);},[storageKey,value,changed]);
 useEffect(()=>{
 if(!ready||!storageKey)return;
 const manager=new DraftSession(latest.current.value,{load:()=>loadDraft(storageKey),write:r=>writeDraft(storageKey,r),journal:r=>journalDraft(storageKey,r),clean:r=>cleanJournal(storageKey,r),restore:v=>restoreRef.current(v as T),notice:setNotice});
 session.current={key:storageKey,manager};manager.update(latest.current.value,latest.current.changed);void manager.start();
 const flush=()=>manager.flush(),hidden=()=>{if(document.visibilityState==="hidden")flush();};
 window.addEventListener("pagehide",flush);window.addEventListener("beforeunload",flush);document.addEventListener("visibilitychange",hidden);
 return()=>{manager.stop();if(session.current?.manager===manager)session.current=null;window.removeEventListener("pagehide",flush);window.removeEventListener("beforeunload",flush);document.removeEventListener("visibilitychange",hidden);};
 },[storageKey,ready]);
 return {notice,clear:()=>session.current?.manager.clear()};
}
