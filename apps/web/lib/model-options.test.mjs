import test from 'node:test';
import assert from 'node:assert/strict';
import { sortModels } from './model-options.ts';
test('new generations precede old, full models precede lightweight and snapshots',()=>{
 const ids=['gpt-4.1','gpt-5-mini','gpt-5','gpt-5-2025-08-07','gpt-6.1-sol','gpt-image-2','gpt-6-sol'];
 assert.deepEqual(sortModels(ids.map(id=>({id,label:id}))).map(m=>m.id),['gpt-6.1-sol','gpt-6-sol','gpt-5','gpt-5-2025-08-07','gpt-5-mini','gpt-4.1','gpt-image-2']);
});
test('Claude uses numeric generation then opus sonnet haiku',()=>{
 const ids=['claude-haiku-4-5','claude-sonnet-4-6','claude-opus-4-6','claude-sonnet-5'];
 assert.deepEqual(sortModels(ids.map(id=>({id,label:id}))).map(m=>m.id),['claude-sonnet-5','claude-opus-4-6','claude-sonnet-4-6','claude-haiku-4-5']);
});
