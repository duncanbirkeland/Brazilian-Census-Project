import json
import time
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

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


CATEGORY_RULES: Dict[str, List[str]] = {
    "religion": ["religiao", "religião"],
    "indigenous": ["quilombola", "quilombolas", "indígena", "indigena", "indígenas", "indegina"],
    "households": [
        "domicilio", "domicílio", "moradia", "familia", "família", "arranjo",
        "agua", "água", "esgoto", "lixo", "energia", "internet", "telefone", "banheiro",
        "aluguel", "propriedade", "adensamento", "comodo", "cômodo"
    ],
    "population": [
        "populacao", "população", "pessoa", "morador", "resident",
        "sexo", "idade", "faixa etaria", "cor", "raca", "raça",
        "nacionalidade", "naturalidade", "migr"
    ],
    "education": [
        "educacao", "educação", "escola", "escolar", "alfabet", "analfabet",
        "frequenta", "ensino", "fundamental", "medio", "médio", "superior",
        "instrucao", "instrução"
    ],
    "work_income": [
        "ocupadas", "trabalho", "ocupacao", "trabalharam", "trabalhos", "rendimento"
    ],
    "marriage_family": [
        "estado civil", "casad", "solteir", "divorci", "viuv", "uniao", "união",
        "conjuge", "cônjuge", "parentesco", "composicao familiar", "familias"
    ],
    "disability_health": [
        "deficien", "deficiência", "pcd", "autismo", "cego", "surdo",
        "dificuldade", "limitacao", "limitação", "saude", "saúde"
    ],
}

CATEGORY_PRIORITY: List[str] = [
    "marriage_family",
    "disability_health",
    "religion",
    "education",
    "work_income",
    "households",
    "indigenous",
    "population"
]


def table_text_blob(table_name: Optional[str], variaveis: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    if table_name:
        parts.append(table_name)
    for v in variaveis or []:
        if v.get("nome"):
            parts.append(str(v["nome"]))
    return norm(" | ".join(parts))


def categorize_table(
    table_name: Optional[str],
    variaveis: List[Dict[str, Any]],
) -> Tuple[str, List[str]]:
    blob = table_text_blob(table_name, variaveis)

    matched: List[str] = []
    for cat, keywords in CATEGORY_RULES.items():
        for kw in keywords:
            if norm(kw) in blob:
                matched.append(cat)
                break

    if not matched:
        return "miscellaneous", []

    for cat in CATEGORY_PRIORITY:
        if cat in matched:
            return cat, matched

    return matched[0], matched


# ============================
# Indigenous override helpers
# ============================

INDIGENOUS_KWS = [norm(k) for k in CATEGORY_RULES["indigenous"]]


def variable_mentions_indigenous(v: Dict[str, Any]) -> bool:
    name = norm(v.get("nome") or "")
    return bool(name) and any(kw in name for kw in INDIGENOUS_KWS)


def all_variables_indigenous(variaveis: List[Dict[str, Any]]) -> bool:
    return bool(variaveis) and all(variable_mentions_indigenous(v) for v in variaveis)


def build_catalog(table_list: List[Dict[str, Any]], sleep_s: float = 0.2) -> Dict[str, Any]:
    all_categories = list(CATEGORY_RULES.keys()) + ["miscellaneous"]

    catalog: Dict[str, Any] = {
        "source": "IBGE Agregados API",
        "periodo": 2022,
        "tables_found": len(table_list),
        "categories": {cat: [] for cat in all_categories},
        "tables": {}
    }

    for t in table_list:
        meta = fetch_json(META_URL.format(id=t["id"]))

        classificacoes = meta.get("classificacoes", []) or []
        variaveis = meta.get("variaveis", []) or []

        primary_cat, matched_cats = categorize_table(
            t.get("table_name"),
            variaveis
        )

        # ✅ FORCE indigenous if all variables reference indigenous
        if all_variables_indigenous(variaveis):
            primary_cat = "indigenous"
            if "indigenous" not in matched_cats:
                matched_cats = ["indigenous"] + matched_cats

        table_payload = {
            "table_name": t["table_name"],
            "group_name": t["group_name"],
            "primary_category": primary_cat,
            "matched_categories": matched_cats,

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

        catalog["tables"][t["id"]] = table_payload
        catalog["categories"].setdefault(primary_cat, []).append(t["id"])

        time.sleep(sleep_s)

    return catalog


if __name__ == "__main__":
    tables = discover_tables_2022_censo()
    print("Total Censo Demográfico tables found:", len(tables))

    catalog = build_catalog(tables)

    print("\nTables per PRIMARY category:")
    counts = [(cat, len(ids)) for cat, ids in catalog["categories"].items()]
    counts.sort(key=lambda x: x[1], reverse=True)
    for cat, n in counts:
        print(f"  {cat}: {n}")

    with open("sidra_catalog_2022_api_only.json", "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print("\nSaved -> sidra_catalog_2022_api_only.json")
