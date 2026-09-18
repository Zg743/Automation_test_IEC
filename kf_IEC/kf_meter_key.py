# -*- coding: utf-8 -*-
"""由 11 位表号生成 STS 密钥（MeterKey）。

算法（反推自 表号与密钥.xlsx，已逐位验证）：

    PAN  = "00727" + 表号                 # IIN 600727 的后 5 位 + 11 位表号
    CB   = "2999152012FF0001"             # KT=2,SGC=999152,TI=01,KRN=2,KEN=FF,"0001"
    X    = PAN XOR CB
    密钥 = STA_encrypt(~X, VK)             # VK = B8123456C7D9EFAB, STS STA 分组密码

只需传入一个 11 位表号即可得到密钥。

用法：
    from gen_meter_key import generate_key
    generate_key("22000470462")        # -> '2D26CA6943E2FF7D'

命令行：
    python gen_meter_key.py 22000470462
"""
import sys

MASK64 = (1 << 64) - 1

# ---- 本工具固定的参数 ----
VK_HEX = "B8123456C7D9EFAB"     # 售卖密钥（Vending Key）
CB_HEX = "2999152012FF0001"     # 控制块（KT+SGC+TI+KRN+KEN+"0001"）
PAN_PREFIX = "00727"            # IIN 最低 5 位

# ---- 真实 STSA 表 ----
_SUB1 = [14, 10, 7, 9, 12, 3, 2, 5, 13, 0, 15, 1, 4, 8, 6, 11]
_SUB2 = [12, 8, 2, 13, 7, 6, 1, 3, 11, 5, 9, 15, 0, 4, 10, 14]
_PERM = [55, 42, 10, 18, 24, 21, 44, 35, 2, 22, 56, 43, 27, 58, 9, 50,
         6, 36, 12, 61, 37, 38, 53, 16, 62, 3, 7, 4, 32, 20, 63, 25,
         51, 52, 54, 33, 49, 19, 46, 29, 48, 31, 23, 30, 41, 28, 13, 5,
         40, 60, 39, 11, 15, 17, 1, 0, 57, 34, 59, 8, 47, 14, 45, 26]


def _rotl64(x, n=1):
    return ((x << n) & MASK64) | (x >> (64 - n))


def _rotr64(x, n=1):
    return (x >> n) | ((x & ((1 << n) - 1)) << (64 - n))


def _sta_encrypt(block64, key64):
    """STS 的 STA 分组密码（16 轮）。"""
    key = _rotr64((~key64) & MASK64, 12)      # 密钥对齐
    d = block64
    for _ in range(16):
        # 代换（按密钥半字节选表）
        sub = 0
        for i in range(16):
            nib = (d >> (4 * i)) & 0xF
            sub |= (_SUB1 if not (key >> (4 * i)) & 8 else _SUB2)[nib] << (4 * i)
        # 置换
        perm = 0
        for i in range(64):
            if (sub >> i) & 1:
                perm |= 1 << _PERM[i]
        d = perm
        key = _rotl64(key, 1)
    return d


def generate_key(meter_no):
    """输入 11 位表号，返回 16 位十六进制密钥字符串。

    meter_no: 11 位数字（str 或 int）
    """
    meter_no = str(meter_no).strip()
    if len(meter_no) != 11 or not meter_no.isdigit():
        raise ValueError("表号必须为 11 位数字，实际: %r" % meter_no)
    pan = int(PAN_PREFIX + meter_no, 16)
    x = pan ^ int(CB_HEX, 16)
    return "%016X" % _sta_encrypt((~x) & MASK64, int(VK_HEX, 16))


def _selftest():
    # 来自 表号与密钥.xlsx 的验证向量
    vectors = [
        ("22000470462", "2D26CA6943E2FF7D"),
        ("22000470355", "AF43AB3B298A01A5"),
        ("22000470421", "9C7DEF6B55495450"),
        ("22000470652", "89E1D15E2164CB3E"),
        ("22000470330", "0345F1AC7732A25E"),
        ("22000470348", "5C7FFA048D089311"),
    ]
    for mn, exp in vectors:
        got = generate_key(mn)
        assert got == exp, (mn, got, exp)
    print("[selftest] %d 个向量全部通过" % len(vectors))


if __name__ == "__main__":
    # if len(sys.argv) == 1:
    #     _selftest()
    #     print("用法: python gen_meter_key.py <11位表号>")
    # elif sys.argv[1] in ("-h", "--help"):
    #     print(__doc__)
    # else:
    #     print(generate_key(sys.argv[1]))

    result = generate_key(22000670335)
    print(result)
