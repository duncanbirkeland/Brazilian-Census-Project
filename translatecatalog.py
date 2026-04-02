import json
import time
from pathlib import Path

from deep_translator import GoogleTranslator

INFILE = Path("sidra_catalog_2022_api_multi_category_prefix.json")
OUTFILE = Path("sidra_catalog_2022_api_multi_category_prefix_en.json")
CACHEFILE = Path("translation_cache_en.json")
FAILEDLOG = Path("translation_failures.log")

translator = GoogleTranslator(source="pt", target="en")


def load_json(path, default):
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


cache = load_json(CACHEFILE, {})


def log_failure(text, error):
    with FAILEDLOG.open("a", encoding="utf-8") as f:
        f.write(f"{text}\t{type(error).__name__}: {error}\n")


def safe_translate(text, retries=3, delay=1.5):
    if not isinstance(text, str) or not text.strip():
        return text

    if text in cache:
        return cache[text]

    for attempt in range(1, retries + 1):
        try:
            translated = translator.translate(text)

            if not translated or not isinstance(translated, str):
                raise ValueError("Empty or invalid translation result")

            cache[text] = translated

            # Save cache immediately so progress is never lost
            save_json(CACHEFILE, cache)
            return translated

        except Exception as e:
            print(f"Failed to translate on attempt {attempt}/{retries}: {text[:80]}...")
            log_failure(text, e)

            if attempt < retries:
                time.sleep(delay * attempt)

    # Fallback: keep original text instead of crashing
    cache[text] = text
    save_json(CACHEFILE, cache)
    return text


def collect_strings(data):
    strings = set()
    tables = data.get("tables", {})

    for table in tables.values():
        if table.get("table_name"):
            strings.add(table["table_name"])

        if table.get("group_name"):
            strings.add(table["group_name"])

        for d in table.get("demographics", []):
            if d:
                strings.add(d)

        for v in table.get("variables", []):
            name = v.get("variable_name")
            if name:
                strings.add(name)

        for k in table.get("classification_ids", {}).keys():
            if k:
                strings.add(k)

        for class_name, members in table.get("classification_members", {}).items():
            if class_name:
                strings.add(class_name)

            for m in members:
                name = m.get("name")
                if name:
                    strings.add(name)

    return sorted(strings)


def build_translation_map(strings):
    total = len(strings)

    for i, text in enumerate(strings, start=1):
        if text in cache:
            percent = (i / total) * 100
            print(f"\rPreparing translations: {i}/{total} ({percent:.1f}%)", end="")
            continue

        safe_translate(text)

        percent = (i / total) * 100
        print(f"\rPreparing translations: {i}/{total} ({percent:.1f}%)", end="")

    print("\nTranslation map complete.")


def tr(text):
    if not isinstance(text, str) or not text.strip():
        return text
    return cache.get(text, text)


def translate_catalog(data):
    out = dict(data)
    tables = out.get("tables", {})
    translated_tables = {}

    total = len(tables)

    for i, (table_id, table) in enumerate(tables.items(), start=1):
        t = dict(table)

        if "table_name" in t:
            t["table_name"] = tr(t["table_name"])

        if "group_name" in t:
            t["group_name"] = tr(t["group_name"])

        if "demographics" in t:
            t["demographics"] = [tr(x) for x in t["demographics"]]

        if "variables" in t:
            new_vars = []
            for v in t["variables"]:
                nv = dict(v)
                if "variable_name" in nv:
                    nv["variable_name"] = tr(nv["variable_name"])
                new_vars.append(nv)
            t["variables"] = new_vars

        if "classification_ids" in t:
            t["classification_ids"] = {
                tr(k): v for k, v in t["classification_ids"].items()
            }

        if "classification_members" in t:
            new_members = {}
            for class_name, members in t["classification_members"].items():
                new_members[tr(class_name)] = [
                    {
                        **m,
                        "name": tr(m["name"]) if "name" in m else m.get("name")
                    }
                    for m in members
                ]
            t["classification_members"] = new_members

        translated_tables[table_id] = t

        percent = (i / total) * 100
        print(f"\rApplying translations to catalog: {i}/{total} ({percent:.1f}%)", end="")

    print("\nCatalog translation complete.")
    out["tables"] = translated_tables
    return out


def main():
    with INFILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    all_strings = collect_strings(data)
    print(f"Found {len(all_strings)} unique strings.")

    build_translation_map(all_strings)
    translated = translate_catalog(data)

    save_json(OUTFILE, translated)
    print(f"Saved translated catalog to: {OUTFILE}")
    print(f"Cache saved to: {CACHEFILE}")
    print(f"Failures logged to: {FAILEDLOG}")


if __name__ == "__main__":
    main()