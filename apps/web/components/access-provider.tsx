"use client";
import {createContext, useContext, useEffect, useState, type ReactNode} from "react";
import {usePathname} from "next/navigation";
import {api, ApiError, setCsrf} from "../lib/registry";
import {navigationItems} from "../lib/navigation";

type Access = {ready:boolean; permissions:string[]; can:(permission:string)=>boolean};
const Context=createContext<Access>({ready:false,permissions:[],can:()=>false});
export function useAccess(){return useContext(Context);}
export function AccessProvider({children}:{children:ReactNode}){
  const pathname=usePathname();
  const [permissions,setPermissions]=useState<string[]>([]);
  const [ready,setReady]=useState(false);
  const [loggedIn,setLoggedIn]=useState(false);
  useEffect(()=>{
    let active=true;
    async function refresh(){
      try{
        const data=await api<{permissions:string[];csrf_token:string}>("/session");
        if(active){setPermissions(data.permissions||[]);setCsrf(data.csrf_token);setLoggedIn(true);setReady(true);}
      }catch(error){if(active){setPermissions([]);setReady(true);if(error instanceof ApiError&&error.status===401)setLoggedIn(false);}}
    }
    void refresh();const timer=setInterval(refresh,30000);
    window.addEventListener("focus",refresh);
    return()=>{active=false;clearInterval(timer);window.removeEventListener("focus",refresh);};
  },[pathname]);
  const can=(permission:string)=>permissions.includes("*")||(permissions.includes(permission)&&permissions.includes(permission.split(".")[0]+".view"));
  const menu=(pathname.startsWith("/work/")||pathname.startsWith("/works/"))?"home":navigationItems.filter(i=>i.href!=="/"?pathname===i.href||pathname.startsWith(i.href+"/"):pathname==="/").sort((a,b)=>b.href.length-a.href.length)[0]?.id;
  const blocked=ready&&loggedIn&&menu&&!can(menu+".view");
  return <Context.Provider value={{ready,permissions,can}}>{blocked?<main className="shell"><section className="card"><h1>접근 권한이 없습니다</h1><p>이 메뉴를 사용할 권한이 없습니다. 관리자에게 역할 설정을 확인해 주세요.</p><nav className="actions">{navigationItems.filter(i=>can(i.id+".view")).map(i=><a className="button button--secondary" key={i.id} href={i.href}>{i.label}</a>)}<a className="button button--secondary" href="/login">로그인 화면</a><button className="button button--secondary" onClick={async()=>{await api('/session','DELETE');window.location.href='/login';}}>로그아웃</button></nav></section></main>:children}</Context.Provider>;
}
