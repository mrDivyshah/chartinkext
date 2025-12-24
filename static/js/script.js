// --- Global ---
let currentJobId = null;
let pollInterval = null;
let loadedPresets = []; // Store full preset objects

document.addEventListener('DOMContentLoaded', () => {
    loadPresets();

    // Toggle Preset Fields based on Checkbox
    const presetCheck = document.getElementById('save_preset_check');
    const presetFields = document.getElementById('preset_fields');
    if (presetCheck) {
        presetCheck.addEventListener('change', (e) => {
            if (e.target.checked) {
                presetFields.classList.remove('hidden');
                document.getElementById('preset_title').required = true;
            } else {
                presetFields.classList.add('hidden');
                document.getElementById('preset_title').required = false;
            }
        });
    }

    // Main Scan Form Submit
    document.getElementById('scanForm').addEventListener('submit', async (e) => {
        e.preventDefault();

        // 1. If "Save as preset" is checked, save it first
        if (presetCheck && presetCheck.checked) {
            await savePresetFromForm();
        }

        // 2. Start Generation
        startScraping();
    });

    // Settings Form
    document.getElementById('settingsForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const token = document.getElementById('tg_bot_token').value;
        const chatId = document.getElementById('tg_chat_id').value;

        try {
            const res = await fetch('/api/update_settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ telegram_bot_token: token, telegram_chat_id: chatId })
            });
            if (res.ok) {
                showToast('Settings saved successfully!');
                toggleSettings();
            } else {
                showToast('Failed to save settings', true);
            }
        } catch (err) {
            console.error(err);
            showToast('Error saving settings', true);
        }
    });
});

// --- Preset Management ---

async function loadPresets() {
    const grid = document.getElementById('presetsGrid');
    const noMsg = document.getElementById('noPresetsMsg');

    try {
        const res = await fetch('/api/presets');
        loadedPresets = await res.json(); // Store globally

        grid.innerHTML = '';

        if (loadedPresets.length === 0) {
            noMsg.classList.remove('hidden');
        } else {
            noMsg.classList.add('hidden');
            loadedPresets.forEach(p => {
                const card = createPresetCard(p);
                grid.appendChild(card);
            });
        }
    } catch (err) {
        console.error("Failed to load presets", err);
    }
}

function createPresetCard(preset) {
    const div = document.createElement('div');
    div.className = 'glass p-6 rounded-2xl border border-slate-700 hover:border-blue-500/50 transition-all group relative overflow-hidden';

    div.innerHTML = `
        <div class="relative z-10">
            <div class="flex justify-between items-start mb-2">
                <h3 class="font-bold text-lg text-white truncate pr-2">${escapeHtml(preset.title)}</h3>
                <div class="flex gap-2">
                     <button onclick="runPreset(${preset.id})" 
                             class="bg-blue-600 hover:bg-blue-500 text-white p-2 rounded-lg text-xs font-bold transition-all shadow-lg shadow-blue-500/20" title="Run Scan">
                        <i class="fa-solid fa-play"></i> Run
                    </button>
                    <button onclick="deletePreset(${preset.id})" class="text-slate-500 hover:text-red-400 p-1 transition-colors" title="Delete">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            </div>
            <p class="text-slate-400 text-sm mb-4 line-clamp-2 min-h-[2.5rem]">${escapeHtml(preset.description || 'No description')}</p>
            
            <div class="flex items-center gap-2 text-xs text-slate-500 font-mono bg-slate-800/50 p-2 rounded border border-slate-700/50">
                <i class="fa-solid fa-link"></i>
                <span class="truncate w-full">${escapeHtml(preset.url)}</span>
            </div>

            <div class="mt-3 flex gap-2">
                 <span class="px-2 py-1 rounded bg-slate-700 text-xs text-slate-300">${preset.period}</span>
                 <span class="px-2 py-1 rounded bg-slate-700 text-xs text-slate-300">${preset.range}</span>
            </div>
        </div>
        <!-- Decorative bg glow -->
        <div class="absolute -right-10 -bottom-10 w-32 h-32 bg-blue-500/10 rounded-full blur-2xl group-hover:bg-blue-500/20 transition-all"></div>
    `;
    return div;
}

