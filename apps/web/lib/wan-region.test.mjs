import {test} from 'node:test';
import assert from 'node:assert/strict';
import {canApplyWanRegion} from './wan-region.ts';

test('region application requires matching fresh authentication and a configured different region',()=>{
  const check={status:'authenticated',checked_at:new Date().toISOString()};
  const state={active_region:'ap-southeast-1',revision:2,regions:[{region:'ap-northeast-1',label:'도쿄',connection_state:'configured',connection_check:check}]};
  const proof={region:'ap-northeast-1',revision:2,check};
  assert.equal(canApplyWanRegion(state,'ap-northeast-1',proof),true);
  assert.equal(canApplyWanRegion(state,'ap-northeast-1',null),false);
  assert.equal(canApplyWanRegion(state,'ap-southeast-1',proof),false);
  assert.equal(canApplyWanRegion(state,'ap-northeast-1',{...proof,region:'ap-southeast-1'}),false);
  assert.equal(canApplyWanRegion(state,'ap-northeast-1',{...proof,revision:1}),false);
  assert.equal(canApplyWanRegion(state,'ap-northeast-1',{...proof,check:{...check,checked_at:new Date(Date.now()-301000).toISOString()}}),false);
  assert.equal(canApplyWanRegion({...state,regions:[{...state.regions[0],connection_state:'missing_key'}]},'ap-northeast-1',proof),false);
});
