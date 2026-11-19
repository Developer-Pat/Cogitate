"""The trash package's own tests.

WHAT IS WORTH TESTING HERE, and why each one is here rather than left to the API
suite: the trash is the one place in the app that destroys things, so its
GUARDS are the subject — the containment rule, the refusal to restore what has no
way back — together with the two properties the design exists for: one shelf's
action never reaches another, and nothing in the trash is invisible.
"""
