from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent

SOURCE_CATALOG_PATH = BASE_DIR / "sidra_catalog_2022_api_multi_category_prefix.json"
TRANSLATION_CACHE_PATH = BASE_DIR / "translation_cache_en.json"
OUTPUT_CATALOG_PATH = BASE_DIR / "sidra_catalog_2022_api_multi_category_prefix_en.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def tr(text, cache):
    if not isinstance(text, str):
        return text
    return cache.get(text, text)


def build_translated_catalog(payload: dict, cache: dict) -> dict:
    categories_map = payload.get("categories", {}) or {}
    tables = payload.get("tables", {}) or {}

    out_tables = {}
    total = len(tables)

    for i, (tid, t) in enumerate(tables.items(), start=1):
        original_demographics = t.get("demographics", []) or []
        translated_demographics = [tr(d, cache) for d in original_demographics]
        class_members = t.get("classification_members", {}) or {}

        translated_variables = []
        for v in (t.get("variables", []) or []):
            if isinstance(v, dict):
                nv = dict(v)
                nv["variable_name"] = tr(v.get("variable_name"), cache)
                translated_variables.append(nv)
            else:
                translated_variables.append(v)

        translated_classification_ids = {
            tr(k, cache): v
            for k, v in (t.get("classification_ids", {}) or {}).items()
        }

        translated_classification_members = {}
        for original_demo, translated_demo in zip(original_demographics, translated_demographics):
            translated_classification_members[translated_demo] = [
                {
                    **m,
                    "name": tr(m.get("name"), cache) if isinstance(m, dict) else m,
                }
                for m in (class_members.get(original_demo, []) or [])
            ]

        nt = dict(t)
        nt["table_name"] = tr(t.get("table_name"), cache)
        nt["group_name"] = tr(t.get("group_name"), cache)
        nt["demographics"] = translated_demographics
        nt["variables"] = translated_variables
        nt["classification_ids"] = translated_classification_ids
        nt["classification_members"] = translated_classification_members

        out_tables[str(tid)] = nt

        percent = (i / total) * 100
        print(f"\rBuilding translated catalog: {i}/{total} ({percent:.1f}%)", end="")

    print()

    return {
        "source": payload.get("source"),
        "periodo": payload.get("periodo"),
        "tables_found": payload.get("tables_found"),
        "categories": categories_map,
        "tables": out_tables,
    }


def main():
    if not SOURCE_CATALOG_PATH.exists():
        raise FileNotFoundError(f"Missing source catalog: {SOURCE_CATALOG_PATH}")

    if not TRANSLATION_CACHE_PATH.exists():
        raise FileNotFoundError(f"Missing translation cache: {TRANSLATION_CACHE_PATH}")

    catalog = load_json(SOURCE_CATALOG_PATH)
    cache = load_json(TRANSLATION_CACHE_PATH)

    translated_catalog = build_translated_catalog(catalog, cache)
    save_json(OUTPUT_CATALOG_PATH, translated_catalog)

    print(f"Saved translated catalog to: {OUTPUT_CATALOG_PATH}")


if __name__ == "__main__":
    main()