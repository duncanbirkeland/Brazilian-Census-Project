import json
import re
import time
import unicodedata
from typing import Any, Dict, List, Optional

import requests

BASE_AGREGADOS = "https://servicodados.ibge.gov.br/api/v3/agregados"
META_URL = "https://servicodados.ibge.gov.br/api/v3/agregados/{id}/metadados"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# ============================
# HTTP + normalization helpers
# ============================

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

WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)

def tokens(s: str) -> List[str]:
    return WORD_RE.findall(s)

# ============================
# Prefix matching (supports phrases)
# ============================

def phrase_prefix_match(phrase: str, toks: List[str]) -> bool:
    p = norm(phrase)
    if not p:
        return False

    p_toks = tokens(p)
    if not p_toks:
        return False

    if len(p_toks) == 1:
        pref = p_toks[0]
        return any(t.startswith(pref) for t in toks)

    n = len(p_toks)
    for i in range(0, len(toks) - n + 1):
        ok = True
        for j in range(n):
            if not toks[i + j].startswith(p_toks[j]):
                ok = False
                break
        if ok:
            return True

    return False

def any_prefix_match(prefixes: List[str], toks: List[str]) -> bool:
    for p in prefixes:
        if phrase_prefix_match(p, toks):
            return True
    return False

# ============================
# Discover Censo 2022 tables
# ============================

def discover_tables_2022_censo() -> List[Dict[str, Any]]:
    grouped = fetch_json(BASE_AGREGADOS, params={"periodo": 2022})
    results: List[Dict[str, Any]] = []

    for group in grouped:
        group_name = group.get("nome", "")
        if "censo demografico" not in norm(group_name):
            continue

        for ag in (group.get("agregados") or []):
            results.append(
                {
                    "id": str(ag["id"]),
                    "table_name": ag.get("nome") or "",
                    "group_name": group_name,
                }
            )

    dedup = {t["id"]: t for t in results}
    return sorted(dedup.values(), key=lambda x: int(x["id"]))

# ============================
# Tight category rules (prefix-based)
# ============================

CATEGORY_RULES: Dict[str, List[str]] = {
    "fertility": [
        "fecund",
        "fertilid",
        "gravidez",
        "gestac",
        "parto",
        "natalid",
        "maternid",
        "filhos",
    ],
    "religion": ["religia", "credo", "culto"],
    "literacy": ["alfabetiz", "leitur", "escrit"],
    "indigenous": ["indig", "quilomb", "aldei", "terra indig"],
    "households": ["domicil", "moradi", "habitac", "famil", "favel", "comod"],
    "population": [
        "populac",
        "pesso",
        "sex",
        "idad",
        "cor",
        "rac",
        "nacionalid",
        "naturalid",
        "migrac",
        "estrange",
        "obit",
        "falec",
    ],
    "sanitation": ["agu", "esgot", "sanitar", "lix", "drenag"],
    "education": ["educac", "escolar", "ensin", "instruc", "curs", "formac"],
    "work_income": ["ocupac", "empreg", "trabalh", "rend", "salari"],
    "marriage_family": ["estado civil", "casament", "divorc", "uniao", "conjugal"],
    "disability_health": ["deficien", "pcd", "autism", "ceg", "surd", "limitac", "dificuldad", "saud"],
}

ALL_CATEGORIES = list(CATEGORY_RULES.keys()) + ["miscellaneous"]

# ============================
# Categorization logic
# ============================

def categorize_text(text: str) -> List[str]:
    blob = norm(text)
    if not blob:
        return []
    toks = tokens(blob)

    matched: List[str] = []
    for cat, keywords in CATEGORY_RULES.items():
        if any_prefix_match(keywords, toks):
            matched.append(cat)
    return matched

def all_variables_indigenous(variables: List[Dict[str, Any]]) -> bool:
    if not variables:
        return False

    indig_kws = CATEGORY_RULES["indigenous"]
    for v in variables:
        name = norm(v.get("nome"))
        if not any_prefix_match(indig_kws, tokens(name)):
            return False
    return True

