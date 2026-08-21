import re
import math
import calendar


def _parse_period(period: str) -> int:
    """
    解析周期并换算为秒。
    支持 '30min'、'30m'、'1h'、'30'（默认分钟），如 '30min' -> 1800
    """
    period = period.strip().lower()

    # 取出数字和单位
    match = re.match(r'(\d+)\s*(min|m|h|s)?', period)
    number = int(match.group(1))
    unit = match.group(2)
    if unit is None:
        unit = 'min'

    if unit == 'h':
        seconds = number * 3600
    elif unit == 's':
        seconds = number
    else:
        seconds = number * 60

    return seconds


def _hms(seconds: int) -> str:
    """将秒数格式化为 HHMMSS"""
    hour = seconds // 3600
    minute = (seconds % 3600) // 60
    second = seconds % 60

    hour_str = f'{hour:02d}'
    minute_str = f'{minute:02d}'
    second_str = f'{second:02d}'

    result = hour_str + minute_str + second_str
    return result


def next_boundary_time(time_str: str, period: str, offset: int) -> str:
    """
    传入 HH:MM:SS 时间、周期(如 30min)、偏移秒(int，如 -3)，
    返回向上取整到下一个周期边界再偏移后的时间，格式 HHMMSS。
    示例: next_boundary_time('17:12:17', '30min', -3) -> '172957'
    """
    # 解析传入时间
    time_parts = time_str.split(':')
    hour = int(time_parts[0])
    minute = int(time_parts[1])
    second = int(time_parts[2])

    # 换算成当天总秒数
    total_seconds = hour * 3600 + minute * 60 + second

    # 周期换算为秒
    period_seconds = _parse_period(period)

    # 向上取整到最近的周期边界
    boundary_count = math.ceil(total_seconds / period_seconds)
    boundary_seconds = boundary_count * period_seconds

    # 加上偏移秒
    target_seconds = boundary_seconds + offset

    # 超过 24 小时则回绕
    if target_seconds >= 86400:
        target_seconds = target_seconds - 86400
    elif target_seconds < 0:
        target_seconds = target_seconds + 86400

    return _hms(target_seconds)


def midnight_time(offset: int) -> str:
    """
    传入偏移秒(int，如 -3)，返回 0 点偏移后的时间，格式 HHMMSS。
    示例: midnight_time(-3) -> '235957'
    """
    # 0 点即 0 秒，加上偏移
    target_seconds = 0 + offset

    # 处理回绕：-3s 应为前一天 23:59:57，显示为 235957
    if target_seconds < 0:
        target_seconds = target_seconds + 86400
    elif target_seconds >= 86400:
        target_seconds = target_seconds - 86400

    return _hms(target_seconds)


def last_day_of_month(date_str: str) -> str:
    """
    传入 YY-MM-DD 日期，返回当月最后一天的日期，格式 YYMMDD。
    示例: last_day_of_month('26-09-01') -> '260930'
    """
    # 拆分日期
    date_parts = date_str.split('-')
    year_yy = int(date_parts[0])
    month = int(date_parts[1])

    # 补全为四位年份，获取当月最后一天
    full_year = 2000 + year_yy
    month_range = calendar.monthrange(full_year, month)
    last_day = month_range[1]

    # 组装为 YYMMDD
    year_str = f'{year_yy:02d}'
    month_str = f'{month:02d}'
    last_day_str = f'{last_day:02d}'
    result = year_str + month_str + last_day_str

    return result


def format_date(date_str: str) -> str:
    """
    传入 YYMMDD 格式日期，返回 YY-MM-DD 格式。
    示例: format_date('260930') -> '26-09-30'
    """
    # 按位拆分
    year_part = date_str[0:2]
    month_part = date_str[2:4]
    day_part = date_str[4:6]

    result = year_part + '-' + month_part + '-' + day_part
    return result


def format_time(time_str: str) -> str:
    """
    传入 HHMMSS 格式时间，返回 HH:MM:SS 格式。
    示例: format_time('172957') -> '17:29:57'
    """
    # 按位拆分
    hour_part = time_str[0:2]
    minute_part = time_str[2:4]
    second_part = time_str[4:6]

    result = hour_part + ':' + minute_part + ':' + second_part
    return result


if __name__ == '__main__':
    print(next_boundary_time('17:12:17', '30min', -3))   # 172957
    print(midnight_time(-3))                             # 235957
    print(last_day_of_month('26-09-01'))                 # 260930
    print(format_date('260930'))                         # 26-09-30
    print(format_time('172957'))                         # 17:29:57
