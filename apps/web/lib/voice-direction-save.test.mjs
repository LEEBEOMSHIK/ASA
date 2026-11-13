import test from 'node:test';
import assert from 'node:assert/strict';
import {retainUnsavedSpeakers} from './voice-direction-save.ts';
test('saving one character preserves other character and narrator drafts',()=>{
 const saved=[{id:'a',text:'saved A'},{id:'b',text:'old B'},{id:'narrator',text:'old N'}];
 const draft=[{id:'a',text:'submitted A'},{id:'b',text:'draft B'},{id:'narrator',text:'draft N'}];
 assert.deepEqual(retainUnsavedSpeakers(saved,draft,'a'),[saved[0],draft[1],draft[2]]);
 assert.equal(saved[1].text,'old B');
});
test('saving narrator keeps character draft and adopts newly returned speakers',()=>{
 const saved=[{id:'a',text:'old A'},{id:'narrator',text:'saved N'},{id:'new',text:'new'}];
 const draft=[{id:'a',text:'draft A'},{id:'narrator',text:'submitted N'}];
 assert.deepEqual(retainUnsavedSpeakers(saved,draft,'narrator'),[draft[0],saved[1],saved[2]]);
});
