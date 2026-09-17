import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

// The repo has no "type":"module", so load the browser ES module through a data URL.
const source = await readFile(new URL('../static/asset-groups.js', import.meta.url), 'utf8');
const {renderAssetGroups} = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));

// --- Test fixtures / helpers ----------------------------------------------
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// renderEntity returns "trusted card HTML" (parent-supplied, not escaped by us).
const renderEntity = id => `<article class="card" data-entity="${id}">${id}</article>`;
const names = new Map([
  ['p1','主角'],
  ['p2','場景'],
  ['l1','道具A'],
  ['l2','道具B'],
  ['l3','道具C'],
  ['u1','未分配1'],
  ['u2','未分配2'],
]);
const nameFor = id => names.get(id) ?? id;

const groups = {
  public_ids: ['p1','p2'],
  chapters: [
    {
      id:'c1', title:'Chapter <One>',
      scenes: [
        { id:'s1', title:'Scene <One>', entity_ids:['l1'], public_ids:['p1','p2'] },
        { id:'s2', title:'Scene Two', entity_ids:['l2','l3'], public_ids:['p2'] },
      ],
    },
  ],
  unassigned_ids: ['u1','u2'],
};

// --- 1. Public cards rendered exactly once ---------------------------------
const html = renderAssetGroups(groups, {renderEntity, esc, nameFor});

// Each public id appears exactly once as a card across the whole document.
for (const id of ['p1','p2']) {
  const count = html.split(`data-entity="${id}"`).length - 1;
  assert.equal(count, 1, `public card ${id} must appear exactly once, found ${count}`);
}
// Public section heading, id and explanatory text.
assert.match(html, /id="public-assets"/);
assert.match(html, /公共資產/);
assert.match(html, /共用身份/);

// --- 2. Local reuse across two scenes --------------------------------------
// l1 is used by scene s1 only; l2 and l3 by scene s2.
assert.equal(html.split('data-entity="l1"').length - 1, 1, 'l1 local card once');
assert.equal(html.split('data-entity="l2"').length - 1, 1, 'l2 local card once');
assert.equal(html.split('data-entity="l3"').length - 1, 1, 'l3 local card once');

// Shared public p2 is referenced by BOTH scenes, yet carded only in the public
// section (already asserted once above). It must appear as a name in each scene.
const p2Name = nameFor('p2');
const sharedBlocks = html.split('使用公共資產').length - 1;
assert.equal(sharedBlocks, 2, 'both scenes list 使用公共資產');

// Scene s1 lists both public assets by name; s2 lists only p2 (not p1).
const s1Start = html.indexOf('Scene &lt;One&gt;');
const s2Start = html.indexOf('Scene Two');
const s1Block = html.slice(s1Start, s2Start);
const s2Block = html.slice(s2Start, html.indexOf('</details>', s2Start));
assert.match(s1Block, new RegExp(p2Name));   // p2 by name
assert.match(s1Block, /主角/);               // p1 by name
// s2 references only p2 by name, never p1 (p1 is not in s2.public_ids).
assert.match(s2Block, new RegExp(p2Name));
assert.doesNotMatch(s2Block, /主角/);

// --- 3. Hierarchy + escaping ------------------------------------------------
// Chapter <details> is expanded (open), scenes nested and collapsed (no open).
assert.match(html, /<details open><summary>章節 · Chapter &lt;One&gt; · 2 個場景/);
// Scene summaries escaped.
assert.match(html, /<summary>場景 · Scene &lt;One&gt; · 本場資產 1/);
assert.match(html, /<summary>場景 · Scene Two · 本場資產 2/);
// Escaped chapter title must NOT appear raw.
assert.doesNotMatch(html, /<summary>章節 · Chapter <One>/);
// Public names escaped in scene lists (no raw < in the names here, but structure holds).

// --- 4. Counts --------------------------------------------------------------
assert.match(html, /2 項共用/);          // public count
assert.match(html, /本場資產 1/);          // scene s1 local count
assert.match(html, /本場資產 2/);          // scene s2 local count

// --- 5. Unassigned rendered when present ------------------------------------
assert.match(html, /待分配資產/);
assert.equal(html.split('data-entity="u1"').length - 1, 1);
assert.equal(html.split('data-entity="u2"').length - 1, 1);
assert.match(html, /2 項/);

// --- 6. Empty unassigned -> section omitted ---------------------------------
const noUn = renderAssetGroups({
  public_ids:['p1'],
  chapters:[{id:'c', title:'C', scenes:[{id:'s', title:'S', entity_ids:[], public_ids:[]}]}],
  unassigned_ids:[],
}, {renderEntity, esc, nameFor});
assert.doesNotMatch(noUn, /待分配資產/);
// Empty scene still renders with a placeholder and count 0.
assert.match(noUn, /本場資產 0/);
assert.match(noUn, /此場景無本場資產/);
// Only one public card.
assert.equal(noUn.split('data-entity="p1"').length - 1, 1);

console.log('Asset groups checks passed: public cards once, local reuse across two scenes, escaped hierarchy, counts, unassigned present and empty-unassigned omission.');
