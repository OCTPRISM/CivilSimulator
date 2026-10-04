import asyncio
from app.labs.workspace import create_or_get_lab, lab_add_manual_events, lab_finance_simulate

async def demo():
    ws = create_or_get_lab(user_id="demo", lab_key="finance", civilization_key="ancient")
    await lab_add_manual_events(ws, [
        {"time": "T+4", "title": "边关战事", "kind": "war", "magnitude": -0.35},
        {"time": "T+12", "title": "开仓平粜", "kind": "policy", "magnitude": 0.28},
    ], use_llm_ner=False)
    out = await lab_finance_simulate(ws, mode="global", horizon=16, skip_llm=True)
    sim = out["simulation"]
    report = out["report"]
    inst = out["finance_lab"]["institutions"]

    print("=== INSTITUTION EVOLUTION (ancient/global) ===")
    for i in inst:
        print(f"  {i['name']}: influence={i['influence']} health={i['health']} capacity={i['capacity']}")
        tx0 = i.get("base_transmission", {})
        tx1 = i.get("transmission", {})
        changed = [k for k in tx0 if abs(tx0[k] - tx1.get(k, tx0[k])) > 0.001]
        if changed:
            print(f"    transmission drift: {', '.join(changed)}")

    print("\n=== AUDIT SAMPLE (step 0) ===")
    a0 = sim["audit_trail"][0]
    print("  equations:", len(a0.get("equations", [])))
    print("  context:", a0.get("context"))
    print("  inst deltas:", [x.get("name") for x in a0.get("institutions", [])[:2]])

    print("\n=== CONFIDENCE BANDS (last) ===")
    b = sim["confidence_bands"][-1]
    print(f"  p10={b['p10']} p50={b['p50']} p90={b['p90']}")

    print("\n=== REPORT STRUCTURE ===")
    print(f"  title: {report['title']}")
    print(f"  charts: {[c['title'] + '(' + c['type'] + ')' for c in report['charts']]}")
    print(f"  tables: {[t['title'] for t in report['tables']]}")
    print(f"  predictions: {len(report['predictions'])}")
    print(f"  event_impacts: {len(report['event_impacts'])}")
    print(f"  analysis sections ({len(report['analysis'])}):")
    for sec in report["analysis"]:
        body = sec["body"][:80].replace("\n", " ")
        print(f"    - {sec['heading']}: {body}...")

asyncio.run(demo())
