import assert from 'node:assert/strict';
import {groupAssetVersions} from '../static/asset-versions.js';
const rows=[{id:'a',target_id:'stairs',created:'1',status:'pending'},{id:'b',target_id:'stairs',created:'2',status:'pending'},{id:'c',target_id:'stairs',created:'3',status:'rejected'},{id:'d',target_id:'person',created:'4',status:'approved'}];
const review=groupAssetVersions(rows,{reviewOnly:true});assert.equal(review.length,1);assert.equal(review[0].primary.id,'b');assert.equal(review[0].versions.length,3);
assert.equal(groupAssetVersions(rows).length,2);assert.equal(rows.length,4);
console.log('One card per target; newest pending version selected; rejected versions retained for explicit deletion.');

// Older pending/stale versions do not return to the queue after a newer adoption.
const adopted=[...rows,{id:'chosen',target_id:'stairs',created:'4',status:'approved'}];
const before=JSON.stringify(adopted);
assert.equal(groupAssetVersions(adopted,{reviewOnly:true}).length,0);
assert.equal(groupAssetVersions(adopted).find(g=>g.primary.target_id==='stairs').versions.length,4);
const stale=adopted.map(a=>a.id==='b'?{...a,status:'stale'}:a);
assert.equal(groupAssetVersions(stale,{reviewOnly:true}).length,0);
// A new candidate and an unrelated target remain visible.
const newer=[...adopted,{id:'new',target_id:'stairs',created:'5',status:'pending'},{id:'other',target_id:'prop',created:'2',status:'pending'}];
assert.deepEqual(groupAssetVersions(newer,{reviewOnly:true}).map(g=>g.primary.id),['new','other']);
// A stale adoption is not reviewable; independently current pending work remains.
const invalid=adopted.map(a=>a.id==='chosen'?{...a,status:'stale'}:a);
assert.equal(groupAssetVersions(invalid,{reviewOnly:true})[0].primary.id,'b');
const outdated=[1,2,3].map(n=>({id:'old'+n,target_id:'frame'+n,created:'1',status:'stale',note:'An approved reference was replaced.'}));
assert.equal(groupAssetVersions(outdated,{reviewOnly:true}).length,0);
assert.equal(groupAssetVersions(outdated).length,3);
assert.deepEqual(groupAssetVersions([...outdated,{id:'replacement',target_id:'frame1',created:'2',status:'pending'}],{reviewOnly:true}).map(g=>g.primary.id),['replacement']);
// A rejected newer attempt doesn't resurrect candidates older than the approval.
assert.equal(groupAssetVersions([...adopted,{id:'no',target_id:'stairs',created:'5',status:'rejected'}],{reviewOnly:true}).length,0);
assert.equal(JSON.stringify(adopted),before);
const {needsAssetReview}=await import('../static/asset-versions.js');
assert.equal(needsAssetReview(adopted[0],adopted),false);
assert.equal(needsAssetReview(newer.find(a=>a.id==='new'),newer),true);
assert.equal(needsAssetReview(outdated[0],outdated),false);
console.log('Newer approval suppresses older pending/stale reminders; newer candidates and unrelated targets remain; histories unchanged.');
