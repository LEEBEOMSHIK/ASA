"use client";

import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { api, ApiError, message } from "../lib/registry";
import { navigationColors, navigationItems, type NavigationColor, type NavigationColorItems, type NavigationColorValue } from "../lib/navigation";
import { navigationAccent, normalizeNavigationHex } from "../lib/navigation-color";

const NavigationContext = createContext<{
  items:NavigationColorItems; open:(menu?:string,returnFocus?:HTMLElement|null)=>void; available:boolean;
}>({items:{},open:()=>{},available:false});
export const useNavigationPreferences = () => useContext(NavigationContext);

export function NavigationPreferences({ready,admin,children}:{ready:boolean;admin:boolean;children:ReactNode}) {
  const [items,setItems] = useState<NavigationColorItems>({});
  const [editing,setEditing] = useState(false),[loading,setLoading] = useState(false),[busy,setBusy] = useState(false);
  const [menu,setMenu] = useState("home"),[color,setColor] = useState<NavigationColor|"default"|"custom">("default");
  const [customHex,setCustomHex] = useState("#3b82f6");
  const [revision,setRevision] = useState(0),[error,setError] = useState("");
  const [loaded,setLoaded] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null),trigger = useRef<HTMLElement|null>(null);
  const editorGeneration = useRef(0), accountGeneration = useRef(0);
  const id = useId();
  const options = navigationItems.filter(item=>!item.admin||admin);
  const normalizedHex=normalizeNavigationHex(customHex);
  const invalidHex=color==="custom"&&!normalizedHex;
  const selectedColor=color==="custom"?normalizedHex:color;
  const refresh = useCallback(async () => {
    const generation = accountGeneration.current;
    const result = await api<{items:NavigationColorItems}>("/profile/navigation-colors");
    if(generation!==accountGeneration.current) return result.items;
    setItems(previous=>{
      const merged = {...previous};
      for (const [key,value] of Object.entries(result.items)) {
        if (value.revision >= (merged[key]?.revision || 0)) merged[key]=value;
      }
      return merged;
    });
    return result.items;
  },[]);
  useEffect(()=>{
    accountGeneration.current++;
    if (!ready) { setItems({});editorGeneration.current++;dialog.current?.close();return; }
    const reload = () => { if (document.visibilityState === "visible") void refresh().catch(()=>{}); };
    reload();
    window.addEventListener("focus",reload); document.addEventListener("visibilitychange",reload);
    return ()=>{accountGeneration.current++;window.removeEventListener("focus",reload);document.removeEventListener("visibilitychange",reload);};
  },[ready,refresh]);
  useEffect(()=>{
    if (editing) dialog.current?.showModal();
  },[editing]);
  function chooseMenu(key:string,values=items) {
    const saved=values[key]?.color;
    const custom=saved?normalizeNavigationHex(saved):null;
    setMenu(key);setColor(custom?"custom":saved||"default");setRevision(values[key]?.revision||0);
    setCustomHex(custom||"#3b82f6");setError("");
  }
  async function loadEditor(key:string) {
    const generation=++editorGeneration.current;
    setLoading(true);setLoaded(false);setError("");
    try { const values=await refresh();if(generation!==editorGeneration.current)return;chooseMenu(key,values);setLoaded(true); }
    catch(e){if(generation===editorGeneration.current)setError(message(e));}
    finally{if(generation===editorGeneration.current)setLoading(false);}
  }
  function open(key="home",returnFocus?:HTMLElement|null) {
    if(!ready)return;
    trigger.current=returnFocus || (document.activeElement instanceof HTMLElement?document.activeElement:null);
    const allowed=options.some(item=>item.id===key)?key:"home";
    setMenu(allowed);setEditing(true);void loadEditor(allowed);
  }
  function close() { if(!busy){dialog.current?.close();} }
  async function save() {
    if(busy||loading||!loaded||invalidHex)return;
    setBusy(true);setError("");
    try {
      const value=await api<NavigationColorValue>(`/profile/navigation-colors/${menu}`,"PUT",{color:selectedColor==="default"?null:selectedColor,revision});
      setItems(previous=>(previous[menu]?.revision||0)>value.revision?previous:{...previous,[menu]:value});setRevision(value.revision);
      dialog.current?.close();
    } catch(e) {
      if(e instanceof ApiError && e.status===409) {
        // Rebase the version, but never silently overwrite or discard the user's choice.
        try { const values=await refresh();setRevision(values[menu]?.revision||0);setError("다른 기기에서 이 메뉴의 색을 변경했습니다. 현재 선택을 적용하려면 다시 저장하세요."); }
        catch {setLoaded(false);setError("최신 설정을 불러오지 못했습니다. 다시 불러온 후 저장하세요.");}
      } else setError(message(e));
    } finally {setBusy(false);}
  }
  return <NavigationContext.Provider value={{items,open,available:ready}}>{children}
    <dialog ref={dialog} className="navigation-colors-dialog" aria-labelledby={`${id}-title`}
      onCancel={event=>{if(busy)event.preventDefault();}}
      onClose={()=>{editorGeneration.current++;setEditing(false);trigger.current?.focus();}}>
      <div className="navigation-colors-heading"><h2 id={`${id}-title`}>메뉴 강조색</h2>
        <button type="button" className="button button--secondary" disabled={busy} onClick={close}>닫기</button></div>
      <div className="navigation-colors-content">
      <p className="muted">자주 쓰는 메뉴를 색으로 구분하세요. PC와 모바일에서 같은 계정·작업 공간에 적용됩니다.</p>
      {loading&&<p role="status">저장된 색을 불러오는 중입니다…</p>}
      {error&&<p role="alert" className="field-error">{error}</p>}
      {!loaded&&!loading&&<button type="button" className="button button--secondary" onClick={()=>void loadEditor(menu)}>다시 불러오기</button>}
      <label className="field" htmlFor={`${id}-menu`}>메뉴
        <select id={`${id}-menu`} disabled={loading||busy||!loaded} value={menu} onChange={e=>chooseMenu(e.target.value)}>
          {options.map(item=><option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
      </label>
      <fieldset className="navigation-color-options" disabled={loading||busy||!loaded}>
        <legend>강조색</legend>
        {[{id:"default",label:"기본색"},...navigationColors,{id:"custom",label:"직접"}].map(choice=><label key={choice.id} className="navigation-color-choice" {...navigationAccent(choice.id==="custom"?normalizedHex:choice.id)}>
          <input type="radio" name={`${id}-color`} value={choice.id} aria-label={choice.id==="custom"?"직접 선택":undefined} checked={color===choice.id} onChange={()=>{setColor(choice.id as NavigationColor|"default"|"custom");}}/>
          <span className="navigation-color-swatch" style={choice.id==="custom"&&normalizedHex?{backgroundColor:normalizedHex}:undefined} aria-hidden="true"/>{choice.label}
        </label>)}
      </fieldset>
      <fieldset className="navigation-custom-color" disabled={loading||busy||!loaded}>
        <legend>원하는 색 고르기</legend>
        <div className="navigation-custom-inputs">
          <label className="field" htmlFor={`${id}-palette`}>팔레트
            <input id={`${id}-palette`} type="color" value={normalizedHex||"#3b82f6"}
              onChange={event=>{setColor("custom");setCustomHex(event.target.value);}}/>
          </label>
          <label className="field" htmlFor={`${id}-hex`}>HEX 색상
            <input id={`${id}-hex`} type="text" value={customHex} maxLength={7} spellCheck={false} autoComplete="off"
              aria-invalid={invalidHex||undefined} aria-describedby={`${id}-hex-hint`}
              onChange={event=>{setColor("custom");setCustomHex(event.target.value);}}
              onBlur={()=>{if(normalizedHex)setCustomHex(normalizedHex);}}/>
          </label>
        </div>
        <p id={`${id}-hex-hint`} className={`navigation-color-feedback ${invalidHex?"field-error":"muted"}`} role={invalidHex?"alert":undefined}>
          {invalidHex?"#과 6자리 숫자·A–F로 입력하세요. 예: #3B82F6":"팔레트 또는 HEX로 선택하세요. 저장 전까지 적용되지 않습니다."}
        </p>
      </fieldset>
      <div className="navigation-color-summary"><div className="navigation-color-preview" {...navigationAccent(selectedColor)}>
        <span aria-hidden="true">◆</span><strong>{options.find(item=>item.id===menu)?.label}</strong><small>색 미리보기</small>
      </div>
      <p className="muted">글자와 배경은 화면 모드에 맞춰 대비를 조정합니다. 기본색으로 저장하면 초기화됩니다. 현재 열린 메뉴는 테두리로 구분됩니다.</p>
      </div>
      </div>
      <div className="actions"><button type="button" className="button button--secondary" disabled={busy} onClick={close}>취소</button>
        <button type="button" className="button button--primary" disabled={busy||loading||!loaded||invalidHex} onClick={()=>void save()}>{busy?"저장 중…":"저장"}</button></div>
    </dialog>
  </NavigationContext.Provider>;
}
