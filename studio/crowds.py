"""Collective cast references are distinct from individual turnaround sheets."""

PLANNING = """
Classify canon by visual scope: kind=character for an individual, kind=crowd for a
collective cast such as neighbours, spectators or background extras. Do not turn
a crowd into one person's four-view sheet. Describe the group's age range,
wardrobe, distinctive member differences and shared condition without inventing
biographies. Keep named, speaking or recurring featured individuals as separate
characters when they need independent identity; do not duplicate them as extras.
A collective dialogue entry may link a crowd, but an individually attributed line
must retain its individual speaker. A crowd voice profile is a representative
voice, not automatic multi-speaker synthesis.
In each scene's first shot establish the crowd's visible count/density, zones and
recognizable members; retain them through subsequent shots unless movement, a cut
or story change explains the difference. Different scenes may require different
numbers. Record these decisions in blocking and continuity states, not just the
group's reusable identity. Preserve explicit source counts; do not invent an exact
canonical headcount when the source only describes an indefinite crowd.
"""

IMAGE = (
    'Create ONE ensemble reference image showing multiple distinct people together, '
    'with readable faces and full-body wardrobe on a simple neutral background. '
    'This is a group cast reference, NOT four views of one person, NOT repeated clones, '
    'and NOT a panel grid. Preserve specified age range, clothing, condition and '
    'distinctive member differences. Follow any explicitly fixed group membership; '
    'for an indefinite large crowd show a manageable representative ensemble, not an '
    'invented definitive roster. Scene-specific counts, positions, props and injuries '
    'are not universal group traits: do not combine separate scene events into this '
    'reference or apply one member\'s accessory/injury to everyone. '
    'Featured individual characters have their own references; do not invent copies '
    'of them inside the extras group. Preserve the project visual style.'
)

REFERENCE = (
    'Crowd references define a collective of multiple distinct people, not one '
    'character across angles. Retain member differences and wardrobe; never clone '
    'one face across the group. The reference ensemble is not a mandatory headcount '
    'or lineup: follow this Scene/Shot for visible number, blocking, state and action; '
    'keep them continuous within the scene. Do not duplicate separately referenced '
    'featured characters as extras.'
)

REVIEW = (
    'CROWD REFERENCE REVIEW: Check that this is a readable ensemble of distinct '
    'people, with source-consistent age range, wardrobe and group condition. '
    'Flag a single-person turnaround, cloned faces, contradictory membership, '
    'incorrect shared accessories/injuries or invented featured characters. '
    'A representative ensemble for an indefinite crowd need not show every person '
    'from a larger scene. Scene-only counts and staging are checked on that scene\'s '
    'keyframes, not imposed universally on this reference. Four-view framing does '
    'not apply. Return character_sheet=not_applicable and use overall verdict/issues.'
)
