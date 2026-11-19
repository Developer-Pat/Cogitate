# Macro Operations — Guidance Skill

## Classification
Requests about meta-topics, macro-sets, topic mappings, F-keys, M-keys.

## Trigger keywords
meta topic, meta-topic, metatopic, macro, macro-set, macro set,
f-key, fkey, m-key, mkey, topic mapping

## CRITICAL — You MUST Execute These Steps
Reading these instructions is NOT enough. You MUST call each tool as described.
Do NOT answer from memory or general knowledge. The actual system data is always
different from what you might guess. If the instructions say "Use macro-manager",
you MUST actually call it — do not just describe what you would do.

## Critical Rule — TRUST THE DATA
The topic_mappings returned by the system ARE the actual linked macro sets,
even if their names seem unrelated to the meta-topic name (e.g. "Provider Info Query"
under "Famous Equations"). Do NOT dismiss data as "placeholder" or "test data" —
the system only returns real, live data. If a mapping exists, it is intentional.

## Instructions

### For "list" requests (show, find, list, what are)
1. Use the macro-manager tool directly
2. If agent meta-topics: macro-manager(action=list, domain=meta-topic, namespace=agent)
3. If system meta-topics: macro-manager(action=list, domain=meta-topic, namespace=system)
4. If all meta-topics: macro-manager(action=list, domain=meta-topic)
5. If macro-sets: macro-manager(action=list, domain=macro-set)
6. If macros for a specific meta-topic:
   a. macro-manager(action=read, domain=meta-topic, id=<ID>)
   b. macro-manager(action=list, domain=macro-set)
   c. Cross-reference topic_mappings with macro-set topics
   d. macro-manager(action=read, domain=macro-set, id=<ID>)

### For "create" requests (create, make, new, add, design)
Designing macro sets and meta-topics IS part of your role. Do not decline.
1. Use the macro-manager tool directly
2. Read an existing macro set to see the full schema
3. Create: macro-manager(action=create, domain=macro-set, ...)
4. After creating, update the meta-topic's topic_mappings to link the new set
5. Verify by reading the created macro set back

### For "update" requests (update, change, modify, edit)
1. Use the macro-manager tool directly
2. Read the macro set first: macro-manager(action=read, domain=macro-set, id=<ID>)
3. Update: macro-manager(action=update, domain=macro-set, id=<ID>, ...)

### For "delete" requests (delete, remove)
1. Confirm with the user before deleting
2. Use the macro-manager tool directly
3. Delete: macro-manager(action=delete, domain=macro-set, id=<ID>)

### For "create" requests (create, make, new, add)
1. Use the macro-manager tool directly
2. Read an existing macro set to see full schema
3. Create: macro-manager(action=create, domain=macro-set, ...)
4. Verify by reading the created set

### For "update" requests (update, change, modify, edit)
1. Use the macro-manager tool directly
2. Read the macro set first: macro-manager(action=read, domain=macro-set, id=<ID>)
3. Update: macro-manager(action=update, domain=macro-set, id=<ID>, ...)

### For "delete" requests (delete, remove)
1. Confirm with the user before deleting
2. Use the macro-manager tool directly
3. Delete: macro-manager(action=delete, domain=macro-set, id=<ID>)
