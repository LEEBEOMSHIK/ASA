import {test} from 'node:test';
import assert from 'node:assert/strict';
import {videoRetryEligible,videoRetryReady} from './video-retry.ts';

test('known provider task or unavailable target blocks fresh paid generation',()=>{
  assert.equal(videoRetryEligible(null),false);
  assert.equal(videoRetryEligible({eligible:true,target:{},original:{provider_task:'existing-provider-task'}}),false);
  assert.equal(videoRetryEligible({eligible:true,target:null,original:{provider_task:null}}),false);
  assert.equal(videoRetryEligible({eligible:false,target:{},original:{provider_task:null}}),false);
  assert.equal(videoRetryEligible({eligible:true,target:{},original:{provider_task:null}}),true);
});
test('only uncertain results require acknowledgment; busy and loading remain blocked',()=>{
  assert.equal(videoRetryReady(true,false,false,false,false),true);
  assert.equal(videoRetryReady(true,true,true,false,false),true);
  for(const args of [[false,false,false,false,false],[true,true,false,false,false],[true,false,false,true,false],[true,false,false,false,true]]) assert.equal(videoRetryReady(...args),false);
});
