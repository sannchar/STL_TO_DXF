document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const fileCard = document.getElementById('file-card');
    const selectedFileName = document.getElementById('selected-file-name');
    const selectedFileSize = document.getElementById('selected-file-size');
    const btnClearFile = document.getElementById('btn-clear-file');
    const btnConvert = document.getElementById('btn-convert');
    const btnDownload = document.getElementById('btn-download');
    const consoleTerminal = document.getElementById('console-terminal');
    const btnClearLogs = document.getElementById('btn-clear-logs');
    const loadingOverlay = document.getElementById('loading-overlay');
    const cadSvg = document.getElementById('cad-svg');
    const viewport = document.getElementById('viewport');
    
    // Zoom/Pan overlay buttons
    const btnZoomIn = document.getElementById('btn-zoom-in');
    const btnZoomOut = document.getElementById('btn-zoom-out');
    const btnZoomFit = document.getElementById('btn-zoom-fit');
    const coordinateTracker = document.getElementById('coordinate-tracker');

    // Stats variables
    const statWidth = document.getElementById('stat-width');
    const statHeight = document.getElementById('stat-height');
    const statArea = document.getElementById('stat-area');
    const statEntities = document.getElementById('stat-entities');

    let selectedFile = null;
    let dxfDownloadUrl = null;
    
    // Interactive Viewer State
    let zoom = 1;
    let panX = 0;
    let panY = 0;
    let isDragging = false;
    let startX = 0;
    let startY = 0;
    let cadBounds = { min_x: 0, min_y: 0, width: 100, height: 100 };

    // --- Logger Helpers ---
    function log(message, type = 'info') {
        const line = document.createElement('div');
        line.classList.add('log-line', type);
        
        // Remove line number prefixes like "10: " if present in output from captured streams
        const cleaned = message.replace(/^\d+:\s*/, '');
        line.textContent = cleaned;
        
        consoleTerminal.appendChild(line);
        consoleTerminal.scrollTop = consoleTerminal.scrollHeight;
    }

    function clearLogs() {
        consoleTerminal.innerHTML = '';
        log('Waiting for user to load a 3D STEP model...', 'system');
    }

    btnClearLogs.addEventListener('click', clearLogs);

    // --- Drag & Drop Event Listeners ---
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
        }, false);
    });

    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFileSelection(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelection(e.target.files[0]);
        }
    });

    btnClearFile.addEventListener('click', (e) => {
        e.stopPropagation();
        clearFileSelection();
    });

    function formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    function handleFileSelection(file) {
        const ext = file.name.split('.').pop().toLowerCase();
        if (ext !== 'stp' && ext !== 'step') {
            log(`[ERROR] File "${file.name}" is not a STEP file!`, 'error');
            return;
        }
        
        selectedFile = file;
        selectedFileName.textContent = file.name;
        selectedFileSize.textContent = formatBytes(file.size);
        
        dropzone.classList.add('hidden');
        fileCard.classList.remove('hidden');
        btnConvert.disabled = false;
        
        log(`Loaded local file: "${file.name}"`, 'success');
        log(`Click "Start Flat Pattern Extraction" to proceed.`, 'info');
    }

    function clearFileSelection() {
        selectedFile = null;
        fileInput.value = '';
        dropzone.classList.remove('hidden');
        fileCard.classList.add('hidden');
        btnConvert.disabled = true;
        log('Cleared selected file.', 'system');
    }

    // --- Action Event (Convert!) ---
    btnConvert.addEventListener('click', async () => {
        if (!selectedFile) return;

        const formData = new FormData();
        formData.append('file', selectedFile);

        loadingOverlay.classList.remove('hidden');
        log('Starting file upload to the server...', 'info');

        try {
            const response = await fetch('/api/convert', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            // Print capture output logs
            if (data.logs) {
                clearLogs();
                data.logs.split('\n').forEach(line => {
                    if (line.trim() !== '') {
                        if (line.includes('[УСПЕХ]')) {
                            log(line, 'success');
                        } else if (line.includes('[ERROR]')) {
                            log(line, 'error');
                        } else {
                            log(line, 'info');
                        }
                    }
                });
            }

            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Server processing error');
            }

            log('Flat pattern extraction completed successfully!', 'success');
            
            // Set stats values
            statWidth.textContent = `${data.bounds.width.toFixed(2)} mm`;
            statHeight.textContent = `${data.bounds.height.toFixed(2)} mm`;
            statArea.textContent = `${(data.bounds.width * data.bounds.height).toFixed(1)} mm²`;
            statEntities.textContent = `${data.entities.length} items`;

            // Setup download button
            dxfDownloadUrl = data.download_url;
            btnDownload.classList.remove('hidden');
            
            // Render geometry
            cadBounds = data.bounds;
            renderCAD(data.entities, data.bounds);

        } catch (err) {
            log(`[CRITICAL ERROR] ${err.message}`, 'error');
            alert(`Conversion failed: ${err.message}`);
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    });

    btnDownload.addEventListener('click', () => {
        if (dxfDownloadUrl) {
            window.location.href = dxfDownloadUrl;
        }
    });

    // --- Interactive Vector CAD Renderer ---
    function renderCAD(entities, bounds) {
        cadSvg.innerHTML = '';
        
        // Compute SVG view box with a comfortable 10% safety margin around the bounds
        const margin = Math.max(bounds.width, bounds.height) * 0.15;
        const viewMinX = bounds.min_x - margin;
        // DXF has Y going up, SVG has Y going down.
        // We will flip Y coordinates by mapping SVG coordinates directly.
        // To make the drawing easily visible, we center the view on CAD bounds.
        const viewMinY = bounds.min_y - margin;
        const viewWidth = bounds.width + (margin * 2);
        const viewHeight = bounds.height + (margin * 2);
        
        cadSvg.setAttribute('viewBox', `${viewMinX} ${viewMinY} ${viewWidth} ${viewHeight}`);
        
        // Let's create an SVG group that acts as our canvas
        const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        
        // Let's manually flip all Y coordinates.
        // SVG_Y = -(CAD_Y) + (Max_Y + Min_Y)
        const centerY = bounds.min_y + (bounds.height / 2);
        const flipY = (y) => {
            return centerY - (y - centerY);
        };

        entities.forEach(ent => {
            if (ent.type === 'line') {
                const el = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                el.setAttribute('x1', ent.x1);
                el.setAttribute('y1', flipY(ent.y1));
                el.setAttribute('x2', ent.x2);
                el.setAttribute('y2', flipY(ent.y2));
                el.setAttribute('class', 'cad-contour');
                group.appendChild(el);
            } 
            else if (ent.type === 'circle') {
                const el = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                el.setAttribute('cx', ent.cx);
                el.setAttribute('cy', flipY(ent.cy));
                el.setAttribute('r', ent.r);
                el.setAttribute('class', 'cad-contour');
                group.appendChild(el);
            }
            else if (ent.type === 'arc') {
                // Generate path for SVG arc
                // An SVG arc requires start and end points
                // DXF arcs angles are measured counter-clockwise starting from the X axis
                const startRad = ent.start * Math.PI / 180;
                const endRad = ent.end * Math.PI / 180;
                
                // In CAD:
                // Start X = cx + r * cos(start)
                // Start Y = cy + r * sin(start)
                const startX = ent.cx + ent.r * Math.cos(startRad);
                const startY = ent.cy + ent.r * Math.sin(startRad);
                const endX = ent.cx + ent.r * Math.cos(endRad);
                const endY = ent.cy + ent.r * Math.sin(endRad);
                
                // Diff angle
                let diff = ent.end - ent.start;
                if (diff < 0) diff += 360;
                
                const largeArc = diff > 180 ? 1 : 0;
                
                // Invert Y for rendering
                const sY = flipY(startY);
                const eY = flipY(endY);
                
                // Since Y is flipped, the drawing sweep direction also flips!
                // Counter-clockwise in CAD is clockwise in standard screen space.
                // We set sweepFlag = 0 to draw correctly.
                const sweepFlag = 0; 
                
                const el = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                el.setAttribute('d', `M ${startX} ${sY} A ${ent.r} ${ent.r} 0 ${largeArc} ${sweepFlag} ${endX} ${eY}`);
                el.setAttribute('class', 'cad-contour');
                el.setAttribute('fill', 'none');
                group.appendChild(el);
            }
        });

        // Add 2D outer bounding dimension rulers
        // Vertical Dimension Line
        const vDim = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        const vLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        vLine.setAttribute('x1', bounds.min_x - (margin * 0.4));
        vLine.setAttribute('y1', flipY(bounds.min_y));
        vLine.setAttribute('x2', bounds.min_x - (margin * 0.4));
        vLine.setAttribute('y2', flipY(bounds.max_y));
        vLine.setAttribute('class', 'cad-dimension');
        vDim.appendChild(vLine);

        const vText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        vText.setAttribute('x', bounds.min_x - (margin * 0.5));
        vText.setAttribute('y', flipY(centerY));
        vText.setAttribute('class', 'cad-dim-text');
        vText.setAttribute('text-anchor', 'end');
        vText.setAttribute('dominant-baseline', 'middle');
        vText.setAttribute('transform', `rotate(-90, ${bounds.min_x - (margin * 0.5)}, ${flipY(centerY)})`);
        vText.textContent = `${bounds.height.toFixed(1)} mm`;
        vDim.appendChild(vText);
        group.appendChild(vDim);

        // Horizontal Dimension Line
        const hDim = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        const hLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        hLine.setAttribute('x1', bounds.min_x);
        hLine.setAttribute('y1', flipY(bounds.min_y) + (margin * 0.4));
        hLine.setAttribute('x2', bounds.max_x);
        hLine.setAttribute('y2', flipY(bounds.min_y) + (margin * 0.4));
        hLine.setAttribute('class', 'cad-dimension');
        hDim.appendChild(hLine);

        const hText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        hText.setAttribute('x', bounds.min_x + (bounds.width / 2));
        hText.setAttribute('y', flipY(bounds.min_y) + (margin * 0.65));
        hText.setAttribute('class', 'cad-dim-text');
        hText.setAttribute('text-anchor', 'middle');
        hText.textContent = `${bounds.width.toFixed(1)} mm`;
        hDim.appendChild(hText);
        group.appendChild(hDim);

        cadSvg.appendChild(group);

        // Reset viewport pan/zoom
        resetView();
    }

    // --- Interactive Navigation Controls (Zoom & Pan) ---
    function updateTransform() {
        cadSvg.style.transform = `translate(${panX}px, ${panY}px) scale(${zoom})`;
    }

    function resetView() {
        zoom = 1;
        panX = 0;
        panY = 0;
        updateTransform();
    }

    viewport.addEventListener('mousedown', (e) => {
        if (e.button === 0) { // left mouse click
            isDragging = true;
            startX = e.clientX - panX;
            startY = e.clientY - panY;
            viewport.style.cursor = 'grabbing';
        }
    });

    window.addEventListener('mousemove', (e) => {
        if (isDragging) {
            panX = e.clientX - startX;
            panY = e.clientY - startY;
            updateTransform();
        }
        
        // Update coordinate HUD tracker relative to drawing scale
        if (cadBounds && cadBounds.width) {
            const rect = cadSvg.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            const cadX = cadBounds.min_x + (mouseX / rect.width) * cadBounds.width;
            // Un-flip Y coordinates to match CAD model coordinates
            const cadY = cadBounds.min_y + (1 - (mouseY / rect.height)) * cadBounds.height;
            
            if (mouseX >= 0 && mouseX <= rect.width && mouseY >= 0 && mouseY <= rect.height) {
                coordinateTracker.textContent = `X: ${cadX.toFixed(2)} mm | Y: ${cadY.toFixed(2)} mm`;
            }
        }
    });

    window.addEventListener('mouseup', () => {
        if (isDragging) {
            isDragging = false;
            viewport.style.cursor = 'grab';
        }
    });

    viewport.addEventListener('wheel', (e) => {
        e.preventDefault();
        
        const zoomIntensity = 0.1;
        const rect = cadSvg.getBoundingClientRect();
        
        // Save viewport-relative offsets before zoom
        const beforeZoomX = (e.clientX - rect.left - panX) / zoom;
        const beforeZoomY = (e.clientY - rect.top - panY) / zoom;
        
        // Calculate new zoom level
        if (e.deltaY < 0) {
            zoom *= (1 + zoomIntensity);
        } else {
            zoom /= (1 + zoomIntensity);
        }
        
        zoom = Math.max(0.1, Math.min(25, zoom));
        
        // Re-center around cursor point
        panX = (e.clientX - rect.left) - beforeZoomX * zoom;
        panY = (e.clientY - rect.top) - beforeZoomY * zoom;
        
        updateTransform();
    }, { passive: false });

    // HUD buttons zoom controls
    btnZoomIn.addEventListener('click', () => {
        zoom *= 1.25;
        zoom = Math.min(25, zoom);
        updateTransform();
    });

    btnZoomOut.addEventListener('click', () => {
        zoom /= 1.25;
        zoom = Math.max(0.1, zoom);
        updateTransform();
    });

    btnZoomFit.addEventListener('click', resetView);
});
