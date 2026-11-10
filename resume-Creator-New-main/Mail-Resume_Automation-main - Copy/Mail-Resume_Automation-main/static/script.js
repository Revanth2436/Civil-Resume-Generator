document.addEventListener('DOMContentLoaded', () => {
    const jdInput = document.getElementById('jdInput');
    const draftEmailBtn = document.getElementById('draftEmailBtn');
    const draftStatus = document.getElementById('draftStatus');

    const jsonInput = document.getElementById('jsonInput');
    const generateResumeBtn = document.getElementById('generateResumeBtn');
    const generateStatus = document.getElementById('generateStatus');

    // Helper to set status
    function setStatus(element, message, type) {
        element.textContent = message;
        element.className = 'status-msg status-' + type;
        if (type === 'success') {
            setTimeout(() => {
                element.textContent = '';
                element.className = 'status-msg';
            }, 5000);
        }
    }

    // Load current resume JSON on startup
    fetch('/api/get-resume-data')
        .then(res => res.json())
        .then(data => {
            if (data && Object.keys(data).length > 0 && !jsonInput.value.trim()) {
                jsonInput.value = JSON.stringify(data, null, 2);
            }
        })
        .catch(err => console.log('Could not pre-load resume data:', err));

    // 1. Draft Email Handler
    draftEmailBtn.addEventListener('click', async () => {
        const jdText = jdInput.value.trim();
        if (!jdText) {
            setStatus(draftStatus, 'Please paste a JD first.', 'error');
            return;
        }

        setStatus(draftStatus, 'Drafting email...', 'loading');

        try {
            const response = await fetch('/api/draft-email', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ jd_text: jdText }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to draft email');
            }

            // Sync location to JSON textarea if detected
            if (data.location) {
                try {
                    let currentJson = jsonInput.value.trim() ? JSON.parse(jsonInput.value) : {};
                    currentJson.LOCATION = data.location;
                    jsonInput.value = JSON.stringify(currentJson, null, 2);
                } catch (e) {
                    console.log('Could not update JSON textarea location:', e);
                }
            }

            // If gmail_url is provided (cloud/Vercel or fallback), open it in a new tab
            if (data.gmail_url) {
                window.open(data.gmail_url, '_blank');
            }

            const locMsg = data.location ? ` | Location: ${data.location}` : '';
            setStatus(draftStatus, `Success! Draft opened. (Recipient: ${data.recipient || 'None found'}${locMsg})`, 'success');
        } catch (error) {
            setStatus(draftStatus, `Error: ${error.message}`, 'error');
        }
    });

    // 2. Generate Resume Handler
    generateResumeBtn.addEventListener('click', async () => {
        const jsonText = jsonInput.value.trim();
        if (!jsonText) {
            setStatus(generateStatus, 'Please paste JSON content first.', 'error');
            return;
        }

        let jsonObj;
        try {
            jsonObj = JSON.parse(jsonText);
        } catch (e) {
            setStatus(generateStatus, 'Invalid JSON format: ' + e.message, 'error');
            return;
        }

        setStatus(generateStatus, 'Generating resume...', 'loading');

        try {
            const response = await fetch('/api/generate-resume', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ json_content: jsonObj }),
            });

            if (!response.ok) {
                let errorMsg = 'Failed to generate resume';
                try {
                    const errData = await response.json();
                    errorMsg = errData.detail || errorMsg;
                } catch (_) {}
                throw new Error(errorMsg);
            }

            const contentType = response.headers.get('content-type') || '';
            const disposition = response.headers.get('content-disposition') || '';

            // Handle direct binary DOCX download (cloud / Vercel response)
            if (
                contentType.includes('application/vnd.openxmlformats') ||
                contentType.includes('application/octet-stream') ||
                disposition.includes('attachment')
            ) {
                const blob = await response.blob();
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = 'Revanth_Dirisipamu.docx';
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(downloadUrl);
                setStatus(generateStatus, 'Success! Resume generated and downloaded.', 'success');
            } else {
                // Handle JSON response (local desktop mode)
                const data = await response.json();
                if (data.download_url) {
                    window.location.href = data.download_url;
                }
                const folderName = data.path ? data.path.split('/').slice(-2, -1)[0] : '';
                const msg = folderName ? `Success! Created folder #${folderName} with Revanth_Dirisipamu.docx` : 'Success! Resume generated.';
                setStatus(generateStatus, msg, 'success');
            }
        } catch (error) {
            setStatus(generateStatus, `Error: ${error.message}`, 'error');
        }
    });
});
