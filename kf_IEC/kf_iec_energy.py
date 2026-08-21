from typing import Dict, Union


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


if __name__ == '__main__':
    result = split_value('000073.90*kWh')
    print(result['number'], result['unit'])   # 73.90 kWh
    print(type(result['number']))
