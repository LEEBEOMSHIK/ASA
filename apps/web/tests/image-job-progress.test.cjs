const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
for (const ext of ['.ts', '.tsx']) require.extensions[ext] = (module, filename) => {
  module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX}}).outputText, filename);
};
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
const {elapsedTime} = require('../lib/image-job-time.ts');
const {ImageJobProgress} = require('../components/image-job-progress.tsx');
const job = {id:'test',version:2,status:'queued',model:'test-model',base_id:'base',created_at:'2026-11-01T00:00:00Z',started_at:null,finished_at:null,change:'모자만 파란색',character:{name:'검증 캐릭터',appearance:'노란 우비',image_prompt:'정면 전신'}};
const render = (patch,online=true) => renderToStaticMarkup(React.createElement(ImageJobProgress,{job:{...job,...patch},online,baseVersion:1}));
test('elapsed time survives reload and freezes at server finish timestamp',()=>{
 assert.equal(elapsedTime(job.created_at,'2026-11-01T00:02:03Z'),'2분 3초');
 assert.equal(elapsedTime(job.created_at,'2026-10-31T23:59:00Z'),'0분 0초');
 assert.equal(elapsedTime(null,Date.now()),'확인 중');
 assert.equal(elapsedTime('invalid',Date.now()),'확인 중');
 assert.equal(elapsedTime(job.created_at,null),'확인 중');
});
test('queued offline explains saved queue, immutable request and no duplicate request',()=>{
 const html=render({},false);
 for(const value of ['이미지 생성 대기','실행 서비스 연결','다시 요청하지','노란 우비','모자만 파란색','v1 이미지 수정','최근 작업']) assert.ok(html.includes(value),value);
});
test('running describes known processing, and finished removes waiting UI',()=>{
 const running=render({status:'running',started_at:job.created_at});
 assert.ok(running.includes('이미지 생성 중')); assert.ok(running.includes('생성 API')); assert.ok(!running.includes('NaN'));
 const done=render({status:'succeeded',started_at:'2026-11-01T00:00:03Z',finished_at:'2026-11-01T00:02:03Z'});
 assert.ok(done.includes('2분 3초')); assert.ok(done.includes('2분 0초')); assert.ok(!done.includes('이번 요청'));
});
test('steps follow queue and generation; review is not auto approved',()=>{
 const queued=render({});
 assert.match(queued,/aria-current="step"[^]*?<strong>실행 대기<\/strong>/);
 const running=render({status:'running',started_at:job.created_at});
 assert.match(running,/aria-current="step"[^]*?<strong>이미지 생성·저장<\/strong>/);
 const done=render({status:'succeeded',started_at:job.created_at,finished_at:job.created_at});
 assert.ok(done.includes('검토 필요')); assert.ok(!done.includes('확정 완료'));
 const approved=renderToStaticMarkup(React.createElement(ImageJobProgress,{job:{...job,status:'succeeded'},online:true,approved:true}));
 assert.ok(approved.includes('확정 완료')); assert.ok(!approved.includes('aria-current'));
});
test('failed and uncertain jobs never report successful generation or review',()=>{
 for(const status of ['failed','unknown']) {
  const html=render({status,started_at:job.created_at,finished_at:job.created_at});
  assert.ok(html.includes('data-state="interrupted"'));
  assert.ok(!html.includes('검토 필요')); assert.ok(!html.includes('생성 완료'));
 }
});

const {ImageReviewPanel}=require('../components/image-review-panel.tsx');
const character={id:'hana',name:'하나',facts:'7살',proposed:'단발',appearance:'노란 우비',scene_ids:'1',image_prompt:'정면'};
const panel=(patch={})=>renderToStaticMarkup(React.createElement(ImageReviewPanel,{imageId:'image',version:1,character,reviews:[],configured:false,online:true,refresh:async()=>{},...patch}));
test('review absence leaves human review available without paid action',()=>{
 const html=panel();assert.ok(html.includes('직접 확인한 뒤 확정'));assert.ok(!html.includes('>AI 검수 요청<'));
});
test('review is scoped to selected image and changed settings require new review',()=>{
 const reviews=[{id:'r',image_id:'image',name:'검수자',agent_ref:'agent:test:1',character:{...character,appearance:'초록 우비'},status:'succeeded',result:'우비 색상을 확인하세요',created_at:job.created_at,finished_at:job.created_at}];
 const html=panel({reviews,configured:true});assert.ok(html.includes('검수 이후 캐릭터 설정을 변경'));assert.ok(html.includes('우비 색상을 확인하세요'));
 assert.ok(!panel({reviews,imageId:'other'}).includes('우비 색상을 확인하세요'));
});

const {AgentIcon}=require('../components/ui.tsx');
const {AgentIconPicker}=require('../components/agent-icon-picker.tsx');
const {agentIcons}=require('../lib/agent-icons.ts');
test('agent icon defaults to a compact display with optional change and shared help',()=>{
 const html=renderToStaticMarkup(React.createElement(AgentIconPicker,{value:'pen',onChange:()=>{}}));
 assert.equal((html.match(/type="radio"/g)||[]).length,0);
 assert.ok(html.includes('아이콘 변경'));
 assert.ok(html.includes('help-trigger--annotation'));
 assert.ok(html.includes('data-agent-icon="pen"'));
 const initial=renderToStaticMarkup(React.createElement(AgentIconPicker,{onChange:()=>{}}));
 assert.ok(initial.includes('로봇 · 기본 아이콘'));
 assert.equal(agentIcons.length,12);
 assert.ok(html.includes('AI에게 전달되지 않습니다'));
 const fallback=renderToStaticMarkup(React.createElement(AgentIcon,{icon:'unknown'}));
 assert.ok(fallback.includes('data-agent-icon="bot"'));
 const chosen=renderToStaticMarkup(React.createElement(AgentIcon,{icon:'shield'}));
 assert.ok(chosen.includes('data-agent-icon="shield"'));
});
