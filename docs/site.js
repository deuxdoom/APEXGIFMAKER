'use strict';

// Progressive enhancement: content and release links work without this file.
const $ = (selector) => document.querySelector(selector);
const motionPreference = matchMedia('(prefers-reduced-motion: reduce)');

function setupTheme() {
  const button = $('#theme-toggle');
  function describe() {
    const dark = document.documentElement.dataset.theme === 'dark';
    button.setAttribute('aria-label', dark ? '라이트 테마로 전환' : '다크 테마로 전환');
    $('meta[name="theme-color"]').content = dark ? '#060b14' : '#f5f7fb';
  }
  button.addEventListener('click', () => {
    const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('apex-site-theme', theme); } catch { /* Storage is optional. */ }
    describe();
  });
  describe();
}

function setupPreview() {
  const source = $('#source-canvas');
  const output = $('#output-canvas');
  const ctx = source.getContext('2d', { alpha: false });
  const out = output.getContext('2d', { alpha: false });
  if (!ctx || !out) return;
  const startInput = $('#trim-start');
  const endInput = $('#trim-end');
  const fpsInput = $('#fps');
  const button = $('#play-toggle');
  const state = { start: 2, end: 8, fps: 12, fit: 'cover', time: 2, playing: !motionPreference.matches };
  let visible = false;
  let frameRequest = 0;
  let lastTime = 0;
  let lastSource = -Infinity;
  let lastOutput = -Infinity;

  // An original procedural scene, not an uploaded video or a real GIF encoder.
  function drawScene(time) {
    const w = source.width, h = source.height;
    const phase = time / 12 * Math.PI * 2;
    const x = 444 + Math.sin(phase) * 22;
    const y = 209 + Math.cos(phase) * 8;
    ctx.fillStyle = '#030c1a';
    ctx.fillRect(0, 0, w, h);
    const sky = ctx.createRadialGradient(x, y, 10, x, y, 400);
    sky.addColorStop(0, '#134777'); sky.addColorStop(.48, '#081e3b'); sky.addColorStop(1, '#030a15');
    ctx.fillStyle = sky; ctx.fillRect(0, 0, w, h);
    for (let i = 0; i < 75; i++) {
      const sx = (i * 131.71 + Math.sin(phase) * (i % 3)) % w;
      const sy = (i * 83.93) % (h * .8);
      ctx.fillStyle = `rgba(178,214,250,${.17 + (i % 5) * .1})`;
      ctx.fillRect(sx, sy, i % 11 === 0 ? 2 : 1, i % 11 === 0 ? 2 : 1);
    }
    const halo = ctx.createRadialGradient(x, y, 90, x, y, 190);
    halo.addColorStop(0, '#3eabff38'); halo.addColorStop(1, '#3eabff00');
    ctx.fillStyle = halo; ctx.fillRect(x - 190, y - 190, 380, 380);
    function ring(front) {
      ctx.save(); ctx.translate(x, y); ctx.rotate(-.3);
      for (let i = 0; i < 6; i++) {
        ctx.beginPath();
        ctx.ellipse(0, 0, 188 + i * 5, 42 + i * 2, 0, front ? 0 : Math.PI, front ? Math.PI : Math.PI * 2);
        ctx.strokeStyle = front ? `rgba(108,192,255,${.49 - i * .065})` : `rgba(58,123,185,${.27 - i * .032})`;
        ctx.lineWidth = i === 0 ? 2 : 1; ctx.stroke();
      }
      ctx.restore();
    }
    ring(false);
    const planet = ctx.createRadialGradient(x - 42, y - 48, 8, x + 24, y + 26, 143);
    planet.addColorStop(0, '#a5deff'); planet.addColorStop(.2, '#50adf0'); planet.addColorStop(.47, '#176dad'); planet.addColorStop(.73, '#0a2c50'); planet.addColorStop(1, '#061121');
    ctx.fillStyle = planet; ctx.beginPath(); ctx.arc(x, y, 104, 0, Math.PI * 2); ctx.fill();
    ctx.save(); ctx.beginPath(); ctx.arc(x, y, 103, 0, Math.PI * 2); ctx.clip();
    for (let i = 0; i < 7; i++) {
      ctx.beginPath(); ctx.ellipse(x + Math.sin(phase + i) * 8, y - 90 + i * 31, 122, 19, -.27, 0, Math.PI * 2);
      ctx.strokeStyle = i % 2 ? '#a4d8ff13' : '#02172d19'; ctx.lineWidth = 10; ctx.stroke();
    }
    ctx.restore(); ring(true);
    const landscape = ctx.createLinearGradient(0, 300, 0, h);
    landscape.addColorStop(0, '#123b60'); landscape.addColorStop(1, '#041121');
    ctx.beginPath(); ctx.moveTo(0, 370); ctx.lineTo(125, 320); ctx.lineTo(265, 379);
    ctx.lineTo(390, 337); ctx.lineTo(557, 389); ctx.lineTo(698, 330); ctx.lineTo(w, 353); ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.closePath();
    ctx.fillStyle = landscape; ctx.fill();
    ctx.beginPath(); ctx.moveTo(0, 370); ctx.lineTo(125, 320); ctx.lineTo(265, 379); ctx.lineTo(390, 337); ctx.lineTo(557, 389); ctx.lineTo(698, 330); ctx.lineTo(w, 353);
    ctx.strokeStyle = '#529ad633'; ctx.lineWidth = 1; ctx.stroke();
  }

  function drawOutput() {
    const w = output.width, h = output.height;
    out.fillStyle = '#000'; out.fillRect(0, 0, w, h);
    const factor = state.fit === 'cover' ? Math.max(w / source.width, h / source.height) : Math.min(w / source.width, h / source.height);
    const width = source.width * factor, height = source.height * factor;
    out.imageSmoothingEnabled = true; out.imageSmoothingQuality = 'high';
    out.drawImage(source, (w - width) / 2, (h - height) / 2, width, height);
  }

  function paint() {
    drawScene(state.time); drawOutput();
    $('#playhead').style.left = `${state.time / 12 * 100}%`;
  }

  function describePlayback() {
    button.setAttribute('aria-pressed', String(state.playing));
    button.querySelector('use').setAttribute('href', state.playing ? '#pause' : '#play');
    button.querySelector('span').textContent = state.playing ? '미리보기 일시정지' : '구간 미리보기';
  }

  function syncControls() {
    const duration = state.end - state.start;
    const frames = Math.round(duration * state.fps);
    startInput.max = String(state.end - 1);
    endInput.min = String(state.start + 1);
    startInput.setAttribute('aria-valuetext', `${state.start.toFixed(1)}초`);
    endInput.setAttribute('aria-valuetext', `${state.end.toFixed(1)}초`);
    fpsInput.setAttribute('aria-valuetext', `초당 ${state.fps}프레임`);
    $('#start-output').textContent = state.start.toFixed(1).padStart(4, '0');
    $('#end-output').textContent = state.end.toFixed(1).padStart(4, '0');
    $('#duration-output').textContent = `${duration.toFixed(1)}초 선택`;
    $('#fps-output').firstChild.textContent = `${state.fps} `;
    $('#frame-output').textContent = String(frames);
    $('#demo-summary').textContent = `${duration.toFixed(1)}s / ${state.fps}fps / ${frames} frames`;
    $('#selection-window').style.left = `${state.start / 12 * 100}%`;
    $('#selection-window').style.width = `${duration / 12 * 100}%`;
    if (state.time < state.start || state.time >= state.end) state.time = state.start;
    paint();
  }

  function tick(now) {
    frameRequest = 0;
    if (!state.playing || !visible || document.hidden) { lastTime = 0; return; }
    if (lastTime) state.time = state.start + ((state.time - state.start + (now - lastTime) / 1000) % (state.end - state.start));
    lastTime = now;
    if (now - lastSource >= 1000 / 30) { drawScene(state.time); lastSource = now; }
    if (now - lastOutput >= 1000 / state.fps) { drawOutput(); lastOutput = now; }
    $('#playhead').style.left = `${state.time / 12 * 100}%`;
    frameRequest = requestAnimationFrame(tick);
  }

  function schedule() {
    cancelAnimationFrame(frameRequest); frameRequest = 0; lastTime = 0;
    if (state.playing && visible && !document.hidden) frameRequest = requestAnimationFrame(tick);
  }
  startInput.addEventListener('input', () => { state.start = Math.min(Number(startInput.value), state.end - 1); state.time = state.start; syncControls(); });
  endInput.addEventListener('input', () => { state.end = Math.max(Number(endInput.value), state.start + 1); syncControls(); });
  fpsInput.addEventListener('input', () => { state.fps = Number(fpsInput.value); lastOutput = -Infinity; syncControls(); });
  document.querySelectorAll('input[name="scale"]').forEach((radio) => radio.addEventListener('change', () => { state.fit = radio.value; drawOutput(); }));
  button.addEventListener('click', () => { state.playing = !state.playing; describePlayback(); schedule(); });
  $('#reset-demo').addEventListener('click', () => {
    Object.assign(state, { start: 2, end: 8, fps: 12, fit: 'cover', time: 2, playing: !motionPreference.matches });
    startInput.max = '11'; endInput.min = '1'; startInput.value = '2'; endInput.value = '8'; fpsInput.value = '12';
    $('input[name="scale"][value="cover"]').checked = true;
    syncControls(); describePlayback(); schedule();
  });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; schedule(); }, { threshold: .05 }).observe($('.studio'));
  } else { visible = true; }
  document.addEventListener('visibilitychange', schedule);
  motionPreference.addEventListener('change', () => { if (motionPreference.matches) state.playing = false; describePlayback(); schedule(); });
  syncControls(); describePlayback(); schedule();
}

