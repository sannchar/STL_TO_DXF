import os
import sys
import uuid
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory, url_for

# Add parent directory to path to import step_to_dxf
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Now we can import the mock casadi and process_step_file logic from step_to_dxf
try:
    import step_to_dxf
except ImportError:
    # Just in case, setup the casadi mock here too
    from types import ModuleType
    mock_casadi = ModuleType('casadi')
    class DummyCasadiType:
        pass
    mock_casadi.Opti = DummyCasadiType
    mock_casadi.MX = DummyCasadiType
    mock_casadi.DM = DummyCasadiType
    sys.modules['casadi'] = mock_casadi
    import step_to_dxf

import ezdxf

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['OUTPUT_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outputs')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB limit

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Set logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web_dxf_converter")

def extract_dxf_entities(dxf_path):
    """
    Parses a DXF file and extracts 2D geometry entities for visualization.
    """
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
    except Exception as e:
        logger.error(f"Failed to read DXF file: {e}")
        return {'entities': [], 'bounds': {'min_x': 0, 'min_y': 0, 'max_x': 100, 'max_y': 100, 'width': 100, 'height': 100}}

    entities = []
    min_x, min_y = float('inf'), float('inf')
    max_x, max_y = float('-inf'), float('-inf')

    def update_bounds(x, y):
        nonlocal min_x, min_y, max_x, max_y
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)

    for entity in msp:
        dxftype = entity.dxftype()
        if dxftype == 'LINE':
            start = entity.dxf.start
            end = entity.dxf.end
            entities.append({
                'type': 'line',
                'x1': start.x, 'y1': start.y,
                'x2': end.x, 'y2': end.y
            })
            update_bounds(start.x, start.y)
            update_bounds(end.x, end.y)

        elif dxftype == 'ARC':
            center = entity.dxf.center
            radius = entity.dxf.radius
            start_angle = entity.dxf.start_angle
            end_angle = entity.dxf.end_angle
            entities.append({
                'type': 'arc',
                'cx': center.x, 'cy': center.y,
                'r': radius,
                'start': start_angle,
                'end': end_angle
            })
            # Crude bounds
            update_bounds(center.x - radius, center.y - radius)
            update_bounds(center.x + radius, center.y + radius)

        elif dxftype == 'CIRCLE':
            center = entity.dxf.center
            radius = entity.dxf.radius
            entities.append({
                'type': 'circle',
                'cx': center.x, 'cy': center.y,
                'r': radius
            })
            update_bounds(center.x - radius, center.y - radius)
            update_bounds(center.x + radius, center.y + radius)

    if min_x == float('inf'):
        min_x, min_y, max_x, max_y = 0, 0, 100, 100

    return {
        'entities': entities,
        'bounds': {
            'min_x': min_x, 'min_y': min_y,
            'max_x': max_x, 'max_y': max_y,
            'width': max_x - min_x,
            'height': max_y - min_y
        }
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/convert', methods=['POST'])
def convert():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in ['.stp', '.step']:
        return jsonify({'error': 'Invalid file format. Only .stp and .step are supported.'}), 400

    # Create safe unique filenames to avoid concurrent overrides
    job_id = str(uuid.uuid4())
    step_filename = f"{job_id}{ext}"
    dxf_filename = f"{job_id}.dxf"
    
    step_path = os.path.join(app.config['UPLOAD_FOLDER'], step_filename)
    dxf_path = os.path.join(app.config['OUTPUT_FOLDER'], dxf_filename)
    
    try:
        # Save uploaded STEP file
        file.save(step_path)
        
        # Capture console outputs
        import io
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        
        # Execute the CAD processing logic
        success = step_to_dxf.process_step_file(step_path, dxf_path)
        
        # Restore stdout
        sys.stdout = old_stdout
        logs = buffer.getvalue()
        
        if not success or not os.path.exists(dxf_path):
            return jsonify({
                'error': 'Failed to process STEP model. See logs for details.',
                'logs': logs
            }), 500
            
        # Extract DXF entities for client preview
        dxf_data = extract_dxf_entities(dxf_path)
        
        # Get original file clean name
        clean_name, _ = os.path.splitext(file.filename)
        out_dxf_name = f"{clean_name}.dxf"
        
        return jsonify({
            'success': True,
            'filename': out_dxf_name,
            'download_url': url_for('download_file', filename=dxf_filename, _external=True) + f"?name={out_dxf_name}",
            'bounds': dxf_data['bounds'],
            'entities': dxf_data['entities'],
            'logs': logs
        })
        
    except Exception as e:
        logger.error(f"Error during conversion: {e}", exc_info=True)
        return jsonify({'error': str(e), 'logs': str(e)}), 500
        
    finally:
        # Clean up the raw uploaded STEP file to save space
        if os.path.exists(step_path):
            try:
                os.remove(step_path)
            except Exception as e:
                logger.error(f"Failed to remove uploaded step file: {e}")

@app.route('/api/download/<filename>')
def download_file(filename):
    custom_name = request.args.get('name', 'output.dxf')
    return send_from_directory(
        app.config['OUTPUT_FOLDER'], 
        filename, 
        as_attachment=True, 
        download_name=custom_name
    )

if __name__ == '__main__':
    # Bind to all interfaces to allow access from local networks or external hosts
    app.run(host='0.0.0.0', port=5000, debug=True)
