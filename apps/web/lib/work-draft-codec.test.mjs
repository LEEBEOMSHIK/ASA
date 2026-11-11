import {test} from 'node:test';
import assert from 'node:assert/strict';
import {decodeWorkDraft} from './work-draft-codec.ts';
test('draft payload only restores supported unexpired object records',()=>{
 const now=100*86400000;
 const encode=(value,time=now,format=1)=>JSON.stringify({value,time,format});
 assert.deepEqual(decodeWorkDraft(encode({text:'입력'}),now),{text:'입력'});
 for(const raw of [encode(null),encode('text'),encode([]),encode({},now+1),encode({},now-30*86400000),encode({},now,2)])assert.equal(decodeWorkDraft(raw,now),undefined);
 assert.throws(()=>decodeWorkDraft('{broken',now));
});
