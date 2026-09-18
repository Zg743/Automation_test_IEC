"""STS 预付费充值凭证（Token）生成/解码工具。

    这是做"预付费"表计（电表/水表/气表）充值用的：
    用户交钱后，后台按固定规则算出一串数字（Token），
    往表里输入这串数字，表就按规定给你充值。

    规则遵循国际标准 IEC 62055-41:2018（EA07 / STA），
    用的是密钥(DecoderKey)加密，防止别人随便算出充值码。

    命令行用法：
        python kf_sts_token.py <key_hex> <tid> <subclass> <amount>
      key_hex  : 16 位十六进制密钥（64位），例如 E7B21AA9EC929C96
      tid      : 十进制的表计编号，范围 0..16777215
      subclass : 充值类型
                 0=电量(kWh)  1=水量(m3)  2=气量(m3)  3=时间(分钟)
                 4=电费      5=水费      6=气费      7=时间金额
                 （0-3 是"充了多少量"，4-7 是"充了多少钱"，钱按 1/100000 单位计）
      amount   : 充值数额，按主单位输入（如 5 立方米就是 5）
                 subclass 为 0-3 时，内部按主单位的 0.1 为基本计量单位，
                 向上取整（取整按对用户有利的原则处理）

    Class 固定为 0（即"充值得额"TransferCredit 类型）。
    RND：subclass 0-3 固定为 5；subclass 4-7（货币）不使用 RND，令牌内该 4 位恒 0
         （与标准模拟器实测一致）。
    CRC：subclass 0-3 用普通 CRC（IEC 62055-41 6.3.7）；subclass 4-7（货币信用）
         用 CRC_C（6.3.22）——在左补零后的 56 位之后追加一个字节 0x01 再计算。

    算法和查表结果已经对照标准模拟器 STSSimulator 验证过：
        水量 sub=1 amount=1 m3        -> Token 63525115892327740484
        电量 sub=0 amount=10 kWh      -> Token 35500312443047940328
        电费 sub=4 amount=100 (CRC_C) -> Token 07420412750539184100
"""

import math
import sys
from datetime import datetime

SUB1 = [14, 10, 7, 9, 12, 3, 2, 5, 13, 0, 15, 1, 4, 8, 6, 11]
SUB2 = [12, 8, 2, 13, 7, 6, 1, 3, 11, 5, 9, 15, 0, 4, 10, 14]
PERM = [55, 42, 10, 18, 24, 21, 44, 35, 2, 22, 56, 43, 27, 58, 9, 50,
        6, 36, 12, 61, 37, 38, 53, 16, 62, 3, 7, 4, 32, 20, 63, 25,
        51, 52, 54, 33, 49, 19, 46, 29, 48, 31, 23, 30, 41, 28, 13, 5,
        40, 60, 39, 11, 15, 17, 1, 0, 57, 34, 59, 8, 47, 14, 45, 26]

SUB1_S = [12, 10, 8, 4, 3, 15, 0, 2, 14, 1, 5, 13, 6, 9, 7, 11]
SUB2_S = [6, 9, 7, 4, 3, 10, 12, 14, 2, 13, 1, 15, 0, 11, 8, 5]
PERM_S = [29, 27, 34, 9, 16, 62, 55, 2, 40, 49, 38, 25, 33, 61, 30, 23,
          1, 41, 21, 57, 42, 15, 5, 58, 19, 53, 22, 17, 48, 28, 24, 39,
          3, 60, 36, 14, 11, 52, 54, 12, 31, 51, 10, 26, 0, 45, 37, 43,
          44, 6, 59, 4, 7, 35, 56, 50, 13, 18, 32, 47, 46, 63, 20, 8]

Token_class = {
    0 : "充值Token",
    1 : "非仪表特定管理",
    2 : "量表特定管理(清窃电或者是清余额)",
    3 : "预留"
}

Token_subclass_class0 = {
    0 : "电表用量",
    1 : "水表用量",
    2 : "气表用量",
    3 : "时间额度",
    4 : "电表货币",
    5 : "水表货币",
    6 : "气表货币",
    7 : "时间余额",
    8 : "保留(厂家自定义)",
    9 : "保留(厂家自定义)",
    10 : "保留(厂家自定义)",
    11 : "保留(厂家自定义)",
    12 : "保留(厂家自定义)",
    13 : "保留(厂家自定义)",
    14 : "保留(厂家自定义)",
    15 : "保留(厂家自定义)"
}

