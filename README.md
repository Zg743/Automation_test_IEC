# Automation_test_IEC
自动化测试框架及脚本_IEC版本
您可以...
(还没想好写什么)


使用指南:

1. 当前已实现且直接使用的接口:

   导入方式（一条导入即可使用下列全部接口）:

       from kf_IEC import *

   ---

   ### 一、电表通信类 IEC62056ModeE（kf_IEC/kf_iec.py）

   **IEC62056ModeE(port, initial_baud=300, timeout=2)**
   - 含义：创建 Mode E 抄表客户端
   - 传参：
     - port：str，串口号，如 "com3"
     - initial_baud：int，初始波特率，默认 300
     - timeout：float，串口读取超时（秒），默认 2
   - 返回：客户端实例
   - 示例：`conn = IEC62056ModeE("com3")`

   **iec_connect(password='00000000', max_rounds=3)**
   - 含义：连接电表，依次完成 设备识别 -> 切换波特率/选择协议 -> 密码校验
   - 双层重试机制：
     - 内层：同一轮内 P1 密码失败重试 3 次（间隔 1s，应对电表忙如零点冻结）
     - 外层：整轮失败后回到 /?! 从头重新握手，最多 max_rounds 轮
       （应对 ACK 051 协议选择丢失导致电表未进入编程模式，此时重试 P1 无用）
   - 传参：password：str，默认 '00000000'；max_rounds：int，默认 3
   - 返回：(制造商, 波特率标识, 设备ID) 三元组，如 ('GML', '5', '2DTSY5558ver3.4')
   - 异常：全部轮次失败后抛出 RuntimeError("密码校验失败")
   - 注意：连接成功后必须调用 iec_disconnect() 断开，两者成对使用

   **iec_disconnect()**
   - 含义：发送 B0 结束通信并关闭串口；B0 后等待 0.5s 让电表完全退出编程模式
   - 传参：无
   - 返回：无

   **read_obis(obis_code)**
   - 含义：读取单个 OBIS 值，内部自动 连表 -> 读取 -> 断开
   - 传参：obis_code：str，OBIS 码。点分格式（如 "0.9.1"）自动用 R1 命令；4 位数据标识（如 "1101"）自动用 R6 命令
   - 返回：str，读取到的值；失败返回空字符串 ''

   **read_obis_list(obis_list)**
   - 含义：批量读取多个 OBIS 值，整个过程只连接/断开一次
   - 传参：obis_list：List[str]，OBIS 码列表，如 ["0.9.2", "0.9.1", "15.8.0"]
   - 返回：Dict[str, str]，{obis: 读取到的值}

   **set_obis(obis_code, value)**
   - 含义：写入单个 OBIS 参数，内部自动 连表 -> 写入 -> 断开
   - 传参：obis_code：str，OBIS 码；value：str，要写入的数据。命令规则与读取对应：点分格式用 W1，4 位数据标识用 W6
   - 返回：bool，True 表示收到 ACK 写入成功

   **set_obis_dict(data_dict)**
   - 含义：批量写入多个 OBIS 参数，整个过程只连接/断开一次
   - 传参：data_dict：Dict[str, str]，{obis: 要写入的数据}
   - 返回：Dict[str, bool]，{obis: 是否写入成功}；判断是否全部成功可用 `all(result.values())`

   **_read_obis(obis_code)**
   - 含义：在已建立的会话中读取单个 OBIS 值（内部方法，不负责连接/断开）
   - 前提：必须已调用 iec_connect() 且尚未 iec_disconnect()
   - 传参/返回：与 read_obis 相同
   - 用途：需要自己控制连接时机时使用，例如一次会话内先读后写，减少重连次数

   **_set_obis(obis_code, value)**
   - 含义：在已建立的会话中写入单个 OBIS 参数（内部方法，不负责连接/断开）
   - 前提：同 _read_obis
   - 传参：与 set_obis 相同
   - 返回：bool，True 表示写入成功

   **auto_read(obis_list, password='00000000')**
   - 含义：一键抄表，连表 -> 逐个读取列表内所有 OBIS -> 断开，一步完成
   - 传参：obis_list：List[str]；password：str，默认 '00000000'
   - 返回：Dict[str, str]，{obis: 读取到的值}

   **close()**
   - 含义：紧急关闭串口（不发送 B0），异常情况下兜底使用
   - 传参：无　返回：无

   典型用法一（简单读写，每次自动连断）:

       conn = IEC62056ModeE("com3")
       value = conn.read_obis("0.9.1")
       ok = conn.set_obis("0.9.1", "120000")

   典型用法二（一次会话内先读后写，只连一次表）:

       conn = IEC62056ModeE("com3")
       conn.iec_connect()
       try:
           t = conn._read_obis("0.9.1")
           ok = conn._set_obis("0.9.1", "120000")
       finally:
           conn.iec_disconnect()

   ---

   ### 二、时间/日期工具（kf_IEC/kf_iec_datetime.py）

   **next_boundary_time(time_str, period, offset)**
   - 含义：将时间向上取整到下一个周期边界，再加偏移秒
   - 传参：time_str：str，"HH:MM:SS"；period：str，周期，支持 '30min'/'30m'/'1h'/'30s'/'30'（纯数字按分钟）；offset：int，偏移秒，可为负
   - 返回：str，"HHMMSS"
   - 示例：`next_boundary_time('17:12:17', '30min', -3)` -> `'172957'`

   **midnight_time(offset)**
   - 含义：0 点加偏移秒，跨天自动回绕（-3s 显示为前一天 23:59:57）
   - 传参：offset：int，偏移秒
   - 返回：str，"HHMMSS"
   - 示例：`midnight_time(-3)` -> `'235957'`

   **last_day_of_month(date_str, offset_months=0)**
   - 含义：获取当月（或偏移后月份）最后一天（自动处理大小月/闰年/跨年）
   - 传参：date_str：str，"YY-MM-DD"；offset_months：int，默认 0，=1 未来一月，=-1 过去一月
   - 返回：str，"YYMMDD"
   - 示例：`last_day_of_month('26-09-01')` -> `'260930'`；`last_day_of_month('26-09-01', 1)` -> `'261031'`

   **first_day_of_month(date_str, offset_months=0)**
   - 含义：获取当月（或偏移后月份）第一天，跨年自动进退位
   - 传参：date_str：str，"YY-MM-DD"；offset_months：int，默认 0
   - 返回：str，"YYMMDD"
   - 示例：`first_day_of_month('26-09-03')` -> `'260901'`；`first_day_of_month('26-09-03', 1)` -> `'261001'`

   **format_date(date_str)**
   - 含义：日期格式转换
   - 传参/返回：str 'YYMMDD' -> str 'YY-MM-DD'
   - 示例：`format_date('260930')` -> `'26-09-30'`

   **format_time(time_str)**
   - 含义：时间格式转换
   - 传参/返回：str 'HHMMSS' -> str 'HH:MM:SS'
   - 示例：`format_time('172957')` -> `'17:29:57'`

   ---

   ### 三、电能值拆分（kf_IEC/kf_iec_energy.py）

   **split_value(value_str)**
   - 含义：把形如 '000073.90*kWh' 的数据值拆分为数字和单位
   - 传参：value_str：str，IEC 62056 数据值字符串
   - 返回：Dict，{'number': float, 'unit': str}；无单位时 unit 为 ''；整数部分前导零和小数末尾零会被去掉
   - 示例：`split_value('000073.90*kWh')` -> `{'number': 73.9, 'unit': 'kWh'}`

   **split_digits(value_str)**
   - 含义：把数据值拆成"去掉小数点的数字串"和"单位"，数字保持原始字符串格式（不去前导零、不转 float）
   - 传参：value_str：str，数据值字符串，带不带 '*单位' 都可以
   - 返回：Tuple (digits, unit)；无单位时 unit 为 ''
   - 示例：`split_digits('000073.90*kWh')` -> `('00007390', 'kWh')`；`split_digits('000073.90')` -> `('00007390', '')`

   ---

   ### 四、打印与日志（kf_IEC/kf_iec_info.py）

   日志按天分目录存放，路径格式：`Log/YYMMDD/YYYYMMDD_HH.log`
   （如 26年8月26日的日志在 `Log/260826/20260826_13.log`），
   固定在项目根目录下，与脚本运行位置无关；跨天时自动切换到新目录。

   **info(*args, **kwargs)**
   - 含义：仅控制台打印，用法与 print 完全相同

   **log_info(*args, **kwargs)**
   - 含义：仅写入日志文件，不在控制台打印（连接/断开过程的报文就用它记录）

   **kf_info(*args, **kwargs)**
   - 含义：控制台打印 + 写日志同时进行，测试脚本中推荐统一使用它代替 print

   ---

   ### 五、测试脚本标签与按标签运行（kf_IEC/kf_iec_tag.py）

   **@kf_tag(*tags)**
   - 含义：装饰器，写在测试函数定义的上一行，给该函数打标签并注册到全局注册表
   - 传参：tags：一个或多个标签字符串，一般第一个写同类脚本的公共前缀，最后一个写脚本自己的全名
   - 返回：原函数（不改变函数本身）
   - 示例：

         @kf_tag("rate_switch", "rate_switch_1")
         def rate_switch_1():
             ...

   **run_by_tag(tag)**
   - 含义：运行所有标签中包含 tag 的已注册脚本，按注册顺序依次执行
   - 传参：tag：str，标签名。传完整标签（如 'rate_switch_1'）只运行这一个脚本；传公共前缀标签（如 'rate_switch'）会运行所有带该标签的脚本
   - 返回：List[str]，实际运行的函数名列表；没有匹配时打印提示并返回空列表
   - 失败隔离：单个脚本报错（含测试 Fail）会被捕获，打印 'xxx脚本测试Fail'、失败原因和完整错误位置（含出错文件与行号的 traceback）后继续下一个脚本
   - 注意：只对"已 import 过的文件"生效，适合单文件内直接运行

   **kf_test_fail(script_name)**
   - 含义：判定当前脚本测试失败，抛出异常让脚本立即报错退出；批量运行时由 run_by_tag 统一打印 Fail 并继续下一个脚本
   - 传参：script_name：str，脚本名，用于拼接 Fail 信息 'xxx脚本测试Fail'
   - 配套状态变量（在脚本函数内维护）：
     - status：整个脚本的测试结果，默认 True
     - step_status：步骤执行结果，每个 step 结束后判断，某一步不符合预期就置为 False
     - 固定写法：步骤不符合预期时 step_status = False；然后 if not step_status: status = False；
       最后 if not status: kf_test_fail("脚本名")

   **run_folder_by_tag(folder, tag)**
   - 含义：跨文件按标签运行：自动导入 folder 目录下的全部 .py 文件（各文件里的 @kf_tag 随导入自动注册），再按 tag 筛选运行
   - 传参：folder：str，脚本所在目录；tag：str，规则同 run_by_tag
   - 返回：List[str]，实际运行的函数名列表
   - 说明：目录下以 __ 开头的文件（如 __init__.py）会被跳过；各脚本文件自己的运行代码必须写在 if __name__ == '__main__': 里，防止被导入时误执行

   跨文件推荐用法：每个脚本文件里用 @kf_tag 打好标签，然后用统一入口 CIU/run_scripts.py 运行：

       python run_scripts.py

   修改 run_scripts.py 里的 tag 字符串即可切换"只跑单个脚本 / 跑一类脚本"。

   ---

   ### 六、弹窗工具（kf_IEC/kf_popup.py）

   基于 tkinter，无需额外安装依赖。三种弹窗对应三种交互需求：

   **kf_alert(title, message)**
   - 含义：非阻塞警告框，弹出后脚本照常运行，不等待用户
   - 特性：新的 kf_alert/kf_prompt/kf_inquire 弹出时，上一个 kf_alert 自动关闭（令牌机制）
   - 返回：无
   - 示例：`kf_alert("提示", "正在执行第3步，请勿断电...")`

   **kf_prompt(title, message)**
   - 含义：阻塞提示框，脚本暂停，点击"确定"后才继续
   - 返回：无
   - 示例：`kf_prompt("操作提示", "请将串口切换到 COM5，然后点确定")`

   **kf_inquire(title, message, ok_text="确定", cancel_text="取消")**
   - 含义：阻塞询问框，可自定义两个按钮的文本；点击确定按钮返回 True，取消（或直接关窗）返回 False
   - 返回：bool
   - 示例：

        if not kf_inquire("derusting_1_1", "水表是否动阀", "动了", "没动"):
            kf_test_fail("derusting_1_1")   # 点"没动"判定失败

   ---

   ### 七、心跳模块（kf_IEC/kf_07_heartbeat.py）

   场景：水表/电表会定时休眠，为避免手动唤醒，可在连接后启动一个后台线程按固定间隔发送心跳帧。

   **Heartbeat(ser, lock, interval=5, frame=DEFAULT_HEARTBEAT_FRAME, name="kf_heartbeat")**
   - 含义：固定间隔的心跳发送器
   - 传参：
     - ser：serial.Serial，与 IEC62056ModeE 共享的串口对象（conn.ser）
     - lock：threading.Lock，与 conn.io_lock 共享的互斥锁，保证心跳与 IEC 收发串行、帧不交错
     - interval：float，发送间隔（秒），默认 5
     - frame：bytes，心跳帧内容，默认 `68 AA*6 68 13 00 DF 16`（645/97 风格读通讯地址）
   - 方法：
     - start()：启动后台守护线程，主进程退出自动结束
     - stop(timeout=2)：停止心跳线程并等待退出
     - send_once()：立即手动发送一次（可用于唤醒后首次衔接）

   用法示例：

       conn = IEC62056ModeE("com3")
       conn.iec_connect()
       hb = Heartbeat(ser=conn.ser, lock=conn.io_lock, interval=5)
       hb.start()
       try:
           value = conn._read_obis("0.9.1")   # 会话内读表，与心跳自动串行
           ...
       finally:
           hb.stop()
           conn.iec_disconnect()

   - 注意：串口字节宽度（7E1/8E1/8N1）由调用方自行切换管理，心跳只负责发送原始字节
   - 提示：会话已建立时应使用内部方法 _read_obis/_set_obis（只读写、不接管连接），不要用 read_obis（它内部会再次连接并断开，与心跳冲突）

   ---

   ### 八、STS 充值 Token（kf_IEC/sts_token_recharge.py）

   符合 IEC 62055-41:2018 (EA07 / STA) 标准的 STS Token 生成/解码。

   **generate_token(key_hex, tid, subclass, amount, token_class=0, rnd=5)**
   - 含义：生成充值 Token（固定 Class=0 TransferCredit，RND=5）
   - 传参：
     - key_hex：str，16 位十六进制密钥（64-bit DecoderKey），如 'E7B21AA9EC929C96'
     - tid：int，0..16777215
     - subclass：int，充值类型。0=电用量 1=水用量 2=气用量 3=时间；4=电金额 5=水金额 6=气金额 7=时间金额
     - amount：float，充值量（主单位，如 kWh / m3）；subclass 0-3 的计量单位为主单位的 0.1（向上取整对客户有利）
   - 返回：str，充值 Token（不带空格）
   - 示例：`generate_token('E7B21AA9EC929C96', 6675056, 1, 1.0)` -> `'63525115892327740484'`

   **decode_token(token_64, key_hex)**
   - 含义：解码 Token，校验 CRC 并还原各字段
   - 返回：Dict，包含 class/subclass/rnd/tid/amount_field/crc_ok/units/amount

   **generate_tid()**
   - 含义：以电脑当前时间为基准生成 TID（int，24 位 0..16777215）
   - 算法：自 2014-01-01 起经过的分钟数，取后 24 位（每分钟 TID+1）
   - 返回：int
   - 示例：`tid = generate_tid()`；配套使用 `generate_token(key, generate_tid(), 1, amount)`

   命令行直接使用：

       python sts_token_recharge.py <key_hex> <tid> <subclass> <amount>

   算法已通过 STS Simulator 对照验证（self-test 内建断言）。 
