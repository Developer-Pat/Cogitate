import sys
sys.path.insert(0, "backend")
from app.domain.tools.registry import init_default_registry
from app.domain.tools.capabilities import is_valid_capability

reg = init_default_registry()
t = reg.get("open-page")
print("registered:", t is not None)
print("capability:", t.capability, "| valid:", is_valid_capability(t.capability))
print("tool count:", len(reg._tools))
sch = t.arguments_schema
print("enum size:", len(sch["properties"]["page"]["enum"]))
print("description chars:", len(t.description))
print()
print("=== the description the model will actually see (first 12 lines):")
for l in t.description.splitlines()[:12]:
    print("   ", l)
print("    ...")
print()
from app.domain.tools.page_map import resolve_page

for probe in ["/settings", "/settings?tab=appearance", "messages", "Settings", "/wiki", "/nope"]:
    e, c = resolve_page(probe)
    hit = e.key if e else "NO MATCH"
    extra = f"  candidates: {[x.label for x in c][:3]}" if (not e and c) else ""
    print(f"  {probe!r:30} -> {hit}{extra}")
