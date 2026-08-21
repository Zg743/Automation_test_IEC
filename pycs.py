data = input("待计算的字符串：")
# data = "68 74 33 10 30 12 26 68 14 0D 12 00 00 CA 00 00 00 00 00 00 00 00 00"
# data = "68 11 11 11 11 11 11 68 11 04"
data_list = data.strip().split(" ")
data_list1 = []
# print(data_list)
for a in data_list:
    data_list1.append(int(a, 16))

print(data_list1)
bytes = sum(data_list1) % 256
print(f"校验值为：{hex(bytes)}")
