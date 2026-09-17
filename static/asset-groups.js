// Bounded asset-group renderer. Pure ES module: no DOM, no fetch, no global state.
//
// The parent (app.js) owns the data model, asset classification (which IDs are
// public/shared versus scene-local), voice-vs-image card rendering and the
// integration point. It hands this module a prepared `groups` object plus three
// callbacks:
//
//   renderEntity(id) -> trusted card HTML  (an <article class="card"> …, parent-supplied)
//   esc(value)       -> HTML-escaped string
//   nameFor(id)      -> display name for an asset/entity id
//
// groups contract:
//   public_ids: string[]
//   chapters: [{ id, title, scenes: [{ id, title, entity_ids: string[] (local only),
//                                      public_ids: string[] }] }]
//   unassigned_ids: string[]
//
// Public assets are rendered once, up front, under a shared-identity section
// (id="public-assets"). Scene-local assets are rendered per scene through
// renderEntity; shared (public) assets are referenced by name inside each scene
// without duplicating their cards. Unassigned assets are listed last, only when
// present. Titles and names are escaped; card HTML is trusted (supplied by parent).

function sceneLocal(scene) {
  const seen = new Set();
  return (scene.entity_ids || []).filter(id => {
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}

function scenePublic(scene) {
  const seen = new Set();
  return (scene.public_ids || []).filter(id => {
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}

export function renderAssetGroups(groups, { renderEntity, esc, nameFor }) {
  const g = groups || {};
  const publicIds = g.public_ids || [];
  const chapters = g.chapters || [];
  const unassignedIds = g.unassigned_ids || [];

  // --- Public / shared-identity section (rendered once) ---
  const publicCards = publicIds
    .map(id => renderEntity(id))
    .filter(Boolean)
    .join('');
  const publicSection = `<section class="panel" id="public-assets"><div class="panel-header"><h2>公共資產</h2><span class="muted">${publicIds.length} 項共用</span></div><p class="muted">以下資產為作品共用身份；需要它的 Scene 沿用同一份參考，不會逐場重製，也不代表每場都要出現。</p><div class="grid">${publicCards}</div></section>`;

  // --- Chapters / scenes ---
  const chapterHtml = chapters
    .map(ch => {
      const scenes = ch.scenes || [];
      const sceneHtml = scenes
        .map(scene => {
          const local = sceneLocal(scene);
          const pub = scenePublic(scene);
          // Shared assets are named here (not carded) so the public section stays canonical.
          const sharedNames = pub
            .map(id => nameFor(id))
            .map(n => `<li>${esc(n)}</li>`)
            .join('');
          const sharedNote = pub.length
            ? `<p class="muted"><strong>使用公共資產（${pub.length}）</strong></p><ul class="facts">${sharedNames}</ul>`
            : '';
          const localCards = local.map(id => renderEntity(id)).filter(Boolean).join('');
          const localNote = local.length
            ? `<div class="grid">${localCards}</div>`
            : `<p class="muted">此場景無本場資產。</p>`;
          return `<details><summary>場景 · ${esc(scene.title)} · 本場資產 ${local.length}</summary><div class="scene-asset-batch-action"><button type="button" data-action="scene-asset-batch" data-id="${esc(scene.id)}">批量製作所需資產</button></div>${sharedNote}${localNote}</details>`;
        })
        .join('');
      return `<details open><summary>章節 · ${esc(ch.title)} · ${scenes.length} 個場景</summary>${sceneHtml || '<p class="muted">此章節尚未有場景。</p>'}</details>`;
    })
    .join('');

  // --- Unassigned (only when present) ---
  const unassigned = unassignedIds.length
    ? `<section class="panel"><div class="panel-header"><h2>待分配資產</h2><span class="muted">${unassignedIds.length} 項</span></div><p class="muted">以下資產尚未歸入任何場景或公共身份；可於此檢視並指派。</p><div class="grid">${unassignedIds.map(id => renderEntity(id)).filter(Boolean).join('')}</div></section>`
    : '';

  return `<div class="asset-groups">${publicSection}${chapterHtml}${unassigned}</div>`;
}

export default renderAssetGroups;
