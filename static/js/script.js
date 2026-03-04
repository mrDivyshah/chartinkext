// ─── Globals ────────────────────────────────────────────────
let currentJobId  = null;
let pollInterval  = null;
let loadedPresets = [];

// ─── Init ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadPresets();

    // Preset-save checkbox → show/hide extra fields
    const presetCheck  = document.getElementById('save_preset_check');
    const presetFields = document.getElementById('preset_fields');
    if (presetCheck) {
        presetCheck.addEventListener('change', () => {
            presetFields.classList.toggle('open', presetCheck.checked);
            document.getElementById('preset_title').required = presetCheck.checked;
        });
    }

    // MA enable checkbox
    const maCheck = document.getElementById('enable_ma');
    if (maCheck) {
        maCheck.addEventListener('change', () => {
            document.getElementById('ma_config_container').classList.toggle('open', maCheck.checked);
        });
    }

    // Scan form submit
    const scanForm = document.getElementById('scanForm');
    if (scanForm) {
        scanForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (presetCheck && presetCheck.checked) {
                await savePresetFromForm();
            }
            startScraping();
        });
    }

    // Settings form submit
    const settingsForm = document.getElementById('settingsForm');
    if (settingsForm) {
        settingsForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const token  = document.getElementById('tg_bot_token').value;
            const chatId = document.getElementById('tg_chat_id').value;
            try {
                const res = await fetch('/api/update_settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ telegram_bot_token: token, telegram_chat_id: chatId })
                });
                if (res.ok) {
                    showToast('Settings saved!');
                    toggleSettings();
                } else {
                    showToast('Failed to save settings', true);
                }
            } catch (err) {
                showToast('Error saving settings', true);
            }
        });
    }
});

// ─── Settings Modal ──────────────────────────────────────────
function toggleSettings() {
    document.getElementById('settingsModal').classList.toggle('show');
}

// Close modal when clicking the backdrop
document.addEventListener('click', (e) => {
    const modal = document.getElementById('settingsModal');
    if (modal && e.target === modal) toggleSettings();
});

// ─── Toast ───────────────────────────────────────────────────
function showToast(msg, isError = false) {
    const toast = document.getElementById('toast');
    const icon  = document.getElementById('toastIcon');
    document.getElementById('toastMsg').textContent = msg;
    icon.className = isError
        ? 'fa-solid fa-circle-exclamation err-icon'
        : 'fa-solid fa-circle-check check-icon';
    toast.classList.add('show');
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.remove('show'), 3000);
}

// ─── Preset Cards ────────────────────────────────────────────
async function loadPresets() {
    const grid  = document.getElementById('presetsGrid');
    const noMsg = document.getElementById('noPresetsMsg');
    if (!grid) return;

    try {
        const res = await fetch('/api/presets');
        loadedPresets = await res.json();

        grid.innerHTML = '';

        if (loadedPresets.length === 0) {
            noMsg.classList.add('show');
        } else {
            noMsg.classList.remove('show');
            loadedPresets.forEach(p => grid.appendChild(createPresetCard(p)));
        }
    } catch (err) {
        console.error('Failed to load presets', err);
    }
}

function createPresetCard(preset) {
    const card = document.createElement('div');
    card.className = 'preset-card';

    // Tags
    const periodTag = preset.period
        ? `<span class="tag">${escapeHtml(preset.period)}</span>` : '';
    const rangeTag  = preset.range
        ? `<span class="tag">${escapeHtml(preset.range)}</span>`  : '';

    card.innerHTML = `
        <div class="preset-card-top">
            <div class="preset-card-title">${escapeHtml(preset.title)}</div>
            <div class="preset-card-actions">
                <button class="btn-run" onclick="runPreset(${preset.id})" title="Run this scan">
                    <i class="fa-solid fa-play"></i> Run
                </button>
                <button class="btn-delete" onclick="deletePreset(${preset.id})" title="Delete preset">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </div>
        </div>
        <div class="preset-card-desc">${escapeHtml(preset.description || 'No description')}</div>
        <div class="preset-card-url">
            <i class="fa-solid fa-link" style="flex-shrink:0;font-size:11px;"></i>
            <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(preset.url)}</span>
        </div>
        <div class="preset-tags">${periodTag}${rangeTag}</div>
    `;
    return card;
}

