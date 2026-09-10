"""
心跳模块：水表会定时休眠，通过固定间隔发送心跳帧防止其进入休眠/保持唤醒。

设计要点（对应需求）：
- 在脚本中执行 iec_connect 后启动一个后台守护线程，按固定间隔发送心跳帧
- 心跳帧为 645/97 风格的 8 位原始字节帧，默认 68 AA AA AA AA AA AA 68 13 00 DF 16
- 与 IEC 读表共享同一串口，通过共享的 threading.Lock 保证串口访问串行，
  心跳线程与 IEC 的发送/接收互不重入，避免帧字节交错
- 串口字节宽度(7E1/8E1/8N1)由调用方自行切换管理，本模块只负责发送原始字节

用法示例：
    conn = IEC62056ModeE("com3")
    conn.iec_connect()

    hb = Heartbeat(conn=conn, lock=conn.io_lock, interval=5)
    hb.start()          # 后台每 5 秒发送一次心跳帧

    # ... 执行其余读表/写操作（IEC 操作与心跳通过 io_lock 自动串行）...

    hb.stop()           # 结束前停止心跳
    conn.iec_disconnect()
"""
from .kf_iec import *
import threading
import time

# 默认心跳帧：68 AA AA AA AA AA AA 68 13 00 DF 16（读通讯地址）
DEFAULT_HEARTBEAT_FRAME = bytes([
    0x68, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0x68,
    0x13, 0x00, 0xDF, 0x16,
])


class Heartbeat:
    """
    固定间隔的心跳发送器。start() 启动后台守护线程，stop() 停止。
    所有串口写入都在传入的 lock 保护下进行，与 IEC 操作互斥串行。
    """

    def __init__(self, conn, lock, interval: float = 5,
                 frame: bytes = DEFAULT_HEARTBEAT_FRAME,
                 name: str = "kf_heartbeat"):
        self.conn = conn        # 持有 IEC62056ModeE 实例，动态取 conn.ser 避免引用失效
        self.lock = lock        # 与 IEC62056ModeE.io_lock 共享的互斥锁
        self.interval = interval
        self.frame = frame
        self.name = name
        self._stop = threading.Event()
        self._thread: threading.Thread = None

    def start(self):
        """启动后台心跳线程（守护线程，主进程退出自动结束）"""
        kf_info("==============开启后台线程,发送心跳==============")
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=self.name,
                                        daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            remain = self.interval
            while remain > 0 and not self._stop.is_set():
                self._stop.wait(min(remain, 1))
                remain -= 1
            if not self._stop.is_set():
                self._send()

    def _send(self):
        """持锁写入心跳帧，避免与 IEC 收发发生字节交错"""
        if self._stop.is_set():
            return
        if self.conn._iec_active:
            return
        try:
            with self.lock:
                if self._stop.is_set():
                    return
                if self.conn._iec_active:
                    return
                self.conn.ser.write(self.frame)
                self.conn.ser.flush()
                self.conn.ser.reset_input_buffer()
        except Exception:
            # 串口已关闭或出错时静默吞掉，等待下次发送；stop() 会真正停止
            pass

    def send_once(self):
        """立即手动发送一次心跳帧（可用于唤醒后首次衔接）"""
        self._send()

    def stop(self):
        """停止心跳线程并等待其退出"""
        kf_info("==============关闭后台线程,停止心跳==============")
        self._stop.set()
        t = self._thread
        if t is not None and threading.current_thread() != t:
            t.join(timeout=5)
        if t is not None and t.is_alive():
            return
        self._thread = None


if __name__ == "__main__":
    # 使用示例：连接水表后启动心跳，维持其不进入休眠
    import time

    conn = IEC62056ModeE("com3")   # 需从 kf_iec 引入
    conn.iec_connect()             # 建立 IEC 会话

    # 启动心跳：每 5 秒发一次默认帧，保持水表唤醒
    hb = Heartbeat(conn=conn, lock=conn.io_lock, interval=5)
    hb.start()

    try:
        # 中间执行其余读表/写操作，IEC 与心跳通过 io_lock 自动串行。
        # 注意：会话已建立，应使用内部 _read_obis/_set_obis（只读写、不接管连接），
        # 不要用 read_obis（它内部会再次 iec_connect 并断开，与当前会话及心跳冲突）
        value = conn._read_obis("0.9.1")
        print("读取到时间:", value)
        time.sleep(20)   # 期间心跳持续发送，水表不会休眠
    finally:
        hb.stop()                 # 收尾先停心跳，再断开
        conn.iec_disconnect()