async function savePresetFromForm() {
    const title = document.getElementById('preset_title').value;
    const desc = document.getElementById('preset_desc').value;
    const url = document.getElementById('screener_url').value;
    const period = document.getElementById('period').value;
    const range = document.getElementById('range').value;

    // Collect MA Config
    let maConfig = null;
    if (document.getElementById('enable_ma').checked) {
        maConfig = {};
        for (let i = 1; i <= 5; i++) {
            if (document.getElementById(`ma_${i}_enabled`).checked) {
                maConfig[`ma_${i}`] = {
                    enabled: true,
                    field: document.getElementById(`ma_${i}_field`).value,
                    type: document.getElementById(`ma_${i}_type`).value,
                    period: parseInt(document.getElementById(`ma_${i}_period`).value)
                };
            }
        }
    }

    try {
        const res = await fetch('/api/presets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                description: desc,
                url,
                period,
                range,
                moving_averages: maConfig
            })
        });
        if (res.ok) {
            showToast('Preset saved!');
            document.getElementById('save_preset_check').checked = false;
            document.getElementById('preset_fields').classList.add('hidden');
            loadPresets(); // Refresh grid
        }
    } catch (err) {
        console.error(err);
    }
}

async function deletePreset(id) {
    if (!confirm('Are you sure you want to delete this preset?')) return;
    try {
        await fetch(`/api/presets/${id}`, { method: 'DELETE' });
        loadPresets();
        showToast('Preset deleted');
    } catch (err) {
        showToast('Error deleting preset', true);
    }
}

function runPreset(id) {
    const preset = loadedPresets.find(p => p.id === id);
    if (!preset) return;

    // Populate form
    document.getElementById('screener_url').value = preset.url;
    document.getElementById('period').value = preset.period;
    document.getElementById('range').value = preset.range;

    // Populate MA
    const maCheck = document.getElementById('enable_ma');
    const maContainer = document.getElementById('ma_config_container');

    // Reset MAs first
    for (let i = 1; i <= 5; i++) {
        document.getElementById(`ma_${i}_enabled`).checked = false;
    }

    if (preset.moving_averages && Object.keys(preset.moving_averages).length > 0) {
        maCheck.checked = true;
        maContainer.classList.remove('hidden');

        Object.keys(preset.moving_averages).forEach(key => {
            const data = preset.moving_averages[key];
            const i = key.split('_')[1]; // ma_1 -> 1
            if (i) {
                document.getElementById(`ma_${i}_enabled`).checked = true;
                document.getElementById(`ma_${i}_field`).value = data.field;
                document.getElementById(`ma_${i}_type`).value = data.type;
                document.getElementById(`ma_${i}_period`).value = data.period;
            }
        });
    } else {
        maCheck.checked = false;
        maContainer.classList.add('hidden');
    }

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });

    // Trigger start
    startScraping();
}

// --- Scraping Logic ---

function toggleMASection() {
    const isChecked = document.getElementById('enable_ma').checked;
    const container = document.getElementById('ma_config_container');
    if (isChecked) {
        container.classList.remove('hidden');
    } else {
        container.classList.add('hidden');
    }
}

async function startScraping() {
    const url = document.getElementById('screener_url').value;
    const period = document.getElementById('period').value;
    const range = document.getElementById('range').value;

    // Moving Averages Collection
    let maConfig = null;
    if (document.getElementById('enable_ma') && document.getElementById('enable_ma').checked) {
        maConfig = {};
        for (let i = 1; i <= 5; i++) {
            if (document.getElementById(`ma_${i}_enabled`).checked) {
                maConfig[`ma_${i}`] = {
                    enabled: true,
                    field: document.getElementById(`ma_${i}_field`).value,
                    type: document.getElementById(`ma_${i}_type`).value,
                    period: parseInt(document.getElementById(`ma_${i}_period`).value)
                };
            }
        }
    }

    if (!url) {
        showToast('Please enter a URL', true);
        return;
    }

    // UI Reset
    const statusContainer = document.getElementById('statusContainer');
    statusContainer.classList.remove('hidden');
    document.getElementById('progressBar').style.width = '0%';
    document.getElementById('progressPercent').innerText = '0%';
    document.getElementById('statusText').innerText = 'Starting job...';
    document.getElementById('currentCompany').innerText = '';

    document.getElementById('downloadBtn').classList.add('hidden');
    document.getElementById('stopBtn').classList.remove('hidden'); // Show stop button

    try {
        const res = await fetch('/start_generation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url,
                period,
                range,
                moving_averages: maConfig
            })
        });
        const data = await res.json();

        if (data.job_id) {
            currentJobId = data.job_id;
            pollInterval = setInterval(pollStatus, 2000);
        } else {
            showToast('Failed to start job', true);
            document.getElementById('stopBtn').classList.add('hidden');
        }
    } catch (err) {
        console.error(err);
        showToast('Error connecting to server', true);
        document.getElementById('stopBtn').classList.add('hidden');
    }
}

