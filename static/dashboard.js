// PostPilot Pro — Command Center JS

let platforms = { fb: false, ig: false, tt: false, gb: false, web: false };
let postsThisWeek = 0;

document.addEventListener('DOMContentLoaded', () => {
    checkConnections();
    bindPreviewUpdates();
    updateStats();
});

// ── Platform Connection Status ────────────────────────────────────
function checkConnections() {
    fetch('/api/connection_status', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({user_id: 'default'}) })
        .then(r => r.json())
        .then(data => {
            Object.entries(data.platforms || {}).forEach(([key, connected]) => {
                platforms[key] = connected;
                const pill = document.getElementById('pill-' + key);
                if (pill) pill.classList.toggle('connected', connected);
            });
            const live = Object.values(platforms).filter(Boolean).length;
            document.getElementById('stat-platforms').textContent = live + '/5';
        })
        .catch(() => {}); // silent fail in testing
}

// ── Live Preview ──────────────────────────────────────────────────
function bindPreviewUpdates() {
    const cap   = document.getElementById('mainCaption');
    const img   = document.getElementById('imageUrl');
    const link  = document.getElementById('linkUrl');
    [cap, img, link].forEach(el => el && el.addEventListener('input', updatePreview));
}

function updatePreview() {
    const caption = document.getElementById('mainCaption').value || 'Your post will preview here…';
    const imgUrl  = document.getElementById('imageUrl').value;
    const linkUrl = document.getElementById('linkUrl').value || '#';
    const tiktok  = toTikTokScript(caption);
    const gbText  = toGooglePost(caption);

    // Facebook
    document.getElementById('prev-fb-text').textContent = caption;
    const fbImg = document.getElementById('prev-fb-img');
    const fbImgEl = document.getElementById('prev-fb-imgEl');
    if (imgUrl) { fbImgEl.src = imgUrl; fbImg.style.display = 'block'; } else { fbImg.style.display = 'none'; }

    // Instagram
    document.getElementById('prev-ig-text').textContent = caption;
    const igImgBox = document.querySelector('#preview-ig .mock-img');
    if (imgUrl) { igImgBox.innerHTML = `<img src="${imgUrl}" style="width:100%;max-height:300px;object-fit:cover">`; }
    else { igImgBox.innerHTML = '<div class="mock-img-placeholder">📷 Image Preview</div>'; }

    // TikTok
    document.getElementById('prev-tt-text').textContent = tiktok;

    // Google Business
    document.getElementById('prev-gb-text').textContent = gbText;
    document.getElementById('prev-gb-link').href = linkUrl;

    // Website Banner
    document.getElementById('prev-web-text').textContent = '📣 ' + caption.split('\n')[0];
    document.getElementById('prev-web-link').href = linkUrl;
}

function switchPreview(name, el) {
    document.querySelectorAll('.preview-frame').forEach(f => f.style.display = 'none');
    document.querySelectorAll('.ptab').forEach(t => t.classList.remove('active'));
    document.getElementById('preview-' + name).style.display = 'block';
    el.classList.add('active');
}

// ── Auto-Generate Caption ─────────────────────────────────────────
async function autoGenerate() {
    const template = 'instagram_location';
    try {
        const res  = await fetch('/api/generate_post', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ user_id: 'default', template })
        });
        const data = await res.json();
        if (data.success) {
            document.getElementById('mainCaption').value = data.post.caption;
            updatePreview();
            toast('✨ Caption auto-generated!', 'success');
        }
    } catch (e) { toast('Could not auto-generate — check setup', 'error'); }
}

