import json
import re
import time
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_AGREGADOS = "https://servicodados.ibge.gov.br/api/v3/agregados"
META_URL = "https://servicodados.ibge.gov.br/api/v3/agregados/{id}/metadados"

HEADERS = {"User-Agent": "Mozilla/5.0"}


# ============================
# HTTP client (retries + session)
# ============================

_SESSION = requests.Session()
_SESSION.headers.update(HEADERS)

_retry = Retry(
    total=5,
    connect=5,
    read=5,
    backoff_factor=0.6,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET"]),
    raise_on_status=False,
)
_adapter = HTTPAdapter(max_retries=_retry)
_SESSION.mount("https://", _adapter)
_SESSION.mount("http://", _adapter)


def fetch_json(url: str, params: Optional[dict] = None) -> Any:
    r = _SESSION.get(url, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


# ============================
# Normalization helpers
# ============================

def norm(s: Optional[str]) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.lower().split())


WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def tokens(s: str) -> List[str]:
    return WORD_RE.findall(s)


def any_prefix_match(prefixes: List[str], toks: List[str]) -> bool:
    for p in prefixes:
        p = norm(p)
        if not p:
            continue
        for t in toks:
            if t.startswith(p):
                return True
    return False


def count_prefix_matches(prefixes: List[str], toks: List[str]) -> int:
    """
    Counts how many prefixes are matched by any token (dedup by prefix).
    This is a simple, stable scoring primitive.
    """
    seen = set()
    for p in prefixes:
        pn = norm(p)
        if not pn or pn in seen:
            continue
        for t in toks:
            if t.startswith(pn):
                seen.add(pn)
                break
    return len(seen)


# ============================
# Discovery
# ============================

def sort_key(item: Dict[str, Any]) -> int:
    return int(item["id"])


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
                    "table_name": ag.get("nome"),
                    "group_name": group_name,
                }
            )

    dedup = {t["id"]: t for t in results}
    results = list(dedup.values())
    results.sort(key=sort_key)
    return results


# ============================
# Category rules (word search)
# ============================

CATEGORY_RULES: Dict[str, List[str]] = {
    "fertility": [
        "fertil", "fecund", "nasc",
        "parto", "filhos", "matern", "gravidez",
        "gestacao", "mulher",
        "femin", "mae",
    ],
    "religion": ["religi"],
    "literacy": ["alfabeti"],
    "indigenous": ["quilombola", "indig"],
    "households": [
        "domicil", "famil", "faces de quadras", "favel", "comodo",
    ],
    "population": [
        "populac", "pessoa", "resid",
        "sexo", "idade", "cor", "raca",
        "nacional", "naturali", "migr", "estrange", "faleci", "obito",
    ],
    "sanitation": [
        "agua", "sanita", "lixo",
    ],
    "education": [
        "educac", "escol", "medi", "superior",
        "instrucao", "ensino", "curso",
    ],
    "work_income": [
        "ocupa", "traba", "rendim", "salario",
    ],
    "marriage_family": [
        "estado", "divorci", "uniao", "conjug", "familia",
    ],
    "disability_health": [
        "deficien", "pcd", "autismo",
        "cego", "surdo", "dificuldade", "limitacao", "saude",
    ],
}

# single definition only (you had two)
CATEGORY_PRIORITY: List[str] = [
    "fertility",
    "marriage_family",
    "disability_health",
    "education",
    "work_income",
    "sanitation",
    "households",
    "indigenous",
    "religion",
    "literacy",
    "population",
]


# ============================
# Indigenous override helpers
# ============================

INDIGENOUS_KWS = [norm(k) for k in CATEGORY_RULES["indigenous"]]


def variable_mentions_indigenous(v: Dict[str, Any]) -> bool:
    name = norm(v.get("nome") or "")
    if not name:
        return False
    toks = tokens(name)
    return any_prefix_match(INDIGENOUS_KWS, toks)


def all_variables_indigenous(variaveis: List[Dict[str, Any]]) -> bool:
    return bool(variaveis) and all(variable_mentions_indigenous(v) for v in variaveis)


# ============================
# Topic classification (FIX)
# ============================

# Weights: what should define "topic"?
WEIGHTS = {
    "table_name": 3.0,      # strongest topic signal
    "variables": 2.0,       # strong topic signal
    "group_name": 1.0,      # weak topic signal
    "classifications": 0.5, # dimensions; only used as last-resort fallback
}


def score_categories_from_text(blob: str) -> Dict[str, int]:
    """
    Returns raw match counts per category for a given text blob.
    """
    b = norm(blob)
    if not b:
        return {cat: 0 for cat in CATEGORY_RULES.keys()}
    toks = tokens(b)
    return {cat: count_prefix_matches(kws, toks) for cat, kws in CATEGORY_RULES.items()}


def pick_best_category(weighted_scores: Dict[str, float]) -> Tuple[str, List[str]]:
    """
    Choose best category using priority for tie-breaks.
    """
    # all zero => miscellaneous
    if not weighted_scores or max(weighted_scores.values()) <= 0:
        return "miscellaneous", []

    max_score = max(weighted_scores.values())
    tied = [cat for cat, sc in weighted_scores.items() if sc == max_score]

    # tie-break by priority
    for cat in CATEGORY_PRIORITY:
        if cat in tied:
            return cat, tied

    return tied[0], tied


