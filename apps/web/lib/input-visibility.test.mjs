import test from 'node:test';
import assert from 'node:assert/strict';
import {inputEntries,isInputVisible,isInputRequired} from './input-requirements.ts';

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
