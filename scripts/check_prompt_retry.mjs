import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const source=await readFile(new URL('../static/app.js',import.meta.url),'utf8');
assert.match(source,/async function start\([^)]*source_prompt=null\)/,
  'start must accept a saved source prompt');
assert.match(source,/source_prompt,\.\.\.image_options/,
  'new jobs must send source_prompt to the API');
assert.match(source,/source_prompt:j\.input\.source_prompt\?\?null/,
  'retry branches must preserve the saved source prompt');
console.log('Prompt retry checks passed: source_prompt is retained for new jobs and retries.');
