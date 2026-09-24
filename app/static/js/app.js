// PRAMAAN RAKSHAK - Production Dashboard Controller

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const fileInfoPill = document.getElementById('fileInfoPill');
  const fileNameDisplay = document.getElementById('fileName');
  const fileSizeDisplay = document.getElementById('fileSize');
  const processBtn = document.getElementById('processBtn');
  const resetBtn = document.getElementById('resetBtn');
  
  const statusBadge = document.getElementById('statusBadge');
  const statusText = document.getElementById('statusText');
  const offlineBanner = document.getElementById('offlineBanner');
  const errorBox = document.getElementById('errorBox');
  const errorMessage = document.getElementById('errorMessage');

  // Document Info Elements
  const docTypeVal = document.getElementById('docTypeVal');
  const docConfVal = document.getElementById('docConfVal');
  const psVal = document.getElementById('psVal');
  const yearVal = document.getElementById('yearVal');
  const statutesVal = document.getElementById('statutesVal');
  const complainantVal = document.getElementById('complainantVal');

  // PII & Redaction Elements
  const piiTableBody = document.getElementById('piiTableBody');
  const redactionCountVal = document.getElementById('redactionCountVal');
  const redactionTypesVal = document.getElementById('redactionTypesVal');
  const previewContainer = document.getElementById('previewContainer');
  const downloadBtn = document.getElementById('downloadBtn');

  // Pipeline Step Items
  const stepKeys = ['upload', 'ocr', 'classify', 'kie', 'pii', 'redact'];
  const steps = {
    upload: document.getElementById('step-upload'),
    ocr: document.getElementById('step-ocr'),
    classify: document.getElementById('step-classify'),
    kie: document.getElementById('step-kie'),
    pii: document.getElementById('step-pii'),
    redact: document.getElementById('step-redact')
  };

  let selectedFile = null;
  let isProcessing = false;

  // Uncaught JS error logger
  window.addEventListener('error', (evt) => {
    console.error('[DEBUG] Uncaught JS Error:', evt.message, 'at', evt.filename, ':', evt.lineno);
  });

  // 1. Informational Health Check (Never blocks document processing)
  async function checkHealth() {
    console.log('[DEBUG] Health check ping: /health');
    try {
      const res = await fetch('/health', { cache: 'no-cache' });
      if (res.ok || res.status === 200) {
        statusBadge.className = 'status-badge online';
        statusText.textContent = 'System Online';
        offlineBanner.style.display = 'none';
        return true;
      }
      setOfflineState();
      return false;
    } catch (e) {
      console.warn('[DEBUG] Health ping exception:', e);
      setOfflineState();
      return false;
    }
  }

  function setOfflineState() {
    statusBadge.className = 'status-badge offline';
    statusText.textContent = 'System Offline';
    offlineBanner.style.display = 'block';
  }

  // Initial health check & periodic polling
  checkHealth();
  setInterval(checkHealth, 20000);

  // 2. Drag & Drop & File Selection
  dropzone.addEventListener('click', () => {
    if (!isProcessing) fileInput.click();
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  });

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (!isProcessing) dropzone.classList.add('dragover');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    }, false);
  });

  dropzone.addEventListener('drop', (e) => {
    if (isProcessing) return;
    const dt = e.dataTransfer;
    if (dt.files && dt.files[0]) {
      handleFileSelected(dt.files[0]);
    }
  });

  function handleFileSelected(file) {
    console.log('[DEBUG] File selected:', file.name, 'size:', file.size);
    const validExtensions = ['.png', '.jpg', '.jpeg', '.pdf'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!validExtensions.includes(ext)) {
      showError(`Unsupported file format '${ext}'. Supported formats: PNG, JPG, JPEG, PDF.`);
      return;
    }

    if (file.size === 0) {
      showError('Selected file is empty (0 bytes).');
      return;
    }

    selectedFile = file;
    fileNameDisplay.textContent = file.name;
    fileSizeDisplay.textContent = formatBytes(file.size);
    fileInfoPill.style.display = 'flex';
    processBtn.disabled = false;
    hideError();
  }

  function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  // 3. Process Document Pipeline (Calls unified relative endpoint POST /process)
  processBtn.addEventListener('click', async () => {
    console.log('[DEBUG] Process Document clicked. Selected file:', selectedFile ? selectedFile.name : 'NONE');
    if (!selectedFile || isProcessing) return;

    isProcessing = true;
    processBtn.disabled = true;
    resetBtn.disabled = true;
    hideError();
    resetResultsUI();

    // Mark upload step active
    updateStepStatus('upload', 'completed');
    updateStepStatus('ocr', 'processing');
    updateStepStatus('classify', 'processing');
    updateStepStatus('kie', 'processing');
    updateStepStatus('pii', 'processing');
    updateStepStatus('redact', 'processing');

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      console.log('[DEBUG] Sending POST /process request...');
      const res = await fetch('/process', {
        method: 'POST',
        body: formData
      });

      console.log('[DEBUG] /process HTTP status:', res.status);

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        console.error('[DEBUG] /process error response:', errData);
        const detailMsg = errData.detail || 'Document processing is temporarily unavailable. Please try again.';
        throw new Error(detailMsg);
      }

      const data = await res.json();
      console.log('[DEBUG] /process response received:', data);

      // Mark all pipeline steps completed
      stepKeys.forEach(k => updateStepStatus(k, 'completed'));

      // Render Dashboard Information Cards
      renderPipelineResults(data);

    } catch (err) {
      console.error('[DEBUG] Pipeline exception:', err);
      stepKeys.forEach(k => {
        if (steps[k] && steps[k].classList.contains('processing')) {
          updateStepStatus(k, 'failed');
        }
      });
      showError(err.message || 'Document processing is temporarily unavailable. Please try again.');
    } finally {
      isProcessing = false;
      processBtn.disabled = false;
      resetBtn.disabled = false;
    }
  });

  // 4. Render Pipeline Results
  function renderPipelineResults(data) {
    // Document Type & Confidence
    docTypeVal.textContent = data.document_type || 'Unknown';
    const confPct = ((data.confidence || 0) * 100).toFixed(1) + '%';
    docConfVal.innerHTML = `<span>${confPct}</span>`;

    // Key Extracted Fields (KIE)
    const fields = data.extracted_fields || {};
    psVal.textContent = (fields.police_station && fields.police_station.value) ? fields.police_station.value : '-';
    yearVal.textContent = (fields.year && fields.year.value) ? fields.year.value : '-';
    statutesVal.textContent = (fields.statutes && fields.statutes.value) ? fields.statutes.value : '-';
    complainantVal.textContent = (fields.complainant_name && fields.complainant_name.value) ? fields.complainant_name.value : '-';

    // PII Detection Table (Sensitive text is masked for security)
    renderPIITable(data.pii_entities || []);

    // Redaction Results & Preview / Download
    renderRedactionSection(data);
  }

  function renderPIITable(entities) {
    piiTableBody.innerHTML = '';
    
    if (!entities || entities.length === 0) {
      piiTableBody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No PII entities detected</td></tr>';
      return;
    }

    entities.forEach(ent => {
      const row = document.createElement('tr');
      const confPct = ((ent.confidence || 0) * 100).toFixed(2) + '%';
      
      row.innerHTML = `
        <td><span class="entity-tag">${ent.type}</span></td>
        <td>${confPct}</td>
        <td>Page ${ent.page || 1}</td>
        <td><span class="status-text-masked">Detected</span></td>
      `;
      piiTableBody.appendChild(row);
    });
  }

  function renderRedactionSection(data) {
    redactionCountVal.textContent = data.redaction_count || 0;

    const typesSet = new Set((data.redactions || []).map(r => r.type));
    const typesArray = Array.from(typesSet);
    
    if (typesArray.length > 0) {
      redactionTypesVal.innerHTML = typesArray.map(t => `<span class="entity-tag">${t}</span>`).join(' ');
    } else {
      redactionTypesVal.textContent = '-';
    }

    if (data.redacted_file_url) {
      downloadBtn.href = data.redacted_file_url;
      downloadBtn.style.display = 'inline-flex';

      previewContainer.innerHTML = '';
      const fileUrl = data.redacted_file_url;
      
      if (data.redacted_filename && data.redacted_filename.endsWith('.pdf')) {
        const iframe = document.createElement('iframe');
        iframe.src = fileUrl;
        iframe.className = 'preview-iframe';
        previewContainer.appendChild(iframe);
      } else {
        const img = document.createElement('img');
        img.src = fileUrl;
        img.alt = 'Redacted Document Preview';
        img.className = 'preview-image';
        previewContainer.appendChild(img);
      }
    }
  }

  // 5. Update Pipeline Step Status
  function updateStepStatus(stepKey, status) {
    const el = steps[stepKey];
    if (!el) return;

    el.className = `pipeline-item ${status}`;
    const badge = el.querySelector('.step-badge');

    if (status === 'pending') {
      badge.className = 'step-badge badge-pending';
      badge.innerHTML = 'Pending';
    } else if (status === 'processing') {
      badge.className = 'step-badge badge-processing';
      badge.innerHTML = '<span class="spinner"></span> Processing';
    } else if (status === 'completed') {
      badge.className = 'step-badge badge-completed';
      badge.innerHTML = 'Completed';
    } else if (status === 'failed') {
      badge.className = 'step-badge badge-failed';
      badge.innerHTML = 'Failed';
    }
  }

  // 6. Reset UI Controller
  resetBtn.addEventListener('click', resetAll);

  function resetAll() {
    if (isProcessing) return;

    selectedFile = null;
    fileInput.value = '';
    fileInfoPill.style.display = 'none';
    processBtn.disabled = true;
    hideError();

    Object.keys(steps).forEach(k => updateStepStatus(k, 'pending'));
    resetResultsUI();
  }

  function resetResultsUI() {
    docTypeVal.textContent = '-';
    docConfVal.textContent = '-';
    psVal.textContent = '-';
    yearVal.textContent = '-';
    statutesVal.textContent = '-';
    complainantVal.textContent = '-';

    piiTableBody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No PII detected yet</td></tr>';
    redactionCountVal.textContent = '0';
    redactionTypesVal.textContent = '-';

    previewContainer.innerHTML = '<div class="preview-placeholder">Processed document preview will appear here</div>';
    downloadBtn.style.display = 'none';
    downloadBtn.href = '#';
  }

  function showError(msg) {
    errorMessage.textContent = msg;
    errorBox.style.display = 'flex';
  }

  function hideError() {
    errorBox.style.display = 'none';
    errorMessage.textContent = '';
  }
});
