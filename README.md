# STEP to DXF Flat Pattern Converter

An automatic converter for 3D sheet metal parts (STEP/.stp/.step) into flat 2D drawings (DXF) for CNC laser, plasma, and waterjet cutting.

The application is available in two variants:
1. **Command Line Interface (CLI)** — for rapid automation and integration.
2. **Graphical User Interface (GUI)** — a modern, beautiful desktop application for Windows.

---

## Features

* 🔍 **Smart Flat Pattern Algorithm**: Scans the 3D part model, automatically detects all planar faces, calculates their surface areas, and selects the **largest planar face** to project onto a 2D drawing.
* 📏 **Positive Quadrant Normalization**:
  Standard CAD export retains global 3D coordinates, which often results in negative coordinate offsets (e.g. $X \approx -200$, $Y \approx -120$). This makes drawings appear completely blank when opened in vector editors such as **LibreOffice Draw** or **Inkscape**.
  Our algorithm automatically calculates the local boundaries of the part and shifts the coordinate origin so that the entire part is guaranteed to lie in the **positive quadrant with a +10 mm margin**, ensuring it renders perfectly on screen or paper in any vector editor.
* 📂 **Recursive Batch Processing**:
  When a directory is selected, the application recursively scans all nested subfolders without depth limits (`os.walk`), identifies all `.stp` / `.step` files, and automatically converts them.
* 🗂️ **Mirrored Directory Structure**:
  For batch mode, the program creates a new parallel folder with a `_DXF` suffix (e.g., `models_DXF`) alongside the source folder. Inside it, **the original nested subfolder structure is completely recreated**, and all generated DXF files are placed in their respective locations, leaving the original source files completely untouched.
* ⚡ **Asynchronous Graphical Interface (GUI)**:
  * Full premium **Modern Dark Theme**.
  * Multi-threaded execution: heavy CAD computations run in a background thread, preventing the UI from freezing or displaying "Not Responding".
  * Real-time interactive log terminal displaying detailed information on the selected face area, coordinate bounds, dimensions, and the count of exported 2D primitives (lines, arcs, circles).

---

## Requirements and Installation

To run the script from the source code, you will need Python 3.10+ and the following libraries:

```bash
pip install cadquery ezdxf pyinstaller
```

*Note: The `cadquery` library uses the professional Open CASCADE Technology (OCCT) geometric kernel under the hood for high-precision geometry import and analysis.*

---

## Usage

### 1. Graphical User Interface (GUI)
To launch the graphical window:
```bash
python step_to_dxf_gui.py
```
Simply choose a file or folder, click **"START CONVERSION"**, and watch the progress in real-time in the log terminal.

### 2. Command Line Utility (CLI)
The script supports flexible arguments:

* **Convert all files in the current folder:**
  ```bash
  python step_to_dxf.py
  ```
* **Convert a specific file:**
  ```bash
  python step_to_dxf.py path/to/file.stp
  ```
* **Convert a file and save to a specific path:**
  ```bash
  python step_to_dxf.py path/to/file.stp -o output_drawing.dxf
  ```
* **Recursively convert an entire folder:**
  ```bash
  python step_to_dxf.py path/to/folder
  ```

---

## Standalone EXE Build

If you want to package the desktop application into a single executable `.exe` file to run on any Windows computer (without having to install Python or any libraries), use `pyinstaller`.

### ⚠️ Critical Build Note:
The `cadquery` library imports the `casadi` solver module by default, which bundles around 200 MB of native C++ DLLs that frequently trigger load failures in isolated PyInstaller environments. Since our converter processes individual flat parts and does not require resolving assembly constraints, we have safely mocked the `casadi` import and excluded it from compilation.

To build the executable, run:
```bash
pyinstaller --onefile --noconsole --name "STEP_to_DXF_Converter" --exclude-module casadi step_to_dxf_gui.py
```

The compiled standalone binary will be saved in `dist/STEP_to_DXF_Converter.exe`.
