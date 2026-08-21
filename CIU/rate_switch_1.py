from random import randint

from kf_IEC import *



@kf_tag("rate_switch", "rate_switch_1")
def rate_switch_1():

    step1 = "step1: 读取当前费率费率表, 按费率套1运行"
    step2 = "step2: 在T1~T8之间持续负载运行, 运行时间在(600s~1200s)随机"
    step3 = "step3: 读取T1~T8之间的所有有功无功电能值, 确保每个对应费率都有值"

    status = True
    step_status = True

    # 步骤1:step1 = "读取当前费率费率表, 按费率套1运行"
    kf_info(step1)
    conn = IEC62056ModeE("com3")
    obis_list = ["1101", "1411", "1501", "15.8.0"]
    result = conn.read_obis_list(obis_list)
    kf_info(f"当前季节费率表为: {result["1501"]}, \n 周费率表为: {result["1411"]}, \n 日费率表为: {result["1101"]}")

    # step1 预期判断: 4 个 OBIS 都要读到值
    for obis in obis_list:
        if result[obis] == '':
            kf_info(f"step1不符合预期: {obis} 没有读到值")
            step_status = False

    # 每个 step 后判断: 步骤失败 -> 脚本失败 -> 报错退出
    if not step_status:
        status = False
    if not status:
        kf_test_fail("rate_switch_1")

    # 判断当前是否为第一套费率
    if result["1501"] != "010101010101010101010101010101010101010101010101010101010101010101010101":
        conn.set_obis("1501", "010101010101010101010101010101010101010101010101010101010101010101010101")

    if result["1411"] != "01010101010101":
        conn.set_obis("1411", "01010101010101")




    rate_dict = {
        1 : "180001000000000000000000000000000000000000000000",
        2 : "180002000000000000000000000000000000000000000000",
        3 : "180003000000000000000000000000000000000000000000",
        4 : "180004000000000000000000000000000000000000000000",
        5 : "180005000000000000000000000000000000000000000000",
        6 : "180006000000000000000000000000000000000000000000",
        7 : "180007000000000000000000000000000000000000000000",
        8 : "180008000000000000000000000000000000000000000000"
    }

    # active_total_energy = split_value(result["15.8.0"])


    # 步骤2:step2: 在T1~T8之间持续负载运行, 运行时间在(600s~1200s)随机
    kf_info(step2)
    i = 1
    while i <= 8:

        # 按照T1~T8配置:

        # if i == 1:
        #     active_total_energy1 = split_value(conn.read_obis(f"15.8.{i}"))['number']
        #     kf_info(f"切换费率前T{i}的电能值:{active_total_energy1}kwh")
        # else:
        #     active_total_energy1 = split_value(conn.read_obis(f"15.8.{i-1}"))['number']
        #     kf_info(f"切换费率前T{i-1}的电能值:{active_total_energy1}kwh")



        # 切换费率, 失败自动重试, 最多重试3次
        retry = 0
        max_retry = 3
        result_rate = False
        while retry < max_retry:
            result_rate = conn.set_obis("1101", rate_dict[i])
            if result_rate:
                break
            retry = retry + 1
            kf_info(f"T{i}费率切换失败, 第{retry}次重试, 1秒后重新尝试")
            time.sleep(1)

        if not result_rate:
            # 重试次数用尽仍未成功, 抛异常强制退出脚本
            raise RuntimeError(f"T{i}费率切换失败, 已重试{max_retry}次, 脚本终止")

        # 切换费率后的对应费率的电能
        active_total_energy1 = split_value(conn.read_obis(f"15.8.{i}"))['number']
        kf_info(f"切换费率后还未加负载时T{i}的电能值:{active_total_energy1}kwh")

        # 在T{i}下加负载, 同一个费率最多尝试3次, 有一次正常累加即符合预期
        rate_ok = False
        t_attempt = 0
        while t_attempt < 3 and not rate_ok:
            ti_wait = randint(60,72)
            kf_info(f"T{i}第{t_attempt+1}次加负载, 等待{ti_wait}s")
            time.sleep(ti_wait)

            active_total_energy2 = split_value(conn.read_obis(f"15.8.{i}"))['number']
            kf_info(f"加负载后T{i}的电能值:{active_total_energy2}")

            if active_total_energy1 < active_total_energy2:
                kf_info(f"T{i}费率正常累加")
                rate_ok = True
            else:
                t_attempt = t_attempt + 1

        # 尝试3次都不累加 -> 本步不符合预期
        if not rate_ok:
            kf_info(f"T{i}费率尝试3次都没有累加")
            step_status = False

        # 每个 step 后判断: 步骤失败 -> 脚本失败 -> 报错退出
        if not step_status:
            status = False
        if not status:
            kf_test_fail("rate_switch_1")

        i += 1


    # 步骤3:step3: 读取T1~T8之间的所有有功无功电能值, 确保每个对应费率都有值
    kf_info(step3)

    try:
        ti_dict = {}
        conn.iec_connect()
        for a in range(1, 9):

            ti = conn._read_obis(f"15.8.{a}")
            if split_value(ti)['number'] == 0:
                kf_info(f"step3不符合预期, T{a}的电能值为0")
                step_status = False
            else:
                ti_dict[a] = ti
    finally:
        conn.break_session()

    # 每个 step 后判断: 步骤失败 -> 脚本失败 -> 报错退出
    if not step_status:
        status = False
    if not status:
        kf_test_fail("rate_switch_1")


    # 把字典拼成多行文本打印, 每个费率一行
    lines = []
    for key in ti_dict:
        lines.append(f"{key}: '{ti_dict[key]}'")
    ti_text = "{\n" + ", \n".join(lines) + "\n}"
    kf_info(ti_text)





if __name__ == '__main__':
    # 在这里改要运行的标签:
    #   "rate_switch_1" -> 只运行本脚本
    #   "rate_switch"   -> 运行所有带 rate_switch 标签的脚本
    run_by_tag("rate_switch_1")