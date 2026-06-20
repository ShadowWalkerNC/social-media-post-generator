// PostPilot Pro — Frontend Logic

function switchTab(name, el) {
    document.querySelectorAll('.tab-content').forEach(t => t.style.display = 'none');
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.getElementById(name).style.display = 'block';
    el.classList.add('active');
}

async function generateWeekly() {
    const btn = document.querySelector('#weekly .btn-success');
    btn.textContent = '⏳ Generating...';
    btn.disabled = true;
    const res  = await fetch('/api/generate_weekly', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_id: 'default'})
    });
    const data = await res.json();
    btn.textContent = '⚡ Generate Week of Posts';
    btn.disabled = false;
    if (!data.success) { alert('Error: ' + data.error); return; }
    renderPosts(data.schedule, 'weeklyResult');
}

async function generateSingle() {
    const template = document.getElementById('templateSelect').value;
    const res  = await fetch('/api/generate_post', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_id: 'default', template})
    });
    const data = await res.json();
    if (!data.success) { alert('Error generating post'); return; }
    renderPosts([data.post], 'singleResult');
}

function renderPosts(posts, targetId) {
    let html = '';
    posts.forEach((post, i) => {
        const isFb  = post.platform === 'facebook';
        const badge = isFb
            ? '<span class="badge badge-fb">📘 Facebook</span>'
            : '<span class="badge badge-ig">📸 Instagram</span>';
        html += `
            <div class="post-card ${isFb ? 'fb' : ''}">
                <div class="post-header">${badge}<span class="post-time">🕐 ${post.post_time}</span></div>
                <pre class="post-caption">${esc(post.caption)}</pre>
                <div class="post-img-hint">📸 ${post.image_suggestion}</div>
                <div class="post-actions">
                    <button class="btn" onclick="copyCaption(${i})">📋 Copy Caption</button>
                    <button class="btn btn-success" onclick="publishPost('${post.platform}', '${escAttr(post.caption)}')">🚀 Publish Now</button>
                    <button class="btn btn-secondary" onclick="showScheduler('${escAttr(post.caption)}', '${post.platform}')">📅 Schedule</button>
                </div>
            </div>`;
    });
    document.getElementById(targetId).innerHTML = html;
    window._posts = posts;
}

function copyCaption(i) {
    navigator.clipboard.writeText(window._posts[i].caption)
        .then(() => alert('✅ Caption copied to clipboard!'));
}

async function publishPost(platform, caption) {
    const imageUrl = prompt('📸 Paste image URL (or leave empty for text-only):');
    const endpoint = platform === 'facebook' ? '/api/publish_facebook' : '/api/publish_instagram';
    const res  = await fetch(endpoint, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_id: 'default', post: {caption}, image_url: imageUrl || null})
    });
    const data = await res.json();
    data.success ? alert(`✅ Published! Post ID: ${data.post_id}`) : alert(`❌ Error: ${data.error}`);
}

function showScheduler(caption, platform) {
    const dt = prompt('📅 Schedule date & time (e.g. 2026-06-23T08:00:00):');
    if (!dt) return;
    const imageUrl = prompt('📸 Image URL (or leave empty):');
    schedulePost(caption, platform, dt, imageUrl);
}

async function schedulePost(caption, platform, publishTime, imageUrl) {
    const res  = await fetch('/api/schedule_post', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({caption, platform, publish_time: publishTime, image_url: imageUrl || null, user_id: 'default'})
    });
    const data = await res.json();
    data.success ? alert(`📅 Scheduled for ${data.scheduled_for}!`) : alert(`❌ Error: ${data.error}`);
}

async function bulkSchedule() {
    if (!window._posts || !window._posts.length) { alert('Generate posts first!'); return; }
    alert('📅 Bulk scheduling — connect Facebook and use the Schedule button on each post.');
}

function esc(str) {
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function escAttr(str) {
    return str.replace(/'/g,"&#39;").replace(/"/g,'&quot;').replace(/\n/g,' ');
}
