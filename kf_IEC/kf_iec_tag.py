"""
测试脚本标签工具：给脚本函数打标签，按标签筛选运行
- kf_tag(*tags)          : 装饰器，打标签并注册
- run_by_tag(tag)        : 运行已注册脚本中带指定标签的（需先 import 所在文件）
- run_folder_by_tag(...) : 自动导入一个文件夹里的所有 .py 再按标签运行（跨文件使用）
"""

import os
import sys
import importlib
import traceback

from .kf_iec_info import kf_info

# 项目根目录（kf_IEC 包的上一级），保证被导入的脚本里 from kf_IEC import * 能找到包
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 全局注册表: [(函数, 标签列表), ...]
_TAG_REGISTRY = []


def kf_tag(*tags):
    """
    装饰器：给测试脚本打标签并注册到全局注册表。
    标签数量不限，一般第一个写同类脚本的公共前缀，最后一个写脚本自己的全名。

    用法:
        @kf_tag("rate_switch", "rate_switch_1")
        def rate_switch_1():
            ...
    """
    def decorator(func):
        # 防止同一函数重复注册
        already = False
        for f, t in _TAG_REGISTRY:
            if f is func:
                already = True

        if not already:
            _TAG_REGISTRY.append((func, list(tags)))
        return func

    return decorator


def run_by_tag(tag):
    """
    运行所有标签中包含 tag 的已注册脚本（按注册顺序依次执行）。
    - 传入完整标签(如 'rate_switch_1'): 只运行这一个脚本
    - 传入公共前缀标签(如 'rate_switch'): 运行所有带该标签的脚本
    - 单个脚本报错不会影响下一个脚本: 异常被捕获, 打印 Fail 后继续
    返回实际运行的函数名列表；没有匹配时打印提示并返回空列表。
    """
    ran_names = []
    for func, tags in _TAG_REGISTRY:
        if tag in tags:
            # 醒目的开始横幅
            kf_info("=" * 64)
            kf_info(f"=============== 开始运行: {func.__name__} ===============")
            kf_info("=" * 64)
            try:
                func()
                # 醒目的通过标记
                kf_info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                kf_info(f">>>>>>>>>>>>> {func.__name__}脚本测试Pass <<<<<<<<<<<<<<<")
                kf_info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
            except Exception as e:
                # 一个脚本失败不影响下一个脚本: 标记 Fail, 继续执行后面的脚本
                kf_info("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                kf_info(f"!!!!!!!!!!!!! {func.__name__}脚本测试Fail !!!!!!!!!!!!!")
                kf_info("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                kf_info(f"失败原因: {e}")
                # 打印完整调用栈(含出错文件和行号), 否则 PyCharm 控制台看不到任何定位信息
                kf_info("错误位置:\n" + traceback.format_exc())
            ran_names.append(func.__name__)

    if len(ran_names) == 0:
        kf_info(f"没有找到带标签 [{tag}] 的脚本")

    return ran_names


def kf_test_fail(script_name):
    """
    判定脚本测试失败: 抛出异常让当前脚本立即报错退出。
    - 批量运行时: 异常被 run_by_tag 捕获, 统一打印 'xxx脚本测试Fail' 后继续下一个脚本
    - 单独运行时: 进程直接带错误退出
    用法: 脚本内维护 status/step_status, 当 status 为 False 时调用 kf_test_fail("脚本名")
    """
    raise RuntimeError(f"{script_name}脚本测试Fail")


def run_folder_by_tag(folder, tag):
    """
    跨文件按标签运行：自动导入 folder 目录下的所有 .py 文件
    （导入时各文件里的 @kf_tag 装饰器自动完成注册），然后运行所有带 tag 标签的脚本。
    - folder: str，脚本所在目录
    - tag:    str，标签名，规则同 run_by_tag（完整标签只跑单个脚本，公共前缀跑一类）
    返回实际运行的函数名列表。
    """
    # 保证能找到 kf_IEC 包和目录下的脚本文件
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
    if folder not in sys.path:
        sys.path.insert(0, folder)

    # 1. 找出目录下所有 .py 文件名（排除 __ 开头，如 __init__.py），去掉 .py 后缀得到模块名
    module_names = []
    for name in os.listdir(folder):
        if name.endswith('.py') and not name.startswith('_'):
            module_names.append(name[:-3])

    # 2. 逐个导入，导入时装饰器自动注册
    for module_name in module_names:
        importlib.import_module(module_name)

    # 3. 按标签筛选并运行
    return run_by_tag(tag)
