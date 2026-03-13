import json
import csv
from collections import OrderedDict

def create_comparison_csv(file1_path, file2_path, csv_file_path):
    """
    Compares the keys in two JSON files and creates a CSV file with the comparison.

    Args:
        file1_path (str): Path to the first JSON file (e.g., Japanese).
        file2_path (str): Path to the second JSON file (e.g., Vietnamese).
        csv_file_path (str): Path to the output CSV file.
    """

    with open(file1_path, 'r', encoding='utf-8') as f1:
        data1 = json.load(f1, object_pairs_hook=OrderedDict)
    with open(file2_path, 'r', encoding='utf-8') as f2:
        data2 = json.load(f2)

    keys1 = list(data1.keys())
    keys2 = set(data2.keys())

    all_keys = keys1[:]  # Start with keys from file1
    for key in keys2:
        if key not in all_keys:
            all_keys.append(key)
    with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
        csv_writer = csv.writer(csvfile)

        # Write header
        csv_writer.writerow(["key", "vietnamese", "japanese"])

        # Write data rows
        for key in all_keys:
            vietnamese_value = data2.get(key, "")
            japanese_value = data1.get(key, "")
            csv_writer.writerow([key, vietnamese_value, japanese_value])


if __name__ == "__main__":
    file_ja = "app/libs/language/strings_ja.json"
    file_vi = "app/libs/language/strings_vi.json"
    csv_output = "app/libs/language/translation.csv"

    create_comparison_csv(file_ja, file_vi, csv_output)
    print(f"CSV file created: {csv_output}")