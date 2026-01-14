import json

def select_one_table_per_category(payload: dict) -> dict:
    categories = payload.get("categories", {})
    tables = payload.get("tables", {})
    chosen = {}

    for category, table_ids in categories.items():
        if not table_ids:
            continue
        for tid in table_ids:
            tid = str(tid)
            if tid in tables:
                chosen[category] = tid
                break

    return chosen


def print_table_summary(category: str, table_obj: dict) -> None:
    print("=" * 80)
    print(f"Category: {category}")
    print(f"Table: {table_obj.get('table_name')}")
    print()

    # Variable names only
    print("Variables:")
    variables = table_obj.get("variables", [])
    if variables:
        for v in variables:
            print(f"  - {v.get('variable_name')}")
    else:
        print("  (none)")
    print()

    # Demographics + classification members
    demographics = table_obj.get("demographics", [])
    classification_members = table_obj.get("classification_members", {})

    print("Demographics and classification members:")
    if not demographics:
        print("  (none)")
    else:
        for demo in demographics:
            print(f"  - {demo}:")
            members = classification_members.get(demo, [])
            if members:
                for m in members:
                    print(f"      * {m}")
            else:
                print("      (no members)")
    print()


def main(payload: dict) -> None:
    chosen = select_one_table_per_category(payload)
    tables = payload.get("tables", {})

    if not chosen:
        print("No tables could be selected.")
        return

    for category, table_id in chosen.items():
        table_obj = tables.get(table_id)
        if table_obj:
            print_table_summary(category, table_obj)


if __name__ == "__main__":
    with open(
        "sidra_catalog_2022_api_first_demo_or_table_name_prefix.json",
        "r",
        encoding="utf-8",
    ) as f:
        payload = json.load(f)

    main(payload)
