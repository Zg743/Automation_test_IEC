from random import randint

from kf_IEC import *


def clock_iec_1():
    conn = IEC62056ModeE("com3")
    datetime_obis_list = ["0.9.2", "0.9.1"]

    date_now = conn.read_obis_list(datetime_obis_list)
    kf_info("当前时间为:", date_now["0.9.2"], date_now["0.9.1"])

    kf_info("步骤2: 生成特定时间并校时")

    results = {}
    for i in range(1, 14):
        # 每次循环只连一次表：读取当前日期时间/累计电能 + 校时写入 在同一个会话中完成
        conn.iec_connect()
        try:
            # 读取当前日期时间, 累计电能
            date_str = conn._read_obis("0.9.2")
            time_str = conn._read_obis("0.9.1")
            last_month_entry = conn._read_obis("15.8.0")

            kf_info(f"第{i}次循环, 当前时间为:{date_str} {time_str}")
            kf_info(f"校时前的累计电能为:{last_month_entry}")

            # 根据当前时间计算校时时间:
            # 校时至当前月的跨月点前300~420s randint(300,420)
            time_pianyi = randint(300, 420)
            set_time = midnight_time(-time_pianyi)

            # 同一会话内完成校时写入
            write_dict = {
                "0.9.2": last_day_of_month(date_str),
                "0.9.1": set_time,
            }
            date_ok = conn._set_obis("0.9.2", write_dict["0.9.2"])
            time_ok = conn._set_obis("0.9.1", write_dict["0.9.1"])
            if date_ok and time_ok:
                kf_info("设置成功")
            else:
                kf_info("设置失败")
        finally:
            conn.iec_disconnect()

        kf_info(f"等待{time_pianyi}+2s")
        time.sleep(time_pianyi + 2)

        # 跨月后重新连表，读取累计电能和日期
        conn.iec_connect()
        try:
            current_entry = conn._read_obis("15.8.0")
            current_date = conn._read_obis("0.9.2")
            kf_info(f'跨月后的累计电能为:{current_entry}')

            # 增量电能: 跨月后读数 - 跨月前读数
            last_number = float(split_value(last_month_entry)["number"])
            current_number = float(split_value(current_entry)["number"])
            increment = current_number - last_number

            # 根据当前日期确定月份，记录累计电能与增量
            date_parts = current_date.split('-')
            year = date_parts[0]
            month = int(date_parts[1])
            month_key = f"{year}-{month:02d}"
            results[month_key] = {
                "累计": current_number,
                "增量": increment,
            }
            kf_info(f"第{i}次循环结束: {month_key} 累计={current_number} 增量={increment}")
        finally:
            conn.iec_disconnect()

    kf_info("\n=== 校时结束 ===")
    kf_info("最近9个月的累计及增量电能:")
    kf_info(results)


if __name__ == '__main__':
    clock_iec_1()