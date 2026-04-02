import json
from collections import defaultdict
from pathlib import Path

def compute_shared_table_counts(input_path, output_path=None):
    """
    For each category, assigns each table ID the number of OTHER categories
    that also include that table.
    """
    # Load JSON
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    categories = data["categories"]

    # Count how many categories each table appears in
    table_counts = defaultdict(int)
    for tables in categories.values():
        for table in tables:
            table_counts[table] += 1

    # Build result
    result = {}
    for category, tables in categories.items():
        result[category] = {
            table: table_counts[table] - 1
            for table in tables
        }

    # Write output or return
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    else:
        return result


if __name__ == "__main__":
    input_file = Path("sidra_catalog_2022_api_multi_category_prefix.json")     # your input file
    output_file = Path("output.json")   # where results go

    compute_shared_table_counts(input_file, output_file)
