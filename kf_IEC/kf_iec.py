import time
import serial
import re
import threading
from typing import List, Dict, Tuple, Optional
from .kf_iec_datetime import *
from .kf_iec_energy import *
from .kf_iec_info import *

# 控制字符的可读名称（用于报文打印）
_CTRL_NAMES = {
    0x01: '<SOH>', 0x02: '<STX>', 0x03: '<ETX>', 0x04: '<EOT>',
    0x05: '<ENQ>', 0x06: '<ACK>', 0x07: '<BEL>', 0x08: '<BS>',
    0x09: '<HT>', 0x0A: '<LF>', 0x0B: '<VT>', 0x0C: '<FF>',
    0x0D: '<CR>', 0x0E: '<SO>', 0x0F: '<SI>',
    0x15: '<NAK>', 0x1B: '<ESC>',
}

class IEC62056ModeE:
    """IEC 62056-21 Mode E 抄表客户端"""

    # 波特率标识映射
    BAUD_MAP = {
        '0': 300,
        '1': 600,
        '2': 1200,
        '3': 2400,
        '4': 4800,
        '5': 9600,
        '6': 19200,
    }

    def __init__(self, port: str, initial_baud: int = 300, timeout: float = 2):
        self.port = port
        self.initial_baud = initial_baud
        self.timeout = timeout
        self._connect_phase = False
        # 共享串口互斥锁：与心跳(Heartbeat)共享，保证串口访问串行、帧不交错
        self.io_lock = threading.Lock()
        #self.ser: Optional[serial.Serial] = None
        self.ser = serial.Serial(rtscts=False, dsrdtr=False, baudrate=self.initial_baud)
        self.ser.set_buffer_size(rx_size=10240, tx_size=5120)

    # ---------- 底层串口与帧操作 ----------
    def _open(self, baud: int):
        """以 7E1 模式打开串口"""
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = serial.Serial(
            port=self.port,
            baudrate=baud,
            bytesize=serial.SEVENBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
            rtscts = False,
            dsrdtr = False
        )
        self.ser.set_buffer_size(rx_size=10240, tx_size=5120)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

    def _hex_str(self, data: bytes) -> str:
        """将字节串格式化为大写、两字节间空一格的十六进制字符串"""
        return ' '.join(f'{b:02X}' for b in data)

    def _ascll_str(self, data: bytes) -> str:
        """将报文转换成可读的 ASCII 格式，控制字符显示为 <NAME>，ETX 后校验字节显示为 <BCC>"""
        out = []
        i = 0
        while i < len(data):
            b = data[i]
            if b == 0x03 and i + 1 < len(data):
                out.append('<ETX><BCC>')
                i += 2
            elif 32 <= b <= 126:
                out.append(chr(b))
                i += 1
            elif b in _CTRL_NAMES:
                out.append(_CTRL_NAMES[b])
                i += 1
            else:
                out.append(f'<0x{b:02X}>')
                i += 1
        return ''.join(out)

    def _show(self, msg: str, blank: bool = False):
        """连接/断开阶段输出到日志，其余阶段输出到控制台"""
        if self._connect_phase:
            log_info(msg)
        else:
            kf_info(msg)
            if blank:
                info()

    def _send(self, data: bytes):
        """发送原始字节（持 io_lock，与心跳线程互斥串行）"""
        with self.io_lock:
            self.ser.rts = False
            self.ser.drt = False
            self._show(f"发送：{self._ascll_str(data)}")
            self.ser.write(data)
            self.ser.flush()

    def _read_line(self) -> bytes:
        """读取以 CR LF 结尾的一行（用于标识响应）"""
        resp = self.ser.read_until(expected=b'\n')
        self._show(f"接收：{self._ascll_str(resp)}", blank=True)
        return resp

    def _read_frame(self) -> Optional[bytes]:
        """读取一个帧：单字节 ACK 或 SOH/STX 开头的完整帧（持 io_lock 与心跳互斥）"""
        with self.io_lock:
            return self._read_frame_unlocked()

    def _read_frame_unlocked(self) -> Optional[bytes]:
        byte = self.ser.read(1)
        if not byte:
            self._show("接收：", blank=True)
            return None
        # 单字节 ACK
        if byte == b'\x06':
            self._show(f"接收：{self._ascll_str(byte)}", blank=True)
            return byte
        # 数据帧（SOH=0x01 或 STX=0x02）
        if byte[0] in (0x01, 0x02):
            frame = byte
            while True:
                ch = self.ser.read(1)
                if not ch:
                    break
                frame += ch
                if ch == b'\x03':           # ETX，下一个字节是 BCC
                    bcc = self.ser.read(1)
                    if bcc:
                        frame += bcc
                    break
            self._show(f"接收：{self._ascll_str(frame)}", blank=True)
            return frame
        # 其他意外字节，原样返回
        self._show(f"接收：{self._ascll_str(byte)}", blank=True)
        return byte

    @staticmethod
    def _bcc(data: bytes) -> int:
        """计算 BCC：从 SOH 之后或 STX 之后到 ETX 之前的所有字节异或，结果取低 7 位"""
        result = 0
        for b in data:
            result ^= b
        return result & 0x7F

    def _build_command_frame(self, cmd: bytes, data_block: bytes = b'') -> bytes:
        """
        构造 SOH + CMD + STX + data + ETX + BCC 的帧
        cmd: 两个字节命令，如 b'P1', b'R1', b'B0'
        data_block: 数据块内容，如 b'(00000000)' 或 b'C.9.66()'
        无数据块时（如 B0）不带 STX
        """
        if data_block:
            body = cmd + b'\x02' + data_block + b'\x03'   # CMD + STX + DATA + ETX
        else:
            body = cmd + b'\x03'                          # CMD + ETX
        frame = b'\x01' + body + bytes([self._bcc(body)])
        return frame

    def _parse_data_block(self, frame: bytes) -> Tuple[str, str]:
        """从响应帧中提取数据块，返回 (obis, value)；多值数据项用 ';' 分隔"""
        # 定位 STX (0x02) 和 ETX (0x03)
        stx = frame.find(b'\x02')
        etx = frame.find(b'\x03')
        if stx == -1 or etx == -1:
            return '', ''
        block = frame[stx+1:etx]
        text = block.decode('ascii', errors='ignore')
        # 格式: OBIS(值) 或 OBIS(值*单位)，多值形如 OBIS(值1)(值2)...
        match = re.match(r'([\w\.]+)', text)
        if not match:
            return text, ''
        obis = match.group(1)
        values = re.findall(r'\(([^)]*)\)', text[len(obis):])
        return obis, ';'.join(values)

    # ---------- 高层交互步骤 ----------
    def identify(self) -> Tuple[str, str, str]:
        """
        步骤1：发送 /?! 并解析标识应答
        返回: (制造商, 波特率标识, 设备ID)
        """
        self._open(self.initial_baud)
        self._send(b'/?!\r\n')
        resp = self._read_line()
        # pyserial 已剥离校验位，数据为纯 7 位 ASCII
        resp = resp.rstrip(b'\r\n')
        if not resp.startswith(b'/'):
            raise ValueError(f"无效标识响应: {resp!r}")
        # 格式: /AAA B \ ID
        payload = resp[1:]          # 去掉 '/'
        # 分离头部和 ID
        if b'\\' in payload:
            head, dev_id = payload.split(b'\\', 1)
        else:
            head = payload
            dev_id = b''
        manufacturer = head[:3].decode()
        baud_id = head[3:4].decode() if len(head) > 3 else '0'
        device_id = dev_id.decode(errors='ignore')
        return manufacturer, baud_id, device_id

    def switch_baud_and_select_protocol(self, baud_id: str) -> Optional[bytes]:
        """
        步骤2：切换波特率并发送协议选择
        返回电表的首次响应（可能为数据帧或 ACK）
        """

        # 发送 ACK + 协议控制字符串 "0<波特率标识>1\r\n"
        # 协议控制串由电表返回的波特率标识决定，例如电表返回 4 -> 发送 "041"
        protocol_str = f'0{baud_id}1\r\n'.encode()
        self._send(b'\x06' + protocol_str)
        time.sleep(0.3)
        # 切换波特率为9600
        new_baud = self.BAUD_MAP.get(baud_id, 300)
        log_info(f"切换波特率: {new_baud}")
        if new_baud != self.initial_baud:
            self._open(new_baud)

        time.sleep(0.3)
        # 接收响应（某些电表会自动上传一个数据帧）
        return self._read_frame()

    def send_password(self, password: str = '00000000') -> bool:
        """
        步骤3：密码校验
        返回 True 表示收到 ACK
        """
        data = f'({password})'.encode()
        frame = self._build_command_frame(b'P1', data)
        self._send(frame)
        resp = self._read_frame()
        return resp == b'\x06'

    def read_obis(self, obis_code: str) -> str:
        """
        外部使用：连接电表 -> 读取单个 OBIS 值 -> 断开会话
        返回读取到的值（字符串），失败返回空字符串
        """
        self.iec_connect()
        try:
            return self._read_obis(obis_code)
        finally:
            self.iec_disconnect()

    def _read_obis(self, obis_code: str) -> str:
        """
        内部使用：在已建立的会话中读取单个 OBIS 值，不负责连接/断开
        返回读取到的值（字符串），失败返回空字符串
        """
        data = f'{obis_code}()'.encode()
        # 点分格式(0.9.1等)用 R1；4位数据标识(1101、2616等)用 R6
        if '.' in obis_code:
            cmd = b'R1'
        else:
            cmd = b'R6'
        frame = self._build_command_frame(cmd, data)
        self._send(frame)
        resp = self._read_frame()
        if resp and resp[0] in (0x01, 0x02):
            _, value = self._parse_data_block(resp)
            return value
        return ''

    def read_obis_list(self, obis_list: List[str]) -> Dict[str, str]:
        """
        根据 OBIS 列表自动逐一读取，返回 {obis: value}
        """
        self.iec_connect()
        results = {}
        try:
            for obis in obis_list:
                value = self._read_obis(obis)
                results[obis] = value
                kf_info(f"读取结果: {obis} = {value}")
            return results
        finally:
            self.iec_disconnect()

    def set_obis(self, obis_code: str, value: str) -> bool:
        """
        外部使用：连接电表 -> 写入单个 OBIS 值 -> 断开会话
        返回 True 表示收到 ACK 写入成功
        """
        self.iec_connect()
        try:
            return self._set_obis(obis_code, value)
        finally:
            self.iec_disconnect()

    def _set_obis(self, obis_code: str, value: str) -> bool:
        """
        内部使用：在已建立的会话中写入单个 OBIS 值，不负责连接/断开
        返回 True 表示收到 ACK 写入成功
        """
        data = f'{obis_code}({value})'.encode()
        # 点分格式(0.9.1等)用 W1；4位数据标识(1101、2616等)用 W6
        if '.' in obis_code:
            cmd = b'W1'
        else:
            cmd = b'W6'
        frame = self._build_command_frame(cmd, data)
        self._send(frame)
        resp = self._read_frame()
        return resp == b'\x06'

    def set_obis_dict(self, data_dict: Dict[str, str]) -> Dict[str, bool]:
        """
        批量写入：传入 {obis: 写入数据} 字典
        返回 {obis: 是否写入成功}
        """
        self.iec_connect()
        results = {}
        try:
            for obis, value in data_dict.items():
                result = self._set_obis(obis, value)
                results[obis] = result
                if result:
                    status = "成功"
                else:
                    status = "失败"
                message = f"写入结果: {obis} = {value} -> {status}"
                kf_info(message)
            return results
        finally:
            self.iec_disconnect()

    def iec_disconnect(self):
        """步骤5：发送 B0 结束通信并关闭串口"""
        self._connect_phase = True
        b0_sent = False
        try:
            frame = self._build_command_frame(b'B0')
            self._send(frame)
            time.sleep(0.5)
            b0_sent = True
            kf_info("==================电表连接断开==================")
        except Exception as e:
            log_info(f"发送 B0 失败: {e}")
        finally:
            self._connect_phase = False
            if self.ser and self.ser.is_open:
                self.ser.close()
            if not b0_sent:
                log_info("==================连接未断开, 强制关闭串口==================")

    def close(self):
        """紧急关闭串口"""
        if self.ser and self.ser.is_open:
            self.ser.close()

    # ---------- 连表 ----------
    def iec_connect(self, password: str = '00000000', max_rounds: int = 3) -> Tuple[str, str, str]:
        """
        连接电表：识别 -> 切换波特率/选择协议 -> 密码校验
        - 单轮内密码失败重试 3 次（间隔 1s，应对电表忙时短暂不响应）
        - 整轮失败后从头重新握手，最多 max_rounds 轮（应对 ACK 051 协议选择丢失，
          此时电表未进入编程模式，原地重发 P1 无用，必须回到 /?! 重新同步）
        返回 (制造商, 波特率标识, 设备ID)
        """
        log_info("==================开始连接电表==================")
        self._connect_phase = True
        try:
            round_now = 1
            password_ok = False
            while round_now <= max_rounds and not password_ok:
                # 每一轮都从 /?! 开始完整握手（identify 内部会重开串口并清空缓冲）
                man, baud_id, dev_id = self.identify()
                log_info(f"设备识别: 制造商={man}, 波特率标识={baud_id}, ID={dev_id}")

                # 步骤2 切换波特率并发送协议选择
                # 这里需要确定是先发协议选择还是先切换波特率再发协议选择
                resp = self.switch_baud_and_select_protocol(baud_id)
                if resp:
                    log_info(f"协议选择响应：{resp.hex()}")
                else:
                    log_info("协议选择响应：无")

                # 步骤3 密码校验（同一轮内重试3次，必须尽快发送，避免电表会话超时）
                pwd_try = 1
                while pwd_try <= 3 and not password_ok:
                    if self.send_password(password):
                        password_ok = True
                    elif pwd_try < 3:
                        time.sleep(1)
                    pwd_try = pwd_try + 1

                # 这一轮没连上：协商可能已断，回到 /?! 重新握手
                if not password_ok:
                    log_info(f"第{round_now}/{max_rounds}轮连接失败, 从头重新握手")
                    round_now = round_now + 1
                    if round_now <= max_rounds:
                        time.sleep(0.5)

            if not password_ok:
                time.sleep(0.5)
                raise RuntimeError("密码校验失败")
            log_info("密码校验成功")
            kf_info("==================电表连接成功==================")
            return man, baud_id, dev_id
        finally:
            self._connect_phase = False

    # ---------- 一键抄表接口 ----------
    def auto_read(self, obis_list: List[str], password: str = '00000000') -> Dict[str, str]:
        """
        一键完成 Mode E 完整流程并读取指定 OBIS 列表
        返回 {obis: value}
        """
        try:
            self.iec_connect(password)
            values = self.read_obis_list(obis_list)
            return values
        finally:
            self.iec_disconnect()
            log_info("会话结束")


# ==================== 使用示例 ====================
if __name__ == '__main__':
    # 需要读取的 OBIS 列表（根据实际需求修改）
    OBIS_TO_READ = [
        '0.2.0',      # 总正向有功电量
        '0.6.0',      # 费率1 正向有功电量
        '0.6.1',      # 费率2 正向有功电量
        '0.9.1',      # 当前时间
        '0.9.2',      # 日期
        '0.9.5',      # 设备地址 (制造商特定)
        'C.9.66',     # 自定义参数
    ]

    meter = IEC62056ModeE(port='COM3')        # Windows 示例
    # meter = IEC62056ModeE(port='/dev/ttyUSB0')  # Linux 示例

    # data = meter.auto_read(["C.9.66"])
    data = meter.auto_read(OBIS_TO_READ)
    # data = meter.read_obis("C.9.66")
    print("\n=== 抄表结果 ===")
    for obis, val in data.items():
        print(f"{obis:10s} : {val}")
