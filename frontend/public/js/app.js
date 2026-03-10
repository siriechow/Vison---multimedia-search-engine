/**
 * Vison — Multimedia Search Engine
 * Frontend Application Logic
 */

(() => {
    'use strict';

    // ━━━ State ━━━
    const state = {
        selectedFile: null,
        currentSection: 'search',
        activeFilter: 'all',
        crawlPollingInterval: null,
    };

    // ━━━ DOM Elements ━━━
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // ━━━ Toast System ━━━
    function showToast(message, type = 'info') {
        let container = $('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(30px)';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // ━━━ Section Navigation ━━━
    function switchSection(section) {
        state.currentSection = section;
        $$('.section').forEach(el => el.classList.remove('active'));
        $(`#section-${section}`)?.classList.add('active');
        $$('.nav-link').forEach(el => {
            el.classList.toggle('active', el.dataset.section === section);
        });

        if (section === 'index') loadIndexStats();
    }

    $$('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            switchSection(link.dataset.section);
        });
    });

    // ━━━ File Upload & Drag-Drop ━━━
    const uploadZone = $('#upload-zone');
    const fileInput = $('#file-input');
    const previewEl = $('#upload-preview');
    const uploadContent = uploadZone?.querySelector('.upload-content');

    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function showFilePreview(file) {
        state.selectedFile = file;
        uploadContent.style.display = 'none';
        previewEl.style.display = 'flex';

        const mediaEl = $('#preview-media');
        mediaEl.innerHTML = '';
        $('#preview-name').textContent = file.name;
        $('#preview-size').textContent = formatBytes(file.size);

        if (file.type.startsWith('image/')) {
            const img = document.createElement('img');
            img.src = URL.createObjectURL(file);
            mediaEl.appendChild(img);
        } else if (file.type.startsWith('video/')) {
            const video = document.createElement('video');
            video.src = URL.createObjectURL(file);
            video.muted = true;
            mediaEl.appendChild(video);
        } else if (file.type.startsWith('audio/')) {
            mediaEl.innerHTML = `<svg class="audio-icon" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>`;
        }

        $('#search-btn').disabled = false;
    }

    function clearFilePreview() {
        state.selectedFile = null;
        uploadContent.style.display = 'block';
        previewEl.style.display = 'none';
        fileInput.value = '';
        $('#search-btn').disabled = true;
    }

    if (uploadZone) {
        uploadZone.addEventListener('click', (e) => {
            if (!e.target.closest('#preview-remove') && !previewEl?.contains(e.target)) {
                fileInput.click();
            }
        });

        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('drag-over');
        });

        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('drag-over');
        });

        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('drag-over');
            const files = e.dataTransfer.files;
            if (files.length > 0) showFilePreview(files[0]);
        });
    }

    fileInput?.addEventListener('change', (e) => {
        if (e.target.files.length > 0) showFilePreview(e.target.files[0]);
    });

    $('#preview-remove')?.addEventListener('click', (e) => {
        e.stopPropagation();
        clearFilePreview();
    });

    // ━━━ Upload Search ━━━
    $('#search-btn')?.addEventListener('click', async () => {
        if (!state.selectedFile) return;

        showLoading('Extracting features and searching...');

        try {
            const formData = new FormData();
            formData.append('file', state.selectedFile);
            formData.append('top_k', '20');

            const response = await fetch('/api/search/upload', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Search failed');
            }

            const data = await response.json();
            displayResults(data);
        } catch (error) {
            showToast(error.message, 'error');
        } finally {
            hideLoading();
        }
    });

    // ━━━ Text Search ━━━
    $('#text-search-btn')?.addEventListener('click', performTextSearch);
    $('#text-search-input')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') performTextSearch();
    });

    async function performTextSearch() {
        const query = $('#text-search-input')?.value?.trim();
        if (!query) return;

        showLoading('Searching indexed content...');

        try {
            const mediaType = state.activeFilter !== 'all' ? `&media_type=${state.activeFilter}` : '';
            const response = await fetch(`/api/search/text?q=${encodeURIComponent(query)}&top_k=20${mediaType}`);

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Search failed');
            }

            const data = await response.json();
            displayResults(data);
        } catch (error) {
            showToast(error.message, 'error');
        } finally {
            hideLoading();
        }
    }

    // ━━━ Filter Tabs ━━━
    $$('.filter-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            $$('.filter-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            state.activeFilter = tab.dataset.type;
        });
    });

    // ━━━ Display Results ━━━
    function displayResults(data) {
        const section = $('#results-section');
        const grid = $('#results-grid');
        const emptyState = $('#empty-state');

        if (data.total_results === 0) {
            section.style.display = 'none';
            emptyState.style.display = 'block';
            emptyState.querySelector('h3').textContent = 'No results found';
            emptyState.querySelector('p').textContent = 'Try uploading a different file or adjusting your search query.';
            return;
        }

        emptyState.style.display = 'none';
        section.style.display = 'block';

        $('#results-title').textContent = `Search Results`;
        $('#results-count').textContent = `${data.total_results} result${data.total_results !== 1 ? 's' : ''}`;
        $('#results-time').textContent = `${data.processing_time_ms}ms`;

        grid.innerHTML = '';

        data.results.forEach((result, index) => {
            const card = document.createElement('div');
            card.className = 'result-card';
            card.style.animationDelay = `${index * 0.05}s`;

            const badgeClass = `badge-${result.media_type}`;
            const thumbnailContent = result.thumbnail_path
                ? `<img src="/api/index/thumbnail/${result.id}" alt="${result.title || 'Media'}" loading="lazy">`
                : getPlaceholderIcon(result.media_type);

            const keywords = result.keywords
                ? result.keywords.split(',').slice(0, 4).map(k =>
                    `<span class="keyword-tag">${k.trim()}</span>`
                ).join('')
                : '';

            card.innerHTML = `
                <div class="result-thumbnail">
                    ${thumbnailContent}
                    <span class="media-type-badge ${badgeClass}">${result.media_type}</span>
                    <span class="result-score">${(result.similarity_score * 100).toFixed(1)}%</span>
                </div>
                <div class="result-info">
                    <div class="result-title">${result.title || 'Untitled'}</div>
                    <div class="result-url">${result.url || result.source_url || ''}</div>
                    ${keywords ? `<div class="result-keywords">${keywords}</div>` : ''}
                </div>
            `;

            card.addEventListener('click', () => showDetailModal(result));
            grid.appendChild(card);
        });
    }

    function getPlaceholderIcon(mediaType) {
        const icons = {
            image: `<svg class="result-placeholder-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`,
            audio: `<svg class="result-placeholder-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>`,
            video: `<svg class="result-placeholder-icon" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>`,
        };
        return icons[mediaType] || icons.image;
    }

    // ━━━ Detail Modal ━━━
    function showDetailModal(item) {
        const modal = $('#detail-modal');
        const body = $('#modal-body');

        let mediaPreview = '';
        if (item.media_type === 'image') {
            mediaPreview = `<img src="/api/index/media/${item.id}" alt="${item.title || ''}">`;
        } else if (item.media_type === 'video') {
            mediaPreview = `<video src="/api/index/media/${item.id}" controls></video>`;
        } else if (item.media_type === 'audio') {
            mediaPreview = `<audio src="/api/index/media/${item.id}" controls style="width:100%;margin-bottom:1rem"></audio>`;
        }

        body.innerHTML = `
            ${mediaPreview}
            <h2>${item.title || 'Untitled'}</h2>
            ${item.description ? `<p style="color:var(--color-text-secondary);margin-bottom:1rem">${item.description}</p>` : ''}
            <div class="detail-row">
                <span class="detail-label">Type</span>
                <span class="detail-value">${item.media_type}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Similarity</span>
                <span class="detail-value" style="color:var(--color-accent)">${(item.similarity_score * 100).toFixed(2)}%</span>
            </div>
            ${item.url ? `<div class="detail-row"><span class="detail-label">URL</span><span class="detail-value"><a href="${item.url}" target="_blank" style="color:var(--color-primary-light)">${item.url}</a></span></div>` : ''}
            ${item.source_url ? `<div class="detail-row"><span class="detail-label">Source</span><span class="detail-value">${item.source_url}</span></div>` : ''}
            ${item.keywords ? `<div class="detail-row"><span class="detail-label">Keywords</span><span class="detail-value">${item.keywords}</span></div>` : ''}
        `;

        modal.style.display = 'flex';
    }

    $('#modal-close')?.addEventListener('click', () => {
        $('#detail-modal').style.display = 'none';
    });

    $('#detail-modal')?.addEventListener('click', (e) => {
        if (e.target === e.currentTarget) {
            $('#detail-modal').style.display = 'none';
        }
    });

    // ━━━ Loading ━━━
    function showLoading(text = 'Processing...') {
        const overlay = $('#loading-overlay');
        $('#loading-text').textContent = text;
        overlay.style.display = 'flex';
    }

    function hideLoading() {
        $('#loading-overlay').style.display = 'none';
    }

    // ━━━ Crawler ━━━
    $('#crawl-start-btn')?.addEventListener('click', async () => {
        const url = $('#crawl-url')?.value?.trim();
        if (!url) {
            showToast('Please enter a URL to crawl', 'warning');
            return;
        }

        try {
            const response = await fetch('/api/crawler/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url,
                    max_depth: parseInt($('#crawl-depth')?.value || '2'),
                    max_pages: parseInt($('#crawl-pages')?.value || '50'),
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to start crawl');
            }

            showToast('Crawl started!', 'success');
            $('#crawl-start-btn').disabled = true;
            $('#crawl-stop-btn').disabled = false;
            $('#crawler-status').style.display = 'block';

            // Start polling status
            startCrawlPolling();
        } catch (error) {
            showToast(error.message, 'error');
        }
    });

    $('#crawl-stop-btn')?.addEventListener('click', async () => {
        try {
            await fetch('/api/crawler/stop', { method: 'POST' });
            showToast('Crawl stop requested', 'warning');
            stopCrawlPolling();
            $('#crawl-start-btn').disabled = false;
            $('#crawl-stop-btn').disabled = true;
        } catch (error) {
            showToast('Failed to stop crawl', 'error');
        }
    });

    function startCrawlPolling() {
        state.crawlPollingInterval = setInterval(updateCrawlStatus, 2000);
    }

    function stopCrawlPolling() {
        if (state.crawlPollingInterval) {
            clearInterval(state.crawlPollingInterval);
            state.crawlPollingInterval = null;
        }
    }

    async function updateCrawlStatus() {
        try {
            const response = await fetch('/api/crawler/status');
            const data = await response.json();
            const crawler = data.crawler;

            $('#crawl-status-text').textContent = crawler.status;
            $('#crawl-pages-count').textContent = crawler.pages_crawled;
            $('#crawl-items-count').textContent = crawler.items_found;

            // Update progress (approximate based on max pages)
            const maxPages = parseInt($('#crawl-pages')?.value || '50');
            const progress = Math.min((crawler.pages_crawled / maxPages) * 100, 100);
            $('#crawl-progress-fill').style.width = `${progress}%`;

            if (!crawler.is_running && crawler.status !== 'idle') {
                stopCrawlPolling();
                $('#crawl-start-btn').disabled = false;
                $('#crawl-stop-btn').disabled = true;
                showToast(`Crawl ${crawler.status}: ${crawler.items_found} items indexed`, 'success');
            }
        } catch (error) {
            // Backend might be unavailable
        }
    }

    // ━━━ Index Management ━━━
    async function loadIndexStats() {
        try {
            const response = await fetch('/api/index/stats');
            if (!response.ok) return;
            const data = await response.json();

            $('#stat-images').textContent = data.by_type?.image || 0;
            $('#stat-audio').textContent = data.by_type?.audio || 0;
            $('#stat-video').textContent = data.by_type?.video || 0;
            $('#stat-crawls').textContent = data.crawl_sessions || 0;

            // Also load items list
            loadIndexedItems();
        } catch (error) {
            // Backend might not be running
        }
    }

    async function loadIndexedItems() {
        try {
            const response = await fetch('/api/index/items?limit=50');
            if (!response.ok) return;
            const data = await response.json();

            const grid = $('#indexed-items-grid');
            grid.innerHTML = '';

            if (data.items.length === 0) {
                grid.innerHTML = '<p style="color:var(--color-text-muted);text-align:center;padding:2rem">No items indexed yet. Use the crawler or upload files to get started.</p>';
                return;
            }

            data.items.forEach((item, index) => {
                const card = document.createElement('div');
                card.className = 'result-card';
                card.style.animationDelay = `${index * 0.03}s`;

                const badgeClass = `badge-${item.media_type}`;

                card.innerHTML = `
                    <div class="result-thumbnail">
                        ${item.thumbnail_path ? `<img src="/api/index/thumbnail/${item.id}" alt="${item.title || ''}" loading="lazy">` : getPlaceholderIcon(item.media_type)}
                        <span class="media-type-badge ${badgeClass}">${item.media_type}</span>
                    </div>
                    <div class="result-info">
                        <div class="result-title">${item.title || 'Untitled'}</div>
                        <div class="result-url">${item.url || 'Manually added'}</div>
                    </div>
                `;

                card.addEventListener('click', () => {
                    showDetailModal({ ...item, similarity_score: 1.0 });
                });

                grid.appendChild(card);
            });
        } catch (error) {
            // Backend might not be running
        }
    }

    // Add to index
    $('#add-btn')?.addEventListener('click', async () => {
        const fileInput = $('#add-file');
        const title = $('#add-title')?.value?.trim();
        const description = $('#add-description')?.value?.trim();

        if (!fileInput?.files?.length) {
            showToast('Please select a file', 'warning');
            return;
        }

        const statusEl = $('#add-status');
        statusEl.textContent = 'Uploading and indexing...';
        statusEl.style.color = 'var(--color-primary-light)';

        try {
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            if (title) formData.append('title', title);
            if (description) formData.append('description', description);

            const response = await fetch(`/api/index/add?title=${encodeURIComponent(title || '')}&description=${encodeURIComponent(description || '')}`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Failed to add item');
            }

            const data = await response.json();
            showToast(data.message, 'success');
            statusEl.textContent = `✓ ${data.message}`;
            statusEl.style.color = 'var(--color-success)';

            // Refresh stats and items
            loadIndexStats();

            // Clear form
            $('#add-title').value = '';
            $('#add-description').value = '';
            fileInput.value = '';
        } catch (error) {
            showToast(error.message, 'error');
            statusEl.textContent = `✕ ${error.message}`;
            statusEl.style.color = 'var(--color-error)';
        }
    });

    // Refresh button
    $('#refresh-items-btn')?.addEventListener('click', loadIndexStats);

    // ━━━ Interactive background glow ━━━
    document.addEventListener('mousemove', (e) => {
        document.documentElement.style.setProperty('--x', e.clientX + 'px');
        document.documentElement.style.setProperty('--y', e.clientY + 'px');
    });

    // ━━━ Keyboard shortcuts ━━━
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            $('#detail-modal').style.display = 'none';
        }
    });

    // ━━━ Init ━━━
    console.log('%c🔍 Vison', 'font-size:20px;font-weight:bold;background:linear-gradient(135deg,#7c3aed,#2dd4bf);-webkit-background-clip:text;-webkit-text-fill-color:transparent');
    console.log('%cMultimedia Search Engine v1.0.0', 'color:#9ca3af');

})();