Token_subclass_class2 = {
    0 : "MaximumPowerLimit",
    1 : "清余额",
    2 : "TariffRate",
    3 : "1stSectionDecoderKey",
    4 : "2ndSectionDecoderKey",
    5 : "清窃电",
    6 : "MaxPhasePowerUnbal",
    7 : "WaterMeterFactor",
    8 : "3rdSectionDecoderKey",
    9 : "4thSectionDecoderKey",
    10 : "Extended Token Set",
    11 : "Reserved for Prop Use",
    12 : "Reserved for Prop Use",
    13 : "Reserved for Prop Use",
    14 : "Reserved for Prop Use",
    15 : "Reserved for Prop Use"
}


def crc16_sts(data_bytes, init=0xFFFF, poly=0xA001):
    """计算 STS 令牌的 16 位校验和（CRC16）。

    :param data_bytes: 待校验的字节串（令牌明文部分）
    :param init: CRC 初始值，默认 0xFFFF（标准值）
    :param poly: 多项式，默认 0xA001（标准值）
    :return: int，16 位校验值
    """
    crc = init
    for b in data_bytes:
        crc ^= b
        for _ in range(8):
            crc = ((crc >> 1) ^ poly) & 0xFFFF if crc & 1 else (crc >> 1) & 0xFFFF
    return ((crc & 0xFF) << 8) | (crc >> 8)


def crc_sts_for(subclass, bytes7):
    """按 IEC 62055-41 计算 Class 0 令牌的校验和。

    6.3.7  : 普通 CRC，对左补零后的 56 bit（7 字节）计算。
    6.3.22 : Class 0 SubClass 4-7（货币信用）使用 CRC_C —— 与 6.3.7 相同，
             但在计算前于 56 bit 值之后追加一个字节 0x01。
    """
    if 4 <= subclass <= 7:
        return crc16_sts(bytes7 + b'\x01')
    return crc16_sts(bytes7)


def rotate_left_64(x, n=1):
    """64 位整数整体循环左移 n 位（头尾相连，不是普通移位）。"""
    return ((x << n) & 0xFFFFFFFFFFFFFFFF) | (x >> (64 - n))


def rotate_right_64(x, n=1):
    """64 位整数整体循环右移 n 位（头尾相连，不是普通移位）。"""
    return (x >> n) | ((x & ((1 << n) - 1)) << (64 - n))


def sta_key_align(key64):
    """密钥对齐：先把密钥按位取反，再循环右移 12 位，得到加密真正用的轮密钥。

    这是 STA 算法的固定预处理步骤，不照做算出的结果会错。
    """
    return rotate_right_64((~key64) & 0xFFFFFFFFFFFFFFFF, 12)


def _substitute(data64, key64, sub1, sub2):
    """S 盒替换：把 64 位数据按 4 位一组（共 16 组）换表。

    每组根据密钥同位置的某一位，从 sub1、sub2 两张替换表中选一张来查。
    """
    out = 0
    for i in range(16):
        nib = (data64 >> (4 * i)) & 0xF
        table = sub1 if not (key64 >> (4 * i)) & 8 else sub2
        out |= table[nib] << (4 * i)
    return out


def _permute(data64, perm):
    """P 盒置换：把 64 位数据的每一个位按 perm 表搬到新位置。"""
    out = 0
    for i in range(64):
        if (data64 >> i) & 1:
            out |= 1 << perm[i]
    return out


def sta_encrypt(block64, key64, sub1=SUB1, sub2=SUB2, perm=PERM):
    """STA 加密：64 位明文数据块 + 密钥，加密出 64 位密文。

    核心流程：对齐密钥 -> 循环 16 轮 [S盒替换 -> P盒置换 -> 密钥左移1位]。
    """
    key = sta_key_align(key64)
    d = block64
    for _ in range(16):
        d = _permute(_substitute(d, key, sub1, sub2), perm)
        key = rotate_left_64(key, 1)
    return d


