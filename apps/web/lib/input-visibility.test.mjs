import test from 'node:test';
import assert from 'node:assert/strict';
import {inputEntries,isInputVisible,isInputRequired} from './input-requirements.ts';
import {retryValues,retryPayload} from './input-requirements.ts';

test('retry keeps original values and parses only current visible input fields',()=>{
  const schema={type:'object',properties:{topic:{type:'string'},count:{type:'integer'},
    choice:{type:'string'},detail:{type:'string','x-visible-when':{field:'choice',equals:'custom'}}}};
  const original={topic:'original',count:2,removed:'legacy',choice:'other',detail:'hidden'};
  const values=retryValues(original,schema);
  assert.equal(values.removed,undefined);
  assert.deepEqual(retryPayload(values,schema),{topic:'original',count:2,choice:'other'});
  assert.equal(original.removed,'legacy');
  assert.equal(retryPayload({value:'hello'},{type:'string'}),'hello');
});

test('custom subject appears next to its choice and hidden text is excluded from payload fields',()=>{
  const rule={field:'subject',equals:'직접 입력'};
  const schema={type:'object',required:['age'],properties:{age:{type:'string'},custom:{type:'string','x-visible-when':rule,'x-required-when':rule},subject:{type:'string',enum:['유령','직접 입력']},tone:{type:'string'}}};
  const fields=inputEntries(schema);
  assert.deepEqual(fields.map(([k])=>k),['age','subject','custom','tone']);
  const visible=values=>fields.filter(([,n])=>isInputVisible(n,values)).map(([k])=>k);
  assert.equal(visible({subject:'유령',custom:'이전 소재'}).includes('custom'),false);
  assert.equal(visible({subject:'직접 입력'}).includes('custom'),true);
  assert.equal(isInputRequired(schema,'custom',{subject:'직접 입력'}),true);
  assert.equal(isInputRequired(schema,'custom',{subject:'유령'}),false);
});


test('video detail survives retry values and payload without leaking into other agents',()=>{
 const schema={type:'object',properties:{video_style:{type:'string'},video_model:{type:'string','x-video-model':true}}};
 const input={video_style:'animation_2d',video_model:'wan3',video_art_style:'수채화 질감'};
 assert.deepEqual(retryPayload(retryValues(input,schema),schema),input);
 assert.equal(retryPayload({...input,video_style:'auto'},schema).video_art_style,undefined);
 const other={type:'object',properties:{video_style:{type:'string'}}};
 assert.equal(retryValues(input,other).video_art_style,undefined);
 assert.equal(retryPayload(input,other).video_art_style,undefined);
});