async function stopJob() {
    if (!currentJobId) return;
    if (!confirm("Are you sure you want to stop the scan?")) return;

    try {
        const res = await fetch(`/stop_job/${currentJobId}`, { method: 'POST' });
        if (res.ok) {
            showToast('Stopping job...');
            document.getElementById('stopBtn').disabled = true;
            document.getElementById('stopBtn').innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Stopping...';
        }
    } catch (err) {
        showToast('Error stopping job', true);
    }
}

async function pollStatus() {
    if (!currentJobId) return;

    try {
        const res = await fetch(`/status/${currentJobId}`);
        const data = await res.json();

        if (data.status === 'not_found' || data.error) {
            clearInterval(pollInterval);
            document.getElementById('statusText').innerText = data.error || 'Unknown error';
            document.getElementById('statusText').classList.add('text-red-500');
            document.getElementById('stopBtn').classList.add('hidden');
            return;
        }

        // Update UI
        let percent = 0;
        if (data.total > 0) {
            percent = Math.round((data.processed / data.total) * 100);
        } else if (data.status === 'scraping_urls') {
            percent = 10;
        }

        document.getElementById('progressBar').style.width = `${percent}%`;
        document.getElementById('progressPercent').innerText = `${percent}%`;

        const statusMap = {
            'queued': 'Queued...',
            'running': 'Initializing...',
            'scraping_urls': 'Scraping Links...',
            'fetching_charts': `Processing ${data.processed} of ${data.total}`,
            'generating_pdf': 'Generating PDF...',
            'completed': 'Completed!',
            'stopped': 'Stopped.'
        };

        const statusLabel = statusMap[data.status] || data.status;
        document.getElementById('statusText').innerText = statusLabel;
        document.getElementById('statusText').classList.remove('text-red-500');

        if (data.current_company) {
            document.getElementById('currentCompany').innerText = `Current: ${data.current_company}`;
        }

        if (data.status === 'completed' || data.status === 'stopped') {
            clearInterval(pollInterval);
            document.getElementById('stopBtn').classList.add('hidden'); // Hide stop button

            const dlBtn = document.getElementById('downloadBtn');
            dlBtn.href = `/download/${currentJobId}`;
            dlBtn.classList.remove('hidden');

            if (data.telegram_sent) {
                showToast('PDF Sent to Telegram!');
            }
        }

    } catch (err) {
        console.error("Poll error", err);
    }
}

// --- Utils ---

function toggleSettings() {
    const modal = document.getElementById('settingsModal');
    if (modal.classList.contains('hidden')) {
        modal.classList.remove('hidden');
        setTimeout(() => document.getElementById('settingsModalContent').classList.remove('scale-95'), 10);
    } else {
        document.getElementById('settingsModalContent').classList.add('scale-95');
        setTimeout(() => modal.classList.add('hidden'), 200);
    }
}

function showToast(msg, isError = false) {
    const toast = document.getElementById('toast');
    const msgSpan = document.getElementById('toastMsg');

    msgSpan.innerText = msg;
    if (isError) {
        toast.querySelector('i').className = 'fa-solid fa-circle-exclamation text-red-500';
    } else {
        toast.querySelector('i').className = 'fa-solid fa-check-circle text-emerald-500';
    }

    toast.classList.remove('translate-y-20', 'opacity-0');
    setTimeout(() => {
        toast.classList.add('translate-y-20', 'opacity-0');
    }, 3000);
}

function escapeHtml(text) {
    if (!text) return text;
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
