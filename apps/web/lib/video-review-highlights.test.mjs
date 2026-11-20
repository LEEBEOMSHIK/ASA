import {test} from 'node:test';
import assert from 'node:assert/strict';
import {reviewPhrases,reviewKinds} from './video-review-highlights.ts';
const annotation=(source,quote,kind='camera',key='c:prompt')=>({source,quote,kind,key});
test('uses AI classifications without keyword inference and preserves every character',()=>{
 const text='😀  그가 잠시 숨을 고른다.\n카메라 줌. <script>x</script>';
 const parts=reviewPhrases(text,[annotation(text,'그가 잠시 숨을 고른다.','expression')],'c:prompt');
 assert.equal(parts.map(p=>p.text).join(''),text);
 assert.equal(parts.find(p=>p.kind)?.kind,'expression');
 assert.ok(parts.some(p=>p.text.includes('카메라 줌')&&!p.kind));
 assert.ok(reviewPhrases(text).every(p=>!p.kind));
});
test('rejects invented, stale, repeated, wrong-section and invalid category annotations',()=>{
 const text='안녕. 안녕. 눈길을 거둔다.';
 const values=[annotation(text,'없는 구절'),annotation('old','눈길을 거둔다.'),annotation(text,'안녕.'),annotation(text,'눈길을 거둔다.','gaze','c:voice'),annotation(text,'눈길을 거둔다.','bad')];
 assert.deepEqual(reviewPhrases(text,values,'c:prompt'),[{text}]);
});
test('rejects overlaps and preserves Unicode and whitespace',()=>{
 const text='😀 조용히 미소를 짓는다.\n';
 const parts=reviewPhrases(text,[annotation(text,'조용히 미소를 짓는다.','expression'),annotation(text,'미소를','gaze')],'c:prompt');
 assert.equal(parts.filter(p=>p.kind).length,1);
 assert.equal(parts.map(p=>p.text).join(''),text);
});
test('supports exact voice/music phrases and six legend categories',()=>{
 assert.equal(reviewKinds.length,6);
 for(const kind of ['voice','music']) {
  const text='따뜻하고 차분하게';
  assert.equal(reviewPhrases(text,[annotation(text,text,kind,'c:voice')],'c:voice')[0].kind,kind);
 }
 assert.deepEqual(reviewPhrases(''),[]);
});
test('accepts independently indexed repeated phrases and Unicode offsets',()=>{
 const text='😀 미소 미소';
 const parts=reviewPhrases(text,[{...annotation(text,'미소','expression'),start:2,end:4},{...annotation(text,'미소','expression'),start:5,end:7}],'c:prompt');
 assert.equal(parts.filter(p=>p.kind).length,2);
 assert.equal(parts.map(p=>p.text).join(''),text);
 assert.ok(reviewPhrases(text,[{...annotation(text,'미소'),start:0,end:1}],'c:prompt').every(p=>!p.kind));
});
