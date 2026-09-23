// PRAMAAN RAKSHAK - Frontend Dashboard Controller

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
  const piiEmptyRow = document.getElementById('piiEmptyRow');
  const redactionCountVal = document.getElementById('redactionCountVal');
  const redactionTypesVal = document.getElementById('redactionTypesVal');
  const previewContainer = document.getElementById('previewContainer');
  const previewPlaceholder = document.getElementById('previewPlaceholder');
  const downloadBtn = document.getElementById('downloadBtn');

  // Pipeline Step Items in execution order
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

  // 1. Health Status Check
  async function checkHealth() {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout for Render wakeups

      const res = await fetch('/health', { signal: controller.signal });
      clearTimeout(timeoutId);

      if (res.ok || res.status === 200) {
        statusBadge.className = 'status-badge online';
        statusText.textContent = 'System Online';
        offlineBanner.style.display = 'none';
        return true;
      }
      setOfflineState();
      return false;
    } catch (e) {
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
  setInterval(checkHealth, 15000);

  // 2. Drag & Drop and File Input
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

  // 3. Process Document Pipeline
  processBtn.addEventListener('click', async () => {
    if (!selectedFile || isProcessing) return;

    const isOnline = await checkHealth();
    if (!isOnline) {
      showError('System Offline: Please verify the server is running.');
      return;
    }

    isProcessing = true;
    processBtn.disabled = true;
    resetBtn.disabled = true;
    hideError();
    resetResultsUI();

    try {
      // Step 1: Uploaded
      updateStepStatus('upload', 'completed');

      // Step 2: OCR
      updateStepStatus('ocr', 'processing');
      const formDataOcr = new FormData();
      formDataOcr.append('file', selectedFile);

      const ocrRes = await fetch('/ocr', { method: 'POST', body: formDataOcr });
      if (!ocrRes.ok) {
        const errData = await ocrRes.json().catch(() => ({ detail: 'OCR processing failed.' }));
        throw { step: 'ocr', message: errData.detail || 'OCR processing failed.' };
      }
      const ocrData = await ocrRes.json();
      updateStepStatus('ocr', 'completed');

      // Step 3: Classification
      updateStepStatus('classify', 'processing');
      const ocrText = ocrData.text || '';
      const classifyRes = await fetch('/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: ocrText })
      });
      
      if (!classifyRes.ok) {
        const errData = await classifyRes.json().catch(() => ({ detail: 'Classification failed.' }));
        throw { step: 'classify', message: errData.detail || 'Classification failed.' };
      }
      const classifyData = await classifyRes.json();
      docTypeVal.textContent = classifyData.document_type || 'Unknown';
      const confPct = (classifyData.confidence * 100).toFixed(1) + '%';
      docConfVal.innerHTML = `<span>${confPct}</span>`;
      updateStepStatus('classify', 'completed');

      // Step 4: KIE
      updateStepStatus('kie', 'processing');
      const formDataKie = new FormData();
      formDataKie.append('file', selectedFile);

      const kieRes = await fetch('/extract/fir', { method: 'POST', body: formDataKie });
      if (!kieRes.ok) {
        const errData = await kieRes.json().catch(() => ({ detail: 'KIE processing failed.' }));
        throw { step: 'kie', message: errData.detail || 'KIE processing failed.' };
      }
      const kieData = await kieRes.json();
      const fields = kieData.extracted_fields || {};
      psVal.textContent = (fields.police_station && fields.police_station.value) ? fields.police_station.value : '-';
      yearVal.textContent = (fields.year && fields.year.value) ? fields.year.value : '-';
      statutesVal.textContent = (fields.statutes && fields.statutes.value) ? fields.statutes.value : '-';
      complainantVal.textContent = (fields.complainant_name && fields.complainant_name.value) ? fields.complainant_name.value : '-';
      updateStepStatus('kie', 'completed');

      // Step 5: PII Detection
      updateStepStatus('pii', 'processing');
      const formDataPii = new FormData();
      formDataPii.append('file', selectedFile);

      const piiRes = await fetch('/detect/pii', { method: 'POST', body: formDataPii });
      if (!piiRes.ok) {
        const errData = await piiRes.json().catch(() => ({ detail: 'PII detection failed.' }));
        throw { step: 'pii', message: errData.detail || 'PII detection failed.' };
      }
      const piiData = await piiRes.json();
      const piiEntities = piiData.pii_entities || [];
      renderPIITable(piiEntities);
      updateStepStatus('pii', 'completed');

      // Step 6: Redaction
      updateStepStatus('redact', 'processing');
      const formDataRedact = new FormData();
      formDataRedact.append('file', selectedFile);

      const redactRes = await fetch('/redact/pii', { method: 'POST', body: formDataRedact });
      if (!redactRes.ok) {
        const errData = await redactRes.json().catch(() => ({ detail: 'Redaction failed.' }));
        throw { step: 'redact', message: errData.detail || 'Redaction failed.' };
      }
      const redactData = await redactRes.json();
      updateStepStatus('redact', 'completed');

      renderRedactionResults(redactData);

    } catch (err) {
      const failedStep = err.step || 'process';
      const msg = err.message || 'An unexpected error occurred during processing.';
      
      // Update failed step and mark subsequent steps as failed/canceled
      let foundFailed = false;
      stepKeys.forEach(k => {
        if (k === failedStep) {
          updateStepStatus(k, 'failed');
          foundFailed = true;
        } else if (foundFailed) {
          updateStepStatus(k, 'failed');
        }
      });
      showError(`Document processing failed at ${failedStep.toUpperCase()} stage: ${msg}`);
    } finally {
      isProcessing = false;
      processBtn.disabled = false;
      resetBtn.disabled = false;
    }
  });

  // 4. Update Pipeline Step UI
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

  // 5. Render PII Table (Sensitive Text is NEVER displayed for security)
  function renderPIITable(entities) {
    piiTableBody.innerHTML = '';
    
    if (!entities || entities.length === 0) {
      piiTableBody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No PII entities detected</td></tr>';
      return;
    }

    entities.forEach(ent => {
      const row = document.createElement('tr');
      const confPct = (ent.confidence * 100).toFixed(2) + '%';
      
      row.innerHTML = `
        <td><span class="entity-tag">${ent.type}</span></td>
        <td>${confPct}</td>
        <td>Page ${ent.page || 1}</td>
        <td><span class="status-text-masked">Detected</span></td>
      `;
      piiTableBody.appendChild(row);
    });
  }

  // 6. Render Redaction Results & Download / Preview
  function renderRedactionResults(redactData) {
    redactionCountVal.textContent = redactData.redaction_count || 0;

    const typesSet = new Set((redactData.redactions || []).map(r => r.type));
    const typesArray = Array.from(typesSet);
    
    if (typesArray.length > 0) {
      redactionTypesVal.innerHTML = typesArray.map(t => `<span class="entity-tag">${t}</span>`).join(' ');
    } else {
      redactionTypesVal.textContent = '-';
    }

    if (redactData.redacted_file_url) {
      downloadBtn.href = redactData.redacted_file_url;
      downloadBtn.style.display = 'inline-flex';

      previewContainer.innerHTML = '';
      const fileUrl = redactData.redacted_file_url;
      
      if (redactData.redacted_filename.endsWith('.pdf')) {
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

  // 7. Reset UI for New Document
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
