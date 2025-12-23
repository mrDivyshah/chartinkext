document.addEventListener('DOMContentLoaded', () => {
    const enableMaCheckbox = document.getElementById('enable_ma');
    const maSettings = document.getElementById('ma-settings');
    const form = document.getElementById('chartForm');
    const submitBtn = document.getElementById('submitBtn');
    const spinner = submitBtn.querySelector('.spinner');
    const btnText = submitBtn.querySelector('.btn-text');
    const statusMessage = document.getElementById('statusMessage');
    const errorContainer = document.getElementById('errorContainer');
    const errorText = errorContainer.querySelector('.error-text');

    // Toggle MA settings visibility
    enableMaCheckbox.addEventListener('change', () => {
        if (enableMaCheckbox.checked) {
            maSettings.classList.remove('hidden');
        } else {
            maSettings.classList.add('hidden');
        }
    });

    // Form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Check if loading
        if (submitBtn.disabled) return;

        // Reset UI
        submitBtn.disabled = true;
        spinner.classList.remove('hidden');
        btnText.textContent = 'Starting...';
        statusMessage.classList.remove('hidden');
        errorContainer.classList.add('hidden');

        // Reset progress
        const progressBar = document.getElementById('progressBar');
        const statusText = document.getElementById('statusText');
        const detailText = document.getElementById('detailText');
        progressBar.style.width = '0%';
        statusText.textContent = 'Initializing...';
        detailText.textContent = '';

        // Gather data
        const screenerUrl = document.getElementById('screener_url').value;
        const range = document.getElementById('range').value;
        const period = document.getElementById('period').value;

        let movingAverages = [];
        if (enableMaCheckbox.checked) {
            const maRows = document.querySelectorAll('.ma-row');
            maRows.forEach(row => {
                const enabled = row.querySelector('div.ma-check input').checked;
                const select = row.querySelector('.ma-select').value;
                const type = row.querySelector('.ma-type').value;
                const number = parseInt(row.querySelector('.ma-number').value, 10);

                movingAverages.push({
                    enabled: enabled,
                    select: select,
                    type: type,
                    number: number
                });
            });
        }

        if (!enableMaCheckbox.checked) {
            movingAverages = Array(5).fill({ enabled: false, select: 'Close', type: 'Simple', number: 20 });
        }

        const payload = {
            screener_url: screenerUrl,
            range: range,
            period: period,
            moving_averages: movingAverages
        };

        try {
            // Start generation
            const startResponse = await fetch('/start_generation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!startResponse.ok) {
                const errorData = await startResponse.json();
                throw new Error(errorData.error || 'Failed to start generation');
            }

            const { job_id } = await startResponse.json();

            // Poll for status
            const pollInterval = setInterval(async () => {
                try {
                    const statusResponse = await fetch(`/status/${job_id}`);
                    if (!statusResponse.ok) throw new Error('Failed to get status');

                    const statusData = await statusResponse.json();

                    // Update UI
                    if (statusData.status === 'scraping_urls') {
                        statusText.textContent = 'Scanning screener for stocks...';
                        progressBar.style.width = '10%';
                    } else if (statusData.status === 'fetching_charts') {
                        const total = statusData.total;
                        const processed = statusData.processed;
                        const percentage = 10 + Math.round((processed / total) * 80); // 10% to 90%

                        progressBar.style.width = `${percentage}%`;
                        statusText.textContent = `Fetching charts: ${processed} / ${total}`;
                        detailText.textContent = `Processing: ${statusData.current_company}`;
                    } else if (statusData.status === 'generating_pdf') {
                        statusText.textContent = 'Compiling PDF...';
                        progressBar.style.width = '95%';
                        detailText.textContent = '';
                    } else if (statusData.status === 'completed') {
                        clearInterval(pollInterval);
                        progressBar.style.width = '100%';
                        statusText.textContent = 'Done!';
                        btnText.textContent = 'Generate PDF';
                        submitBtn.disabled = false;
                        spinner.classList.add('hidden');

                        // Trigger download
                        window.location.href = `/download/${job_id}`;
                    } else if (statusData.status === 'failed') {
                        clearInterval(pollInterval);
                        throw new Error(statusData.error || 'Job failed');
                    }

                } catch (err) {
                    clearInterval(pollInterval);
                    console.error('Polling error:', err);
                    statusMessage.classList.add('hidden');
                    errorContainer.classList.remove('hidden');
                    errorText.textContent = err.message;
                    submitBtn.disabled = false;
                    spinner.classList.add('hidden');
                    btnText.textContent = 'Generate PDF';
                }
            }, 1000);

        } catch (error) {
            console.error('Error:', error);
            statusMessage.classList.add('hidden');
            errorContainer.classList.remove('hidden');
            errorText.textContent = error.message;
            submitBtn.disabled = false;
            spinner.classList.add('hidden');
            btnText.textContent = 'Generate PDF';
        }
    });
});
