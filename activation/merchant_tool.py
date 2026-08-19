#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClassTrack YRL — 商家端激活文件生成工具
========================================
独立 Tkinter GUI 工具，内置 RSA 私钥，用于：
1. 接收用户提供的硬件指纹导出字符串
2. 一键生成绑定该设备的激活文件
3. 保存为 .dat 文件，用户导入即可激活

使用方式：
  方式A（Python环境）:  python activation/merchant_tool.py
  方式B（打包exe）:    pyinstaller --onefile --windowed activation/merchant_tool.py

安全警告: 本工具包含 RSA 私钥，请妥善保管，不得随软件分发！
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

# 确保可以导入 activation 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from activation.crypto import load_private_key_from_pem
from activation.license_manager import generate_activation, decode_fingerprint

# ============================================================
# RSA 私钥（⚠️ 绝密，仅商家持有，严禁随软件分发）
# 私钥存储在 activation/private_key.pem 文件中
# 本工具仅从文件加载，不内嵌私钥
# ============================================================

def load_private_key():
    """从文件加载私钥"""
    # 优先查找同级目录下的 private_key.pem
    key_file = Path(__file__).resolve().parent / "private_key.pem"
    if not key_file.exists():
        # 也尝试查找 data 目录
        key_file = Path(__file__).resolve().parent.parent / "data" / "private_key.pem"
    if not key_file.exists():
        return None, f"未找到私钥文件\n请将 private_key.pem 放在:\n{key_file.parent}"

    try:
        pem = key_file.read_text(encoding="utf-8")
        key = load_private_key_from_pem(pem)
        return key, pem
    except Exception as e:
        return None, f"私钥加载失败: {str(e)}"


