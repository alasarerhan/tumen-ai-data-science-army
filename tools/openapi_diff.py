"""OpenAPI şeması üret + frontend TS tipleri ile diff et.

Kanban 5.1, 5.2, 5.9. Uvicorn ayakta olmalı; yoksa hata verir.
Çalıştırma: python3 tools/openapi_diff.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path("/Users/erhanalasar/Desktop/ERHAN/AI_Agents/AI_Agents")
API_DIR = ROOT / "ai_data_science_team" / "apps" / "platform-api-app"
FRONTEND_API = ROOT / "ai_data_science_team" / "frontend" / "src" / "app" / "api"
OUT = ROOT / "ai_data_science_team" / "tests" / "contract"
OUT.mkdir(parents=True, exist_ok=True)


def fetch_openapi() -> dict | None:
    """Uvicorn 8010'dan OpenAPI JSON çek. Ayakta değilse None."""
    import httpx

    try:
        r = httpx.get("http://127.0.0.1:8010/openapi.json", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def fetch_openapi_from_main() -> dict | None:
    """Uvicorn ayakta değilse, platform_api.main'i doğrudan çağır."""
    import os
    import sys

    sys.path.insert(0, str(API_DIR))
    sys.path.insert(0, str(ROOT / "ai_data_science_team"))
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+psycopg://tumen:dev_local_password_change_me@localhost:5432/tumen_fresh",
    )
    try:
        from platform_api.main import create_app

        app = create_app()
        return app.openapi()
    except Exception as exc:
        print(f"create_app failed: {exc}")
        return None


def frontend_endpoints_from_ts() -> list[str]:
    """frontend/src/app/api/*.ts dosyalarındaki endpoint string'lerini çıkar."""
    eps = set()
    if not FRONTEND_API.exists():
        return []
    for f in FRONTEND_API.glob("*.ts"):
        if f.name.endswith(".test.ts"):
            continue
        text = f.read_text()
        # endpoint strings: "/v1/...", '/v1/...'
        for m in re.finditer(r'[`\'"](/v\d+/[^`\'"]+)[`\'"]', text):
            eps.add(m.group(1))
    return sorted(eps)


def main():
    print("=== OpenAPI ↔ Frontend TS diff ===")
    openapi = fetch_openapi()
    if openapi is None:
        print("Uvicorn ayakta değil, create_app ile deneniyor...")
        openapi = fetch_openapi_from_main()

    if openapi is None:
        print("OpenAPI alınamadı (uvicorn kapalı + create_app import başarısız)")
        print("Uvicorn'u başlatıp tekrar deneyin: bash tests/soak/run_soak.sh 60")
        return 1

    # OpenAPI'den path'leri çıkar
    paths = sorted(openapi.get("paths", {}).keys())

    # Frontend'ten endpoint'leri çıkar
    fe_eps = frontend_endpoints_from_ts()

    # OpenAPI yaz
    openapi_path = OUT / "openapi.json"
    openapi_path.write_text(json.dumps(openapi, indent=2))

    # Diff
    overlap = set(paths) & set(fe_eps)
    only_oas = sorted(set(paths) - set(fe_eps))
    only_fe = sorted(set(fe_eps) - set(paths))

    diff = {
        "oas_total": len(paths),
        "fe_total": len(fe_eps),
        "overlap": len(overlap),
        "only_in_openapi": only_oas[:10],
        "only_in_frontend": only_fe[:10],
        "drift_score": round(len(only_oas) / max(len(paths), 1), 4),
    }
    (OUT / "openapi_diff.json").write_text(json.dumps(diff, indent=2))

    # Markdown rapor
    md = OUT / "openapi_diff.md"
    md.write_text(f"""# OpenAPI ↔ Frontend TypeScript Diff

**Tarih:** {time.strftime("%Y-%m-%d")}
**OpenAPI paths:** {diff["oas_total"]}
**Frontend endpoints:** {diff["fe_total"]}
**Overlap:** {diff["overlap"]}
**Drift score:** {diff["drift_score"]} (lower is better)

## Only in OpenAPI (backend tanımlı, frontend kullanmıyor)

{chr(10).join(f"- `{p}`" for p in diff["only_in_openapi"]) or "_none_"}

## Only in Frontend (frontend çağırıyor, backend yok)

{chr(10).join(f"- `{p}`" for p in diff["only_in_frontend"]) or "_none_"}

## Kanıt

- OpenAPI: `tests/contract/openapi.json`
- Diff: `tests/contract/openapi_diff.json`
- Tool: `tools/openapi_diff.py`

---
Kanban: 5.1 + 5.2 + 5.9
""")
    print(f"OpenAPI: {diff['oas_total']} paths")
    print(f"Frontend: {diff['fe_total']} endpoints")
    print(f"Overlap: {diff['overlap']}")
    print(f"Drift score: {diff['drift_score']}")
    print(f"Output: {md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