// ── Push to All Platforms ─────────────────────────────────────────
async function pushToAll() {
    const caption   = document.getElementById('mainCaption').value.trim();
    const imageUrl  = document.getElementById('imageUrl').value.trim() || null;
    const linkUrl   = document.getElementById('linkUrl').value.trim() || null;
    const schedTime = document.getElementById('scheduleTime').value;

    if (!caption) { toast('Please write a caption first!', 'warn'); return; }

    const selected = {
        fb:  document.getElementById('tog-fb').checked,
        ig:  document.getElementById('tog-ig').checked,
        tt:  document.getElementById('tog-tt').checked,
        gb:  document.getElementById('tog-gb').checked,
        web: document.getElementById('tog-web').checked
    };

    if (!Object.values(selected).some(Boolean)) {
        toast('Select at least one platform!', 'warn'); return;
    }

    addFeed('🚀 Pushing update to selected platforms…', 'info');

    const payload = {
        user_id: 'default',
        caption, image_url: imageUrl, link_url: linkUrl,
        platforms: selected,
        schedule_time: schedTime || null
    };

    try {
        const res  = await fetch('/api/push_all', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        Object.entries(data.results || {}).forEach(([platform, result]) => {
            const name = { fb: 'Facebook', ig: 'Instagram', tt: 'TikTok', gb: 'Google Business', web: 'Website' }[platform];
            if (result.success) {
                addFeed(`✅ ${name}: ${result.message || 'Published!'}`, 'success');
                toast(`✅ ${name} updated`, 'success');
            } else if (result.skipped) {
                // silently skip unchecked platforms
            } else {
                addFeed(`❌ ${name}: ${result.error || 'Failed'}`, 'error');
                toast(`❌ ${name} error`, 'error');
            }
        });

        postsThisWeek++;
        document.getElementById('stat-posts').textContent = postsThisWeek;

    } catch (e) {
        addFeed('❌ Network error — check connection', 'error');
        toast('Network error', 'error');
    }
}

async function loadWeeklyPlan() {
    try {
        const res  = await fetch('/api/generate_weekly', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ user_id: 'default' })
        });
        const data = await res.json();
        if (data.success) {
            toast('📅 Weekly plan ready — go to Generate page', 'info');
            addFeed('📋 Weekly plan generated (' + data.schedule.length + ' posts)', 'info');
        }
    } catch (e) { toast('Could not load plan', 'error'); }
}

// ── Content Transformers ──────────────────────────────────────────
function toTikTokScript(caption) {
    const first = caption.split('\n')[0];
    return `🎵 TIKTOK SCRIPT\n\n[HOOK — first 3 seconds]\n"${first}"\n\n[BODY]\n${caption}\n\n[CALL TO ACTION]\n"Follow us for daily updates — link in bio!"\n\n#foodtok #fyp #viral`;
}

function toGooglePost(caption) {
    return caption.replace(/[#🔥🌟⭐💥✨🎉🎊🎁🎵📸📘📍🚀✏️]/g, '').trim().substring(0, 300);
}

// ── Helpers ───────────────────────────────────────────────────────
function addFeed(message, type = 'info') {
    const feed = document.getElementById('activityFeed');
    const el   = document.createElement('div');
    el.className = 'feed-item feed-' + type;
    el.textContent = new Date().toLocaleTimeString() + ' — ' + message;
    feed.insertBefore(el, feed.firstChild);
    if (feed.children.length > 50) feed.removeChild(feed.lastChild);
}

function toast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const el        = document.createElement('div');
    el.className    = 'toast toast-' + type;
    el.textContent  = message;
    container.appendChild(el);
    setTimeout(() => el.remove(), 3500);
}

function updateStats() {
    // Load from API when connected
    fetch('/api/analytics', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ user_id: 'default' })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success && data.posts) {
            document.getElementById('stat-posts').textContent  = data.total_posts || 0;
            const totalReach = data.posts.reduce((s, p) => s + (p.reach || 0), 0);
            const totalLikes = data.posts.reduce((s, p) => s + (p.likes || 0), 0);
            document.getElementById('stat-reach').textContent = totalReach > 999 ? (totalReach/1000).toFixed(1)+'k' : totalReach;
            document.getElementById('stat-likes').textContent = totalLikes;
        }
    })
    .catch(() => {});
}
