import test from 'node:test';
import assert from 'node:assert/strict';
import { aiCardInfo } from './ai-card.ts';
const node={instructions:'  검색 결과를\n대본으로 작성  ',provider:'openai'};
test('uses server default without a false missing-model warning',()=>{
 const info=aiCardInfo(node,'default-model');
 assert.equal(info.summary,'검색 결과를 대본으로 작성');
 assert.equal(info.model,'OpenAI · default-model');
 assert.equal(info.warning,'');
});
test('Claude cannot inherit OpenAI default; missing instructions take priority',()=>{
 assert.equal(aiCardInfo({...node,provider:'anthropic'},'openai-model').warning,'모델을 선택하세요');
 assert.equal(aiCardInfo({...node,instructions:' '},null).warning,'지시문을 입력하세요');
});
test('explicit model is retained and loading is not reported as missing',()=>{
 assert.equal(aiCardInfo({...node,provider:'anthropic',model:'chosen'},null).model,'Claude · chosen');
 assert.equal(aiCardInfo(node,null).warning,'');
});

assert.equal(aiCardInfo({instructions:"대본 작성"},"claude-default","anthropic").model,"Claude · claude-default");
assert.equal(aiCardInfo({instructions:"대본 작성",provider:"anthropic"},"claude-default","anthropic").warning,"");
