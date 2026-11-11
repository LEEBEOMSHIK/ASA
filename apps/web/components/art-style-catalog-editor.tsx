"use client";
import {useEffect,useId,useState} from "react";
import Image from "next/image";
import {api,ApiError,message} from "../lib/registry";
import type {ArtCatalog,ArtPreset} from "../lib/art-style-catalog";
import {videoStyles} from "../lib/video-prompt-settings";
import {Button,DisclosureButton,Field,StatusBadge} from "./ui";

export function ArtStyleCatalogEditor({onDirtyChange}:{onDirtyChange:(dirty:boolean)=>void}){
  const id=useId();
  const [saved,setSaved]=useState<ArtCatalog|null>(null),[items,setItems]=useState<ArtPreset[]>([]);
  const [open,setOpen]=useState(false),[media,setMedia]=useState("animation_2d");
  const [busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
  const dirty=!!saved&&JSON.stringify(items)!==JSON.stringify(saved.items);
  useEffect(()=>{onDirtyChange(dirty);return()=>onDirtyChange(false);},[dirty,onDirtyChange]);
  function accept(value:ArtCatalog){setSaved(value);setItems(value.items);setError("");}
  useEffect(()=>{let alive=true;api<ArtCatalog>("/art-style-catalog").then(v=>{if(alive)accept(v);}).catch(e=>{if(alive)setError(message(e));});return()=>{alive=false;};},[]);
  function edit(key:string,patch:Partial<ArtPreset>){setItems(old=>old.map(p=>p.id===key?{...p,...patch}:p));setNotice("");}
  async function upload(key:string,file?:File){if(!file)return;setError("");
    if(!["image/png","image/jpeg","image/webp"].includes(file.type)||file.size>1024*1024){setError("PNG·JPEG·WebP 이미지(최대 1MB)를 선택하세요.");return;}
    try{const data=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=reject;reader.readAsDataURL(file);});edit(key,{image:data});}
    catch{setError("이미지 파일을 읽지 못했습니다. 다시 선택해 주세요.");}}
  async function save(){if(!saved||busy)return;setBusy(true);setError("");setNotice("");try{accept(await api<ArtCatalog>("/art-style-catalog","PUT",{revision:saved.revision,items}));setNotice("공통 화풍 목록을 저장했습니다. 기존 작품 설정은 유지됩니다.");}
    catch(e){setError(e instanceof ApiError&&e.code==="art_catalog_conflict"?"다른 관리자가 목록을 변경했습니다. 입력을 보관한 뒤 변경 취소·새로 불러오기로 최신 목록을 확인하세요.":e instanceof ApiError&&e.issues.length?e.issues.map(issue=>issue.message).join(" · "):message(e));}finally{setBusy(false);}}
  return <section className="art-catalog-editor" aria-label="관리자 공통 화풍 관리">
    <div className="voice-direction-heading"><div><h2>공통 화풍 관리</h2><p className="muted">캐릭터·씬·비디오 프롬프트가 함께 사용하는 목록입니다.</p>{dirty&&<StatusBadge>저장 전 변경</StatusBadge>}</div>
      <DisclosureButton variant="secondary" aria-expanded={open} aria-controls={id} onClick={()=>setOpen(!open)}>{open?"공통 화풍 접기":"공통 화풍 편집"}</DisclosureButton></div>
    <div id={id} hidden={!open} className="art-catalog-panel">
      <p className="muted">이 에이전트만의 설정이 아닙니다. 작품에서 선택해 저장할 때 적용되며, 기존 작품과 생성 결과는 바꾸지 않습니다.</p>
      {!saved?<p role="status">공통 목록을 불러오는 중…</p>:<form onSubmit={e=>{e.preventDefault();void save();}}>
        <fieldset disabled={busy} className="art-catalog-fields">
          <Field id={id+"type"} label="관리할 영상 유형">{p=><select {...p} value={media} onChange={e=>setMedia(e.target.value)}>{videoStyles.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select>}</Field>
          <div className="art-catalog-list">{items.filter(p=>p.media_type===media).map((item,index)=><section key={item.id} className="art-catalog-item" aria-label={`화풍 ${index+1}: ${item.label}`}>
            <div className="art-catalog-item-fields">
              <Field id={id+item.id+"name"} label="화풍 이름">{p=><input {...p} required maxLength={80} value={item.label} onChange={e=>edit(item.id,{label:e.target.value})}/>}</Field>
              <Field id={id+item.id+"media"} label="영상 유형">{p=><select {...p} value={item.media_type} onChange={e=>edit(item.id,{media_type:e.target.value})}>{videoStyles.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select>}</Field>
              <Field id={id+item.id+"prompt"} label="화풍 지침" hint="이미지와 영상 생성에 전달할 색감·질감·선·조명 등을 적어 주세요.">{p=><textarea {...p} required maxLength={2000} rows={4} value={item.description} onChange={e=>edit(item.id,{description:e.target.value})}/>}</Field>
              <Field id={id+item.id+"enabled"} label="선택 목록 표시">{p=><select {...p} value={item.enabled?"on":"off"} onChange={e=>edit(item.id,{enabled:e.target.value==="on"})}><option value="on">사용</option><option value="off">숨김 · 기존 작품 유지</option></select>}</Field>
            </div>
            <div className="art-catalog-preview">{item.image?<Image src={item.image} width={640} height={426} alt={`${item.label||"화풍"} 예시 이미지`}/>:<p className="muted">등록된 예시 이미지가 없습니다.</p>}
              <Field id={id+item.id+"file"} label="예시 이미지 업로드·교체" hint="PNG·JPEG·WebP, 최대 1MB. 화풍 선택용 예시이며 생성 참조 이미지로 보내지 않습니다.">{p=><input {...p} type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>{void upload(item.id,e.target.files?.[0]);e.target.value="";}}/>}</Field>
              {item.image&&<Button variant="secondary" onClick={()=>edit(item.id,{image:null})}>예시 이미지 제거</Button>}
            </div>
          </section>)}</div>
          <Button variant="secondary" disabled={items.length>=30} onClick={()=>{setItems(old=>[...old,{id:crypto.randomUUID(),media_type:media,label:"새 화풍",description:"",image:null,enabled:true}]);setNotice("");}}>화풍 추가</Button>
          <div className="art-catalog-actions"><Button variant="secondary" onClick={()=>void api<ArtCatalog>("/art-style-catalog").then(v=>{accept(v);setNotice("최신 공통 목록을 불러왔습니다.");}).catch(e=>setError(message(e)))}>변경 취소·새로 불러오기</Button><Button type="submit" disabled={!dirty}>{busy?"저장 중…":"공통 화풍 목록 저장"}</Button></div>
        </fieldset>
      </form>}
    </div>
    {error&&<p className="notice" role="alert">{error}</p>}{error&&!saved&&<Button variant="secondary" onClick={()=>void api<ArtCatalog>("/art-style-catalog").then(accept).catch(e=>setError(message(e)))}>공통 목록 다시 불러오기</Button>}{notice&&<p role="status">{notice}</p>}
  </section>;
}
