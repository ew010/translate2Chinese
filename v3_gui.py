import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import threading
from llama_cpp import Llama
import time

class TranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI 文档翻译助手")
        self.root.geometry("700x550")
        self.root.configure(bg="#f5f5f7") # 仿 Mac 背景色

        # 核心逻辑变量
        self.model_path = tk.StringVar()
        self.input_file = tk.StringVar()
        self.lang_to = "中文"
        self.is_translating = False
        self.llm = None
        self.stop_event = threading.Event()

        self.setup_ui()

    def setup_ui(self):
        # 整体内边距
        main_frame = tk.Frame(self.root, bg="#f5f5f7", padx=20, pady=20)
        main_frame.pack(expand=True, fill="both")

        # --- 第一部分：文件选择 ---
        selection_frame = tk.LabelFrame(main_frame, text="配置选项", bg="#f5f5f7", padx=10, pady=10)
        selection_frame.pack(fill="x", pady=(0, 20))

        # 模型选择
        tk.Label(selection_frame, text="GGUF 模型:", bg="#f5f5f7").grid(row=0, column=0, sticky="w")
        tk.Entry(selection_frame, textvariable=self.model_path, width=50).grid(row=0, column=1, padx=5)
        tk.Button(selection_frame, text="浏览...", command=self.select_model).grid(row=0, column=2)

        # 待翻译文件选择
        tk.Label(selection_frame, text="翻译文件:", bg="#f5f5f7").grid(row=1, column=0, sticky="w", pady=10)
        tk.Entry(selection_frame, textvariable=self.input_file, width=50).grid(row=1, column=1, padx=5)
        tk.Button(selection_frame, text="浏览...", command=self.select_file).grid(row=1, column=2)

        # --- 第二部分：进度显示 ---
        progress_frame = tk.Frame(main_frame, bg="#f5f5f7")
        progress_frame.pack(fill="x", pady=(0, 10))

        self.progress_label = tk.Label(progress_frame, text="准备就绪", bg="#f5f5f7", font=("Arial", 10))
        self.progress_label.pack(side="left")

        self.percent_label = tk.Label(progress_frame, text="0%", bg="#f5f5f7", font=("Arial", 10))
        self.percent_label.pack(side="right")

        self.progress_bar = ttk.Progressbar(main_frame, orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill="x", pady=(0, 20))

        # --- 第三部分：日志显示 ---
        self.log_area = scrolledtext.ScrolledText(main_frame, height=12, state='disabled', font=("Monaco", 9))
        self.log_area.pack(fill="both", expand=True, pady=(0, 20))

        # --- 第四部分：控制按钮 ---
        btn_frame = tk.Frame(main_frame, bg="#f5f5f7")
        btn_frame.pack(fill="x")

        self.start_btn = tk.Button(btn_frame, text="开始翻译", command=self.start_translation_thread, 
                                  bg="#007aff", fg="black", width=15, height=2)
        self.start_btn.pack(side="right")

        self.stop_btn = tk.Button(btn_frame, text="停止", command=self.stop_translation, 
                                 state="disabled", width=10, height=2)
        self.stop_btn.pack(side="right", padx=10)

    def log(self, message):
        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state='disabled')

    def select_model(self):
        path = filedialog.askopenfilename(title="选择 GGUF 模型文件", filetypes=[("Model files", "*.gguf")])
        if path: self.model_path.set(path)

    def select_file(self):
        path = filedialog.askopenfilename(title="选择要翻译的文件", filetypes=[("Compatible files", "*.txt *.md")])
        if path: self.input_file.set(path)

    def stop_translation(self):
        if self.is_translating:
            self.stop_event.set()
            self.log("正在尝试停止翻译进程...")

    def start_translation_thread(self):
        if not self.model_path.get() or not self.input_file.get():
            messagebox.showwarning("警告", "请先选择模型和要翻译的文件！")
            return
        
        self.is_translating = True
        self.stop_event.clear()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        
        # 启动后台线程
        thread = threading.Thread(target=self.run_translation, daemon=True)
        thread.start()

    def translate_text(self, text):
        prompt = f"Translate the following text into {self.lang_to}, maintain formatting, only output translated content:\n\n{text}"
        
        # 使用 create_chat_completion 替代直接调用 self.llm
        response = self.llm.create_chat_completion(
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=1024,
            # 这里不用再手动写 stop 了，llama.cpp 会自动处理该模型的停止符
        )
        # 提取返回值的方式也有所变化
        return response['choices'][0]['message']['content'].strip()

    def run_translation(self):
        try:
            # 1. 加载模型
            if not self.llm:
                self.log("正在加载核心模型，这可能需要几秒钟...")
                self.llm = Llama(model_path=self.model_path.get(), n_ctx=2048, n_threads=8, n_gpu_layers=0, verbose=True)
            
            # 2. 读取文件
            input_path = self.input_file.get()
            with open(input_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 3. 进度与断点检查
            dir_name = os.path.dirname(input_path)
            base_name = os.path.basename(input_path)
            name, ext = os.path.splitext(base_name)
            output_file = os.path.join(dir_name, f"{name}_translated{ext}")
            progress_file = os.path.join(dir_name, f"{name}_translated.progress")

            start_index = 0
            file_mode = 'w'

            if os.path.exists(output_file) and os.path.exists(progress_file):
                with open(progress_file, 'r') as pf:
                    start_index = int(pf.read().strip())
                
                if start_index < len(lines):
                    res = messagebox.askyesno("继续翻译", f"检测到上次进度 ({start_index}/{len(lines)})，是否继续？")
                    if res: file_mode = 'a'
                    else: start_index = 0

            self.log(f"开始翻译: {base_name}")
            self.progress_bar["maximum"] = len(lines)

            with open(output_file, file_mode, encoding='utf-8') as f_out:
                for i in range(start_index, len(lines)):
                    if self.stop_event.is_set():
                        self.log("翻译已手动停止。进度已保存。")
                        break
                    
                    line = lines[i].strip()
                    if not line:
                        f_out.write("\n")
                    else:
                        translated = self.translate_text(line)
                        f_out.write(translated + "\n")
                    
                    f_out.flush()
                    with open(progress_file, 'w') as pf:
                        pf.write(str(i + 1))
                    
                    # 更新UI进度
                    self.root.after(0, self.update_ui_progress, i + 1, len(lines))
            
            if not self.stop_event.is_set():
                self.log("🎉 任务圆满完成！")
                if os.path.exists(progress_file): os.remove(progress_file)
                messagebox.showinfo("完成", "翻译任务已全部完成！")

        except Exception as e:
            self.log(f"❌ 错误: {str(e)}")
            messagebox.showerror("运行错误", str(e))
        finally:
            self.is_translating = False
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")

    def update_ui_progress(self, current, total):
        self.progress_bar["value"] = current
        percent = (current / total) * 100
        self.percent_label.config(text=f"{percent:.1f}%")
        self.progress_label.config(text=f"进度: {current}/{total}")

if __name__ == "__main__":
    root = tk.Tk()
    app = TranslatorApp(root)
    root.mainloop()
