"""
一键配置费率表
"""


from kf_IEC import *

def rate_switch_3():
    """
    一键配置费率表
    """

    step1 = "step1:定义多费率表和阶梯费率表及单费率表"
    step2 = "step2:一键配置"
    step3 = "step3:检查配置是否正确"

    status = True
    step_status = True

    # step1:定义多费率表和阶梯费率表及单费率表
    kf_info(step1)

    step_parameters = {
        "C.9.27" : "00001100",
        "C.9.28" : "00001200",
        "C.9.29" : "00001300",
        "C.9.30" : "00001400",
        "C.9.31" : "00001500",
        "C.9.32" : "00001600",
        "C.9.33" : "00001700",
        "C.9.34" : "00001800",
        "C.9.11" : "00001500",
        "C.9.12" : "00002000",
        "C.9.13" : "00002500",
        "C.9.14" : "00003000",
        "C.9.15" : "00003500",
        "C.9.16" : "00004000",
        "C.9.17" : "00004500"
    }

    TOU_paramaters = {
        "C.9.43": "00002100",
        "C.9.44": "00002200",
        "C.9.45": "00002300",
        "C.9.46": "00002400",
        "C.9.47": "00002500",
        "C.9.48": "00002600",
        "C.9.49": "00002700",
        "C.9.50": "00002800"
    }

    TI_paramaters = {"C.9.60":"00003210"}



    kf_info(f"{step1}**successful")

    # 步骤2: 一键配置
    kf_info(step2)

    conn = IEC62056ModeE("com3")

    result = conn.set_obis_dict(step_parameters)
    if all(result.values()):
        kf_info("设置阶梯费率表成功")
    else:
        kf_info("设置阶梯费率表失败")
        step_status = False

    result = conn.set_obis_dict(TOU_paramaters)
    if all(result.values()):
        kf_info("设置多费率表成功")
    else:
        kf_info("设置多费率表失败")
        step_status = False

    result = conn.set_obis_dict(TI_paramaters)
    if all(result.values()):
        kf_info("设置单费率表成功")
    else:
        kf_info("设置单费率表失败")
        step_status = False

    if not step_status:
        status = False
    if not status :
        kf_test_fail("rate_switch_3")

    kf_info(f"{step2}**successful")



    # 步骤3: step3:检查配置是否正确
    kf_info(step3)

    step_list = []
    TOU_list = []
    TI_list = []

    for k in step_status.keys():
        step_list.append(k)

    for k in TOU_paramaters.keys():
        TOU_list.append(k)

    for k in TI_paramaters.keys():
        TI_list.append(k)

    conn.iec_connect()
    try:
        for k in step_list:
            result = split_digits(conn._read_obis(k))
            if result[0]!= step_parameters[k]:
                step_status = False

        for k in TOU_list:
            result = split_digits(conn._read_obis(k))
            if result[0]!= TOU_paramaters[k]:
                step_status = False

        for k in TI_list:
            result = split_digits(conn._read_obis(k))
            if result[0]!= TI_paramaters[k]:
                step_status = False

        if not step_status:

            status = False
        if not status:
            kf_info(f"{step3}**Fail")
            kf_test_fail("rate_switch_3")

        kf_info(f"{step3}**Success")


    finally:
        conn.iec_disconnect()




if __name__ == "__main__":
    rate_switch_3()

