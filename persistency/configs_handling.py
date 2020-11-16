#!/usr/bin/env python
import csv

from typing import Dict

from utils.functions import get_path_to_file, log


def read_csv_files():
    configs = {'units': {}, 'buildings': {}, 'technologies': {}}

    for key in configs:
        try:
            configs[key].update(read_single_file(f'{key}.csv'))
        except Exception as e:
            log(f'{str(e)}')

    print(configs)
    return configs


def read_single_file(filename: str):
    category_dict = {}
    with open(get_path_to_file(filename), newline='') as file:
        for row in csv.DictReader(file):
            category_dict[row['object_name']] = convert_csv_numeric_data(row)

    return category_dict


def convert_csv_numeric_data(row) -> Dict:
    """Identify numeric values and convert them to int or float."""
    converted = {}
    for key, value in row.items():
        if value[0].isnumeric():
            converted[key] = float(value) if '.' in value else int(value)
        else:
            converted[key] = value
    return converted
