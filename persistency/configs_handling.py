#!/usr/bin/env python
import csv

from typing import Dict, Union, Tuple, List, Any

from utils.functions import get_path_to_file, log


def read_csv_files():
    configs = {'units': {}, 'buildings': {}, 'technologies': {}}
    for key in configs:
        try:
            configs[key].update(read_single_file(f'{key}.csv'))
        except Exception as e:
            log(f'{str(e)}')
    return configs


def read_single_file(filename: str):
    category_dict = {}
    with open(get_path_to_file(filename), newline='') as file:
        for row in csv.DictReader(file):
            category_dict[row['object_name']] = convert_csv_data(row)
    return category_dict


def convert_csv_data(row) -> Dict:
    """
    Read values from CSV file, unpack them from strings, convert to numeric
    types if required and assign as dict values.
    """
    converted = {}
    for key, value in row.items():
        if value.startswith(('(', '[')):
            converted[key] = unpack_value(value, value[0])
        else:
            converted[key] = convert_value(value)
    return converted


def unpack_value(value: str, bracket: str) -> Union[Tuple, List]:
    """Convert str representation of tuple or list to python tuple or list."""
    values = [convert_value(v) for v in value.strip('([)]').split(';')]
    return tuple(values) if bracket == '(' else values


def convert_value(value: str) -> Union[str, float, int, bool, None]:
    if value[0].isnumeric():
        return convert_to_numeric(value)
    elif value in ('True', 'False', 'None'):
        return eval(value)
    return value


def convert_to_numeric(value: str) -> Union[float, int]:
    """Identify numeric values and convert them to int or float."""
    return float(value) if '.' in value else int(value)


def load_player_configs() -> Dict[str, Any]:
    pass
