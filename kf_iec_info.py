"""
提供控制台打印, 日志打印, 控制台+日志打印
"""

import time
import logging
import os


def info(*args, **kwargs):
    """
    控制台打印
    """
    print(*args, **kwargs)


# 日志存放目录
LOG_DIR = "Log"
os.makedirs(LOG_DIR, exist_ok=True)

# 全局变量：保存当前使用的 logger 和对应的小时标识
_current_logger = None
_current_hour = None


def _get_logger():
    """
    根据当前小时获取（或创建）对应的 logger。
    如果小时发生变化，则关闭旧 handler 并创建新 handler。
    """
    global _current_logger, _current_hour

    # 获取当前小时字符串，例如 "20260819_14"
    current_hour = time.strftime("%Y%m%d_%H", time.localtime())

    # 如果小时没变，直接返回已有的 logger
    if current_hour == _current_hour:
        return _current_logger

    # 小时变化了，需要重新创建 logger
    if _current_logger is not None:
        # 关闭并移除旧的所有 handler
        for handler in _current_logger.handlers[:]:
            _current_logger.removeHandler(handler)
            handler.close()

    # 创建新的 logger（名称唯一，避免干扰）
    _current_logger = logging.getLogger(f"log_info_{current_hour}")
    _current_logger.setLevel(logging.INFO)
    _current_logger.propagate = False  # 防止传播到根 logger

    # 创建文件 handler
    log_path = os.path.join(LOG_DIR, f"{current_hour}.log")
    file_handler = logging.FileHandler(log_path, encoding='utf-8')

    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s : %(message)s')
    file_handler.setFormatter(formatter)

    # 添加到 logger
    _current_logger.addHandler(file_handler)

    # 更新当前小时
    _current_hour = current_hour

    return _current_logger


def log_info(*args, **kwargs):
    """
    仅写入日志，不打印控制台。
    支持 print 的所有参数（sep、end、file、flush 等）。
    """
    # 构造要写入日志的消息字符串
    # 注意：日志系统会自动在每条记录末尾添加换行，所以这里不包含 end
    sep = kwargs.get('sep', ' ')
    if args:
        message = sep.join(str(arg) for arg in args)
    else:
        message = ""

    logger = _get_logger()
    logger.info(message)


def kf_info(*args, **kwargs):
    """
    控制台和日志同时打印
    功能与 print 相同，同时将相同内容写入按小时分割的日志文件。
    支持 print 的所有参数（sep、end、file、flush 等）。
    """
    # 1. 在控制台打印（保持 print 的原始行为）
    print(*args, **kwargs)

    # 2. 写入日志
    log_info(*args, **kwargs)


# 测试
if __name__ == "__main__":
    a = 3
    b = 4
    kf_info(f"a+b = {a+b}")
    log_info("多个", "参数", "测试", sep=" | ")
    info("仅控制台", "打印")
