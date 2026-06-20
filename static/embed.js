// PostPilot Pro — Website Banner Embed
// Add this ONE line to your website's <head>:
// <script src="https://YOUR-APP-URL/static/embed.js"></script>

(function() {
    fetch('/static/banner.json')
        .then(r => r.json())
        .then(function(b) {
            if (!b.active || !b.message) return;
            var bar = document.createElement('div');
            bar.style.cssText = 'position:fixed;top:0;left:0;right:0;background:linear-gradient(90deg,#0f4c81,#1a73e8);color:#fff;padding:10px 20px;display:flex;justify-content:space-between;align-items:center;z-index:99999;font-family:sans-serif;font-size:14px;font-weight:600;';
            var msg = document.createElement('span');
            msg.textContent = '📣 ' + b.message;
            bar.appendChild(msg);
            if (b.link) {
                var cta = document.createElement('a');
                cta.href = b.link; cta.target = '_blank';
                cta.style.cssText = 'background:#fff;color:#1a73e8;padding:5px 12px;border-radius:6px;text-decoration:none;font-size:13px;margin-left:16px;';
                cta.textContent = 'View Details →';
                bar.appendChild(cta);
            }
            var close = document.createElement('button');
            close.textContent = '✕';
            close.style.cssText = 'background:none;border:none;color:#fff;cursor:pointer;font-size:16px;margin-left:12px;';
            close.onclick = function() { bar.remove(); };
            bar.appendChild(close);
            document.body.prepend(bar);
        })
        .catch(function() {});
})();
