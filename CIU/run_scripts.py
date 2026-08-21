"""
按标签批量运行本目录下的测试脚本（跨文件）
用法: python run_scripts.py
切换运行范围: 修改下面 tag 字符串即可
"""
import os
import sys

# 把项目根目录加进搜索路径, 保证能找到 kf_IEC 包
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from kf_IEC import run_folder_by_tag

if __name__ == '__main__':
    # 在这里改要运行的标签:
    #   "rate_switch_1" -> 只运行 rate_switch_1.py
    #   "rate_switch"   -> 运行所有带 rate_switch 标签的脚本(如 rate_switch_1.py、rate_switch_2.py ...)
    tag = "rate_switch"

    # 脚本目录 = 本文件所在目录, 该目录下所有 .py 都会被自动导入参与筛选
    script_dir = os.path.dirname(os.path.abspath(__file__))
    run_folder_by_tag(script_dir, tag)