function setupScreenshot() {
  const dialog = $('#screenshot-dialog');
  const opener = $('#open-screenshot');
  if (typeof dialog.showModal !== 'function') {
    opener.addEventListener('click', () => { location.href = 'images/app-preview.webp'; });
    return;
  }
  opener.addEventListener('click', () => dialog.showModal());
  dialog.addEventListener('click', (event) => {
    if (event.target !== dialog) return;
    const r = dialog.getBoundingClientRect();
    if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close();
  });
  dialog.addEventListener('close', () => opener.focus({ preventScroll: true }));
}

async function syncRelease() {
  // Failure (offline, timeout or GitHub rate limit) leaves the working release-page links intact.
  const repository = 'https://github.com/deuxdoom/APEXGIFMAKER/';
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 6000);
  function safeUrl(value, kind) {
    try {
      const url = new URL(value);
      const prefix = kind === 'asset' ? `${repository}releases/download/` : `${repository}releases/tag/`;
      return url.protocol === 'https:' && !url.username && !url.password && url.href.startsWith(prefix) ? url.href : null;
    } catch { return null; }
  }
  try {
    const response = await fetch('https://api.github.com/repos/deuxdoom/APEXGIFMAKER/releases/latest', { signal: controller.signal, headers: { Accept: 'application/vnd.github+json' } });
    if (!response.ok) return;
    const release = await response.json();
    if (release.draft || release.prerelease || !safeUrl(release.html_url, 'release')) return;
    const assets = Array.isArray(release.assets) ? release.assets : [];
    const asset = assets.find((item) => /^ApexGIFMaker[^/\\]*\.zip$/i.test(item.name) && safeUrl(item.browser_download_url, 'asset'));
    if (asset) {
      document.querySelectorAll('[data-download]').forEach((link) => { link.href = safeUrl(asset.browser_download_url, 'asset'); });
    }
    const version = typeof release.tag_name === 'string' && release.tag_name.length < 40 ? release.tag_name : '최신 안정 버전';
    const size = asset && Number.isFinite(asset.size) && asset.size > 0 ? ` · ${(asset.size / 1048576).toFixed(1)} MB` : '';
    $('#release-meta').textContent = `${version}${size} · Windows x64 · GitHub 공식 저장소`;
  } catch { /* Static, usable fallback is intentional. */ }
  finally { clearTimeout(timer); }
}

setupTheme();
setupPreview();
setupScreenshot();
syncRelease();
