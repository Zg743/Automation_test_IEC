"""
弹窗工具：kf_alert(警告), kf_prompt(提示), kf_inquire(询问)
- kf_alert   : 非阻塞警告框，弹出后脚本继续运行，点击确定或关闭窗口后消失；
               新的 kf_alert/kf_prompt/kf_inquire 弹出时，上一个 kf_alert 自动关闭
- kf_prompt  : 阻塞提示框，点击确定后脚本才继续
- kf_inquire : 阻塞询问框，点击确定返回 True，点击取消返回 False
"""

import threading
import tkinter as tk
from tkinter import messagebox

# 警告弹窗令牌：每次创建新弹窗时递增，旧弹窗检测到令牌变化后自行关闭
_alert_token = [0]


def kf_alert(title: str, message: str):
    """
    警告弹窗：在后台线程弹出非模态窗口，脚本不会暂停。
    点击确定或关闭窗口后消失；新的弹窗弹出时上一个 kf_alert 自动关闭。
    """
    _alert_token[0] += 1
    my_token = _alert_token[0]

    def _show():
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        win = tk.Toplevel(root)
        win.title(title)
        win.attributes('-topmost', True)
        tk.Label(win, text=message, padx=20, pady=10, wraplength=500,
                 justify='left', anchor='nw').pack()
        tk.Button(win, text="确定", command=root.destroy, width=10,
                  padx=20, pady=5).pack(pady=(0, 10))
        win.protocol("WM_DELETE_WINDOW", root.destroy)

        def _check_close():
            if _alert_token[0] != my_token:
                root.destroy()
                return
            root.after(200, _check_close)

        root.after(200, _check_close)
        root.mainloop()

    threading.Thread(target=_show, daemon=True).start()


def kf_prompt(title: str, message: str):
    """
    提示弹窗：脚本暂停，点击确定后继续运行。
    弹出前会自动关闭已存在的 kf_alert 警告窗口。
    """
    _alert_token[0] += 1
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    messagebox.showinfo(title, message, parent=root)
    root.destroy()


def kf_inquire(title: str, message: str,
               ok_text: str = "确定", cancel_text: str = "取消") -> bool:
    """
    询问弹窗：脚本暂停，可自定义两个按钮的文本。
    点击"确定"(或自定义 ok_text)返回 True，点击"取消"(或自定义 cancel_text)返回 False。
    弹出前会自动关闭已存在的 kf_alert 警告窗口。

    用法示例：
        if not kf_inquire("确认", "是否继续执行下一步？"):
            kf_test_fail("rate_switch_2")
        # 自定义按钮文本
        if not kf_inquire("derusting_1_1", "水表是否动阀", "动了", "没动"):
            kf_test_fail("derusting_1_1")   # 点击"没动" -> False, 判定失败
    """
    _alert_token[0] += 1
    result = [None]

    def _on_ok():
        result[0] = True
        root.destroy()

    def _on_cancel():
        result[0] = False
        root.destroy()

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    win = tk.Toplevel(root)
    win.title(title)
    win.attributes('-topmost', True)
    win.minsize(200, 100)

    tk.Label(win, text=message, padx=20, pady=10, wraplength=500,
             justify='left', anchor='nw').pack()

    button_frame = tk.Frame(win)
    button_frame.pack(pady=(0, 10))
    tk.Button(button_frame, text=ok_text, command=_on_ok, width=10,
              padx=10, pady=5).pack(side='left', padx=5)
    tk.Button(button_frame, text=cancel_text, command=_on_cancel, width=10,
              padx=10, pady=5).pack(side='left', padx=5)

    win.protocol("WM_DELETE_WINDOW", _on_cancel)
    root.mainloop()

    return bool(result[0])


if __name__ == "__main__":
    result = kf_inquire("derusting_1_1", "水表是否动阀?", "动了", "没动")
    if not result:
        print("返回False")
    else:
        print("返回True")
