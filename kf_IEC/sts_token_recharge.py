"""STS token generator per IEC 62055-41:2018 (EA07 / STA).

    python sts_token_recharge.py <key_hex> <tid> <subclass> <amount>
      key_hex  : 16 hex chars (64-bit DecoderKey), e.g. E7B21AA9EC929C96
      tid      : decimal, 0..16777215
      subclass : 0-3 kind (0=electricity kWh, 1=water m3, 2=gas m3, 3=time min)
                 4-7 currency (10^-5 base currency)
      amount   : value in the main unit (kWh / m3 / ...); for subclass 0-3 the
                 unit of credit is 0.1 of the main unit (rounds up to customer)

    Class is fixed to 0 (TransferCredit), RND fixed to 5.

    Algorithm and tables validated against STSSimulator:
        sub=1 amount=1 m3 -> 63525115892327740484
        sub=0 amount=10 kWh -> 35500312443047940328
"""

import math
import sys

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


def crc16_sts(data_bytes, init=0xFFFF, poly=0xA001):
    crc = init
    for b in data_bytes:
        crc ^= b
        for _ in range(8):
            crc = ((crc >> 1) ^ poly) & 0xFFFF if crc & 1 else (crc >> 1) & 0xFFFF
    return ((crc & 0xFF) << 8) | (crc >> 8)


def rotate_left_64(x, n=1):
    return ((x << n) & 0xFFFFFFFFFFFFFFFF) | (x >> (64 - n))


def rotate_right_64(x, n=1):
    return (x >> n) | ((x & ((1 << n) - 1)) << (64 - n))


def sta_key_align(key64):
    return rotate_right_64((~key64) & 0xFFFFFFFFFFFFFFFF, 12)


def _substitute(data64, key64, sub1, sub2):
    out = 0
    for i in range(16):
        nib = (data64 >> (4 * i)) & 0xF
        table = sub1 if not (key64 >> (4 * i)) & 8 else sub2
        out |= table[nib] << (4 * i)
    return out


def _permute(data64, perm):
    out = 0
    for i in range(64):
        if (data64 >> i) & 1:
            out |= 1 << perm[i]
    return out


def sta_encrypt(block64, key64, sub1=SUB1, sub2=SUB2, perm=PERM):
    key = sta_key_align(key64)
    d = block64
    for _ in range(16):
        d = _permute(_substitute(d, key, sub1, sub2), perm)
        key = rotate_left_64(key, 1)
    return d


def sta_decrypt(block64, key64, sub1=SUB1, sub2=SUB2, perm=PERM):
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
    b28 = (data64 >> 28) & 1
    b27 = (data64 >> 27) & 1
    return ((b28 << 65) | (b27 << 64) | ((data64 >> 29) << 29)
            | (token_class << 27) | (data64 & ((1 << 27) - 1)))


def remove_class_bits(token66):
    b28 = (token66 >> 65) & 1
    b27 = (token66 >> 64) & 1
    return ((b28 << 28) | (b27 << 27)
            | (((token66 >> 29) & ((1 << 35) - 1)) << 29)
            | (token66 & ((1 << 27) - 1)))


def amount_to_field(amount, subclass):
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
    e = (field >> 14) & 3
    m = field & 0x3FFF
    if e == 0:
        return m
    offset = sum(16384 * (10 ** n) for n in range(e))
    return (10 ** e) * m + offset


def parse_key(key_hex):
    s = str(key_hex).strip().lower()
    if s.startswith('0x'):
        s = s[2:]
    if len(s) != 16:
        raise ValueError('key must be 16 hex chars')
    return int(s, 16)


def generate_token(key_hex, tid, subclass, amount, token_class=0, rnd=5):
    """
    传入密钥, TID, 充值类型(subclass), 充值量(amount), 返回充值Token(不带空格)
    :param key_hex: 密钥
    :param tid: TID
    :param subclass:充值类型(0:电表用量, 1:水表用量,2:气表用量,3:时间,4:电表金额,5:水表金额,6:气表金额,7:时间金额)
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
    field = amount_to_field(amount, subclass)
    pre = (token_class << 48) | (subclass << 44) | (rnd << 40) | ((tid & 0xFFFFFF) << 16) | field
    bytes7 = int(bin(pre)[2:].zfill(50).zfill(56), 2).to_bytes(7, 'big')
    crc = crc16_sts(bytes7)
    data64 = (subclass << 60) | (rnd << 56) | ((tid & 0xFFFFFF) << 32) | (field << 16) | crc
    enc = sta_encrypt(data64, key)
    return str(insert_class_bits(enc, token_class))


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
    crc_calc = crc16_sts(bytes7)
    units = field_to_amount_units(field)
    divisor = 10.0 if subclass <= 3 else 1e5
    amount = units / divisor
    return {
        'class': token_class,
        'subclass': subclass,
        'rnd': rnd,
        'tid': tid,
        'amount_field': field,
        'crc_ok': crc_in == crc_calc,
        'units': units,
        'amount': amount,
    }


if __name__ == '__main__':
    assert crc16_sts(bytes.fromhex('00004A2D900FF2')) == 0x0FFA
    assert crc16_sts(bytes.fromhex('000B19EB230100')) == 0xC207
    s_out = sta_encrypt(0x0B19EB230100C207, 0x0ABC12DEF3456789, SUB1_S, SUB2_S, PERM_S)
    assert insert_class_bits(s_out, 0) == 0x2C45ED1618406DF95
    assert generate_token('E7B21AA9EC929C96', 6675056, 1, 1.0) == '63525115892327740484'
    assert generate_token('E7B21AA9EC929C96', 6675056, 0, 10.0) == '35500312443047940328'
    for tok, field, sub in [('63525115892327740484', 10, 1),
                            ('35500312443047940328', 100, 0)]:
        d = decode_token(tok, 'E7B21AA9EC929C96')
        assert d['crc_ok'] and d['amount_field'] == field and d['subclass'] == sub
    print('self-test OK')

    if len(sys.argv) == 5:
        tok = generate_token(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]))
        print(tok)
        print(decode_token(tok, sys.argv[1]))
    else:
        print('usage: python sts_token_recharge.py <key_hex> <tid> <subclass> <amount>')