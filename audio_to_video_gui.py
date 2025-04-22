import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import shutil
import os
import re
import threading
import queue

class VideoCreatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Creator")
        self.root.geometry("600x400")
        
        self.images = []
        self.audio_file = ""
        self.output_file = ""
        self.process = None
        self.running = False
        self.queue = queue.Queue()
        
        self.create_widgets()
        self.check_ffmpeg()
        
    def create_widgets(self):
        # Images Selection
        ttk.Label(self.root, text="Images:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.images_entry = ttk.Entry(self.root, width=50)
        self.images_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(self.root, text="Browse", command=self.select_images).grid(row=0, column=2, padx=5, pady=5)
        
        # Audio Selection
        ttk.Label(self.root, text="Audio:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.audio_entry = ttk.Entry(self.root, width=50)
        self.audio_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(self.root, text="Browse", command=self.select_audio).grid(row=1, column=2, padx=5, pady=5)
        
        # Output Selection
        ttk.Label(self.root, text="Output:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.output_entry = ttk.Entry(self.root, width=50)
        self.output_entry.grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(self.root, text="Browse", command=self.select_output).grid(row=2, column=2, padx=5, pady=5)
        
        # Resolution
        ttk.Label(self.root, text="Resolution (optional):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.res_entry = ttk.Entry(self.root, width=50)
        self.res_entry.grid(row=3, column=1, padx=5, pady=5)
        
        # Progress
        self.progress = ttk.Progressbar(self.root, orient="horizontal", mode="determinate")
        self.progress.grid(row=4, column=0, columnspan=3, padx=5, pady=5, sticky="we")
        
        # Log
        self.log = tk.Text(self.root, height=8, state="disabled")
        self.log.grid(row=5, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        
        # Buttons
        self.start_btn = ttk.Button(self.root, text="Start", command=self.start_process)
        self.start_btn.grid(row=6, column=1, padx=5, pady=5)
        ttk.Button(self.root, text="Cancel", command=self.cancel_process).grid(row=6, column=2, padx=5, pady=5)
        
        # Configure grid weights
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(5, weight=1)
        
    def check_ffmpeg(self):
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            messagebox.showerror("Error", "FFmpeg and ffprobe must be installed")
            self.root.destroy()
            
    def select_images(self):
        files = filedialog.askopenfilenames(filetypes=[("Image files", "*.jpg *.jpeg *.png")])
        if files:
            self.images = list(files)
            self.images_entry.delete(0, tk.END)
            self.images_entry.insert(0, ", ".join([os.path.basename(f) for f in files]))
            
    def select_audio(self):
        file = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3 *.wav")])
        if file:
            self.audio_file = file
            self.audio_entry.delete(0, tk.END)
            self.audio_entry.insert(0, os.path.basename(file))
            
    def select_output(self):
        file = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4 files", "*.mp4")])
        if file:
            self.output_file = file
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, file)
            
    def start_process(self):
        if not self.validate_inputs():
            return
            
        self.running = True
        self.start_btn.config(state="disabled")
        self.progress["value"] = 0
        self.log_message("Starting process...")
        
        thread = threading.Thread(target=self.run_ffmpeg)
        thread.start()
        self.monitor_progress()
        
    def validate_inputs(self):
        if len(self.images) == 0:
            messagebox.showerror("Error", "Select at least one image")
            return False
        if not self.audio_file:
            messagebox.showerror("Error", "Select an audio file")
            return False
        if not self.output_file:
            messagebox.showerror("Error", "Select output file")
            return False
        return True
        
    def log_message(self, message):
        self.log.config(state="normal")
        self.log.insert(tk.END, message + "\n")
        self.log.see(tk.END)
        self.log.config(state="disabled")
        
    def run_ffmpeg(self):
        try:
            duration = float(subprocess.check_output([
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                self.audio_file
            ]).decode().strip())
        except Exception as e:
            self.queue.put(("error", "Failed to get audio duration"))
            return
            
        num_images = len(self.images)
        per_image_duration = duration / num_images
        
        ffmpeg_cmd = ['ffmpeg', '-y', '-i', self.audio_file]
        for img in self.images:
            ffmpeg_cmd += ['-loop', '1', '-t', f'{per_image_duration:.2f}', '-i', img]
            
        filter_complex = []
        concat_inputs = []
        for i in range(num_images):
            if self.res_entry.get():
                filter_complex.append(f'[{i+1}:v]scale={self.res_entry.get()},setsar=1[s{i}]')
            else:
                filter_complex.append(f'[{i+1}:v]setsar=1[s{i}]')
            concat_inputs.append(f'[s{i}]')
            
        filter_complex.append(f'{"".join(concat_inputs)}concat=n={num_images}:v=1:a=0[v]')
        ffmpeg_cmd += ['-filter_complex', ';'.join(filter_complex)]
        ffmpeg_cmd += ['-map', '[v]', '-map', '0:a', '-c:v', 'libx264', '-preset', 'medium', '-c:a', 'aac', self.output_file]
        
        try:
            self.process = subprocess.Popen(
                ffmpeg_cmd,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            time_pattern = re.compile(r'time=(\d+:\d+:\d+\.\d+)')
            while self.running:
                line = self.process.stderr.readline()
                if not line:
                    break
                    
                if 'error' in line.lower():
                    self.queue.put(("error", line.strip()))
                    
                match = time_pattern.search(line)
                if match:
                    try:
                        h, m, s = map(float, match.group(1).split(':'))
                        current_time = h * 3600 + m * 60 + s
                        progress = (current_time / duration) * 100
                        self.queue.put(("progress", progress))
                    except:
                        pass
                        
            if self.process.wait() == 0 and self.running:
                self.queue.put(("complete", "Video created successfully"))
            else:
                self.queue.put(("error", "Process failed"))
                
        except Exception as e:
            self.queue.put(("error", str(e)))
            
    def monitor_progress(self):
        while not self.queue.empty():
            msg_type, content = self.queue.get()
            if msg_type == "progress":
                self.progress["value"] = content
            elif msg_type == "error":
                self.log_message(f"Error: {content}")
            elif msg_type == "complete":
                self.log_message(content)
                messagebox.showinfo("Success", "Video created successfully")
                
        if self.running:
            self.root.after(100, self.monitor_progress)
        else:
            self.start_btn.config(state="normal")
            
    def cancel_process(self):
        if self.process and self.running:
            self.process.terminate()
            self.running = False
            self.log_message("Process cancelled")
            self.start_btn.config(state="normal")
            
if __name__ == '__main__':
    root = tk.Tk()
    app = VideoCreatorApp(root)
    root.mainloop()