# ============================================================
# Tkinter GUI
# ============================================================
class MerchantToolApp:
    """商家端激活文件生成工具 GUI"""

    # 品牌色（与主程序马卡龙色系一致）
    BG_COLOR = "#F5F1ED"
    CARD_BG = "#FFFFFF"
    BLUE = "#7EB5D6"
    PINK = "#E8A0BF"
    GREEN = "#A8D5BA"
    TEXT = "#5D5A5A"
    TEXT_LIGHT = "#999595"
    FONT = ("Microsoft YaHei", 10)
    FONT_TITLE = ("Microsoft YaHei", 14, "bold")
    FONT_MONO = ("Consolas", 10)

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ClassTrack YRL — 商家激活文件生成工具")
        self.root.geometry("580x520")
        self.root.resizable(False, False)
        self.root.configure(bg=self.BG_COLOR)

        # 居中显示
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - 580) // 2
        y = (sh - 520) // 2
        self.root.geometry(f"+{x}+{y}")

        # 加载私钥
        self.private_key, self.private_key_pem = load_private_key()
        self.key_loaded = self.private_key is not None

        self._build_ui()

    def _build_ui(self):
        """构建界面"""
        # 主容器
        main_frame = tk.Frame(self.root, bg=self.BG_COLOR, padx=28, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ---- 标题 ----
        title_frame = tk.Frame(main_frame, bg=self.BG_COLOR)
        title_frame.pack(fill=tk.X, pady=(0, 16))

        tk.Label(
            title_frame, text="🔑", font=("Segoe UI Emoji", 28), bg=self.BG_COLOR
        ).pack()

        tk.Label(
            title_frame,
            text="ClassTrack YRL 激活文件生成工具",
            font=self.FONT_TITLE,
            fg=self.TEXT,
            bg=self.BG_COLOR,
        ).pack(pady=(4, 0))

        tk.Label(
            title_frame,
            text="商家端 · 粘贴用户机器指纹 → 生成密钥 → 复制发送",
            font=("Microsoft YaHei", 9),
            fg=self.TEXT_LIGHT,
            bg=self.BG_COLOR,
        ).pack()

        # ---- 密钥状态 ----
        status_frame = tk.Frame(main_frame, bg=self.CARD_BG, padx=14, pady=8,
                                highlightbackground="#E0DCD8", highlightthickness=1)
        status_frame.pack(fill=tk.X, pady=(0, 14))

        if self.key_loaded:
            tk.Label(status_frame, text="🔒 私钥已加载",
                     font=("Microsoft YaHei", 9, "bold"), fg="#2D6A3F",
                     bg=self.CARD_BG).pack(side=tk.LEFT)
        else:
            tk.Label(status_frame, text="⚠️ 私钥未加载，请配置私钥文件",
                     font=("Microsoft YaHei", 9, "bold"), fg="#7A2D3A",
                     bg=self.CARD_BG).pack(side=tk.LEFT)

        # ---- 输入区 ----
        input_label_frame = tk.Frame(main_frame, bg=self.BG_COLOR)
        input_label_frame.pack(fill=tk.X, pady=(0, 4))
        tk.Label(input_label_frame, text="📥 粘贴用户机器指纹：",
                 font=("Microsoft YaHei", 9, "bold"), fg=self.TEXT,
                 bg=self.BG_COLOR).pack(side=tk.LEFT)
        tk.Label(input_label_frame, text="（用户从软件激活页复制）",
                 font=("Microsoft YaHei", 8), fg=self.TEXT_LIGHT,
                 bg=self.BG_COLOR).pack(side=tk.LEFT, padx=(4, 0))

        self.input_text = tk.Text(
            main_frame, height=3, font=self.FONT_MONO,
            bg="#FAF8F5", fg=self.TEXT,
            relief="solid", borderwidth=1,
            wrap=tk.WORD, padx=10, pady=8,
        )
        self.input_text.pack(fill=tk.X, pady=(0, 14))

        # ---- 生成按钮 ----
        btn_frame = tk.Frame(main_frame, bg=self.BG_COLOR)
        btn_frame.pack(fill=tk.X, pady=(0, 14))

        self.btn_generate = tk.Button(
            btn_frame,
            text="🔐 生成激活密钥",
            font=("Microsoft YaHei", 11, "bold"),
            bg="#E8A0BF", fg="#6D3A4A",
            activebackground="#F2C8DA", activeforeground="#6D3A4A",
            relief="flat", padx=24, pady=10,
            cursor="hand2",
            command=self._on_generate,
        )
        if not self.key_loaded:
            self.btn_generate.config(state=tk.DISABLED, bg="#E0DCD8", fg="#BFBBBB")
        self.btn_generate.pack()

        # ---- 输出区 ----
        output_label_frame = tk.Frame(main_frame, bg=self.BG_COLOR)
        output_label_frame.pack(fill=tk.X, pady=(0, 4))
        tk.Label(output_label_frame, text="🔑 生成的激活密钥：",
                 font=("Microsoft YaHei", 9, "bold"), fg=self.TEXT,
                 bg=self.BG_COLOR).pack(side=tk.LEFT)
        tk.Label(output_label_frame, text="（用户粘贴到软件激活页即可）",
                 font=("Microsoft YaHei", 8), fg=self.TEXT_LIGHT,
                 bg=self.BG_COLOR).pack(side=tk.LEFT, padx=(4, 0))

        self.output_text = tk.Text(
            main_frame, height=4, font=self.FONT_MONO,
            bg="#F0F4E8", fg=self.TEXT,
            relief="solid", borderwidth=1,
            wrap=tk.WORD, padx=10, pady=8,
            state=tk.DISABLED,
        )
        self.output_text.pack(fill=tk.X, pady=(0, 14))

        # ---- 操作按钮区 ----
        action_frame = tk.Frame(main_frame, bg=self.BG_COLOR)
        action_frame.pack(fill=tk.X)

        self.btn_copy_key = tk.Button(
            action_frame,
            text="📋 复制密钥",
            font=("Microsoft YaHei", 10, "bold"),
            bg="#7EB5D6", fg="#FFFFFF",
            activebackground="#B8D8E8", activeforeground="#FFFFFF",
            relief="flat", padx=16, pady=8,
            cursor="hand2",
            state=tk.DISABLED,
            command=self._on_copy_key,
        )
        self.btn_copy_key.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_save = tk.Button(
            action_frame,
            text="💾 保存为文件 (.dat)",
            font=("Microsoft YaHei", 10),
            bg="#A8D5BA", fg="#2D6A3F",
            activebackground="#C8E6D0", activeforeground="#2D6A3F",
            relief="flat", padx=16, pady=8,
            cursor="hand2",
            state=tk.DISABLED,
            command=self._on_save,
        )
        self.btn_save.pack(side=tk.LEFT)

        self.btn_clear = tk.Button(
            action_frame,
            text="🗑 清空",
            font=("Microsoft YaHei", 10),
            bg="#FFFFFF", fg=self.TEXT_LIGHT,
            activebackground="#F5F1ED",
            relief="flat", padx=16, pady=8,
            cursor="hand2",
            command=self._on_clear,
        )
        self.btn_clear.pack(side=tk.RIGHT)

        self.output_file_content = None

    # ============================================================
    # 事件处理
    # ============================================================
    def _on_generate(self):
        """生成激活密钥"""
        fingerprint = self.input_text.get("1.0", "end-1c").strip()
        if not fingerprint:
            messagebox.showwarning("输入为空", "请先粘贴用户提供的机器指纹。\n（用户从激活页面点击「📤 复制机器指纹（发送给商家）」获得）")
            return

        # ---- 输入校验：防止用户误发机器码 ----
        # 机器码格式: XXXX-XXXX-... (含短横线, ~47字符)
        # 机器指纹格式: Base64 (无短横线, ~30-50字符)
        if "-" in fingerprint and len(fingerprint) < 80:
            messagebox.showwarning(
                "输入错误 — 这是「机器码」不是「机器指纹」",
                "您粘贴的是机器码（短横线格式），不能用于生成激活密钥。\n\n"
                "请让用户点击激活页面的「📤 复制机器指纹（发送给商家）」按钮，\n"
                "然后粘贴到这里。\n\n"
                "机器指纹是一长串字母数字（约30-50字符），不含短横线。",
            )
            return

        # 尝试解码指纹（Base64 编码的硬件ID）
        hardware_id = decode_fingerprint(fingerprint)
        if hardware_id is None:
            # 未被识别为有效指纹
            if len(fingerprint) < 10:
                messagebox.showerror(
                    "输入无效",
                    "无法识别此内容。\n\n"
                    "请确保用户从激活页面点击的是：\n"
                    "「📤 复制机器指纹（发送给商家）」\n\n"
                    "而不是复制「机器码」。（机器码带短横线，仅供查看）",
                )
                return
            # 可能是用户直接发了原始硬件ID
            hardware_id = fingerprint

        if not hardware_id:
            messagebox.showerror("解码失败", "无法解析机器指纹，请确认用户复制的内容完整。")
            return

        try:
            result = generate_activation(self.private_key_pem, hardware_id)
            if result is None:
                messagebox.showerror("生成失败", "激活文件生成失败，请检查私钥配置。")
                return

            self.output_file_content = result

            # 显示到输出框
            self.output_text.config(state=tk.NORMAL)
            self.output_text.delete("1.0", "end")
            self.output_text.insert("1.0", result)
            self.output_text.config(state=tk.DISABLED)

            self.btn_copy_key.config(state=tk.NORMAL)
            self.btn_save.config(state=tk.NORMAL)
        except Exception as e:
            messagebox.showerror("生成失败", f"激活文件生成出错：\n{str(e)}")

    def _on_copy_key(self):
        """复制激活密钥到剪贴板"""
        if not self.output_file_content:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.output_file_content)
        self.root.update()  # 保持剪贴板内容在窗口关闭后仍可用
        orig_text = self.btn_copy_key.cget("text")
        self.btn_copy_key.config(text="✅ 已复制！发送给用户即可", bg="#A8D5BA")
        self.root.after(2500, lambda: self.btn_copy_key.config(text=orig_text, bg="#7EB5D6"))

    def _on_save(self):
        """保存激活文件到磁盘（备选）"""
        if not self.output_file_content:
            return

        file_path = filedialog.asksaveasfilename(
            title="保存激活文件",
            defaultextension=".dat",
            filetypes=[("激活文件", "*.dat"), ("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile="ClassTrack_activation.dat",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.output_file_content)
            messagebox.showinfo("保存成功",
                              f"激活文件已保存到：\n{file_path}\n\n"
                              "请将此文件发送给用户。\n"
                              "用户在激活页面粘贴密钥内容即可完成激活。")
        except Exception as e:
            messagebox.showerror("保存失败", f"文件保存失败：{str(e)}")

    def _on_clear(self):
        """清空输入和输出"""
        self.input_text.delete("1.0", "end")
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", "end")
        self.output_text.config(state=tk.DISABLED)
        self.output_file_content = None
        self.btn_save.config(state=tk.DISABLED)
        self.btn_copy_key.config(state=tk.DISABLED)


# ============================================================
# 启动入口
# ============================================================
def main():
    root = tk.Tk()
    app = MerchantToolApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