def categorize_table_topic(
    table_name: Optional[str],
    group_name: Optional[str],
    variables: List[Dict[str, Any]],
    classifications: List[Dict[str, Any]],
) -> Tuple[str, Dict[str, Any]]:
    """
    Classify the TABLE TOPIC (not its available breakdown dimensions).

    Uses weighted scoring from:
      - table_name (high)
      - variable names (high)
      - group_name (low)
    Ignores classifications by default (dimensions), but uses them only if
    everything else yields miscellaneous.
    """
    weighted: Dict[str, float] = {cat: 0.0 for cat in CATEGORY_RULES.keys()}
    debug: Dict[str, Any] = {
        "signals": {},
        "weights": WEIGHTS.copy(),
    }

    # 1) table_name
    tn = table_name or ""
    tn_scores = score_categories_from_text(tn)
    for cat, c in tn_scores.items():
        weighted[cat] += c * WEIGHTS["table_name"]
    debug["signals"]["table_name"] = {"text": tn, "raw_scores": tn_scores}

    # 2) variables (concatenate variable names)
    var_text = " ".join([v.get("nome") or "" for v in (variables or []) if (v.get("nome") or "").strip()])
    var_scores = score_categories_from_text(var_text)
    for cat, c in var_scores.items():
        weighted[cat] += c * WEIGHTS["variables"]
    debug["signals"]["variables"] = {"text": var_text[:5000], "raw_scores": var_scores}  # avoid huge debug

    # 3) group_name
    gn = group_name or ""
    gn_scores = score_categories_from_text(gn)
    for cat, c in gn_scores.items():
        weighted[cat] += c * WEIGHTS["group_name"]
    debug["signals"]["group_name"] = {"text": gn, "raw_scores": gn_scores}

    primary, tied = pick_best_category(weighted)
    debug["weighted_scores"] = weighted
    debug["tied_categories_at_max"] = tied

    # 4) last-resort fallback: classifications ONLY if still miscellaneous
    if primary == "miscellaneous" and classifications:
        cls_text = " ".join([c.get("nome") or "" for c in classifications if (c.get("nome") or "").strip()])
        cls_scores = score_categories_from_text(cls_text)
        for cat, c in cls_scores.items():
            weighted[cat] += c * WEIGHTS["classifications"]
        debug["signals"]["classifications_fallback"] = {"text": cls_text, "raw_scores": cls_scores}
        primary, tied = pick_best_category(weighted)
        debug["weighted_scores_after_classification_fallback"] = weighted
        debug["tied_categories_at_max_after_fallback"] = tied

    return primary, debug


# ============================
# Build catalog
# ============================

_META_CACHE: Dict[str, Any] = {}


def build_catalog(table_list: List[Dict[str, Any]], sleep_s: float = 0.2) -> Dict[str, Any]:
    all_categories = list(CATEGORY_RULES.keys()) + ["miscellaneous"]

    catalog: Dict[str, Any] = {
        "source": "IBGE Agregados API",
        "periodo": 2022,
        "tables_found": len(table_list),
        "categories": {cat: [] for cat in all_categories},
        "tables": {},
    }

    for t in table_list:
        tid = t["id"]

        if tid in _META_CACHE:
            meta = _META_CACHE[tid]
        else:
            meta = fetch_json(META_URL.format(id=tid))
            _META_CACHE[tid] = meta

        classificacoes = meta.get("classificacoes", []) or []
        variaveis = meta.get("variaveis", []) or []

        # ✅ classify TOPIC from table_name + variables + group_name (NOT from demographics)
        primary_cat, debug = categorize_table_topic(
            table_name=t.get("table_name"),
            group_name=t.get("group_name"),
            variables=variaveis,
            classifications=classificacoes,
        )

        matched_cats = debug.get("tied_categories_at_max", [])
        if primary_cat != "miscellaneous" and primary_cat not in matched_cats:
            matched_cats = [primary_cat] + matched_cats

        # ✅ FORCE indigenous if all variables reference indigenous
        if all_variables_indigenous(variaveis):
            primary_cat = "indigenous"
            if "indigenous" not in matched_cats:
                matched_cats = ["indigenous"] + matched_cats

        catalog["categories"].setdefault(primary_cat, []).append(tid)

        table_payload = {
            "table_name": t.get("table_name"),
            "group_name": t.get("group_name"),
            "primary_category": primary_cat,
            "matched_categories": matched_cats,

            # keep demographics listed (but not used to pick topic)
            "demographics": [c.get("nome") for c in classificacoes if c.get("nome")],

            # explain how classification happened
            "topic_classification_debug": debug,

            "variables": [
                {
                    "variable_id": v.get("id"),
                    "variable_name": v.get("nome"),
                    "unit": v.get("unidade"),
                    "decimals": v.get("decimais"),
                    "demographics": [c.get("nome") for c in classificacoes if c.get("nome")],
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
            },
        }

        catalog["tables"][tid] = table_payload
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

    out = "sidra_catalog_2022_topic_weighted_table_variables.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"\nSaved -> {out}")