async function savePresetFromForm() {
    const title  = document.getElementById('preset_title').value;
    const desc   = document.getElementById('preset_desc').value;
    const url    = document.getElementById('screener_url').value;
    const period = document.getElementById('period').value;
    const range  = document.getElementById('range').value;

    let maConfig = null;
    if (document.getElementById('enable_ma').checked) {
        maConfig = {};
        for (let i = 1; i <= 5; i++) {
            if (document.getElementById(`ma_${i}_enabled`).checked) {
                maConfig[`ma_${i}`] = {
                    enabled: true,
                    field:   document.getElementById(`ma_${i}_field`).value,
                    type:    document.getElementById(`ma_${i}_type`).value,
                    period:  parseInt(document.getElementById(`ma_${i}_period`).value)
                };
            }
        }
    }

    try {
        const res = await fetch('/api/presets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, description: desc, url, period, range, moving_averages: maConfig })
        });
        if (res.ok) {
            showToast('Preset saved!');
            document.getElementById('save_preset_check').checked = false;
            document.getElementById('preset_fields').classList.remove('open');
            loadPresets();
        }
    } catch (err) {
        console.error(err);
    }
}

async function deletePreset(id) {
    if (!confirm('Delete this preset?')) return;
    try {
        await fetch(`/api/presets/${id}`, { method: 'DELETE' });
        showToast('Preset deleted');
        loadPresets();
    } catch (err) {
        showToast('Error deleting preset', true);
    }
}

function runPreset(id) {
    const preset = loadedPresets.find(p => p.id === id);
    if (!preset) return;

    document.getElementById('screener_url').value = preset.url;
    document.getElementById('period').value        = preset.period;
    document.getElementById('range').value         = preset.range;

    // MA config
    const maCheck     = document.getElementById('enable_ma');
    const maContainer = document.getElementById('ma_config_container');
    for (let i = 1; i <= 5; i++) {
        document.getElementById(`ma_${i}_enabled`).checked = false;
    }

    if (preset.moving_averages && Object.keys(preset.moving_averages).length > 0) {
        maCheck.checked = true;
        maContainer.classList.add('open');
        Object.keys(preset.moving_averages).forEach(key => {
            const data = preset.moving_averages[key];
            const i    = key.split('_')[1];
            if (i) {
                document.getElementById(`ma_${i}_enabled`).checked = true;
                document.getElementById(`ma_${i}_field`).value     = data.field;
                document.getElementById(`ma_${i}_type`).value      = data.type;
                document.getElementById(`ma_${i}_period`).value    = data.period;
            }
        });
    } else {
        maCheck.checked = false;
        maContainer.classList.remove('open');
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
    startScraping();
}

// ─── Scraping ────────────────────────────────────────────────
async function startScraping() {
    const url    = document.getElementById('screener_url').value;
    const period = document.getElementById('period').value;
    const range  = document.getElementById('range').value;

    if (!url) { showToast('Please enter a screener URL', true); return; }

    // Collect MA
    let maConfig = null;
    const maCheck = document.getElementById('enable_ma');
    if (maCheck && maCheck.checked) {
        maConfig = {};
        for (let i = 1; i <= 5; i++) {
            if (document.getElementById(`ma_${i}_enabled`).checked) {
                maConfig[`ma_${i}`] = {
                    enabled: true,
                    field:   document.getElementById(`ma_${i}_field`).value,
                    type:    document.getElementById(`ma_${i}_type`).value,
                    period:  parseInt(document.getElementById(`ma_${i}_period`).value)
                };
            }
        }
    }

    // Show status box
    const statusBox = document.getElementById('statusContainer');
    statusBox.classList.add('show');
    document.getElementById('progressBar').style.width    = '0%';
    document.getElementById('progressPercent').innerText  = '0%';
    document.getElementById('statusText').innerText       = 'Starting...';
    document.getElementById('statusText').style.color     = '';
    document.getElementById('currentCompany').innerText   = 'Waiting to start...';

    // Show stop, hide download
    const stopBtn = document.getElementById('stopBtn');
    const dlBtn   = document.getElementById('downloadBtn');
    stopBtn.style.display  = 'block';
    stopBtn.disabled       = false;
    stopBtn.innerHTML      = '<i class="fa-solid fa-stop"></i> Stop Scan';
    dlBtn.style.display    = 'none';

    try {
        const res  = await fetch('/start_generation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, period, range, moving_averages: maConfig })
        });
        const data = await res.json();

        if (data.job_id) {
            currentJobId = data.job_id;
            if (pollInterval) clearInterval(pollInterval);
            pollInterval = setInterval(pollStatus, 2000);
        } else {
            showToast('Failed to start job', true);
            stopBtn.style.display = 'none';
        }
    } catch (err) {
        console.error(err);
        showToast('Error connecting to server', true);
        stopBtn.style.display = 'none';
    }
}

