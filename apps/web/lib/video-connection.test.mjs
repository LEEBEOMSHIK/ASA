import {test} from 'node:test';
import assert from 'node:assert/strict';
import {connectionAuthenticated,connectionLabel} from './video-connection.ts';

test('configured or missing authentication evidence never implies authenticated',()=>{
  assert.equal(connectionAuthenticated(),false);
  for(const status of ['unchecked','denied','unreachable','unsupported','missing_key','missing_workspace']) {
    assert.equal(connectionAuthenticated({status,checked_at:new Date().toISOString()}),false);
  }
  assert.equal(connectionAuthenticated({status:'authenticated',checked_at:null}),false);
  assert.equal(connectionAuthenticated({status:'authenticated',checked_at:'invalid'}),false);
});
test('only recent successful authentication stays valid',()=>{
  assert.equal(connectionAuthenticated({status:'authenticated',checked_at:new Date(Date.now()-1000).toISOString()}),true);
  const stale={status:'authenticated',checked_at:new Date(Date.now()-301000).toISOString()};
  assert.equal(connectionAuthenticated(stale),false);
  assert.equal(connectionLabel(stale),'인증 재확인 필요');
  assert.equal(connectionAuthenticated({status:'authenticated',checked_at:new Date(Date.now()+60000).toISOString()}),false);
});
