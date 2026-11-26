/*
 * Copyright 2026 Chajns777
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/* Nova UI — terminal chat (dependency-free, works offline) */

(() => {
  const TOKEN = document.querySelector('meta[name=nova-token]').content;
  const $ = (s, r = document) => r.querySelector(s);
  const el = (tag, cls, html) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  };

  const ART = [
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣷⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⡇⠀⠀⠀⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣾⣿⣿⠀⠀⢸⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣼⣿⣿⣿⣧⡀⢸⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠰⠶⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡶⠄⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠈⠙⢿⣿⣿⣿⡿⠋⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⢿⣿⡿⠀⢰⣿⣿⣷⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⠇⠀⣾⣿⢹⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⠀⠈⣿⢀⣼⣿⠃⠀⢻⣿⣄⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⣸⣀⣠⣿⣿⡿⠁⠀⠀⠀⠻⣿⣶⣤⡀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠠⣴⣶⣾⣿⣿⣿⣛⠁⠀⠀⠀⠀⠀⠀⠀⢙⣻⣿⣿⣷⣶⣦⡤",
    "⠀⠀⠀⠀⠀⠀⠀⠈⠉⣿⡟⠿⣿⣷⣦⠀⠀⠀⠀⣀⣶⣿⡿⠟⠋⠉⠉⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⢰⣿⣧⠀⠀⠙⣿⣷⡄⠀⣰⣿⡟⠁⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⡄⠀⠀⠘⣿⣷⢰⣿⡟⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣧⠀⠀⠀⢹⣿⣿⡿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⢀⣠⣼⣿⣿⣿⣿⣿⣷⣤⡀⠘⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠤⣶⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡧⠄⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠉⠙⠻⢿⣿⣿⣿⣿⣿⣿⠿⠛⠉⢹⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠈⢻⣿⣿⣿⡿⠃⠀⠀⠀⢸⡏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⣿⣿⣿⠃⠀⠀⠀⠀⢸⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⢹⣿⣿⠀⠀⠀⠀⠀⠈⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠹⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀"
  ];
  const logo = (() => {
    const BIT = [[0, 0], [0, 1], [0, 2], [1, 0], [1, 1], [1, 2], [0, 3], [1, 3]], pts = [];
    ART.forEach((line, r) => [...line].forEach((ch, c) => BIT.forEach(([dx, dy], b) => {
      if ((ch.codePointAt(0) - 0x2800) >> b & 1) pts.push([c * 2 + dx, r * 4 + dy]);
    })));
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]), x0 = Math.min(...xs), y0 = Math.min(...ys);
    const w = Math.max(...xs) - x0 + 1, h = Math.max(...ys) - y0 + 1, R = 0.46;
    const d = pts.map(([x, y]) => `M${x - x0 + 0.5 - R} ${y - y0 + 0.5}a${R} ${R} 0 1 0 ${2 * R} 0a${R} ${R} 0 1 0 ${-2 * R} 0`).join('');
    const svg = `<svg viewBox="0 0 ${w} ${h}" aria-hidden="true"><path d="${d}" fill="currentColor"/></svg>`;
    return () => svg;
  })();

  const ICONS = {
    chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z"/>',
    memory: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5"/><path d="m3 17.5 9 5 9-5" opacity=".5"/>',
    skills: '<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z"/>',
    files: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/>',
    settings: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    attach: '<path d="m21 11-8.5 8.5a5 5 0 0 1-7-7L14 4a3.5 3.5 0 0 1 5 5l-8.6 8.6a2 2 0 0 1-3-3L15 7"/>',
    send: '<path d="M12 19V5M5 12l7-7 7 7"/>',
    stop: '<rect x="6.5" y="6.5" width="11" height="11" rx="2.5"/>',
    close: '<path d="M6 6l12 12M18 6 6 18"/>',
    trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  };
  const icon = n => `<svg class="i" viewBox="0 0 24 24">${ICONS[n]}</svg>`;

  function updateClock() {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const dateStr = now.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
    const tEl = $('#clkTime'), dEl = $('#clkDate');
    if (tEl) tEl.textContent = `${hh}:${mm}`;
    if (dEl) dEl.textContent = dateStr;
  }
  updateClock();
  setInterval(updateClock, 10000);

  const api = (path, body, method) => fetch(path, {
    method: method || (body !== undefined ? 'POST' : 'GET'),
    headers: { 'X-Nova-Token': TOKEN, 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const getJSON = async (p) => (await api(p)).json();
  const postJSON = async (p, b) => (await api(p, b || {})).json();

  const esc = s => s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
  function inline(s) {
    const codes = [];
    s = esc(s).replace(/`([^`\n]+)`/g, (m, c) => { codes.push(c); return `\u0001${codes.length - 1}\u0001`; });
    s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*\w])\*([^*\s][^*\n]*?)\*(?!\w)/g, '$1<em>$2</em>')
      .replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
      .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>');
    return s.replace(/\u0001(\d+)\u0001/g, (m, i) => `<code>${codes[i]}</code>`);
  }
  function md(src) {
    const fences = [];
    let t = src;
    if ((t.match(/```/g) || []).length % 2) t += '\n```';
    t = t.replace(/```([\w+#.-]*)[ \t]*\n([\s\S]*?)```/g, (m, lang, code) => {
      fences.push({ lang, code: code.replace(/\n$/, '') });
      return `\n\n\u0000${fences.length - 1}\u0000\n\n`;
    });
    return t.split(/\n{2,}/).map(block => {
      block = block.replace(/^\n+|\n+$/g, '');
      if (!block.trim()) return '';
      let m = block.match(/^\u0000(\d+)\u0000$/);
      if (m) {
        const f = fences[+m[1]];
        return `<div class="code"><div class="code-h"><span>${esc(f.lang || 'code')}</span><button class="copy">Copy</button></div><pre><code>${esc(f.code)}</code></pre></div>`;
      }
      const lines = block.split('\n');
      if (/^#{1,4}\s/.test(lines[0]) && lines.length === 1) {
        const lv = lines[0].match(/^#+/)[0].length;
        return `<h${lv}>${inline(lines[0].replace(/^#+\s*/, ''))}</h${lv}>`;
      }
      if (lines.every(l => /^\s*[-*•]\s+/.test(l))) return '<ul>' + lines.map(l => `<li>${inline(l.replace(/^\s*[-*•]\s+/, ''))}</li>`).join('') + '</ul>';
      if (lines.every(l => /^\s*\d+[.)]\s+/.test(l))) return '<ol>' + lines.map(l => `<li>${inline(l.replace(/^\s*\d+[.)]\s+/, ''))}</li>`).join('') + '</ol>';
      if (lines.every(l => /^>\s?/.test(l))) return `<blockquote>${lines.map(l => inline(l.replace(/^>\s?/, ''))).join('<br>')}</blockquote>`;
      if (/^(-{3,}|\*{3,})$/.test(block.trim())) return '<hr>';
      return `<p>${lines.map(inline).join('<br>')}</p>`;
    }).join('');
  }

  const col = $('#col'), scroll = $('#scroll'), input = $('#input'), sendBtn = $('#send'),
    chipsBox = $('#chips'), pill = $('#pill'), pillText = $('#pillText'), banner = $('#banner'),
    drawer = $('#drawer'), drawerBody = $('#drawerBody'), drawerTitle = $('#drawerTitle'), app = $('#app');

  document.querySelectorAll('[data-icon]').forEach(b => b.innerHTML = icon(b.dataset.icon));
  $('#brandLogo').innerHTML = logo();

  let S = {}, busy = false, attachments = [], panel = 'chat';

  const nearBottom = () => scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 140;
  const toBottom = (force) => { if (force || nearBottom()) scroll.scrollTop = scroll.scrollHeight; };
  const startChat = () => app.classList.add('chatting');

  function fileChip(f, withRemove) {
    const c = el('span', 'fchip' + (f.busy ? ' busy' : '') + (f.bad ? ' bad' : ''));
    const ext = (f.name.split('.').pop() || '').slice(0, 4);
    c.innerHTML = (f.kind === 'image' && f.id ? `<img src="/api/file/${f.id}?t=${TOKEN}" alt="">` : `<span class="ext">${esc(ext)}</span>`)
      + `<span class="nm">${esc(f.name)}</span>`;
    if (withRemove) {
      const x = el('button', null, '×'); x.title = 'Remove';
      x.onclick = () => { attachments = attachments.filter(a => a !== f); renderChips(); updateSend(); };
      c.appendChild(x);
    }
    return c;
  }
  function renderChips() {
    chipsBox.innerHTML = '';
    attachments.forEach(f => chipsBox.appendChild(fileChip(f, true)));
  }

  const PROMPTS = ['Tell me about yourself', 'What can you do?', 'Learn something new from the web', 'Help me write some code'];
  const lname = () => (S.name || 'Nova').toLowerCase().replace(/\s+/g, '-');
  const ps = () => `you@${lname()}:~ #`;
  let heroFor = null;
  function renderHero() {
    const name = S.name || 'Nova';
    if (heroFor === name) return;
    heroFor = name;
    const W = 60, rows = [`${name} is a companion that runs on your own computer.`, '',
      'Type a message and press Enter to chat.', 'Drop, paste or attach files and images (+).', 'Memory, skills and settings are in the sidebar.', '',
      'Everything stays local: no account, no cloud.'];
    const wrap = t => t.length > W ? t.match(new RegExp(`.{1,${W}}(\\s|$)`, 'g')).map(x => x.trim()) : [t];
    const lines = rows.flatMap(wrap);
    const box = ['╭' + '─'.repeat(W + 2) + '╮', ...lines.map(l => '│ ' + l.padEnd(W) + ' │'), '╰' + '─'.repeat(W + 2) + '╯'].join('\n');
    $('#hero').innerHTML = `<pre class="box-art">${esc(box).replace(esc(name), `<span class="mag">${esc(name)}</span>`)}</pre>
      <div class="emblem">${logo()}</div>
      <div class="cmd"><span class="ps">${esc(ps())}</span> ${esc(lname())} --prompts</div>
      <div class="opts">${PROMPTS.map((p, i) => `<button class="opt" data-prompt="${esc(p)}"><span class="n">${i}:</span> ${esc(p)}</button>`).join('')}</div>
      <div class="note opts-note"> -- Click a line or type its number, or just start talking --</div>`;
  }

  function addUser(text, files) {
    startChat();
    const m = el('div', 'msg user'), b = el('div', 'body');
    b.innerHTML = `<span class="ps">${esc(ps())}</span> `;
    if (files && files.length) {
      const fc = el('div', 'fchips');
      files.forEach(f => fc.appendChild(fileChip(f, false)));
      b.appendChild(fc);
    }
    b.appendChild(document.createTextNode(text));
    m.appendChild(b); col.appendChild(m); toBottom(true);
  }
  function addNova(html, cls) {
    startChat();
    const m = el('div', 'msg nova' + (cls ? ' ' + cls : ''));
    const b = el('div', 'body', html || '');
    m.append(b); col.appendChild(m); toBottom(true);
    return { m, b };
  }

  function renderState(s) {
    S = s;
    $('#brandName').textContent = s.name;
    renderHero(); $('#promptLabel').textContent = ps();
    document.title = s.name;
    pill.className = 'pill ' + (s.status === 'ready' ? '' : s.status === 'loading' || s.status === 'starting' ? 'loading' : s.status);
    const label = {
      ready: s.model, loading: 'Waking up…', starting: 'Waking up…',
      offline: 'Ollama is offline', missing: 'Model not downloaded',
    }[s.status] || s.model;
    pillText.innerHTML = esc(label) + (s.status === 'ready' && s.tps ? ` <span class="tps">· ${s.tps} tok/s</span>` : '');
    if (s.status === 'offline') {
      showBanner('offline', `<b>I can’t reach Ollama.</b> Install it from <a href="https://ollama.com/download" target="_blank" rel="noopener noreferrer">ollama.com/download</a>, start it, and I’ll wake up on my own.`);
    } else if (s.status === 'missing') {
      showBanner('missing:' + s.model, `<b>One-time setup:</b> I need to download my brain (<code>${esc(s.model)}</code>, a few GB).${pullRow(s.model, 'Download now')}`);
    } else {
      banner.dataset.key = ''; banner.classList.add('hidden');
    }
    renderPull(s.pull);
    updateSend();
  }
  function showBanner(key, html) {
    if (banner.dataset.key !== key) { banner.innerHTML = html; banner.dataset.key = key; }
    banner.classList.remove('hidden');
  }
  const pullRow = (model, label) => `<div class="row"><button class="btn primary pbtn" data-model="${esc(model)}">${esc(label)}</button><div class="bar hidden pbar"><i></i></div><span class="ptxt"></span></div>`;

  let pullTimer = 0, wasPulling = false;
  async function startPull(model) {
    const r = await postJSON('/api/pull', { model });
    await refreshState();
    if (r.error) document.querySelectorAll('.ptxt').forEach(x => x.textContent = r.error);
  }
  function renderPull(p) {
    p = p || {};
    const act = !!p.active;
    document.querySelectorAll('.pbar').forEach(b => { b.classList.toggle('hidden', !act); b.firstElementChild.style.width = (p.percent || 0) + '%'; });
    document.querySelectorAll('.pbtn').forEach(b => b.disabled = act);
    const txt = act ? `${p.percent != null ? p.percent + '% · ' : ''}${p.detail || p.status || ''}`
      : p.error ? p.error : p.status === 'success' ? 'Downloaded ✓' : '';
    document.querySelectorAll('.ptxt').forEach(x => x.textContent = txt);
    if (act && !pullTimer) pullTimer = setInterval(refreshState, 700);
    if (!act && pullTimer) { clearInterval(pullTimer); pullTimer = 0; }
    if (wasPulling && !act && !p.error && panel === 'settings') openPanel('settings');
    wasPulling = act;
  }
  document.addEventListener('click', e => { const b = e.target.closest('.pbtn[data-model]'); if (b) startPull(b.dataset.model); });

  async function refreshState() {
    try { renderState(await getJSON('/api/state')); } catch (e) { /* server gone */ }
  }

  async function readSSE(res, onEvent) {
    const reader = res.body.getReader(), dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf('\n\n')) >= 0) {
        const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
        if (chunk.startsWith('data: ')) { try { onEvent(JSON.parse(chunk.slice(6))); } catch (e) { /* ignore */ } }
      }
    }
  }

  function updateSend() {
    const uploading = attachments.some(a => a.busy);
    sendBtn.disabled = !busy && (uploading || (!input.value.trim() && !attachments.length) || S.status === 'offline');
    sendBtn.classList.toggle('stop', busy);
    sendBtn.innerHTML = icon(busy ? 'stop' : 'send');
    sendBtn.title = busy ? 'Stop' : 'Send';
  }
  function autoGrow() { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 200) + 'px'; }

  async function send(textOverride) {
    if (busy) { api('/api/stop', {}); return; }
    let text = (textOverride ?? input.value).trim();
    if (!app.classList.contains('chatting') && /^[0-3]$/.test(text)) text = PROMPTS[+text];
    const files = attachments.filter(a => a.id);
    if ((!text && !files.length) || attachments.some(a => a.busy)) return;
    input.value = ''; autoGrow(); attachments = []; renderChips();
    busy = true; updateSend();
    addUser(text || 'Have a look at what I’ve shared.', files);

    const { m, b } = addNova('<span class="typing"><i></i><i></i><i></i></span>', 'thinking');
    const act = el('div', 'act'), out = el('div', 'out');
    let buf = '', raf = 0, started = false, curAct = null;
    const draw = () => {
      raf = 0; out.innerHTML = md(buf);
      if (busy) {
        let last = out.lastElementChild;
        if (last && (last.tagName === 'UL' || last.tagName === 'OL') && last.lastElementChild) last = last.lastElementChild;
        if (last && !last.classList.contains('code')) last.insertAdjacentHTML('beforeend', '<span class="caret"></span>');
        else out.insertAdjacentHTML('beforeend', '<span class="caret"></span>');
      }
      toBottom();
    };
    const schedule = () => { if (!raf) raf = requestAnimationFrame(draw); };
    const begin = () => { if (!started) { started = true; b.innerHTML = ''; b.append(act, out); } };
    const doneAct = () => { if (curAct) { curAct.classList.add('ok'); curAct = null; } };

    try {
      const res = await api('/api/chat', { message: text, files: files.map(f => f.id) });
      if (res.status === 409) throw new Error('I’m still busy with the last message.');
      await readSSE(res, ev => {
        if (ev.t === 'token') { begin(); doneAct(); buf += ev.d; schedule(); }
        else if (ev.t === 'reset') { buf = ''; schedule(); }
        else if (ev.t === 'status') { begin(); doneAct(); curAct = el('span', null, esc(ev.d)); act.appendChild(curAct); if (buf && !buf.endsWith('\n\n')) buf += '\n\n'; toBottom(); }
        else if (ev.t === 'skills' || ev.t === 'memory' || ev.t === 'state') { if (panel !== 'chat') openPanel(panel); refreshState(); }
        else if (ev.t === 'error') {
          m.classList.add('err'); begin(); doneAct();
          out.innerHTML = esc(ev.d);
          if (ev.code === 'missing') {
            const row = el('div', 'banner', pullRow(ev.model, 'Download ' + ev.model));
            row.style.marginTop = '10px'; b.appendChild(row);
          }
          refreshState();
        }
        else if (ev.t === 'done') { if (ev.stats && ev.stats.tps) S.tps = ev.stats.tps; }
      });
    } catch (e) {
      m.classList.add('err'); begin(); out.textContent = e.message || 'Something went wrong.';
    }
    busy = false; m.classList.remove('thinking');
    if (!started) { b.innerHTML = ''; }
    doneAct(); if (raf) cancelAnimationFrame(raf);
    if (buf) out.innerHTML = md(buf);
    if (!act.children.length) act.remove();
    updateSend(); refreshState(); toBottom();
  }

  async function addFiles(fileList) {
    const files = [...fileList].slice(0, 6 - attachments.length);
    for (const file of files) {
      const rec = { name: file.name || 'pasted-image.png', kind: /^image\//.test(file.type) ? 'image' : 'file', busy: true };
      attachments.push(rec); renderChips(); updateSend();
      try {
        const res = await fetch('/api/upload?name=' + encodeURIComponent(rec.name), {
          method: 'POST', headers: { 'X-Nova-Token': TOKEN }, body: file,
        });
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        Object.assign(rec, data, { busy: false });
      } catch (e) {
        rec.busy = false; rec.bad = true; rec.name = rec.name + ' (failed)';
        setTimeout(() => { attachments = attachments.filter(a => a !== rec); renderChips(); updateSend(); }, 2500);
      }
      renderChips(); updateSend();
    }
    input.focus();
  }
  $('#attach').onclick = () => $('#file').click();
  $('#file').onchange = e => { addFiles(e.target.files); e.target.value = ''; };

  let dragDepth = 0;
  const hasFiles = e => e.dataTransfer && [...e.dataTransfer.types].includes('Files');
  window.addEventListener('dragenter', e => { if (hasFiles(e)) { dragDepth++; $('#drop').classList.remove('hidden'); } });
  window.addEventListener('dragleave', e => { if (hasFiles(e) && --dragDepth <= 0) { dragDepth = 0; $('#drop').classList.add('hidden'); } });
  window.addEventListener('dragover', e => { if (hasFiles(e)) e.preventDefault(); });
  window.addEventListener('drop', e => { if (hasFiles(e)) { e.preventDefault(); dragDepth = 0; $('#drop').classList.add('hidden'); addFiles(e.dataTransfer.files); } });
  window.addEventListener('paste', e => {
    const fs = [...(e.clipboardData?.items || [])].filter(i => i.kind === 'file').map(i => i.getAsFile()).filter(Boolean);
    if (fs.length) { e.preventDefault(); addFiles(fs); }
  });

  input.addEventListener('input', () => { autoGrow(); updateSend(); });
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (!busy) send(); } });
  sendBtn.onclick = () => send();
  $('#hero').onclick = e => { const b = e.target.closest('.opt'); if (b) send(b.dataset.prompt); };
  col.addEventListener('click', e => {
    if (e.target.classList.contains('copy')) {
      const code = e.target.closest('.code').querySelector('pre').innerText;
      navigator.clipboard.writeText(code).then(() => { e.target.textContent = 'Copied'; setTimeout(() => e.target.textContent = 'Copy', 1400); });
    }
  });

  const railBtns = [...document.querySelectorAll('.rail-btn')];
  railBtns.forEach(b => b.onclick = () => (b.dataset.panel === 'chat' || (panel === b.dataset.panel && drawer.classList.contains('open'))) ? closePanel() : openPanel(b.dataset.panel));
  $('#drawerClose').onclick = closePanel;
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closePanel(); });

  function closePanel() {
    drawer.classList.remove('open'); panel = 'chat';
    railBtns.forEach(b => b.classList.toggle('active', b.dataset.panel === 'chat'));
  }
  async function openPanel(name) {
    panel = name;
    railBtns.forEach(b => b.classList.toggle('active', b.dataset.panel === name));
    drawerTitle.textContent = { memory: 'Memory', skills: 'Skills', files: 'Files', settings: 'Settings' }[name];
    drawer.classList.add('open');
    drawerBody.innerHTML = '';
    if (name === 'memory') await panelMemory();
    if (name === 'skills') await panelSkills();
    if (name === 'files') await panelFiles();
    if (name === 'settings') await panelSettings();
  }

  const item = (key, text, onDelete, extra) => {
    const d = el('div', 'item');
    d.innerHTML = `<div class="t">${key ? `<span class="k">${esc(key)}</span>` : ''}${esc(text)}</div>`;
    if (onDelete) { const x = el('button', 'x', icon('trash')); x.querySelector('svg').style.cssText = 'width:15px;height:15px'; x.title = 'Forget'; x.onclick = async () => { await onDelete(); d.remove(); refreshState(); }; d.appendChild(x); }
    if (extra) d.appendChild(extra);
    return d;
  };
  const sec = (t) => el('div', 'sec', esc(t));

  async function panelMemory() {
    const m = await getJSON('/api/memory');
    drawerBody.append(sec('What I know about you'));
    const facts = Object.entries(m.facts);
    if (!facts.length) drawerBody.append(el('div', 'empty', 'Nothing yet. Just talk to me - I’ll pick things up as we go.'));
    facts.forEach(([k, v]) => drawerBody.append(item(k.replace(/_/g, ' '), v, () => postJSON('/api/memory/forget', { kind: 'fact', key: k }))));
    drawerBody.append(sec('Things I’ve learned'));
    if (!m.notes.length) drawerBody.append(el('div', 'empty', 'When I research something for you, the key points land here.'));
    m.notes.slice().reverse().forEach(n => drawerBody.append(item(n.kind, n.text, () => postJSON('/api/memory/forget', { kind: 'note', id: n.id }))));
    if (m.summary) { drawerBody.append(sec('Our earlier conversations')); drawerBody.append(el('div', 'item', `<div class="t">${esc(m.summary)}</div>`)); }
    const clear = el('button', 'btn danger', 'Clear our conversation (keeps what I know)');
    clear.style.marginTop = '22px';
    clear.onclick = async () => { await postJSON('/api/memory/forget', { kind: 'history' }); col.innerHTML = ''; app.classList.remove('chatting'); closePanel(); };
    drawerBody.append(clear);
  }

  async function panelSkills() {
    const k = await getJSON('/api/skills');
    drawerBody.append(sec('Skills I taught myself'));
    if (!k.learned.length) drawerBody.append(el('div', 'empty', 'None yet. Ask me to learn something - like “learn how to convert currencies”.'));
    k.learned.forEach(s => drawerBody.append(item(s.name + s.signature, s.description || '(no description)')));
    if (k.learned.length) {
      const b = el('button', 'btn', 'View code'); b.style.marginTop = '8px';
      b.onclick = () => { const pre = el('pre', 'src'); pre.textContent = k.code; b.replaceWith(pre); };
      drawerBody.append(b);
    }
    if (k.backups.length) {
      drawerBody.append(sec('Backups (taken before every change)'));
      k.backups.forEach((name, i) => {
        const r = el('button', 'btn', 'Restore'); r.onclick = async () => { await postJSON('/api/skills/rollback', { index: i + 1 }); r.textContent = 'Done'; openPanel('skills'); };
        drawerBody.append(item('', name.replace('learned_tools_', '').replace('.py', ''), null, r));
      });
    }
    drawerBody.append(sec('Built in'));
    Object.entries(k.builtin).forEach(([n, d]) => drawerBody.append(item(n, d)));
  }

  async function panelFiles() {
    const f = (await getJSON('/api/files')).files.slice().reverse();
    drawerBody.append(sec('Shared with me'));
    if (!f.length) drawerBody.append(el('div', 'empty', 'Drop files or images into the chat. I can read PDFs, Word, Excel, CSV, code, text, images, and more.'));
    f.forEach(x => {
      const d = el('div', 'item click');
      d.innerHTML = (x.kind === 'image' ? `<img class="th" src="/api/file/${x.id}?t=${TOKEN}" alt="">` : '')
        + `<div class="t"><span class="k">${esc(x.kind)}</span>${esc(x.name)}</div>`;
      d.title = 'Attach again to your next message';
      d.onclick = () => { if (!attachments.find(a => a.id === x.id)) { attachments.push({ ...x }); renderChips(); updateSend(); } closePanel(); input.focus(); };
      drawerBody.append(d);
    });
  }

  async function panelSettings() {
    const s = await getJSON('/api/state');
    const models = [...new Set([s.model, ...s.installed])];
    drawerBody.innerHTML = `
      <div class="field"><label>Name</label><input type="text" id="sName" value="${esc(s.name)}"></div>
      <div class="field"><label>How I speak</label><textarea id="sStyle">${esc(s.style)}</textarea>
        <div class="help">You can also just tell me: “be more casual” - I’ll update this myself.</div></div>
      <div class="field"><label>Brain (Ollama model)</label>
        <select id="sModel">${models.map(m => `<option ${m === s.model ? 'selected' : ''}>${esc(m)}</option>`).join('')}</select>
        <div class="help">Qwen3-VL handles chat, tools and images in one model. On a slower PC try <code>qwen3-vl:2b-instruct</code>.</div></div>
      <div class="field"><label>Download another model</label>
        <input type="text" id="sPull" placeholder="e.g. qwen3-vl:2b-instruct">
        <div class="row" style="display:flex;gap:10px;align-items:center;margin-top:8px"><button class="btn" id="sPullBtn">Download</button><div class="bar hidden pbar"><i></i></div><span class="help ptxt"></span></div></div>
      <div class="field"><label>Separate vision model (optional)</label><input type="text" id="sVision" value="${esc(s.vision_model)}" placeholder="only if the brain can’t see images">
      </div>
      <label class="toggle">Let me use the internet<input type="checkbox" id="sWeb" ${s.web_enabled ? 'checked' : ''}></label>
      <label class="toggle">Quietly learn about me while we chat<input type="checkbox" id="sLearn" ${s.auto_learn ? 'checked' : ''}></label>
      <button class="btn primary" id="sSave" style="margin-top:18px;width:100%">Save</button>`;
    $('#sPullBtn').onclick = () => { const v = $('#sPull').value.trim(); if (v) startPull(v); };
    renderPull(S.pull);
    $('#sSave').onclick = async () => {
      renderState(await postJSON('/api/settings', {
        name: $('#sName').value, speaking_style: $('#sStyle').value, model: $('#sModel').value,
        vision_model: $('#sVision').value, web_enabled: $('#sWeb').checked, auto_learn: $('#sLearn').checked,
      }));
      $('#sSave').textContent = 'Saved ✓'; setTimeout(closePanel, 600);
    };
  }

  async function boot() {
    renderHero();
    try {
      const s = await getJSON('/api/state?history=1');
      renderState(s);
      (s.history || []).forEach(m => {
        if (m.role === 'user') addUser(m.content, (m.files || []).map(n => ({ name: n, kind: 'file' })));
        else { const { b } = addNova(''); b.innerHTML = md(m.content); }
      });
      if (s.history && s.history.length) setTimeout(() => { scroll.style.scrollBehavior = 'auto'; scroll.scrollTop = scroll.scrollHeight; scroll.style.scrollBehavior = ''; }, 0);
    } catch (e) { pillText.textContent = 'Connection lost'; }
    updateSend(); input.focus();
    setInterval(() => { if (!busy) refreshState(); }, 4000);
    setInterval(() => api('/api/ping', {}).catch(() => { }), 5000);
    api('/api/ping', {}).catch(() => { });
  }
  window.addEventListener('pagehide', () => navigator.sendBeacon('/api/bye?t=' + TOKEN, '{}'));
  boot();
})();