async function stopJob() {
    if (!currentJobId) return;
    if (!confirm('Stop the current scan?')) return;
    try {
        const res = await fetch(`/stop_job/${currentJobId}`, { method: 'POST' });
        if (res.ok) {
            showToast('Stopping scan...');
            const stopBtn = document.getElementById('stopBtn');
            stopBtn.disabled  = true;
            stopBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Stopping...';
        }
    } catch (err) {
        showToast('Error stopping scan', true);
    }
}

async function pollStatus() {
    if (!currentJobId) return;
    try {
        const res  = await fetch(`/status/${currentJobId}`);
        const data = await res.json();

        const statusText = document.getElementById('statusText');
        const stopBtn    = document.getElementById('stopBtn');
        const dlBtn      = document.getElementById('downloadBtn');

        if (data.status === 'not_found' || data.error) {
            clearInterval(pollInterval);
            statusText.innerText   = data.error || 'Unknown error';
            statusText.style.color = '#DC2626';
            stopBtn.style.display  = 'none';
            return;
        }

        // Progress
        let percent = 0;
        if (data.total > 0) {
            percent = Math.round((data.processed / data.total) * 100);
        } else if (data.status === 'scraping_urls') {
            percent = 10;
        }
        document.getElementById('progressBar').style.width   = `${percent}%`;
        document.getElementById('progressPercent').innerText = `${percent}%`;

        // Status label
        const statusMap = {
            queued:        'Queued...',
            running:       'Initializing...',
            scraping_urls: 'Scraping stock links...',
            fetching_charts: `Processing ${data.processed} of ${data.total} charts`,
            generating_pdf: 'Generating PDF...',
            completed:     '✓ Completed!',
            stopped:       'Stopped.'
        };
        statusText.innerText   = statusMap[data.status] || data.status;
        statusText.style.color = '';

        if (data.current_company) {
            document.getElementById('currentCompany').innerText = `Current: ${data.current_company}`;
        }

        if (data.status === 'completed' || data.status === 'stopped') {
            clearInterval(pollInterval);
            stopBtn.style.display = 'none';
            dlBtn.href            = `/download/${currentJobId}`;
            dlBtn.style.display   = 'flex';
            if (data.telegram_sent) showToast('PDF sent to Telegram! 🚀');
        }

    } catch (err) {
        console.error('Poll error', err);
    }
}

// ─── Helpers ─────────────────────────────────────────────────
function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g,  '&amp;')
        .replace(/</g,  '&lt;')
        .replace(/>/g,  '&gt;')
        .replace(/"/g,  '&quot;')
        .replace(/'/g,  '&#039;');
}
