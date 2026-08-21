import pymysql


conn = pymysql.connect(
    host='60.205.216.142',
    port=3306,
    user='remote_wh',
    password='qwerty@123456!',
    database='wh_meter_sts_test',
    charset='utf8'
)
cu = conn.cursor()
# cursor.execute("SELECT VERSION()")
cu.execute("SHOW DATABASES") # 实际返回结果是数字
result2 = cu.fetchall() # 取命令执行结果的真实返回值，是一个元组
print("当前数据库：")
for db in result2:
    print(db[0])

cu.execute("USE wh_meter_sts_test")
cu.execute("SHOW TABLES")
result3 = cu.fetchall()
print("当前数据表：")
for a in result3:
    print(a[0])

cu.execute("DESC t_sts_key_info")
print("当前表字段结构：")
for b in cu.fetchall():
    print(b[0])
cu.execute("SELECT id,final_meter_num,decoder_key,order_no,is_used FROM t_sts_key_info WHERE final_meter_num = 22000470496")
print("读取结果")
for c in cu.fetchall():
    print(c[0])
conn.close()