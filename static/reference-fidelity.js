// Save this explicit director choice in the job's existing feedback/provenance.
export const HIGH_REFERENCE_FIDELITY = `[High reference preservation]
Preserve the selected references according to their assigned roles; make only the requested visual changes.
[/High reference preservation]`;

export function referenceFidelityFeedback(feedback, enabled) {
 const clean=String(feedback||'').replace(/\n?\[High reference preservation\][\s\S]*?\[\/High reference preservation\]/g,'').trim();
 return enabled ? [clean,HIGH_REFERENCE_FIDELITY].filter(Boolean).join('\n\n') : clean;
}