def sta_decrypt(block64, key64, sub1=SUB1, sub2=SUB2, perm=PERM):
    """STA 解密：64 位密文 + 密钥，还原出 64 位明文。

    与加密相反：先算出 16 个轮密钥，再逆序做 [逆P盒 -> 逆S盒] 各 16 轮。
    """
    inv = [0] * 64
    for i, p in enumerate(perm):
        inv[p] = i
    isub1 = [0] * 16
    for i, v in enumerate(sub1):
        isub1[v] = i
    isub2 = [0] * 16
    for i, v in enumerate(sub2):
        isub2[v] = i
    key = sta_key_align(key64)
    keys = []
    k = key
    for _ in range(16):
        keys.append(k)
        k = rotate_left_64(k, 1)
    d = block64
    for k in reversed(keys):
        d = _substitute(_permute(d, inv), k, isub1, isub2)
    return d


def insert_class_bits(data64, token_class):
    """把 2 位 Token 类别(Class)插进 64 位密文，拼成 66 位完整令牌。

    做法：把密文的第 27、28 两位"抠出来"，整体往高位挪，腾出的位置放 Class。
    """
    b28 = (data64 >> 28) & 1
    b27 = (data64 >> 27) & 1
    return ((b28 << 65) | (b27 << 64) | ((data64 >> 29) << 29)
            | (token_class << 27) | (data64 & ((1 << 27) - 1)))


def remove_class_bits(token66):
    """insert_class_bits 的逆操作：从 66 位令牌里取走 Class 位，还原 64 位密文。"""
    b28 = (token66 >> 65) & 1
    b27 = (token66 >> 64) & 1
    return ((b28 << 28) | (b27 << 27)
            | (((token66 >> 29) & ((1 << 35) - 1)) << 29)
            | (token66 & ((1 << 27) - 1)))


def amount_to_field(amount, subclass):
    """把充值量换算成令牌里的 16 位金额字段（大额拆档存储）。

    subclass 0-3（充量）：基本单位是主单位的 0.1，向上取整；
    subclass 4-7（充金额）：按 1/100000 计。值太大时按 10 的倍数分档存。
    """
    factor = 10.0 if 0 <= subclass <= 3 else 1e5
    if not (0 <= subclass <= 7):
        raise ValueError('subclass must be 0..7')
    t = max(0, int(math.ceil(amount * factor)))
    if t <= 16383:
        return t
    offset = 0
    for e in range(1, 4):
        offset += 16384 * (10 ** (e - 1))
        m = (t - 1 - offset) // (10 ** e) + 1
        if m <= 16383:
            return (e << 14) | m
    raise ValueError('amount too large')


def field_to_amount_units(field):
    """amount_to_field 的逆操作：把 16 位金额字段还原成基本单位个数。"""
    e = (field >> 14) & 3
    m = field & 0x3FFF
    if e == 0:
        return m
    offset = sum(16384 * (10 ** n) for n in range(e))
    return (10 ** e) * m + offset


def currency_amount_encode(amount):
    """Class 0 SubClass 4-7（货币）金额编码，见 IEC 62055-41 6.3.6.3。

    与 subclass 0-3 不同，货币金额的指数 e 由 5 位组成：
        e = e0 + 2*e1 + 4*e2 + 8*e3 + 16*e4   (0..31)
    其中 e0、e1 在 16 位 Amount 字段的最高两位，e2、e3、e4 在 S&E 字段
    （即原先 RND 的 4 位）里，S&E 的最高位 s 是符号（0=正，1=负）。
        Amount 字段 = (e1<<15) | (e0<<14) | m
        S&E 字段    = (s<<3) | (e4<<2) | (e3<<1) | e2
    金额换算：t = 10^e * m + Σ(2^14 * 10^(n-1), n=1..e)，向上取整。

    :return: (amount_field16, se4)
    """
    t = int(math.ceil(abs(amount) * 1e5))
    s = 1 if amount < 0 else 0
    for e in range(32):
        offset = sum(16384 * (10 ** n) for n in range(e))
        num = t - offset
        if num <= 0:
            m = 0
        else:
            m = (num + 10 ** e - 1) // (10 ** e)      # 向上取整
        if m <= 0x3FFF:
            field = (((e >> 1) & 1) << 15) | ((e & 1) << 14) | m
            se = (s << 3) | (((e >> 4) & 1) << 2) | (((e >> 3) & 1) << 1) | ((e >> 2) & 1)
            return field, se
    raise ValueError('amount too large (exceeds currency field range)')


