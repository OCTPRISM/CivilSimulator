#!/usr/bin/env python3
"""
Hero Character Compiler — iteration 0.1 for wuxia_wanderer (散修剑客).

This is the LONG-RUN refinement entry point. Re-run anytime during the 6-month
polish cycle; it bumps manifest iteration, records notes, and validates assets.

Future iterations will:
  - Import Blender/MakeHuman exports into public/models/characters/hero/wuxia_wanderer/
  - Bake LODs, run quality gates, emit CompiledCharacterManifest

Today: manifest + policy enforcement only (R3F hero route, no batch GLB).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "frontend/public/models/characters/hero/wuxia_wanderer/manifest.json"
HERO_COMPONENT = ROOT / "frontend/src/components/hero/HeroWuxiaWanderer.tsx"


def main() -> None:
    if not HERO_COMPONENT.exists():
        raise SystemExit(f"Missing hero component: {HERO_COMPONENT}")

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    data["iteration"] = int(data.get("iteration", 0)) + 1
    data["last_compiled"] = date.today().isoformat()

    log = data.setdefault("iteration_log", [])
    log.append({
        "iteration": data["iteration"],
        "date": data["last_compiled"],
        "notes": f"compile_wuxia_wanderer.py run — R3F hero v{data.get('generator_version', '?')}",
    })

    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"hero wuxia_wanderer iteration {data['iteration']} → {MANIFEST.relative_to(ROOT)}")
    print("render_path:", data.get("render_path"))
    print("policy: batch GLB disabled for this role until quality_gates pass")


if __name__ == "__main__":
    main()
