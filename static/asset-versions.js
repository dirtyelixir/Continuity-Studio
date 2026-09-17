export function needsAssetReview(asset,versions){
 // Stale pixels cannot be made current by reviewing them again. They remain
 // available in version history and require a replacement, not approval.
 if(asset.status!=='pending')return false;
 // An adopted newer version settles older alternatives without rewriting
 // their history. A candidate made after that version still needs review.
 return !versions.some(a=>a.target_id===asset.target_id&&a.status==='approved'&&a.created>=asset.created);
}

export function groupAssetVersions(assets,{reviewOnly=false}={}){
 const groups=new Map();
 for(const asset of [...assets].sort((a,b)=>b.created.localeCompare(a.created))){
  if(!groups.has(asset.target_id))groups.set(asset.target_id,[]);
  groups.get(asset.target_id).push(asset);
 }
 return [...groups.values()].map(versions=>({versions,primary:reviewOnly?versions.find(a=>needsAssetReview(a,versions)):versions[0]})).filter(g=>g.primary);
}
