import test from 'node:test';
import assert from 'node:assert/strict';
import { priceStatus, validPrice } from './model-pricing.ts';
test('blank or partial rates are not registered',()=>{
 assert.equal(priceStatus(null),'확인 필요');
 assert.equal(validPrice({label:'manual',input:'',output:'2'}),false);
 assert.equal(validPrice({label:'manual',input:'0',output:'2',cache_read:''}),true);
 assert.equal(validPrice({label:'manual',input:'1',output:'-2'}),false);
});
test('manual and official rates are distinguishable',()=>{
 assert.equal(priceStatus({label:'공식 문서 표준 요율',input:'1',output:'2'}),'자동 확인됨');
 assert.equal(priceStatus({label:'관리자 수정 요율',input:'1',output:'2'}),'직접 수정됨');
});
