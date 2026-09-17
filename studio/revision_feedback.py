"""Interpret only Studio's exact historical empty revision templates."""
import re

_EMPTY_TEMPLATES=(
    r'Director requests a revision to ([a-zA-Z0-9_-]+):\s*\. Preserve all other shots and canonical identities unless the requested change requires continuity updates\. Preserve stable IDs\.',
    r'Revise shot ([a-zA-Z0-9_-]+):\s*\. Preserve all other shots in this chapter and all shared canon IDs and facts\.',
)


def canonical_feedback(feedback,shot_id):
    for template in _EMPTY_TEMPLATES:
        match=re.fullmatch(template,feedback)
        if match:
            return (f'The generation request targeted {match[1]}; this source is {shot_id}. '
                'No additional user-authored revision constraint was supplied: the user expects autonomous generation. '
                'Validate the saved candidate as authored against its supplied exact states and timed beats. '
                'An empty optional feedback field or a different source Shot is not a source conflict and does not require user clarification. '
                'Do not invent a missing creative instruction or change this source during validation. '
                'Preserve canonical identities, stable IDs and all supported source facts; report actual state/timing contradictions normally.')
    return feedback
