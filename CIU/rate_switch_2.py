
from kf_IEC import *

@kf_tag("rate_switch", "rate_switch_2")
def rate_switch_2():
    # status: 整个脚本的测试结果, 默认 True
    status = True
    # step_status: 步骤执行结果, 每个step后判断, 某一步不符合预期就置为 False
    step_status = True

    # ---- step1 ----
    kf_info("这是脚本2")

    # 本步骤的预期判断, 不符合预期时把 step_status 置为 False:
    # step_status = False

    # 每个 step 后判断: 步骤失败 -> 脚本失败 -> 报错退出
    if not step_status:
        status = False
    if not status:
        kf_test_fail("rate_switch_2")


# if __name__ == '__main__':
#     run_by_tag("rate_switch_2")

if __name__ == "__main__":
    rate_switch_2()


