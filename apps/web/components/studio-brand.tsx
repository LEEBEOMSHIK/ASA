"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/registry";

export type Branding = {revision:number;name:string;logo:string|null};
export const defaultBrand: Branding = {revision:0,name:"AI Shorts Studio",logo:null};
export function BrandPreview({name,logo}: Pick<Branding,"name"|"logo">) {
  return <><span className="brand-mark" aria-hidden="true">{logo ? <img src={logo} alt=""/> : (name.trim()[0] || "A")}</span><span className="brand-name">{name}</span></>;
}
export function StudioBrand({ready=true, syncFavicon=true, publicView=false, placement="sidebar"}: {
  ready?:boolean; syncFavicon?:boolean; publicView?:boolean; placement?:"sidebar"|"header";
}) {
  const [brand,setBrand]=useState<Pick<Branding,"name"|"logo">>(defaultBrand);
  useEffect(()=>{
    if(!ready || !syncFavicon)return;
    const href=brand.logo || "/icons/asa.svg";
    const type=brand.logo?"image/png":"image/svg+xml";
    const sync=()=>{
      document.querySelectorAll<HTMLLinkElement>('link#asa-favicon').forEach(icon=>{
        if(icon.getAttribute("href")!==href)icon.setAttribute("href",href);
        if(icon.type!==type)icon.type=type;
      });
    };
    sync();
    // Next may reconcile head links after hydration or client navigation.
    const observer=new MutationObserver(sync);
    observer.observe(document.head,{childList:true,subtree:true,attributes:true,attributeFilter:["href","type"]});
    return ()=>{observer.disconnect();document.querySelectorAll<HTMLLinkElement>('link#asa-favicon').forEach(icon=>{icon.type="image/svg+xml";icon.href="/icons/asa.svg";});};
  },[ready,brand.logo,syncFavicon]);
  useEffect(()=>{
    if(!ready)return;
    let active=true;
    const load=()=>{void api<Pick<Branding,"name"|"logo">>(publicView ? "/branding/public" : "/branding").then(value=>{if(active)setBrand(value);}).catch(()=>{});};
    load();
    window.addEventListener("asa-branding-saved",load);
    return ()=>{active=false;window.removeEventListener("asa-branding-saved",load);};
  },[ready,publicView]);
  return <a className={`brand ${placement}-brand`} href="/" title={brand.name}><BrandPreview {...brand}/></a>;
}
