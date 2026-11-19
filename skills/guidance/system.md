# System Health — Guidance Skill

## Classification
Requests about system status, diagnostics, and introspection.

## Trigger keywords
health, diagnostic, status, introspection, self-diagnosis, self diagnosis,
are you OK, why did you stop, what happened, how are you, system check

## Instructions

### For "health check" requests (health, status, system check)
1. Use the macro-manager tool directly
2. Call macro-manager(action=read, domain=system)
3. Report the system health status to the user

### For "self diagnosis" requests (introspection, self-diagnosis, why did you stop)
1. Use the macro-manager tool directly
2. Call macro-manager(action=list, domain=meta-topic) to verify system state
3. Check your own checked-out tools using sequential-thinking
4. Report findings: "I am operational. [tool count] tools available."

### For "are you OK" requests (how are you, you OK, what happened)
1. Acknowledge the user's concern
2. Briefly state that you are operational
3. Ask if they want to continue with the previous task