def currency_amount_decode(field, se):
    """currency_amount_encode 的逆运算。

    :return: (amount, units, e, s)
    """
    e0 = (field >> 14) & 1
    e1 = (field >> 15) & 1
    m = field & 0x3FFF
    s = (se >> 3) & 1
    e2 = se & 1
    e3 = (se >> 1) & 1
    e4 = (se >> 2) & 1
    e = e0 + 2 * e1 + 4 * e2 + 8 * e3 + 16 * e4
    offset = sum(16384 * (10 ** n) for n in range(e))
    units = (10 ** e) * m + offset
    amount = units / 1e5
    if s:
        amount = -amount
    return amount, units, e, s


def parse_key(key_hex):
    """把 16 位十六进制密钥字符串解析成 64 位整数密钥。

    :param key_hex: str，形如 'E7B21AA9EC929C96'（开头可带 0x，大小写均可）
    :return: int，64 位密钥
    """
    s = str(key_hex).strip().lower()
    if s.startswith('0x'):
        s = s[2:]
    if len(s) != 16:
        raise ValueError('key must be 16 hex chars')
    return int(s, 16)


# TID 基准时间：2014-01-01 00:00:00（本地时区）
_TID_EPOCH = datetime(2014, 1, 1, 0, 0, 0)


def generate_tid() -> int:
    """
    以电脑当前时间为基准生成 TID（24 位，0..16777215）。
    计算方法：自 2014-01-01 起经过的分钟数，取后 24 位。
    （按每分钟 TID 加 1，约 32 年后才会用满 24 位）
    返回 int。
    示例：2026-09-03 12:00 -> 已过约 6.6M 分钟，TID 在 660 万左右
    """
    now = datetime.now()
    total_minutes = int((now - _TID_EPOCH).total_seconds() // 60)
    return total_minutes & 0xFFFFFF


def generate_token(key_hex, tid, subclass, amount, token_class=0, rnd=5):
    """
    传入密钥, TID, 充值类型(subclass), 充值量(amount), 返回充值Token(不带空格)

    subclass充值类型:
        0:电表用量,  1:水表用量,  2:气表用量,  3:时间

        4:电表金额,  5:水表金额,  6:气表金额,  7:时间金额
    :param key_hex: 密钥
    :param tid: TID
    :param subclass:充值类型
    :param amount:充值量
    :param token_class:默认值0
    :param rnd:默认值5
    :return:
    """
    key = parse_key(key_hex)
    if not 0 <= tid <= 0xFFFFFF:
        raise ValueError('tid must be 0..16777215')
    if not 0 <= subclass <= 15:
        raise ValueError('subclass must be 0..15')
    if 4 <= subclass <= 7:
        # 货币信用：用扩展指数编码，S&E 占原先 RND 的 4 位（见 6.3.6.3 / 6.3.21）
        field, used_rnd = currency_amount_encode(amount)
    else:
        field = amount_to_field(amount, subclass)
        used_rnd = rnd
    pre = (token_class << 48) | (subclass << 44) | (used_rnd << 40) | ((tid & 0xFFFFFF) << 16) | field
    bytes7 = int(bin(pre)[2:].zfill(50).zfill(56), 2).to_bytes(7, 'big')
    crc = crc_sts_for(subclass, bytes7)
    data64 = (subclass << 60) | (used_rnd << 56) | ((tid & 0xFFFFFF) << 32) | (field << 16) | crc
    enc = sta_encrypt(data64, key)
    return str(insert_class_bits(enc, token_class)).zfill(20)


def decode_token(token_64, key_hex, sub1=SUB1, sub2=SUB2, perm=PERM):
    """
    输入Token和密钥, 返回（class/subclass/rnd/tid/amount_field/crc_ok/amount）
    decode_token(token, key) → 字典（class/subclass/rnd/tid/amount_field/crc_ok/amount），带 CRC 校验
    :param token_64:
    :param key_hex:
    :param sub1:
    :param sub2:
    :param perm:
    :return:
    """
    key = parse_key(key_hex)
    t66 = int(token_64)
    if not 0 <= t66 < (1 << 66):
        raise ValueError('token out of range')
    token_class = (t66 >> 27) & 3
    data64 = remove_class_bits(t66)
    db = sta_decrypt(data64, key, sub1, sub2, perm)
    subclass = (db >> 60) & 0xF
    rnd = (db >> 56) & 0xF
    tid = (db >> 32) & 0xFFFFFF
    field = (db >> 16) & 0xFFFF
    crc_in = db & 0xFFFF
    pre = (token_class << 48) | (subclass << 44) | (rnd << 40) | (tid << 16) | field
    bytes7 = int(bin(pre)[2:].zfill(50).zfill(56), 2).to_bytes(7, 'big')
    crc_calc = crc_sts_for(subclass, bytes7)
    if 4 <= subclass <= 7:
        amount, units, exponent, sign = currency_amount_decode(field, rnd)
    else:
        units = field_to_amount_units(field)
        amount = units / 10.0
        exponent = None
        sign = 0
    return {
        'class': Token_class[token_class],
        'subclass': Token_subclass_class0[subclass],
        'rnd': rnd,
        'tid': tid,
        'amount_field': field,
        'crc_ok': crc_in == crc_calc,
        'units': units,
        'amount': amount,
        'exponent': exponent,
        'sign': sign,
    }

def generate_meter_specific(key_hex, tid, subclass, value, rnd=5):
    """Class 2 (Meter Specific Management) 令牌生成.

    Class 2 令牌位布局 (66 bit):
        Class(2) + SubClass(4) + RND(4) + TID(24) + value(16) + CRC(16)

    value 是 16 位的 Register(清余额等) 或 Pad(清窃电等) 字段。
    RND 缺省为 5,与用户约定一致;token 内部数据块:
        data64 = SubClass(4) << 60 | RND(4) << 56 | TID(24) << 32
               | value(16) << 16 | CRC(16)
    CRC 覆盖 [Class|SubClass|RND|TID|value] 共 50 bit,补位到 56 bit 计算,
    与 Class 0 的算法/填位方式一致(见 generate_token)。
    """
    key = parse_key(key_hex)
    if not 0 <= tid <= 0xFFFFFF:
        raise ValueError('tid must be 0..16777215')      # TID 24 bit 上限
    if not 0 <= subclass <= 15:
        raise ValueError('subclass must be 0..15')        # SubClass 4 bit
    if not 0 <= value <= 0xFFFF:
        raise ValueError('value must be 0..65535')        # value 16 bit
    token_class = 2
    # 50-bit 明文(CRC 待算):Class(2)<<48 | SubClass(4)<<44 | RND(4)<<40 | TID(24)<<16 | value(16)
    pre = (token_class << 48) | (subclass << 44) | (rnd << 40) | ((tid & 0xFFFFFF) << 16) | value
    # 50 bit 高位补零成 56 bit(7 字节)计算 CRC
    bytes7 = int(bin(pre)[2:].zfill(50).zfill(56), 2).to_bytes(7, 'big')
    crc = crc16_sts(bytes7)
    # 组装 64-bit 加密数据块并代入 STA 加密,最后把 Class 位插入为 66 位令牌
    data64 = (subclass << 60) | (rnd << 56) | ((tid & 0xFFFFFF) << 32) | (value << 16) | crc
    enc = sta_encrypt(data64, key)
    return str(insert_class_bits(enc, token_class)).zfill(20)


def generate_clear_credit_token(key_hex, tid, register=0, rnd=5):
    """ClearCredit 清余额令牌生成 (Class 2, SubClass = 1).

    register: 要清除的信用寄存器,见 IEC 62055-41 Table 28:
        0 = 电用量    1 = 水用量    2 = 气用量    3 = 时间信用
        4 = 电货币    5 = 水货币    6 = 气货币    0xFFFF = 清除全部
    只有 TID 和 Register 需要外部传入,RND 固定为 5。
    """
    return generate_meter_specific(key_hex, tid, 1, register, rnd)


def generate_clear_tamper_token(key_hex, tid, pad=0, rnd=5):
    """ClearTamperCondition 清窃电令牌生成 (Class 2, SubClass = 5).

    pad: Pad 字段共 16 bit,协议规定不用,恒为 0。
    只有 TID 需要外部传入,Pad 固定为 0,RND 固定为 5。
    """
    return generate_meter_specific(key_hex, tid, 5, pad, rnd)


def decode_meter_specific(token_64, key_hex, sub1=SUB1, sub2=SUB2, perm=PERM):
    """解码 Class 2 令牌,返回 {class, subclass, rnd, tid, value, crc_ok}.

    流程:66 位令牌 -> 去掉 Class 位还原 64 位 -> STA 解密 -> 拆字段:
        subclass = bit63-60, rnd = bit59-56, tid = bit55-32,
        value(Register/Pad) = bit31-16, crc = bit15-0
    并用 [Class|SubClass|RND|TID|value] 50 位重算 CRC 校验 crc_ok。
    """
    key = parse_key(key_hex)
    t66 = int(token_64)
    if not 0 <= t66 < (1 << 66):
        raise ValueError('token out of range')
    token_class = (t66 >> 27) & 3   # 66 位令牌中的 Class 位

    data64 = remove_class_bits(t66)  # 还原为 64 位加密数据块
    db = sta_decrypt(data64, key, sub1, sub2, perm)
    subclass = (db >> 60) & 0xF
    rnd = (db >> 56) & 0xF
    tid = (db >> 32) & 0xFFFFFF
    value = (db >> 16) & 0xFFFF
    if subclass == 1:
        value_result = Token_subclass_class0[value]
    else:
        value_result = value
    crc_in = db & 0xFFFF
    pre = (token_class << 48) | (subclass << 44) | (rnd << 40) | (tid << 16) | value
    bytes7 = int(bin(pre)[2:].zfill(50).zfill(56), 2).to_bytes(7, 'big')
    crc_calc = crc16_sts(bytes7)
    return {
        'class': Token_class[token_class],
        'subclass': Token_subclass_class2[subclass],
        'rnd': rnd,
        'tid': tid,
        'value': value_result,
        'crc_ok': crc_in == crc_calc,
    }



# if __name__ == '__main__':
#     assert crc16_sts(bytes.fromhex('00004A2D900FF2')) == 0x0FFA
#     assert crc16_sts(bytes.fromhex('000B19EB230100')) == 0xC207
#     s_out = sta_encrypt(0x0B19EB230100C207, 0x0ABC12DEF3456789, SUB1_S, SUB2_S, PERM_S)
#     assert insert_class_bits(s_out, 0) == 0x2C45ED1618406DF95
#     assert generate_token('E7B21AA9EC929C96', 6675056, 1, 1.0) == '63525115892327740484'
#     assert generate_token('E7B21AA9EC929C96', 6675056, 0, 10.0) == '35500312443047940328'
#     for tok, field, sub in [('63525115892327740484', 10, 1),
#                             ('35500312443047940328', 100, 0)]:
#         d = decode_token(tok, 'E7B21AA9EC929C96')
#         assert d['crc_ok'] and d['amount_field'] == field and d['subclass'] == sub
#     t = generate_tid()
#     assert isinstance(t, int) and 0 <= t <= 0xFFFFFF
#     print('self-test OK')
#     print('generate_tid ->', t)
#
#     if len(sys.argv) == 5:
#         tok = generate_token(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]))
#         print(tok)
#         print(decode_token(tok, sys.argv[1]))
#     else:
#         print('usage: python kf_sts_token.py <key_hex> <tid> <subclass> <amount>')


if __name__ == "__main__":
    meter_key = "4530EDB79B5F083D"
    tid1 = generate_tid()
    print(f"生成的tid为: {tid1}")
    tid2 = 6680788
    # clear_credit_token = generate_clear_credit_token(meter_key, tid2, 1)
    # clear_tamper_token = generate_clear_tamper_token(meter_key, tid2)
    recharge_token = generate_token(meter_key, tid2, 4, 50000)

    # print(f"生成的清余额的Token为: {clear_credit_token}")
    # print(f"生成的清窃电的Token为: {clear_tamper_token}")
    print(f"生成的充值水量的Token为: {recharge_token}")

    # print(f"生成的Token数据类型为: {type(clear_credit_token)}")

    # assert clear_credit_token == "64780804373480967093"
    # assert clear_tamper_token == "12707367341805666529"
    # assert recharge_token == "33146270756150045052"


    # 尝试反向解码:
    # 解充值Token:
    result = decode_token(recharge_token, meter_key)
    print(result)
    # 解清余额Token:
    # result = decode_meter_specific(clear_credit_token, meter_key)
    # print(result)
    # # 解清窃电Token:
    # result = decode_meter_specific(clear_tamper_token, meter_key)
    # print(result)

    # # 尝试通用解析:
    # result = decode_meter_specific(recharge_token, meter_key)
    # print("解析如下:", result)
    # print(result)

    result = decode_token("07420412750539184100", meter_key)
    print(result)