export type DraftRecord={format:1;time:number;value?:unknown;deleted?:boolean};
export function parseDraft(raw:string|null,now=Date.now()):DraftRecord|undefined {
 if(!raw)return;try{const r=JSON.parse(raw);if(r?.format!==1||!Number.isFinite(r.time)||r.time>now+1000||now-r.time>=30*86400000)return;
 if(r.deleted===true)return r;if(r.value&&typeof r.value==='object'&&!Array.isArray(r.value))return r;}catch{}
}
export function latestDraft(...records:(DraftRecord|undefined)[]){return records.filter((r):r is DraftRecord=>!!r).reduce<DraftRecord|undefined>((a,b)=>!a||b.time>=a.time?b:a,undefined);}
let database:Promise<IDBDatabase>|undefined;
function open(){if(!database)database=new Promise<IDBDatabase>((resolve,reject)=>{
 const r=indexedDB.open('asa-work-drafts',1);r.onupgradeneeded=()=>r.result.createObjectStore('drafts');
 r.onsuccess=()=>{r.result.onversionchange=()=>{r.result.close();database=undefined;};resolve(r.result);};
 r.onerror=()=>{database=undefined;reject(r.error);};r.onblocked=()=>{database=undefined;reject(new Error('draft_database_blocked'));};
 });return database;}
async function read(key:string){const db=await open();return new Promise<DraftRecord|undefined>((resolve,reject)=>{
 const tx=db.transaction('drafts','readonly'),r=tx.objectStore('drafts').get(key);let value:DraftRecord|undefined;
 r.onsuccess=()=>{value=parseDraft(r.result??null);};tx.oncomplete=()=>resolve(value);tx.onabort=()=>reject(tx.error);tx.onerror=()=>reject(tx.error);
 });}
export async function writeDraft(key:string,record:DraftRecord){const db=await open();return new Promise<void>((resolve,reject)=>{
 const tx=db.transaction('drafts','readwrite'),store=tx.objectStore('drafts'),r=store.get(key);
 r.onsuccess=()=>{const old=parseDraft(r.result??null);if(!old||old.time<=record.time)store.put(JSON.stringify(record),key);};
 tx.oncomplete=()=>resolve();tx.onabort=()=>reject(tx.error);tx.onerror=()=>reject(tx.error);
 });}
const recoveryKey=(key:string)=>`asa-draft-recovery:${key}`;
export function journalDraft(key:string,record:DraftRecord){const old=parseDraft(localStorage.getItem(recoveryKey(key)));if(!old||old.time<=record.time)localStorage.setItem(recoveryKey(key),JSON.stringify(record));}
export function cleanJournal(key:string,record:DraftRecord){for(const k of [key,recoveryKey(key)]){const raw=localStorage.getItem(k),old=parseDraft(raw);if(raw&&(!old||old.time<=record.time))localStorage.removeItem(k);}}
export async function loadDraft(key:string){
 let disk:DraftRecord|undefined,failure:unknown;
 try{disk=await read(key);}catch(e){failure=e;}
 const legacy=parseDraft(localStorage.getItem(key)),recovery=parseDraft(localStorage.getItem(recoveryKey(key)));
 const latest=latestDraft(disk,legacy,recovery);
 if(latest){try{await writeDraft(key,latest);cleanJournal(key,latest);}catch{/* Keep the legacy/recovery record until a transaction commits. */}return latest;}
 if(failure)throw failure;
}
