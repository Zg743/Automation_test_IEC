from typing import Dict, Tuple, Union


def split_value(value_str: str) -> Dict[str, Union[float, str]]:
    """
    将 IEC 62056 数据值字符串拆分为数字和单位，返回字典。
    示例: split_value('000073.90*kWh') -> {'number': 73.9, 'unit': 'kWh'}
    """
    # 1. 按 '*' 拆分数字部分和单位部分
    if '*' in value_str:
        index = value_str.index('*')
        value_part = value_str[0:index]
        unit_part = value_str[index + 1:]
    else:
        value_part = value_str
        unit_part = ''

    # 2. 把数字部分拆成整数部分和小数部分
    if '.' in value_part:
        dot_index = value_part.index('.')
        integer_part = value_part[0:dot_index]
        decimal_part = value_part[dot_index:]
    else:
        integer_part = value_part
        decimal_part = ''

    # 3. 去掉整数部分的前导零
    start = 0
    while start < len(integer_part) and integer_part[start] == '0':
        start = start + 1
    if start < len(integer_part):
        integer_stripped = integer_part[start:]
    else:
        integer_stripped = '0'

    # 4. 拼接数字部分
    number = float(integer_stripped + decimal_part)

    result = {
        'number': number,
        'unit': unit_part,
    }
    return result


def split_digits(value_str: str) -> Tuple[str, str]:
    """
    将数据值字符串拆成"去掉小数点的数字串"和"单位"，以元组返回。
    数字保持原始字符串格式，不去前导零、不转 float。
    示例: split_digits('000073.90*kWh') -> ('00007390', 'kWh')
          split_digits('000073.90')     -> ('00007390', '')
    """
    # 1. 按 '*' 拆分数字部分和单位部分
    if '*' in value_str:
        index = value_str.index('*')
        value_part = value_str[0:index]
        unit_part = value_str[index + 1:]
    else:
        value_part = value_str
        unit_part = ''

    # 2. 去掉数字部分的小数点（没有小数点时原样保留）
    digits = value_part.replace('.', '')

    return digits, unit_part


if __name__ == '__main__':
    result = split_value('000073.90*kWh')
    print(result['number'], result['unit'])   # 73.90 kWh
    print(type(result['number']))

    print(split_digits('000073.90*kWh'))      # ('00007390', 'kWh')
    print(split_digits('000073.90'))          # ('00007390', '')
