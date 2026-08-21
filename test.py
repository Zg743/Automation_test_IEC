from random import randint

from kf_iec import *
# from kf_iec_info import kf_info

def clock_iec_1():
    conn = IEC62056ModeE("com3")
    datetime_obis_list = ["0.9.2", "0.9.1"]
    # 连表并保持会话打开（auto_read 会在结束后自动断开会话，不能用于循环校时）
    # conn.iec_connect()
    date_now = conn.read_obis_list(datetime_obis_list)

    kf_info("当前时间为:", date_now["0.9.2"], date_now["0.9.1"])

    kf_info("步骤2: 生成特定时间并校时")

    # 循环9次
    i = 1
    results = {}
    for i in range(1, 10):

        # 读取当前日期时间, 累计电能

        obis_list = ["0.9.2", "0.9.1", "15.8.0"]

        date_time_and_entry = conn.read_obis_list(obis_list)
        date_str = date_time_and_entry["0.9.2"]
        time_str = date_time_and_entry["0.9.1"]
        last_month_entry = date_time_and_entry["15.8.0"]

        # date_str = conn.read_obis("0.9.2")
        # time_str = conn.read_obis("0.9.1")
        # last_month_entry = conn.read_obis("15.8.0")

        kf_info(f"第{i}次循环, 当前时间为:{date_str} {time_str}")
        kf_info(f"校时前的累计电能为:{last_month_entry}")
        # 根据当前时间计算校时时间:
        # 校时至当前月的跨月点前300~420s randint(300,420)
        time_pianyi = randint(300,420)
        set_time = midnight_time(-time_pianyi)

        dict = {
            "0.9.2" : last_day_of_month(date_str),
            "0.9.1" : set_time
        }

        result = conn.set_obis_dict(dict)
        # result = conn.set_obis("0.9.2", last_day_of_month(date_str))
        if all(result.values()):
            kf_info("设置成功")
        else:
            kf_info("设置失败")

        # kf_info(f"设置的时间为:{format_date(last_day_of_month(date_str))} {format_time(set_time)}")
        # result = conn.set_obis("0.9.1", set_time)
        # if result:
        #     kf_info("设置成功")
        # else:
        #     kf_info("设置失败")

        kf_info(f"等待{time_pianyi}+3s")
        time.sleep(time_pianyi+3)


        # 读取跨月后的累计电能和日期
        current_month_and_entry = conn.read_obis_list(["15.8.0", "0.9.2"])

        # current_month_entry = conn.read_obis("15.8.0")
        kf_info(f'跨月后的累计电能为:{current_month_and_entry["15.8.0"]}')

        # 增量电能: 跨月后读数 - 跨月前读数
        last_number = float(split_value(last_month_entry)["number"])
        current_number = float(split_value(current_month_and_entry["15.8.0"])["number"])
        increment = current_number - last_number


        # 根据当前日期确定月份，记录累计电能与增量
        # current_month = conn.read_obis("0.9.2")

        date_parts = current_month_and_entry["0.9.2"].split('-')
        year = date_parts[0]
        month = int(date_parts[1])
        month_key = f"{year}-{month:02d}"
        results[month_key] = {
            "累计": current_number,
            "增量": increment,
        }
        kf_info(f"第{i}次循环结束: {month_key} 累计={current_number} 增量={increment}")

    kf_info("\n=== 校时结束 ===")
    kf_info("最近9个月的累计及增量电能:")
    kf_info(results)
    # conn.break_session()



if __name__ == '__main__':
    clock_iec_1()