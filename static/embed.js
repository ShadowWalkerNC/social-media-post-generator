/**
 * PostPilot Embed Widget  v1.0
 * Drop-in script for any external website.
 *
 * Usage:
 *   <div data-postpilot-slug="your-business-slug"
 *        data-postpilot-theme="light"
 *        data-postpilot-sections="posts,hours,services"></div>
 *   <script src="https://yourapp.com/static/embed.js" async></script>
 */
(function () {
  'use strict';

  const BASE_URL = (function () {
    const s = document.currentScript;
    if (s && s.src) {
      const u = new URL(s.src);
      return u.origin;
    }
    return '';
  })();

  const THEMES = {
    light: {
      bg: '#ffffff',
      card: '#f8fafc',
      border: '#e2e8f0',
      text: '#1e293b',
      muted: '#64748b',
      accent: '#6366f1',
    },
    dark: {
      bg: '#0f172a',
      card: '#1e293b',
      border: '#334155',
      text: '#f1f5f9',
      muted: '#94a3b8',
      accent: '#818cf8',
    },
  };

  function css(t) {
    return `
      .pp-widget { font-family: system-ui, sans-serif; background: ${t.bg}; color: ${t.text};
                   border: 1px solid ${t.border}; border-radius: 12px; padding: 20px;
                   max-width: 700px; box-sizing: border-box; }
      .pp-widget * { box-sizing: border-box; }
      .pp-section-title { font-size: 1.1rem; font-weight: 700; color: ${t.accent};
                          margin: 0 0 12px; border-bottom: 2px solid ${t.border}; padding-bottom: 6px; }
      .pp-post { background: ${t.card}; border: 1px solid ${t.border}; border-radius: 10px;
                 overflow: hidden; margin-bottom: 12px; }
      .pp-post img { width: 100%; max-height: 200px; object-fit: cover; display: block; }
      .pp-post-body { padding: 12px 14px; }
      .pp-post-caption { font-size: .9rem; line-height: 1.5; margin: 0 0 6px; }
      .pp-post-date { font-size: .75rem; color: ${t.muted}; margin: 0; }
      .pp-hours-row { display: flex; justify-content: space-between;
                      padding: 8px 12px; border-bottom: 1px solid ${t.border}; font-size: .88rem; }
      .pp-hours-row:last-child { border-bottom: none; }
      .pp-hours-label { font-weight: 600; }
      .pp-service { background: ${t.card}; border: 1px solid ${t.border}; border-radius: 10px;
                    padding: 14px; margin-bottom: 10px; }
      .pp-service-name { font-weight: 700; margin: 0 0 4px; }
      .pp-service-desc { font-size: .85rem; color: ${t.muted}; margin: 0 0 6px; }
      .pp-service-price { font-size: .88rem; font-weight: 600; color: ${t.accent}; margin: 0; }
      .pp-powered { text-align: right; font-size: .72rem; color: ${t.muted};
                    margin-top: 14px; opacity: .7; }
      .pp-powered a { color: ${t.accent}; text-decoration: none; }
      .pp-error { color: #ef4444; font-size: .85rem; padding: 10px 0; }
    `;
  }

  function renderPosts(posts, el) {
    if (!posts || !posts.length) {
      el.innerHTML += '<p style="color:#94a3b8;font-size:.85rem">No posts yet.</p>';
      return;
    }
    posts.slice(0, 6).forEach(function (p) {
      const d = document.createElement('div');
      d.className = 'pp-post';
      const img = p.image_url ? `<img src="${p.image_url}" alt="" loading="lazy">` : '';
      const cap = (p.caption || '').slice(0, 160) + ((p.caption || '').length > 160 ? '\u2026' : '');
      const dt  = p.created_at ? `<p class="pp-post-date">${p.created_at}</p>` : '';
      d.innerHTML = img + `<div class="pp-post-body"><p class="pp-post-caption">${cap}</p>${dt}</div>`;
      el.appendChild(d);
    });
  }

  function renderHours(hours, el) {
    if (!hours || !Object.keys(hours).length) {
      el.innerHTML += '<p style="color:#94a3b8;font-size:.85rem">Hours not set.</p>';
      return;
    }
    const tbl = document.createElement('div');
    tbl.style.cssText = 'border:1px solid var(--pp-border);border-radius:8px;overflow:hidden';
    Object.entries(hours).forEach(function (kv) {
      const row = document.createElement('div');
      row.className = 'pp-hours-row';
      row.innerHTML = `<span class="pp-hours-label">${kv[0]}</span><span>${kv[1]}</span>`;
      tbl.appendChild(row);
    });
    el.appendChild(tbl);
  }

  function renderServices(services, el) {
    if (!services || !services.length) {
      el.innerHTML += '<p style="color:#94a3b8;font-size:.85rem">No services listed.</p>';
      return;
    }
    services.forEach(function (s) {
      const d = document.createElement('div');
      d.className = 'pp-service';
      const icon  = s.icon  ? `<span style="font-size:1.4rem;margin-right:6px">${s.icon}</span>` : '';
      const desc  = s.description ? `<p class="pp-service-desc">${s.description}</p>` : '';
      const price = s.price ? `<p class="pp-service-price">${s.price}</p>` : '';
      d.innerHTML = `<p class="pp-service-name">${icon}${s.name || ''}</p>${desc}${price}`;
      el.appendChild(d);
    });
  }

  function buildWidget(container, data) {
    const themeKey = (container.dataset.postpilotTheme || 'light').toLowerCase();
    const t = THEMES[themeKey] || THEMES.light;
    const wantedRaw = container.dataset.postpilotSections || 'posts,hours,services';
    const wanted = wantedRaw.split(',').map(function (s) { return s.trim(); });

    // inject scoped styles once
    if (!document.getElementById('pp-embed-styles')) {
      const style = document.createElement('style');
      style.id = 'pp-embed-styles';
      style.textContent = css(t);
      document.head.appendChild(style);
    }

    const widget = document.createElement('div');
    widget.className = 'pp-widget';

    if (wanted.includes('posts') && data.recent_posts) {
      const sec = document.createElement('div');
      const h   = document.createElement('p');
      h.className = 'pp-section-title';
      h.textContent = data.name ? data.name + ' — Latest Updates' : 'Latest Updates';
      sec.appendChild(h);
      renderPosts(data.recent_posts, sec);
      widget.appendChild(sec);
    }

    if (wanted.includes('hours') && data.hours) {
      const sec = document.createElement('div');
      const h   = document.createElement('p');
      h.className = 'pp-section-title';
      h.textContent = 'Hours';
      sec.appendChild(h);
      renderHours(data.hours, sec);
      widget.appendChild(sec);
    }

    if (wanted.includes('services') && data.services) {
      const sec = document.createElement('div');
      const h   = document.createElement('p');
      h.className = 'pp-section-title';
      h.textContent = 'Services';
      sec.appendChild(h);
      renderServices(data.services, sec);
      widget.appendChild(sec);
    }

    const pow = document.createElement('p');
    pow.className = 'pp-powered';
    pow.innerHTML = 'Powered by <a href="' + BASE_URL + '" target="_blank" rel="noopener">PostPilot</a>';
    widget.appendChild(pow);

    container.innerHTML = '';
    container.appendChild(widget);
  }

  function initWidgets() {
    const containers = document.querySelectorAll('[data-postpilot-slug]');
    containers.forEach(function (container) {
      const slug = container.dataset.postpilotSlug;
      if (!slug) return;

      const url = BASE_URL + '/api/embed/' + encodeURIComponent(slug);
      fetch(url)
        .then(function (r) {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.json();
        })
        .then(function (data) {
          if (data.success) {
            buildWidget(container, data);
          } else {
            container.innerHTML = '<p class="pp-error">PostPilot: ' + (data.error || 'Not found') + '</p>';
          }
        })
        .catch(function (err) {
          container.innerHTML = '<p class="pp-error">PostPilot widget could not load.</p>';
          console.warn('[PostPilot embed]', err);
        });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initWidgets);
  } else {
    initWidgets();
  }
})();
