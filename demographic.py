import json
import time
import unicodedata
from typing import Any, Dict, List, Optional

import requests

BASE_AGREGADOS = "https://servicodados.ibge.gov.br/api/v3/agregados"
META_URL = "https://servicodados.ibge.gov.br/api/v3/agregados/{id}/metadados"

HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_json(url: str, params: Optional[dict] = None) -> Any:
    r = requests.get(url, headers=HEADERS, params=params, timeout=60)
    r.raise_for_status()
    return r.json()

def norm(s: Optional[str]) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.lower().split())

def sort_key(item):
    return int(item["id"])

def discover_tables_2022_censo() -> List[Dict[str, Any]]:
    """
    Discover ALL tables from Censo Demográfico (periodo=2022).
    No thematic filtering.
    """
    grouped = fetch_json(BASE_AGREGADOS, params={"periodo": 2022})
    results: List[Dict[str, Any]] = []

    for group in grouped:
        group_name = group.get("nome", "")
        if "censo demografico" not in norm(group_name):
            continue

        for ag in (group.get("agregados") or []):
            results.append({
                "id": str(ag["id"]),
                "table_name": ag.get("nome"),
                "group_name": group_name,
            })

    dedup = {t["id"]: t for t in results}
    results = list(dedup.values())

    results.sort(key=sort_key)

    return results

def build_catalog(table_list: List[Dict[str, Any]], sleep_s: float = 0.2) -> Dict[str, Any]:
    catalog = {
        "source": "IBGE Agregados API",
        "periodo": 2022,
        "tables_found": len(table_list),
        "tables": {}
    }

    for t in table_list:
        meta = fetch_json(META_URL.format(id=t["id"]))

        classificacoes = meta.get("classificacoes", []) or []
        variaveis = meta.get("variaveis", []) or []

        catalog["tables"][t["id"]] = {
            "table_name": t["table_name"],
            "group_name": t["group_name"],

            "demographics": [c.get("nome") for c in classificacoes if c.get("nome")],

            "variables": [
                {
                    "variable_id": v.get("id"),
                    "variable_name": v.get("nome"),
                    "unit": v.get("unidade"),
                    "decimals": v.get("decimais"),
                    "demographics": [c.get("nome") for c in classificacoes if c.get("nome")]
                }
                for v in variaveis
            ],

            "classification_members": {
                c.get("nome"): [
                    cat.get("nome")
                    for cat in (c.get("categorias") or [])
                    if cat.get("nome")
                ]
                for c in classificacoes
                if c.get("nome")
            }
        }

        time.sleep(sleep_s)

    return catalog

if __name__ == "__main__":
    tables = discover_tables_2022_censo()
    print("Total Censo Demográfico tables found:", len(tables))

    tables = tables[:200]
    print("Cataloging first 50 tables:", [t["id"] for t in tables])

    catalog = build_catalog(tables)

    with open("sidr a_catalog_2022_api_only.json", "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print("Saved -> sidra_catalog_2022_api_only.json")
