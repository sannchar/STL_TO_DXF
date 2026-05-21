#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
STEP to DXF Flat Pattern Converter (GUI Version)
Developed by Antigravity (Google DeepMind Advanced Agentic Coding team)

A premium graphical utility to convert 3D STEP files (.stp/.step)
into flat 2D DXF files for laser/plasma CNC cutting.
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

# Mock casadi to avoid loading massive native C++ DLLs which are not needed for flat pattern exports
from types import ModuleType
mock_casadi = ModuleType('casadi')
class DummyCasadiType:
    pass
mock_casadi.Opti = DummyCasadiType
mock_casadi.MX = DummyCasadiType
mock_casadi.DM = DummyCasadiType
sys.modules['casadi'] = mock_casadi

class StepToDxfGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("STEP to DXF Flat Pattern Converter")
        self.root.geometry("700x550")
        self.root.minsize(650, 480)
        
        # Configure colors (Modern Dark theme)
        self.bg_color = "#1e1e24"
        self.card_bg = "#2a2a35"
        self.fg_color = "#f5f5f7"
        self.fg_muted = "#a0a0b0"
        self.primary_color = "#00adb5"  # Teal
        self.primary_hover = "#00c2cb"
        self.success_color = "#2ecc71"
        self.error_color = "#e74c3c"
        
        self.root.configure(bg=self.bg_color)
        
        # Variables
        self.input_path = tk.StringVar()
        self.is_folder_mode = tk.BooleanVar(value=False)
        self.is_processing = False
        
        # Setup custom styles for TTK widgets
        self.setup_styles()
        
        # Keep track of original stdout so self.write can print to console during startup
        self.original_stdout = sys.stdout
        
        # Create Layout
        self.create_widgets()
        
        # Redirect stdout to our GUI log box
        sys.stdout = self
        
    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        # Configure overall style mapping
        self.style.configure(".", background=self.bg_color, foreground=self.fg_color)
        self.style.configure("TLabel", background=self.bg_color, foreground=self.fg_color, font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", background=self.bg_color, foreground=self.primary_color, font=("Segoe UI", 16, "bold"))
        self.style.configure("Sub.TLabel", background=self.bg_color, foreground=self.fg_muted, font=("Segoe UI", 9, "italic"))
        
        self.style.configure("Card.TFrame", background=self.card_bg, relief="flat")
        self.style.configure("Card.TLabel", background=self.card_bg, foreground=self.fg_color, font=("Segoe UI", 10))
        self.style.configure("CardBold.TLabel", background=self.card_bg, foreground=self.fg_color, font=("Segoe UI", 10, "bold"))
        
        self.style.configure("Action.TButton", 
                             background=self.primary_color, 
                             foreground=self.fg_color, 
                             bordercolor=self.primary_color, 
                             font=("Segoe UI", 11, "bold"),
                             padding=8)
        self.style.map("Action.TButton",
                       background=[("active", self.primary_hover), ("disabled", "#555555")],
                       foreground=[("disabled", "#a0a0a0")])
                       
        self.style.configure("Browse.TButton", 
                             background="#3a3a4a", 
                             foreground=self.fg_color, 
                             bordercolor="#3a3a4a", 
                             font=("Segoe UI", 9, "bold"),
                             padding=5)
        self.style.map("Browse.TButton", background=[("active", "#4a4a5a")])
        
        self.style.configure("TProgressbar", thickness=15, troughcolor="#2a2a35", background=self.primary_color)

    def write(self, text):
        """Used to redirect stdout to the ScrolledText log box."""
        self.log_box.configure(state='normal')
        self.log_box.insert(tk.END, text)
        self.log_box.see(tk.END)
        self.log_box.configure(state='disabled')
        # Keep original stdout working in console too if it exists (can be None under pyinstaller --noconsole)
        if self.original_stdout is not None:
            try:
                self.original_stdout.write(text)
            except:
                pass

    def flush(self):
        pass

    def create_widgets(self):
        # Header Container
        header_frame = tk.Frame(self.root, bg=self.bg_color, padx=20, pady=15)
        header_frame.pack(fill="x")
        
        header_lbl = ttk.Label(header_frame, text="STEP to DXF Flat Pattern Converter", style="Header.TLabel")
        header_lbl.pack(anchor="w")
        sub_lbl = ttk.Label(header_frame, text="Автоматический экспорт наибольшей плоской грани в чертеж DXF для ЧПУ резки", style="Sub.TLabel")
        sub_lbl.pack(anchor="w", pady=(2, 0))
        
        # Separator line
        sep = tk.Frame(self.root, height=1, bg="#2d2d3a")
        sep.pack(fill="x", padx=20)
        
        # Main input Card
        input_card = ttk.Frame(self.root, style="Card.TFrame", padding=15)
        input_card.pack(fill="x", padx=20, pady=15)
        
        # Mode selector radio buttons
        mode_frame = tk.Frame(input_card, bg=self.card_bg)
        mode_frame.pack(fill="x", pady=(0, 10))
        
        mode_lbl = ttk.Label(mode_frame, text="Режим работы:", style="CardBold.TLabel")
        mode_lbl.pack(side="left", padx=(0, 15))
        
        rb_file = tk.Radiobutton(mode_frame, text="Один файл (.stp/.step)", 
                                 variable=self.is_folder_mode, value=False,
                                 bg=self.card_bg, fg=self.fg_color, selectcolor=self.card_bg,
                                 activebackground=self.card_bg, activeforeground=self.fg_color,
                                 font=("Segoe UI", 9), command=self.on_mode_change)
        rb_file.pack(side="left", padx=10)
        
        rb_folder = tk.Radiobutton(mode_frame, text="Вся папка (пакетно)", 
                                   variable=self.is_folder_mode, value=True,
                                   bg=self.card_bg, fg=self.fg_color, selectcolor=self.card_bg,
                                   activebackground=self.card_bg, activeforeground=self.fg_color,
                                   font=("Segoe UI", 9), command=self.on_mode_change)
        rb_folder.pack(side="left", padx=10)
        
        # Path selection entry & button
        path_frame = tk.Frame(input_card, bg=self.card_bg)
        path_frame.pack(fill="x")
        
        self.path_lbl = ttk.Label(path_frame, text="Выберите STEP-файл:", style="Card.TLabel")
        self.path_lbl.pack(anchor="w", pady=(0, 5))
        
        self.path_entry = tk.Entry(path_frame, textvariable=self.input_path, 
                                   bg="#1a1a24", fg=self.fg_color, insertbackground=self.fg_color,
                                   relief="flat", font=("Segoe UI", 10), bd=5)
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=3)
        
        self.browse_btn = ttk.Button(path_frame, text="Обзор...", style="Browse.TButton", command=self.browse_path)
        self.browse_btn.pack(side="right", padx=(10, 0))
        
        # Action & Progress Section
        action_frame = tk.Frame(self.root, bg=self.bg_color, padx=20)
        action_frame.pack(fill="x")
        
        self.convert_btn = ttk.Button(action_frame, text="НАЧАТЬ КОНВЕРТАЦИЮ", style="Action.TButton", command=self.start_conversion)
        self.convert_btn.pack(fill="x", pady=(0, 10))
        
        self.progress = ttk.Progressbar(action_frame, mode="determinate", style="TProgressbar")
        self.progress.pack(fill="x")
        
        # Log Section Card
        log_frame = tk.Frame(self.root, bg=self.bg_color, padx=20, pady=15)
        log_frame.pack(fill="both", expand=True)
        
        log_lbl = ttk.Label(log_frame, text="Журнал событий:", style="TLabel")
        log_lbl.pack(anchor="w", pady=(0, 5))
        
        self.log_box = ScrolledText(log_frame, bg="#15151c", fg="#a8ffb2", insertbackground=self.fg_color,
                                    font=("Consolas", 9), relief="flat", state='disabled')
        self.log_box.pack(fill="both", expand=True)
        
        # Status footer
        self.status_lbl = ttk.Label(self.root, text="Готов к работе", style="Sub.TLabel")
        self.status_lbl.pack(side="bottom", anchor="w", padx=20, pady=10)
        
        # Welcome message
        self.write("=== STEP to DXF Converter GUI ===\n")
        self.write("[СИСТЕМА] Программа готова к работе.\n")
        self.write("[СИСТЕМА] Выберите файл или папку и нажмите кнопку начала конвертации.\n")

    def on_mode_change(self):
        self.input_path.set("")
        if self.is_folder_mode.get():
            self.path_lbl.configure(text="Выберите папку со STEP-файлами:")
        else:
            self.path_lbl.configure(text="Выберите STEP-файл:")

    def browse_path(self):
        if self.is_folder_mode.get():
            folder = filedialog.askdirectory(title="Выберите папку со STEP-файлами")
            if folder:
                self.input_path.set(os.path.normpath(folder))
        else:
            file_path = filedialog.askopenfilename(
                title="Выберите STEP-файл",
                filetypes=[("STEP Files", "*.stp *.step"), ("All Files", "*.*")]
            )
            if file_path:
                self.input_path.set(os.path.normpath(file_path))

    def set_gui_state(self, enabled):
        state = "normal" if enabled else "disabled"
        self.convert_btn.configure(state=state)
        self.browse_btn.configure(state=state)
        self.path_entry.configure(state=state)
        self.is_processing = not enabled

    def start_conversion(self):
        path = self.input_path.get().strip()
        if not path:
            messagebox.showwarning("Внимание", "Пожалуйста, выберите файл или папку!")
            return
            
        if not os.path.exists(path):
            messagebox.showerror("Ошибка", f"Указанный путь не существует:\n{path}")
            return
            
        # Start conversion in a background thread to prevent GUI freezing
        self.set_gui_state(False)
        self.progress.configure(mode="indeterminate")
        self.progress.start(10)
        self.status_lbl.configure(text="Обработка моделей...", foreground=self.primary_color)
        
        thread = threading.Thread(target=self.run_conversion_thread, args=(path,))
        thread.daemon = True
        thread.start()

    def run_conversion_thread(self, path):
        try:
            # Import cadquery inside thread in case it takes time
            import cadquery as cq
            success = False
            
            if os.path.isfile(path):
                # Single file mode
                success = self.convert_single_file(cq, path)
            else:
                # Folder mode
                success = self.convert_folder(cq, path)
                
        except Exception as e:
            self.write(f"\n[КРИТИЧЕСКАЯ ОШИБКА] {e}\n")
            success = False
            
        # Update GUI on completion in the main thread
        self.root.after(0, self.on_conversion_complete, success)

    def convert_single_file(self, cq, step_path, dxf_path=None):
        if not dxf_path:
            base, _ = os.path.splitext(step_path)
            dxf_path = base + ".dxf"
        filename = os.path.basename(step_path)
        
        self.write("\n" + "="*60 + "\n")
        self.write(f"Обработка файла: \"{filename}\"\n")
        self.write("-"*60 + "\n")
        
        start_time = time.time()
        
        # 1. Load file
        self.write("[1/5] Загрузка 3D-модели STEP...\n")
        try:
            part = cq.importers.importStep(step_path)
            self.write(f"      - Модель успешно загружена за {time.time() - start_time:.2f} сек.\n")
        except Exception as e:
            self.write(f"[ERROR] Ошибка при чтении файла: {e}\n")
            return False
            
        # 2. Geometry check
        self.write("[2/5] Анализ геометрии 3D-модели...\n")
        try:
            faces = part.faces()
            total_faces = len(faces.objects)
            self.write(f"      - Всего граней обнаружено: {total_faces}\n")
            
            planar_faces = part.faces("%plane")
            total_planar = len(planar_faces.objects)
            self.write(f"      - Обнаружено плоских граней: {total_planar}\n")
            
            if total_planar == 0:
                self.write("[ERROR] В модели не найдено ни одной плоской грани!\n")
                return False
        except Exception as e:
            self.write(f"[ERROR] Ошибка при анализе геометрии: {e}\n")
            return False
            
        # 3. Find largest planar face
        self.write("[3/5] Поиск наибольшей плоской грани (развертки)...\n")
        try:
            sorted_faces = sorted(planar_faces.objects, key=lambda f: f.Area(), reverse=True)
            largest_face = sorted_faces[0]
            area = largest_face.Area()
            normal = largest_face.normalAt(None)
            center = largest_face.Center()
            
            self.write(f"      - Выбрана грань #1:\n")
            self.write(f"        * Площадь: {area:.2f} мм^2\n")
            self.write(f"        * Центр: ({center.x:.2f}, {center.y:.2f}, {center.z:.2f})\n")
            self.write(f"        * Нормаль: ({normal.x:.2f}, {normal.y:.2f}, {normal.z:.2f})\n")
        except Exception as e:
            self.write(f"[ERROR] Ошибка при поиске грани: {e}\n")
            return False
            
        # 4. Project and Normalize
        self.write("[4/5] Выравнивание координатной сетки по выбранной плоскости...\n")
        try:
            plane = cq.Plane(origin=center, normal=normal)
            
            # Shift plane origin to align entire drawing in the positive quadrant (+10mm margin)
            # This ensures it loads perfectly on-page in vector editors (LibreOffice Draw, Inkscape)
            local_points = [plane.toLocalCoords(cq.Vector(v.X, v.Y, v.Z)) for v in largest_face.Vertices()]
            min_x = min(p.x for p in local_points)
            min_y = min(p.y for p in local_points)
            
            shift_local = cq.Vector(min_x - 10.0, min_y - 10.0, 0.0)
            new_origin = plane.toWorldCoords(shift_local)
            
            new_plane = cq.Plane(origin=new_origin, normal=normal)
            wp = cq.Workplane(new_plane).add(largest_face)
            self.write("      - Грань спроецирована и смещена в положительный квадрант (Z=0, отступ +10мм).\n")
        except Exception as e:
            self.write(f"[ERROR] Ошибка при выравнивании плоскости: {e}\n")
            return False
            
        # 5. Export to DXF
        self.write("[5/5] Экспорт плоского контура в DXF...\n")
        try:
            if os.path.exists(dxf_path):
                os.remove(dxf_path)
            cq.exporters.exportDXF(wp, dxf_path)
            
            if os.path.exists(dxf_path):
                file_size = os.path.getsize(dxf_path) / 1024.0
                import ezdxf
                doc = ezdxf.readfile(dxf_path)
                msp = doc.modelspace()
                entities_count = len(list(msp))
                
                self.write(f"[УСПЕХ] Файл DXF сохранен: \"{os.path.basename(dxf_path)}\"\n")
                self.write(f"        * Размер файла: {file_size:.1f} KB\n")
                self.write(f"        * Количество 2D-элементов: {entities_count}\n")
                self.write(f"Время обработки: {time.time() - start_time:.2f} сек.\n")
                return True
            else:
                self.write("[ERROR] Не удалось сохранить DXF файл!\n")
                return False
        except Exception as e:
            self.write(f"[ERROR] Ошибка при экспорте: {e}\n")
            return False

    def convert_folder(self, cq, folder_path):
        folder_path = os.path.abspath(folder_path)
        parent_dir = os.path.dirname(folder_path)
        base_name = os.path.basename(folder_path)
        output_folder = os.path.join(parent_dir, f"{base_name}_DXF")
        
        self.write("\n" + "="*60 + "\n")
        self.write(f"Рекурсивное сканирование папки: \"{folder_path}\"\n")
        self.write(f"Выходная папка для DXF чертежей:\n\"{output_folder}\"\n")
        self.write("="*60 + "\n")
        
        step_files = []
        for root_dir, dirs, files in os.walk(folder_path):
            for file in files:
                _, ext = os.path.splitext(file.lower())
                if ext in ['.stp', '.step']:
                    step_files.append(os.path.join(root_dir, file))
                    
        if not step_files:
            self.write("[WARNING] В папке не найдено файлов .stp или .step!\n")
            return True
            
        self.write(f"Найдено STEP-файлов для обработки: {len(step_files)}\n")
        for f in step_files:
            rel = os.path.relpath(f, folder_path)
            self.write(f"  - {rel}\n")
            
        processed = 0
        success_count = 0
        
        for step_file in step_files:
            processed += 1
            # Recreate mirrored subfolder tree in output_folder
            rel_path = os.path.relpath(step_file, folder_path)
            rel_dxf_path = os.path.splitext(rel_path)[0] + ".dxf"
            target_dxf_path = os.path.join(output_folder, rel_dxf_path)
            
            os.makedirs(os.path.dirname(target_dxf_path), exist_ok=True)
            
            if self.convert_single_file(cq, step_file, target_dxf_path):
                success_count += 1
                
        self.write("\n" + "="*60 + "\n")
        self.write(f"ИТОГ: Обработано {processed} файлов, Успешно: {success_count}, Ошибок: {processed - success_count}\n")
        self.write("="*60 + "\n")
        return success_count == processed

    def on_conversion_complete(self, success):
        self.progress.stop()
        self.progress.configure(mode="determinate", value=100)
        self.set_gui_state(True)
        
        if success:
            self.status_lbl.configure(text="Конвертация завершена успешно!", foreground=self.success_color)
            messagebox.showinfo("Успех", "Все файлы успешно сконвертированы!")
        else:
            self.status_lbl.configure(text="Произошли ошибки во время конвертации.", foreground=self.error_color)
            messagebox.showerror("Ошибка", "Некоторые файлы не удалось сконвертировать. Проверьте журнал.")

def main():
    root = tk.Tk()
    
    # Set default app icon to a gear/tool if available, or just standard
    try:
        # Some OS window tweaks
        if sys.platform == "win32":
            root.iconbitmap(default=None)
    except:
        pass
        
    app = StepToDxfGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