def _member_id(cat: Dict[str, Any]) -> Optional[str]:
    """
    Some payloads may have int ids; normalize to str.
    """
    cid = cat.get("id")
    if cid is None:
        return None
    return str(cid)

def _classification_id(c: Dict[str, Any]) -> Optional[str]:
    """
    Classification (dimension) id from meta['classificacoes'][...]['id'].
    Normalize to str.
    """
    cid = c.get("id")
    if cid is None:
        return None
    return str(cid)

# ============================
# Build catalog (NO primary category)
# ============================

def build_catalog(table_list: List[Dict[str, Any]], sleep_s: float = 0.2) -> Dict[str, Any]:
    catalog: Dict[str, Any] = {
        "source": "IBGE Agregados API",
        "periodo": 2022,
        "tables_found": len(table_list),
        "categories": {cat: [] for cat in ALL_CATEGORIES},
        "tables": {},
    }

    for t in table_list:
        meta = fetch_json(META_URL.format(id=t["id"]))
        classificacoes = meta.get("classificacoes") or []
        variaveis = meta.get("variaveis") or []

        # Scan all classification names + table name
        texts_to_scan: List[str] = []
        for c in classificacoes:
            if c.get("nome"):
                texts_to_scan.append(c["nome"])
        if t.get("table_name"):
            texts_to_scan.append(t["table_name"])

        # Collect ALL categories that match ANY scanned text
        matched_set = set()
        for txt in texts_to_scan:
            for cat in categorize_text(txt):
                matched_set.add(cat)

        # Indigenous override
        if all_variables_indigenous(variaveis):
            matched_set.add("indigenous")

        matched_categories = sorted(matched_set) or ["miscellaneous"]

        for cat in matched_categories:
            catalog["categories"].setdefault(cat, []).append(t["id"])

        # ✅ NEW: store classification (dimension) ID per demographic name
        classification_ids: Dict[str, str] = {}
        for c in classificacoes:
            cname = c.get("nome")
            cid = _classification_id(c)
            if cname and cid:
                classification_ids[cname] = cid

        # ✅ classification members: include member ID + name
        classification_members: Dict[str, List[Dict[str, Optional[str]]]] = {}
        for c in classificacoes:
            cname = c.get("nome")
            if not cname:
                continue

            members: List[Dict[str, Optional[str]]] = []
            for cat in (c.get("categorias") or []):
                mname = cat.get("nome")
                mid = _member_id(cat)
                if not mname:
                    continue
                members.append(
                    {
                        "id": mid,   # member/category id (e.g. 1140)
                        "name": mname,
                    }
                )

            classification_members[cname] = members

        table_payload = {
            "table_name": t["table_name"],
            "group_name": t["group_name"],
            "categories": matched_categories,
            "demographics": [c.get("nome") for c in classificacoes if c.get("nome")],
            "variables": [
                {
                    "variable_id": v.get("id"),
                    "variable_name": v.get("nome"),
                    "unit": v.get("unidade"),
                    "decimals": v.get("decimais"),
                }
                for v in variaveis
            ],

            # ✅ NEW: demographic name -> classification (dimension) id for /c{ID}/{member}
            "classification_ids": classification_ids,

            "classification_members": classification_members,
        }

        catalog["tables"][t["id"]] = table_payload
        time.sleep(sleep_s)

    for cat, ids in catalog["categories"].items():
        catalog["categories"][cat] = sorted(ids, key=lambda x: int(x))

    return catalog

# ============================
# Main
# ============================

if __name__ == "__main__":
    tables = discover_tables_2022_censo()
    print("Total Censo Demográfico tables found:", len(tables))

    catalog = build_catalog(tables)

    print("\nTables per category (multi-label):")
    counts = [(cat, len(ids)) for cat, ids in catalog["categories"].items()]
    counts.sort(key=lambda x: x[1], reverse=True)
    for cat, n in counts:
        print(f" {cat}: {n}")

    out_path = "sidra_catalog_2022_api_multi_category_prefix.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"\nSaved -> {out_path}")