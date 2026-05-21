#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
STEP to DXF Flat Pattern Converter
Developed by Antigravity (Google DeepMind Advanced Agentic Coding team)

This script scans the directory for STEP (.stp / .step) files,
identifies the largest planar face of the 3D model, projects it to a 2D plane,
and exports it as a DXF file suitable for CNC cutting / laser cutting.
"""

import os
import sys
import time
import argparse

# Mock casadi to avoid loading massive native C++ DLLs which are not needed for flat pattern exports
from types import ModuleType
mock_casadi = ModuleType('casadi')
class DummyCasadiType:
    pass
mock_casadi.Opti = DummyCasadiType
mock_casadi.MX = DummyCasadiType
mock_casadi.DM = DummyCasadiType
sys.modules['casadi'] = mock_casadi

# Global start time to measure overall script run
SCRIPT_START_TIME = time.time()

print("=" * 80)
print("  STEP to DXF Flat Pattern Converter  ".center(80, "="))
print("=" * 80)
print("[INFO] Инициализация CAD-движка (первый запуск может занять несколько секунд)...")

try:
    import cadquery as cq
    print("[INFO] CAD-движок успешно загружен!")
except ImportError:
    print("[ERROR] Не удалось импортировать библиотеку 'cadquery'.")
    print("Пожалуйста, установите её с помощью команды: pip install cadquery")
    sys.exit(1)

def process_step_file(step_path, dxf_path=None):
    """
    Loads a STEP file, extracts its largest planar face, and exports it to a DXF file.
    """
    if not dxf_path:
        # Save DXF in the same folder with the same name
        base, _ = os.path.splitext(step_path)
        dxf_path = base + ".dxf"
        
    filename = os.path.basename(step_path)
    print(f"\nОбработка файла: \"{filename}\"")
    print("-" * 80)
    
    start_time = time.time()
    
    # 1. Load STEP file
    print("[1/5] Загрузка 3D-модели STEP...")
    try:
        part = cq.importers.importStep(step_path)
        load_time = time.time() - start_time
        print(f"      - Модель успешно загружена за {load_time:.2f} сек.")
    except Exception as e:
        print(f"[ERROR] Ошибка при чтении STEP файла: {e}")
        return False
        
    # 2. Inspect geometry
    print("[2/5] Анализ геометрии 3D-модели...")
    try:
        faces = part.faces()
        total_faces = len(faces.objects)
        print(f"      - Всего граней обнаружено: {total_faces}")
        
        planar_faces = part.faces("%plane")
        total_planar = len(planar_faces.objects)
        print(f"      - Обнаружено плоских граней: {total_planar}")
        
        if total_planar == 0:
            print("[ERROR] В модели не найдено ни одной плоской грани для экспорта!")
            return False
            
    except Exception as e:
        print(f"[ERROR] Ошибка при анализе геометрии: {e}")
        return False
        
    # 3. Find largest planar face
    print("[3/5] Поиск наибольшей плоской грани (развертки)...")
    try:
        # Sort planar faces by area descending
        sorted_faces = sorted(planar_faces.objects, key=lambda f: f.Area(), reverse=True)
        largest_face = sorted_faces[0]
        area = largest_face.Area()
        
        # Get face details
        normal = largest_face.normalAt(None)
        center = largest_face.Center()
        
        print(f"      - Выбрана грань #1:")
        print(f"        * Площадь: {area:.2f} мм^2")
        print(f"        * Центр: ({center.x:.2f}, {center.y:.2f}, {center.z:.2f})")
        print(f"        * Вектор нормали: ({normal.x:.2f}, {normal.y:.2f}, {normal.z:.2f})")
        
        if len(sorted_faces) > 1:
            print(f"      - Справочно: вторая по величине грань имеет площадь {sorted_faces[1].Area():.2f} мм^2")
            
    except Exception as e:
        print(f"[ERROR] Ошибка при определении наибольшей грани: {e}")
        return False
        
    # 4. Create local 2D workplane
    print("[4/5] Выравнивание координатной сетки по выбранной плоскости...")
    try:
        # Create initial plane centered at the face center
        plane = cq.Plane(origin=center, normal=normal)
        
        # Calculate local bounding box to shift the origin
        # This shifts the entire part into the positive quadrant (starting at X=10mm, Y=10mm)
        # to ensure it fits perfectly inside the page bounds in vector editors like LibreOffice/Inkscape
        local_points = [plane.toLocalCoords(cq.Vector(v.X, v.Y, v.Z)) for v in largest_face.Vertices()]
        min_x = min(p.x for p in local_points)
        min_y = min(p.y for p in local_points)
        
        shift_local = cq.Vector(min_x - 10.0, min_y - 10.0, 0.0)
        new_origin = plane.toWorldCoords(shift_local)
        
        new_plane = cq.Plane(origin=new_origin, normal=normal)
        wp = cq.Workplane(new_plane).add(largest_face)
        print("      - Грань спроецирована и смещена в положительный квадрант (Z=0, отступ +10мм).")
    except Exception as e:
        print(f"[ERROR] Ошибка при выравнивании плоскости: {e}")
        return False
        
    # 5. Export to DXF
    print("[5/5] Экспорт плоского контура в DXF...")
    try:
        if os.path.exists(dxf_path):
            os.remove(dxf_path)
            
        cq.exporters.exportDXF(wp, dxf_path)
        
        # Verify file creation and size
        if os.path.exists(dxf_path):
            file_size = os.path.getsize(dxf_path) / 1024.0 # in KB
            # Let's count entities as a quick verification
            import ezdxf
            doc = ezdxf.readfile(dxf_path)
            msp = doc.modelspace()
            entities_count = len(list(msp))
            
            print(f"[УСПЕХ] Файл DXF сохранен: \"{os.path.basename(dxf_path)}\"")
            print(f"        * Размер файла: {file_size:.1f} KB")
            print(f"        * Количество 2D-элементов (линии/дуги/окружности): {entities_count}")
        else:
            print("[ERROR] Не удалось сохранить DXF файл!")
            return False
            
    except Exception as e:
        print(f"[ERROR] Ошибка при экспорте в DXF: {e}")
        return False
        
    elapsed = time.time() - start_time
    print(f"Время обработки файла: {elapsed:.2f} сек.")
    print("-" * 80)
    return True

def main():
    parser = argparse.ArgumentParser(description="Конвертер 3D STEP моделей в плоский DXF по наибольшей грани.")
    parser.add_argument("path", nargs="?", default=".", help="Путь к STEP-файлу или папке (по умолчанию текущая папка)")
    parser.add_argument("-o", "--output", help="Путь к выходному DXF-файлу (применяется только если обрабатывается один файл)")
    
    args = parser.parse_args()
    
    target_path = args.path
    
    if os.path.isfile(target_path):
        # Process single file
        _, ext = os.path.splitext(target_path.lower())
        if ext not in ['.stp', '.step']:
            print(f"[ERROR] Указанный файл \"{target_path}\" не является STEP-файлом (.stp / .step)!")
            sys.exit(1)
        success = process_step_file(target_path, args.output)
        sys.exit(0 if success else 1)
        
    elif os.path.isdir(target_path):
        # Scan folder recursively
        selected_folder = os.path.abspath(target_path)
        parent_dir = os.path.dirname(selected_folder)
        base_name = os.path.basename(selected_folder)
        output_folder = os.path.join(parent_dir, f"{base_name}_DXF")
        
        print(f"[INFO] Рекурсивное сканирование папки \"{selected_folder}\" на наличие STEP-файлов...")
        print(f"[INFO] Выходная папка для DXF чертежей: \"{output_folder}\"")
        
        step_files = []
        for root_dir, dirs, files in os.walk(selected_folder):
            for file in files:
                _, ext = os.path.splitext(file.lower())
                if ext in ['.stp', '.step']:
                    step_files.append(os.path.join(root_dir, file))
                 
        if not step_files:
            print("[WARNING] В указанной папке не найдено файлов с расширением .stp или .step!")
            sys.exit(0)
            
        print(f"[FOUND] Найдено STEP-файлов для обработки: {len(step_files)}")
        for f in step_files:
            rel = os.path.relpath(f, selected_folder)
            print(f"  - {rel}")
            
        processed_count = 0
        success_count = 0
        
        for step_file in step_files:
            processed_count += 1
            # Recreate mirrored subfolder tree in output_folder
            rel_path = os.path.relpath(step_file, selected_folder)
            rel_dxf_path = os.path.splitext(rel_path)[0] + ".dxf"
            target_dxf_path = os.path.join(output_folder, rel_dxf_path)
            
            os.makedirs(os.path.dirname(target_dxf_path), exist_ok=True)
            
            if process_step_file(step_file, target_dxf_path):
                success_count += 1
                 
        print("\n" + "=" * 80)
        print(f"  ИТОГ РАБОТЫ  ".center(80, "="))
        print("=" * 80)
        print(f"Всего файлов обработано: {processed_count}")
        print(f"Успешно сконвертировано: {success_count}")
        print(f"Ошибок при конвертации:  {processed_count - success_count}")
        print(f"Общее время выполнения:  {time.time() - SCRIPT_START_TIME:.2f} сек.")
        print("=" * 80)
        
    else:
        print(f"[ERROR] Путь \"{target_path}\" не существует!")
        sys.exit(1)

if __name__ == "__main__":
    main()
