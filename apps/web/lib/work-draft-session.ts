import type {DraftRecord} from './work-draft-storage';
type IO={load:()=>Promise<DraftRecord|undefined>;write:(r:DraftRecord)=>Promise<void>;journal:(r:DraftRecord)=>void;clean:(r:DraftRecord)=>void;restore:(v:unknown)=>void;notice:(s:string)=>void};
export class DraftSession {
 private loaded=false;private stopped=false;private timer:ReturnType<typeof setTimeout>|undefined;private pending:DraftRecord|undefined;
 private serial:string;private skip:string;private time=0;private changed=false;private value:unknown;
 constructor(value:unknown,private io:IO,private delay=400){this.value=value;this.serial=JSON.stringify(value);this.skip=this.serial;}
 async start(){this.stopped=false;const initial=this.serial;try{const saved=await this.io.load();if(this.stopped)return;this.time=Math.max(this.time,saved?.time??0);this.loaded=true;
 if(saved&&!saved.deleted&&!this.pending&&this.serial===initial){this.skip=JSON.stringify(saved.value);this.io.restore(saved.value);this.io.notice('임시 저장한 입력을 복원했습니다. 아직 정식 저장되지 않았습니다.');return;}
 }catch{if(this.stopped)return;this.loaded=true;this.io.notice('임시 저장소를 읽지 못했습니다. 입력은 복구본으로 보호하며 저장 상태를 확인해 주세요.');}if(this.pending){clearTimeout(this.timer);this.timer=setTimeout(()=>{if(this.pending)void this.persist(this.pending);},this.delay);}else this.update(this.value,this.changed);}
 update(value:unknown,changed:boolean){this.value=value;this.serial=JSON.stringify(value);this.changed=changed;
 if(this.stopped||this.serial===this.skip)return;this.skip=this.serial;
 this.pending={format:1,time:this.time=Math.max(Date.now(),this.time+1),...(changed?{value}:{deleted:true})};
 clearTimeout(this.timer);this.io.notice(changed?'입력 임시 저장 대기 중…':'');if(!this.loaded)return;this.timer=setTimeout(()=>{if(this.pending)void this.persist(this.pending);},this.delay);}
 private async persist(record:DraftRecord){try{await this.io.write(record);this.io.clean(record);if(this.pending===record){this.pending=undefined;if(!this.stopped)this.io.notice(record.deleted?'':'이 브라우저에 임시 저장됨 · 정식 저장 전');}}
 catch{try{this.io.journal(record);if(!this.stopped)this.io.notice('IndexedDB 저장을 완료하지 못해 복구본에 보관했습니다.');}catch{if(!this.stopped)this.io.notice('임시 저장하지 못했습니다. 새로고침 전에 내용을 복사해 주세요.');}}}
 flush(){clearTimeout(this.timer);if(!this.pending)return;try{this.io.journal(this.pending);}catch{if(!this.stopped)this.io.notice('복구본을 저장하지 못했습니다. 새로고침 전에 내용을 복사해 주세요.');}void this.persist(this.pending);}
 clear(){clearTimeout(this.timer);this.skip=this.serial;this.pending={format:1,time:this.time=Math.max(Date.now(),this.time+1),deleted:true};this.io.notice('');this.flush();}
 stop(){this.flush();this.stopped=true;}
}
