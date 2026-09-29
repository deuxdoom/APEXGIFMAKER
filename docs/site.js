'use strict';

// Progressive enhancement: content and release links work without this file.
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
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

// ---------------------------------------------------------------------------
// 앱 규칙: src/core(config.py, trim.py, timecode.py, gif.py)와 src/ui/widgets/timeline_math.py를 옮겼습니다.
// ---------------------------------------------------------------------------
const TRIM_MIN = 1, TRIM_MAX = 30, RECO_MAX = 15;
const SIZE_MIN = 8, SIZE_MAX = 4096, FPS_MIN = 1, FPS_MAX = 60;
const DEFAULT_SIZE = { width: 160, height: 80 };
const INVALID_FILENAME_CHARS = '<>:"/\\|?*';
const clamp = (value, lo, hi) => (value < lo ? lo : value > hi ? hi : value);
const round3 = (value) => Math.round(value * 1000) / 1000;

// gif.py와 같이 밀리초 길이로 정수 계산하고 .5는 올립니다. (ffmpeg도 경계값에서 올림으로 셈)
const estimateFrames = (length, fps) => Math.max(1, Math.floor((Math.round(Math.max(0, length) * 1000) * fps + 500) / 1000));
// gif.py ONE_PASS_MAX_PIXELS: 예상 프레임 × 가로 × 세로가 이 값 이하이면 영상을 한 번만 읽는 1-pass로 만듭니다.
const ONE_PASS_MAX_PIXELS = 50000000;

function formatTime(seconds) {
  const total = Math.max(0, Math.round(seconds * 1000));
  const pad = (value, size = 2) => String(value).padStart(size, '0');
  const hours = Math.floor(total / 3600000), minutes = Math.floor(total % 3600000 / 60000);
  const secs = Math.floor(total % 60000 / 1000), ms = total % 1000;
  return hours ? `${pad(hours)}:${pad(minutes)}:${pad(secs)}.${pad(ms, 3)}` : `${pad(minutes)}:${pad(secs)}.${pad(ms, 3)}`;
}

function parseTime(text) {
  // 허용 형식: 90, 90.5, 1:30, 01:30.250, 1:02:03.5, 3.5s, 소수점 쉼표(1,5)
  let s = String(text || '').trim().toLowerCase().replace(/,/g, '.');
  if (s.endsWith('s')) s = s.slice(0, -1).trim();
  if (!s) throw new RangeError('empty time');
  const parts = s.split(':');
  if (parts.length > 3) throw new RangeError('invalid time');
  const head = parts.slice(0, -1).map((part) => {
    if (!/^\s*\d+\s*$/.test(part)) throw new RangeError('invalid time');
    return Number.parseInt(part, 10);
  });
  const lastText = parts[parts.length - 1].trim();
  if (!/^(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/.test(lastText)) throw new RangeError('invalid time');
  const last = Number.parseFloat(lastText);
  if (!Number.isFinite(last)) throw new RangeError('invalid time');
  if (parts.length >= 2 && last >= 60) throw new RangeError('seconds must be < 60');
  if (parts.length === 3 && head[1] >= 60) throw new RangeError('minutes must be < 60');
  const total = head.reduce((sum, value) => sum * 60 + value, 0);
  return head.length ? total * 60 + last : last;
}

function trimRules(duration, minLen = TRIM_MIN, maxLen = TRIM_MAX) {
  const lo = Math.min(minLen, duration);
  const hi = Math.max(lo, Math.min(maxLen, duration));
  const valid = (length) => lo - 1e-6 <= length && length <= hi + 1e-6;
  const sel = (start, end) => ({ start, end });
  const move = (s, newStart) => {
    const length = clamp(s.end - s.start, lo, hi);
    const start = clamp(newStart, 0, duration - length);
    return sel(round3(start), round3(start + length));
  };
  return {
    duration, lo, hi, move,
    normalize(s) {
      const length = clamp(s.end - s.start, lo, hi);
      const start = clamp(s.start, 0, duration - length);
      return sel(round3(start), round3(Math.min(duration, start + length)));
    },
    dragStart(s, t) {
      const low = Math.max(0, s.end - hi), high = Math.max(low, s.end - lo);
      return sel(round3(clamp(t, low, high)), s.end);
    },
    dragEnd(s, t) {
      const high = Math.min(duration, s.start + hi), low = Math.min(high, s.start + lo);
      return sel(s.start, round3(clamp(t, low, high)));
    },
    setStart(s, t) {
      t = clamp(t, 0, duration);
      return valid(s.end - t) ? sel(round3(t), s.end) : move(s, t);
    },
    setEnd(s, t) {
      t = clamp(t, 0, duration);
      return valid(t - s.start) ? sel(s.start, round3(t)) : move(s, t - (s.end - s.start));
    },
    setLength(s, length) {
      length = clamp(length, lo, hi);
      const start = Math.max(0, Math.min(s.start, duration - length));
      return sel(round3(start), round3(start + length));
    },
  };
}

const RULER_STEPS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200];
const TILE_BASE = [1, 1.5, 2, 3, 5, 7.5];
const rulerStep = (pps, minGap = 90) => RULER_STEPS.find((step) => step * pps >= minGap) ?? RULER_STEPS[RULER_STEPS.length - 1];

function minorStep(step, pps, minGap = 8) {
  for (const divisor of [5, 2]) if (step / divisor * pps >= minGap) return step / divisor;
  return 0;
}

function formatTick(t, step, longVideo) {
  if (step < 1) {
    const tenths = Math.round(t * 10);
    const minutes = Math.floor(tenths / 600), rest = tenths % 600;
    return `${minutes}:${String(Math.floor(rest / 10)).padStart(2, '0')}.${rest % 10}`;
  }
  const total = Math.round(t);
  const hours = Math.floor(total / 3600), minutes = Math.floor(total % 3600 / 60), seconds = total % 60;
  if (longVideo) return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  return `${hours * 60 + minutes}:${String(seconds).padStart(2, '0')}`;
}

function tileSpan(nominal, frameStep) {
  nominal = Math.max(nominal, frameStep, 0.01);
  const exponent = Math.floor(Math.log10(nominal));
  for (const power of [exponent, exponent + 1]) {
    for (const base of TILE_BASE) {
      const value = base * 10 ** power;
      if (value >= nominal - 1e-9) return value;
    }
  }
  return nominal;
}

// ---------------------------------------------------------------------------
// 샘플 영상: 업로드한 영상이 아니라 코드로 그리는 48초짜리 장면입니다. 처음 4초는 멈춘 타이틀 화면입니다.
// ---------------------------------------------------------------------------
const VIDEO = { name: 'sample_orbit.mp4', stem: 'sample_orbit', duration: 48, fps: 30, still: 4 };
const FRAME_STEP = 1 / VIDEO.fps;
const INITIAL_SELECTION = { start: 12, end: 18 };
const FONT = "ApexSiteSans, 'Segoe UI', sans-serif";
const STARS = Array.from({ length: 90 }, (_, i) => ({ x: (i * 131.71) % 800, y: (i * 83.93) % 330, size: i % 11 === 0 ? 2 : 1, alpha: .17 + (i % 5) * .1, phase: i * 1.7 }));
const smoothstep = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };

function drawScene(ctx, time) {
  // 800×450 좌표계에 그립니다. 크기와 맞춤은 부르는 쪽에서 변환 행렬로 정합니다.
  const still = time < VIDEO.still;
  const a = still ? 0 : time - VIDEO.still;
  const m = a / (VIDEO.duration - VIDEO.still);
  const phase = a / 12 * Math.PI * 2;
  const hue = 206 + 20 * Math.sin(m * Math.PI * 2);
  const px = 430 + Math.sin(m * Math.PI * 2) * 60 + Math.sin(phase) * 14;
  const py = 206 + Math.cos(phase) * 6;
  const r = 92 + 16 * m;
  const sky = ctx.createRadialGradient(px, py, 10, px, py, 440);
  sky.addColorStop(0, `hsl(${hue}, 62%, 27%)`);
  sky.addColorStop(.5, `hsl(${hue + 6}, 70%, 12%)`);
  sky.addColorStop(1, `hsl(${hue + 10}, 72%, 5%)`);
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, 800, 450);
  for (const star of STARS) {
    ctx.fillStyle = `rgba(190,220,255,${clamp(star.alpha + .12 * Math.sin(a * 2.2 + star.phase), .05, .9)})`;
    ctx.fillRect((star.x + a * 1.5) % 800, star.y, star.size, star.size);
  }
  for (const [begin, x0, y0] of [[13, 120, 40], [31, 540, 34]]) {
    const k = (a - begin) / 1.4;
    if (k < 0 || k > 1) continue;
    const x = x0 + k * 260, y = y0 + k * 90;
    const tail = ctx.createLinearGradient(x - 80, y - 28, x, y);
    tail.addColorStop(0, 'rgba(255,255,255,0)');
    tail.addColorStop(1, `rgba(235,245,255,${.9 * (1 - k * .6)})`);
    ctx.strokeStyle = tail;
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(x - 80, y - 28); ctx.lineTo(x, y); ctx.stroke();
  }
  const halo = ctx.createRadialGradient(px, py, r * .9, px, py, r * 1.9);
  halo.addColorStop(0, `hsla(${hue - 6}, 100%, 62%, .22)`);
  halo.addColorStop(1, `hsla(${hue - 6}, 100%, 62%, 0)`);
  ctx.fillStyle = halo;
  ctx.fillRect(px - r * 2, py - r * 2, r * 4, r * 4);
  const tilt = -.3 + .08 * Math.sin(a / 9);
  const moonAngle = a / 7 * Math.PI * 2 + 1.2;
  const moonBehind = Math.sin(moonAngle) < 0;
  function moon() {
    const mx = Math.cos(moonAngle) * r * 2.35, my = Math.sin(moonAngle) * r * .5;
    const cx = px + mx * Math.cos(tilt) - my * Math.sin(tilt), cy = py + mx * Math.sin(tilt) + my * Math.cos(tilt);
    const body = ctx.createRadialGradient(cx - 4, cy - 5, 1, cx, cy, 14);
    body.addColorStop(0, '#f1f6ff'); body.addColorStop(.55, '#a9bddb'); body.addColorStop(1, '#3b4d6d');
    ctx.fillStyle = body;
    ctx.beginPath(); ctx.arc(cx, cy, 13, 0, Math.PI * 2); ctx.fill();
  }
  function ring(front) {
    ctx.save(); ctx.translate(px, py); ctx.rotate(tilt);
    for (let i = 0; i < 6; i++) {
      ctx.beginPath();
      ctx.ellipse(0, 0, r * 1.82 + i * 5, r * .41 + i * 2, 0, front ? 0 : Math.PI, front ? Math.PI : Math.PI * 2);
      ctx.strokeStyle = front ? `rgba(108,192,255,${.49 - i * .065})` : `rgba(58,123,185,${.27 - i * .032})`;
      ctx.lineWidth = i === 0 ? 2 : 1;
      ctx.stroke();
    }
    ctx.restore();
  }
  if (moonBehind) moon();
  ring(false);
  const planet = ctx.createRadialGradient(px - r * .4, py - r * .46, 8, px + r * .23, py + r * .25, r * 1.38);
  planet.addColorStop(0, `hsl(${hue - 12}, 100%, 82%)`);
  planet.addColorStop(.2, `hsl(${hue - 8}, 84%, 63%)`);
  planet.addColorStop(.47, `hsl(${hue - 4}, 77%, 38%)`);
  planet.addColorStop(.73, `hsl(${hue}, 78%, 18%)`);
  planet.addColorStop(1, `hsl(${hue + 4}, 69%, 8%)`);
  ctx.fillStyle = planet;
  ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
  ctx.save();
  ctx.beginPath(); ctx.arc(px, py, r - 1, 0, Math.PI * 2); ctx.clip();
  for (let i = 0; i < 7; i++) {
    ctx.beginPath();
    ctx.ellipse(px + Math.sin(phase + i) * 8, py - r * .87 + i * r * .3, r * 1.17, r * .18, -.27, 0, Math.PI * 2);
    ctx.strokeStyle = i % 2 ? 'rgba(164,216,255,.075)' : 'rgba(2,23,45,.1)';
    ctx.lineWidth = r * .1;
    ctx.stroke();
  }
  ctx.restore();
  ring(true);
  if (!moonBehind) moon();
  const dawn = smoothstep(.5, .85, m);
  if (dawn > 0) {
    const glow = ctx.createRadialGradient(560, 480, 20, 560, 480, 400);
    glow.addColorStop(0, `rgba(255,170,90,${.55 * dawn})`);
    glow.addColorStop(.5, `rgba(255,110,80,${.18 * dawn})`);
    glow.addColorStop(1, 'rgba(255,110,80,0)');
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, 800, 450);
  }
  function ridge(offset, base, amp, fill, edge) {
    ctx.beginPath();
    for (let x = 0; x <= 800; x += 8) {
      const u = x + offset;
      const y = base - amp * (Math.sin(u / 97) * .6 + Math.sin(u / 41 + 1.3) * .3 + Math.sin(u / 17 + .4) * .1);
      if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    if (edge) { ctx.strokeStyle = edge; ctx.lineWidth = 1; ctx.stroke(); }
    ctx.lineTo(800, 450); ctx.lineTo(0, 450); ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
  }
  ridge(a * 2, 352, 26, `hsl(${hue}, 42%, 17%)`, `hsla(${hue - 10}, 70%, 64%, .25)`);
  ridge(a * 7 + 300, 394, 20, `hsl(${hue + 4}, 50%, 8%)`, '');
  if (still) {
    ctx.fillStyle = 'rgba(3,7,14,.58)';
    ctx.fillRect(0, 0, 800, 450);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'alphabetic';
    ctx.fillStyle = '#e7eef9';
    ctx.font = `700 64px ${FONT}`;
    ctx.fillText('ORBIT', 400, 226);
    ctx.fillStyle = '#95a6c4';
    ctx.font = `500 16px ${FONT}`;
    ctx.fillText('SAMPLE CLIP  ·  0:48', 400, 262);
  }
}

function paintFrame(ctx, time, width, height, mode) {
  // mode: contain(프리뷰), cover·letterbox·stretch(GIF 스케일 방식과 같음)
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, width, height);
  let sx, sy, ox = 0, oy = 0;
  if (mode === 'stretch') {
    sx = width / 800; sy = height / 450;
  } else {
    sx = sy = mode === 'cover' ? Math.max(width / 800, height / 450) : Math.min(width / 800, height / 450);
    ox = (width - 800 * sx) / 2; oy = (height - 450 * sy) / 2;
  }
  ctx.setTransform(sx, 0, 0, sy, ox, oy);
  ctx.beginPath(); ctx.rect(0, 0, 800, 450); ctx.clip();
  drawScene(ctx, time);
  ctx.restore();
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  if (ctx.roundRect) { ctx.roundRect(x, y, w, h, r); return; }
  r = Math.min(r, w / 2, h / 2);
  ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

function lighter(hex, factor) {
  const value = Number.parseInt(hex.replace('#', ''), 16);
  const channel = (shift) => Math.min(255, Math.round(((value >> shift) & 255) * factor));
  return `rgb(${channel(16)},${channel(8)},${channel(0)})`;
}

// ---------------------------------------------------------------------------
// GIF 색 처리: 구간을 분석해 256색 팔레트를 만들고(palettegen), 디더링을 적용합니다(paletteuse).
// ---------------------------------------------------------------------------
const BAYER8 = [0, 32, 8, 40, 2, 34, 10, 42, 48, 16, 56, 24, 50, 18, 58, 26, 12, 44, 4, 36, 14, 46, 6, 38, 60, 28, 52, 20, 62, 30, 54, 22,
  3, 35, 11, 43, 1, 33, 9, 41, 51, 19, 59, 27, 49, 17, 57, 25, 15, 47, 7, 39, 13, 45, 5, 37, 63, 31, 55, 23, 61, 29, 53, 21];

function medianCut(histogram, maxColors) {
  const items = [];
  for (let i = 0; i < histogram.length; i++) if (histogram[i]) items.push(i);
  const channel = (item, c) => (item >> (10 - c * 5)) & 31;
  const expand = (v) => (v << 3) | (v >> 2);
  function box(list) {
    const min = [31, 31, 31], max = [0, 0, 0];
    let count = 0;
    for (const item of list) {
      count += histogram[item];
      for (let c = 0; c < 3; c++) { const v = channel(item, c); if (v < min[c]) min[c] = v; if (v > max[c]) max[c] = v; }
    }
    const spans = [max[0] - min[0], max[1] - min[1], max[2] - min[2]];
    const axis = spans.indexOf(Math.max(...spans));
    return { list, count, axis, range: spans[axis] };
  }
  const boxes = [box(items)];
  while (boxes.length < maxColors) {
    let best = -1, bestScore = 0;
    boxes.forEach((b, index) => { const score = b.list.length > 1 ? b.range * b.count : 0; if (score > bestScore) { bestScore = score; best = index; } });
    if (best < 0) break;
    const target = boxes[best];
    target.list.sort((p, q) => channel(p, target.axis) - channel(q, target.axis));
    let acc = 0, cut = 1;
    for (let i = 0; i < target.list.length - 1; i++) {
      acc += histogram[target.list[i]];
      if (acc >= target.count / 2) { cut = i + 1; break; }
    }
    boxes.splice(best, 1, box(target.list.slice(0, cut)), box(target.list.slice(cut)));
  }
  return boxes.map((b) => {
    const sum = [0, 0, 0];
    for (const item of b.list) for (let c = 0; c < 3; c++) sum[c] += expand(channel(item, c)) * histogram[item];
    return sum.map((v) => Math.round(v / b.count));
  });
}

function makeQuantizer(palette) {
  const flat = palette.flat();
  const cache = new Int16Array(32768).fill(-1);
  return function nearest(r, g, b) {
    const key = ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3);
    let index = cache[key];
    if (index >= 0) return index;
    const cr = ((r >> 3) << 3) + 4, cg = ((g >> 3) << 3) + 4, cb = ((b >> 3) << 3) + 4;
    let best = Infinity;
    for (let i = 0; i < flat.length; i += 3) {
      const dr = flat[i] - cr, dg = flat[i + 1] - cg, db = flat[i + 2] - cb;
      const d = dr * dr + dg * dg + db * db;
      if (d < best) { best = d; index = i / 3; }
    }
    cache[key] = index;
    return index;
  };
}

function ditherImage(image, palette, nearest, mode) {
  const { width, height, data } = image;
  const toByte = (v) => (v < 0 ? 0 : v > 255 ? 255 : v | 0);
  if (mode === 'floyd_steinberg') {
    let current = new Float32Array((width + 2) * 3), next = new Float32Array((width + 2) * 3);
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const i = (y * width + x) * 4, e = (x + 1) * 3;
        const r = toByte(data[i] + current[e]), g = toByte(data[i + 1] + current[e + 1]), b = toByte(data[i + 2] + current[e + 2]);
        const color = palette[nearest(r, g, b)];
        data[i] = color[0]; data[i + 1] = color[1]; data[i + 2] = color[2]; data[i + 3] = 255;
        const errors = [r - color[0], g - color[1], b - color[2]];
        for (let c = 0; c < 3; c++) {
          current[e + 3 + c] += errors[c] * 7 / 16;
          next[e - 3 + c] += errors[c] * 3 / 16;
          next[e + c] += errors[c] * 5 / 16;
          next[e + 3 + c] += errors[c] / 16;
        }
      }
      [current, next] = [next, current];
      next.fill(0);
    }
    return;
  }
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = (y * width + x) * 4;
      const offset = mode === 'bayer' ? (BAYER8[(y & 7) * 8 + (x & 7)] >> 2) - 8 : 0;
      const color = palette[nearest(toByte(data[i] + offset), toByte(data[i + 1] + offset), toByte(data[i + 2] + offset))];
      data[i] = color[0]; data[i + 1] = color[1]; data[i + 2] = color[2]; data[i + 3] = 255;
    }
  }
}

// ---------------------------------------------------------------------------
// 웹 체험판: src/ui의 메인 창(제목 표시줄·프리뷰·타임라인·GIF 옵션·출력·로그)을 옮겼습니다.
// ---------------------------------------------------------------------------
function setupSimulator() {
  const sim = $('#sim');
  if (!sim) return;
  const timelineCanvas = $('#sim-timeline');
  const tctx = timelineCanvas.getContext('2d');
  const startCanvas = $('#sim-start-frame'), endCanvas = $('#sim-end-frame');
  if (!tctx || !startCanvas.getContext('2d')) return;

  const rules = trimRules(VIDEO.duration);
  const state = {
    sel: rules.normalize(INITIAL_SELECTION),
    view0: 0, view1: Math.min(VIDEO.duration, Math.max(120, (INITIAL_SELECTION.end - INITIAL_SELECTION.start) * 4)),
    options: { width: 160, height: 80, fps: 12, scale: 'cover', frames: 'even', dither: 'floyd_steinberg' },
    appTheme: 'dark', job: null, made: new Set(), autoName: '', userNamed: false,
  };
  let palette = {};
  const dpr = () => Math.min(2, window.devicePixelRatio || 1);

  // --- 테마 (설정 메뉴 → 테마) ---
  const systemDark = matchMedia('(prefers-color-scheme: dark)');
  function applyAppTheme(mode) {
    state.appTheme = mode;
    const resolved = mode === 'system' ? (systemDark.matches ? 'dark' : 'light') : mode;
    $$('[data-app-theme]').forEach((element) => { element.dataset.appTheme = resolved; });
    $$('[data-theme-choice]', sim).forEach((item) => item.setAttribute('aria-checked', String(item.dataset.themeChoice === mode)));
    readPalette();
    paintPanes();
  }
  function readPalette() {
    const css = getComputedStyle(sim);
    const v = (name) => css.getPropertyValue(name).trim();
    palette = {
      select: v('--a-select'), selectText: v('--a-select-text'), media: v('--a-media'), border: v('--a-border'),
      borderStrong: v('--a-border-strong'), faint: v('--a-faint'), muted: v('--a-muted'), text: v('--a-text'),
      surface: v('--a-surface'), surfaceHover: v('--a-surface-hover'), accent: v('--a-accent'),
    };
  }
  systemDark.addEventListener('change', () => { if (state.appTheme === 'system') applyAppTheme('system'); });

  // --- 알림·대화상자 ---
  const toastBox = $('#sim-toast');
  let toastTimer = 0;
  function toast(text) {
    toastBox.textContent = text;
    toastBox.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastBox.hidden = true; }, 4200);
  }

  const messageDialog = $('#sim-message');
  const MESSAGE_ICONS = { info: ['fi-info', ''], warning: ['fi-warning', 'warning'], error: ['fi-error-circle', 'danger'], question: ['fi-help', ''], success: ['fi-check-circle', 'success'] };
  function showMessage({ title, text, kind = 'info', buttons = [{ key: 'ok', label: '확인', variant: 'primary' }], defaultKey = 'ok' }) {
    if (typeof messageDialog.showModal !== 'function') { toast(text); return Promise.resolve(''); }
    if (messageDialog.open) return Promise.resolve('');
    $('#sim-message-title').textContent = title;
    $('#sim-message-text').textContent = text;
    const [icon, tone] = MESSAGE_ICONS[kind] || MESSAGE_ICONS.info;
    const glyph = $('.message-icon', messageDialog);
    glyph.setAttribute('class', `fi message-icon ${tone}`.trim());
    $('use', glyph).setAttribute('href', `#${icon}`);
    const row = $('#sim-message-buttons');
    row.replaceChildren(...buttons.map(({ key, label, variant }) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `app-btn ${variant || ''}`.trim();
      button.textContent = label;
      button.dataset.choice = key;
      return button;
    }));
    return new Promise((resolve) => {
      let choice = '';
      function onClick(event) {
        const button = event.target.closest('button');
        if (!button) return;
        if (button.dataset.choice) { choice = button.dataset.choice; messageDialog.close(); }
        else if (button.hasAttribute('data-close')) messageDialog.close();
      }
      messageDialog.addEventListener('click', onClick);
      messageDialog.addEventListener('close', () => { messageDialog.removeEventListener('click', onClick); resolve(choice); }, { once: true });
      messageDialog.showModal();
      $(`[data-choice="${defaultKey}"]`, row)?.focus();
    });
  }
  $$('.app-dialog').forEach((dialog) => {
    dialog.addEventListener('click', (event) => {
      if (dialog !== messageDialog && event.target.closest('[data-close]')) dialog.close();
    });
  });

  // --- 로그 ---
  const logBox = $('#sim-log'), lastLine = $('#sim-last-line');
  function log(line) {
    const stamp = new Date().toTimeString().slice(0, 8);
    logBox.textContent += `${logBox.textContent ? '\n' : ''}[${stamp}] ${line}`;
    logBox.scrollTop = logBox.scrollHeight;
    lastLine.textContent = line;
  }
  $('#sim-log-toggle').addEventListener('click', (event) => {
    const expanded = event.currentTarget.getAttribute('aria-expanded') !== 'true';
    event.currentTarget.setAttribute('aria-expanded', String(expanded));
    logBox.hidden = !expanded;
    if (expanded) logBox.scrollTop = logBox.scrollHeight;
  });
  $('#sim-log-clear').addEventListener('click', () => { logBox.textContent = ''; lastLine.textContent = ''; });

  // --- 프리뷰 (시작·끝 장면, 꽉 채우기 크롭 가이드) ---
  function paintPane(canvas, time) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = palette.media || '#03070e';
    ctx.fillRect(0, 0, w, h);
    const scale = Math.min(w / 800, h / 450);
    const iw = 800 * scale, ih = 450 * scale, ix = (w - iw) / 2, iy = (h - ih) / 2;
    ctx.save();
    ctx.translate(ix, iy);
    ctx.scale(scale, scale);
    ctx.beginPath(); ctx.rect(0, 0, 800, 450); ctx.clip();
    drawScene(ctx, time);
    ctx.restore();
    const { width, height, scale: mode } = state.options;
    if (mode !== 'cover') return;
    const aspect = width / height;
    let crop;
    if (iw / ih > aspect) { const cw = ih * aspect; crop = [ix + (iw - cw) / 2, iy, cw, ih]; }
    else { const ch = iw / aspect; crop = [ix, iy + (ih - ch) / 2, iw, ch]; }
    ctx.fillStyle = 'rgba(0,0,0,.47)';
    ctx.beginPath();
    ctx.rect(ix, iy, iw, ih);
    ctx.rect(crop[0], crop[1], crop[2], crop[3]);
    ctx.fill('evenodd');
    const ratio = dpr();
    ctx.setLineDash([4.8 * ratio, 2.4 * ratio]);
    ctx.lineWidth = 1.2 * ratio;
    ctx.strokeStyle = 'rgba(255,255,255,.78)';
    ctx.strokeRect(crop[0] + ratio * .6, crop[1] + ratio * .6, crop[2] - ratio * 1.2, crop[3] - ratio * 1.2);
    ctx.setLineDash([]);
  }

  // --- 타임라인 (src/ui/widgets/timeline.py) ---
  const RULER_H = 22, STRIP_H = 58, OVERVIEW_GAP = 7, OVERVIEW_H = 6, HANDLE_W = 12, PAD_X = HANDLE_W + 2, RADIUS = 7;
  const MIN_VIEW = 2, ZOOM_STEP = 1.25, ASPECT = 16 / 9;
  const tl = { drag: null, grab: 0, hover: null, hoverHit: null, last: null, pendingTap: null, autopan: 0, width: 800 };
  const thumbs = new Map();

  const span = () => Math.max(1e-6, state.view1 - state.view0);
  const minSpan = () => Math.min(VIDEO.duration, MIN_VIEW);
  const isZoomed = () => span() < VIDEO.duration - 1e-6;
  const canZoomIn = () => span() > minSpan() + 1e-6;
  const track = () => ({ x: PAD_X, y: RULER_H, w: Math.max(10, tl.width - 2 * PAD_X), h: STRIP_H });
  const overview = () => ({ x: PAD_X, y: RULER_H + STRIP_H + OVERVIEW_GAP, w: Math.max(10, tl.width - 2 * PAD_X), h: OVERVIEW_H });
  const toX = (t) => { const tr = track(); return tr.x + (t - state.view0) / span() * tr.w; };
  const toT = (x) => { const tr = track(); return state.view0 + (x - tr.x) / tr.w * span(); };

  function setView(start, width) {
    width = Math.min(Math.max(width, minSpan()), VIDEO.duration);
    start = Math.min(Math.max(start, 0), VIDEO.duration - width);
    if (start === state.view0 && start + width === state.view1) return;
    state.view0 = start; state.view1 = start + width;
    syncZoomButtons();
    requestPaint();
  }
  function zoom(factor, anchor) {
    const s = span();
    anchor ??= (state.view0 + state.view1) / 2;
    const next = s / factor;
    setView(anchor - (anchor - state.view0) * next / s, next);
  }
  const selCenter = () => (state.sel.start + state.sel.end) / 2;
  const zoomIn = () => zoom(ZOOM_STEP ** 2, selCenter());
  const zoomOut = () => zoom(1 / ZOOM_STEP ** 2, selCenter());
  const zoomFit = () => setView(0, VIDEO.duration);
  function zoomToSelection() {
    const width = (state.sel.end - state.sel.start) / 0.6;
    setView(selCenter() - width / 2, width);
  }
  function reveal(sel) {
    const s = span();
    if (sel.start >= state.view0 && sel.end <= state.view1) return;
    const length = sel.end - sel.start;
    if (length > s * .9) setView((sel.start + sel.end) / 2 - length / 1.4, length / .7);
    else if (sel.start < state.view0) setView(sel.start - s * .1, s);
    else setView(sel.end - s * .9, s);
  }

  function thumbnail(t) {
    const key = Math.round(t * 1000);
    let canvas = thumbs.get(key);
    if (canvas) return canvas;
    const ratio = dpr();
    canvas = document.createElement('canvas');
    canvas.width = Math.round(STRIP_H * ASPECT * ratio);
    canvas.height = Math.round(STRIP_H * ratio);
    paintFrame(canvas.getContext('2d'), t, canvas.width, canvas.height, 'cover');
    if (thumbs.size > 600) thumbs.delete(thumbs.keys().next().value);
    thumbs.set(key, canvas);
    return canvas;
  }

  function paintTimeline() {
    const ratio = dpr();
    const ctx = tctx;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, tl.width, 96);
    const tr = track();
    // 눈금자
    const pps = tr.w / span();
    const step = rulerStep(pps), minor = minorStep(step, pps);
    const base = RULER_H - 2;
    ctx.font = `11px ${FONT}`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'bottom';
    ctx.lineWidth = 1;
    if (minor) {
      ctx.strokeStyle = palette.borderStrong;
      ctx.beginPath();
      for (let k = Math.floor(state.view0 / minor); k * minor <= state.view1; k++) {
        const x = Math.round(toX(k * minor)) + .5;
        if (x >= tr.x - 1 && x <= tr.x + tr.w + 1) { ctx.moveTo(x, base - 3); ctx.lineTo(x, base); }
      }
      ctx.stroke();
    }
    for (let k = Math.floor(state.view0 / step); k * step <= state.view1 + 1e-9; k++) {
      const t = k * step, x = Math.round(toX(t)) + .5;
      if (x < tr.x - 1 || x > tr.x + tr.w + 1) continue;
      ctx.strokeStyle = palette.faint;
      ctx.beginPath(); ctx.moveTo(x, base - 7); ctx.lineTo(x, base); ctx.stroke();
      const label = formatTick(t, step, false);
      if (x + 3 + ctx.measureText(label).width <= tl.width - 2) { ctx.fillStyle = palette.muted; ctx.fillText(label, x + 3, base - 3); }
    }
    // 필름스트립
    ctx.save();
    roundRect(ctx, tr.x, tr.y, tr.w, tr.h, RADIUS);
    ctx.clip();
    ctx.fillStyle = palette.media;
    ctx.fillRect(tr.x, tr.y, tr.w, tr.h);
    const tileTime = tileSpan(STRIP_H * ASPECT / pps, FRAME_STEP);
    for (let index = Math.floor(state.view0 / tileTime); ; index++) {
      const t0 = index * tileTime;
      if (t0 >= Math.min(VIDEO.duration, state.view1)) break;
      const t1 = Math.min(VIDEO.duration, t0 + tileTime);
      const x0 = toX(t0), x1 = toX(t1), w = x1 - x0;
      const sample = Math.min(t0 + tileTime / 2, Math.max(0, VIDEO.duration - FRAME_STEP));
      const image = thumbnail(sample);
      const target = w / tr.h;
      const sw = image.width, sh = image.height;
      if (sw / sh > target) { const crop = sh * target; ctx.drawImage(image, (sw - crop) / 2, 0, crop, sh, x0, tr.y, w, tr.h); }
      else { const crop = sw / target; ctx.drawImage(image, 0, (sh - crop) / 2, sw, crop, x0, tr.y, w, tr.h); }
      ctx.fillStyle = 'rgba(0,0,0,.35)';
      ctx.fillRect(x0, tr.y, 1, tr.h);
    }
    const x0 = toX(state.sel.start), x1 = toX(state.sel.end);
    ctx.globalAlpha = 170 / 255;
    ctx.fillStyle = palette.media;
    ctx.fillRect(tr.x, tr.y, Math.max(0, x0 - tr.x), tr.h);
    ctx.fillRect(x1, tr.y, Math.max(0, tr.x + tr.w - x1), tr.h);
    ctx.globalAlpha = 1;
    const hovering = tl.hover !== null && !tl.drag && (tl.hoverHit === 'track' || tl.hoverHit === 'body');
    if (hovering && tl.hover >= tr.x && tl.hover <= tr.x + tr.w) {
      ctx.strokeStyle = 'rgba(255,255,255,.67)';
      ctx.beginPath(); ctx.moveTo(tl.hover, tr.y); ctx.lineTo(tl.hover, tr.y + tr.h); ctx.stroke();
    }
    ctx.restore();
    // 선택 구간과 손잡이
    ctx.fillStyle = palette.select;
    ctx.fillRect(x0, tr.y, Math.max(0, x1 - x0), 3);
    ctx.fillRect(x0, tr.y + tr.h - 3, Math.max(0, x1 - x0), 3);
    for (const [which, left] of [['start', x0 - HANDLE_W], ['end', x1]]) {
      const active = tl.drag === which || (!tl.drag && tl.hoverHit === which);
      ctx.fillStyle = active ? lighter(palette.select, 1.12) : palette.select;
      roundRect(ctx, left, tr.y, HANDLE_W, tr.h, 5);
      ctx.fill();
      ctx.fillRect(left + (which === 'start' ? HANDLE_W - 5 : 0), tr.y, 5, tr.h);
      ctx.strokeStyle = palette.selectText;
      ctx.lineWidth = 1.4;
      const mid = left + HANDLE_W / 2;
      ctx.beginPath();
      for (const dx of [-1.6, 1.6]) { ctx.moveTo(mid + dx, tr.y + tr.h / 2 - 7); ctx.lineTo(mid + dx, tr.y + tr.h / 2 + 7); }
      ctx.stroke();
    }
    paintLabel(ctx, tr, (x0 + x1) / 2, `${(state.sel.end - state.sel.start).toFixed(2)}초`, palette.select, palette.selectText);
    if (hovering) paintLabel(ctx, tr, tl.hover, formatTick(toT(tl.hover), 0.1, false), palette.surface, palette.text, palette.borderStrong);
    // 개요 막대
    const ov = overview();
    ctx.fillStyle = palette.surfaceHover;
    roundRect(ctx, ov.x, ov.y, ov.w, ov.h, OVERVIEW_H / 2); ctx.fill();
    if (isZoomed()) {
      ctx.fillStyle = palette.borderStrong;
      roundRect(ctx, ov.x + state.view0 / VIDEO.duration * ov.w, ov.y, Math.max(6, span() / VIDEO.duration * ov.w), ov.h, OVERVIEW_H / 2); ctx.fill();
    }
    ctx.fillStyle = palette.select;
    roundRect(ctx, ov.x + state.sel.start / VIDEO.duration * ov.w, ov.y - 1, Math.max(3, (state.sel.end - state.sel.start) / VIDEO.duration * ov.w), ov.h + 2, 2); ctx.fill();
    if (document.activeElement === timelineCanvas) {
      ctx.strokeStyle = palette.accent;
      ctx.lineWidth = 1.2;
      roundRect(ctx, tr.x - 1.5, tr.y - 1.5, tr.w + 3, tr.h + 3, RADIUS + 1); ctx.stroke();
    }
  }

  function paintLabel(ctx, tr, center, text, fill, ink, border) {
    ctx.font = `700 11px ${FONT}`;
    const width = ctx.measureText(text).width + 14;
    const left = Math.min(Math.max(center - width / 2, tr.x - HANDLE_W), tr.x + tr.w + HANDLE_W - width);
    const height = RULER_H - 5;
    roundRect(ctx, left, 1, width, height, height / 2);
    ctx.fillStyle = fill; ctx.fill();
    if (border) { ctx.strokeStyle = border; ctx.lineWidth = 1; ctx.stroke(); }
    ctx.fillStyle = ink;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, left + width / 2, 1 + height / 2 + .5);
    ctx.textAlign = 'left';
    ctx.textBaseline = 'bottom';
  }

  function hitTest(x, y, slop = 3) {
    const tr = track();
    if (isZoomed()) { const ov = overview(); if (y >= ov.y - 4 && y <= ov.y + ov.h + 4 && x >= ov.x && x <= ov.x + ov.w) return 'overview'; }
    if (y > tr.y + tr.h + 3) return null;
    const x0 = toX(state.sel.start), x1 = toX(state.sel.end);
    const inStart = x0 - HANDLE_W - slop <= x && x <= x0 + slop;
    const inEnd = x1 - slop <= x && x <= x1 + HANDLE_W + slop;
    if (inStart && inEnd) return Math.abs(x - (x0 - HANDLE_W / 2)) <= Math.abs(x - (x1 + HANDLE_W / 2)) ? 'start' : 'end';
    if (inStart) return 'start';
    if (inEnd) return 'end';
    if (x0 < x && x < x1) return 'body';
    if (tr.x - HANDLE_W <= x && x <= tr.x + tr.w + HANDLE_W) return 'track';
    return null;
  }

  function setCursor(hit) {
    const shapes = { start: 'ew-resize', end: 'ew-resize', body: 'grab', track: 'pointer', overview: 'pointer' };
    timelineCanvas.style.cursor = tl.drag === 'move' ? 'grabbing' : shapes[hit] || 'default';
  }

  const pointerPos = (event) => { const rect = timelineCanvas.getBoundingClientRect(); return { x: event.clientX - rect.left, y: event.clientY - rect.top }; };

  function applyDrag(pos) {
    let next;
    if (tl.drag === 'start') next = rules.dragStart(state.sel, toT(pos.x - tl.grab));
    else if (tl.drag === 'end') next = rules.dragEnd(state.sel, toT(pos.x - tl.grab));
    else if (tl.drag === 'move') next = rules.move(state.sel, toT(pos.x) - tl.grab);
    else return;
    setSelection(next, { reveal: false });
  }

  function panToOverview(x) {
    const ov = overview();
    setView((x - ov.x) / ov.w * VIDEO.duration - span() / 2, span());
  }

  function autopanTick() {
    tl.autopan = 0;
    const tr = track();
    const x = tl.last?.x ?? 0;
    const distance = x > tr.x + tr.w ? x - (tr.x + tr.w) : x < tr.x ? x - tr.x : 0;
    if (!['start', 'end', 'move'].includes(tl.drag) || distance === 0 || !isZoomed()) return;
    setView(state.view0 + clamp(distance / 30, -4, 4) * span() * .006, span());
    applyDrag(tl.last);
    tl.autopan = requestAnimationFrame(autopanTick);
  }

  timelineCanvas.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    timelineCanvas.focus({ preventScroll: true });
    const pos = pointerPos(event);
    const touch = event.pointerType === 'touch';
    let hit = hitTest(pos.x, pos.y, touch ? 12 : 3);
    tl.last = pos;
    if (hit === 'start') tl.grab = pos.x - toX(state.sel.start);
    else if (hit === 'end') tl.grab = pos.x - toX(state.sel.end);
    else if (hit === 'body') { tl.grab = toT(pos.x) - state.sel.start; hit = 'move'; }
    else if (hit === 'track') {
      if (touch) { tl.pendingTap = pos; return; }  // 세로 스크롤과 구분하려고 손을 뗄 때 옮깁니다.
      setSelection(rules.move(state.sel, toT(pos.x) - (state.sel.end - state.sel.start) / 2), { reveal: false });
      tl.grab = (state.sel.end - state.sel.start) / 2;
      hit = 'move';
    }
    if (!hit) return;
    tl.drag = hit;
    timelineCanvas.setPointerCapture(event.pointerId);
    if (hit === 'overview') panToOverview(pos.x);
    setCursor(hit);
    requestPaint();
  });
  timelineCanvas.addEventListener('pointermove', (event) => {
    const pos = pointerPos(event);
    tl.last = pos;
    if (!tl.drag) {
      if (event.pointerType !== 'mouse') return;
      tl.hover = pos.x;
      tl.hoverHit = hitTest(pos.x, pos.y);
      setCursor(tl.hoverHit);
      requestPaint();
      return;
    }
    if (tl.drag === 'overview') { panToOverview(pos.x); return; }
    applyDrag(pos);
    const tr = track();
    if ((pos.x < tr.x || pos.x > tr.x + tr.w) && isZoomed()) { if (!tl.autopan) tl.autopan = requestAnimationFrame(autopanTick); }
    else if (tl.autopan) { cancelAnimationFrame(tl.autopan); tl.autopan = 0; }
  });
  function endDrag(event) {
    if (tl.pendingTap && event.type === 'pointerup') {
      const pos = pointerPos(event);
      if (Math.hypot(pos.x - tl.pendingTap.x, pos.y - tl.pendingTap.y) < 10) {
        setSelection(rules.move(state.sel, toT(pos.x) - (state.sel.end - state.sel.start) / 2), { reveal: false });
      }
    }
    tl.pendingTap = null;
    if (!tl.drag) return;
    tl.drag = null;
    if (tl.autopan) { cancelAnimationFrame(tl.autopan); tl.autopan = 0; }
    setCursor(event.type === 'pointerup' ? hitTest(pointerPos(event).x, pointerPos(event).y) : null);
    requestPaint();
  }
  timelineCanvas.addEventListener('pointerup', endDrag);
  timelineCanvas.addEventListener('pointercancel', endDrag);
  timelineCanvas.addEventListener('pointerleave', () => { if (!tl.drag) { tl.hover = null; tl.hoverHit = null; requestPaint(); } });
  timelineCanvas.addEventListener('dblclick', (event) => {
    const pos = pointerPos(event);
    const hit = hitTest(pos.x, pos.y);
    if (['body', 'start', 'end'].includes(hit) && span() > (state.sel.end - state.sel.start) / .55) zoomToSelection();
    else zoomFit();
  });
  let wheelHintShown = false;
  timelineCanvas.addEventListener('wheel', (event) => {
    // 페이지 스크롤을 가로채지 않도록, 타임라인을 한 번 누르거나 Tab으로 고른 뒤에만 휠을 받습니다.
    if (document.activeElement !== timelineCanvas) {
      if (!wheelHintShown) { wheelHintShown = true; toast('타임라인을 한 번 누른 뒤 휠을 돌리면 확대·축소됩니다.'); }
      return;
    }
    event.preventDefault();
    const unit = event.deltaMode === 1 ? 33 : event.deltaMode === 2 ? 800 : 1;
    const dx = event.deltaX * unit, dy = event.deltaY * unit;
    const horizontal = Math.abs(dx) > Math.abs(dy);
    if (horizontal || event.shiftKey) setView(state.view0 + (horizontal ? dx : dy) / 100 * span() * .12, span());
    else zoom(ZOOM_STEP ** (-dy / 100), toT(pointerPos(event).x));
  }, { passive: false });
  timelineCanvas.addEventListener('keydown', (event) => {
    let step = event.shiftKey ? 1 : 0.1;
    if (event.altKey) step = FRAME_STEP;
    const sel = state.sel;
    switch (event.key) {
      case 'ArrowLeft':
      case 'ArrowRight': {
        const direction = event.key === 'ArrowLeft' ? -1 : 1;
        setSelection(event.ctrlKey || event.metaKey ? rules.dragEnd(sel, sel.end + direction * step) : rules.move(sel, sel.start + direction * step), { announce: true });
        break;
      }
      case 'Home': setSelection(rules.move(sel, 0), { announce: true }); break;
      case 'End': setSelection(rules.move(sel, VIDEO.duration), { announce: true }); break;
      case '+': case '=': zoomIn(); break;
      case '-': zoomOut(); break;
      case '0': zoomFit(); break;
      default: return;
    }
    event.preventDefault();
  });
  timelineCanvas.addEventListener('focus', requestPaint);
  timelineCanvas.addEventListener('blur', requestPaint);

  const zoomButtons = { in: $('#sim-zoom-in'), out: $('#sim-zoom-out'), fit: $('#sim-zoom-fit'), sel: $('#sim-zoom-sel') };
  zoomButtons.in.addEventListener('click', zoomIn);
  zoomButtons.out.addEventListener('click', zoomOut);
  zoomButtons.fit.addEventListener('click', zoomFit);
  zoomButtons.sel.addEventListener('click', zoomToSelection);
  function syncZoomButtons() {
    zoomButtons.in.disabled = !canZoomIn();
    zoomButtons.out.disabled = !isZoomed();
    zoomButtons.fit.disabled = !isZoomed();
  }

  // --- 구간·시간 입력칸 (timeline_panel.py, TimeField) ---
  const fields = {
    start: { input: $('#sim-field-start'), format: formatTime },
    length: { input: $('#sim-field-length'), format: (v) => v.toFixed(2) },
    end: { input: $('#sim-field-end'), format: formatTime },
  };
  let announceTimer = 0;
  function setSelection(next, { reveal: doReveal = true, announce = false } = {}) {
    next = rules.normalize(next);
    const changed = next.start !== state.sel.start || next.end !== state.sel.end;
    state.sel = next;
    if (doReveal) reveal(next);
    if (changed) onSelectionChanged();
    else requestPaint();
    if (announce) {
      clearTimeout(announceTimer);
      announceTimer = setTimeout(() => {
        $('#sim-announce').textContent = `시작 ${formatTime(next.start)}, 끝 ${formatTime(next.end)}, 길이 ${(next.end - next.start).toFixed(2)}초`;
      }, 250);
    }
  }
  function syncFields(force = false) {
    const values = { start: state.sel.start, length: state.sel.end - state.sel.start, end: state.sel.end };
    for (const [key, field] of Object.entries(fields)) {
      field.shown = field.format(values[key]);
      if (force || document.activeElement !== field.input || field.input.value === field.shown) field.input.value = field.shown;
    }
    const length = values.length;
    const frames = estimateFrames(length, state.options.fps);
    $('#sim-frames').textContent = state.options.frames === 'dedupe' ? `최대 ${frames}프레임` : `약 ${frames}프레임`;
    $('#sim-reco').hidden = !(length > RECO_MAX + 1e-6);
  }
  for (const [key, field] of Object.entries(fields)) {
    const box = field.input.closest('.tf-box');
    let flash = 0;
    function commit() {
      const text = field.input.value;
      if (text === field.shown) return;
      let value;
      try { value = parseTime(text); } catch {
        field.input.value = field.shown;
        box.classList.add('invalid');
        box.title = '시간 형식이 올바르지 않습니다. (예: 01:23.500 또는 83.5)';
        clearTimeout(flash);
        flash = setTimeout(() => box.classList.remove('invalid'), 1600);
        return;
      }
      box.classList.remove('invalid');
      const sel = state.sel;
      const next = key === 'start' ? rules.setStart(sel, value) : key === 'end' ? rules.setEnd(sel, value) : rules.setLength(sel, value);
      setSelection(next);
      syncFields(true);   // 값이 그대로여도(규칙에 막힌 입력 등) 정리된 표기로 되돌립니다.
    }
    field.input.addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); commit(); } });
    field.input.addEventListener('blur', commit);
    $$('.tf-nudge', box).forEach((button) => button.addEventListener('click', (event) => {
      const delta = Number(button.dataset.dir) * (event.shiftKey ? 1 : 0.1);
      const sel = state.sel;
      const next = key === 'start' ? rules.dragStart(sel, sel.start + delta) : key === 'end' ? rules.dragEnd(sel, sel.end + delta) : rules.setLength(sel, sel.end - sel.start + delta);
      setSelection(next);
    }));
  }

  // --- GIF 옵션 (options_panel.py) ---
  const widthInput = $('#sim-width'), heightInput = $('#sim-height'), fpsInput = $('#sim-fps');
  const scaleSelect = $('#sim-scale'), framesSelect = $('#sim-frame-mode'), ditherSelect = $('#sim-dither');
  function commitNumber(input, key, lo, hi) {
    const value = Number.parseInt(input.value, 10);
    if (Number.isFinite(value)) state.options[key] = clamp(value, lo, hi);
    input.value = String(state.options[key]);
    onOptionsChanged();
  }
  widthInput.addEventListener('change', () => commitNumber(widthInput, 'width', SIZE_MIN, SIZE_MAX));
  heightInput.addEventListener('change', () => commitNumber(heightInput, 'height', SIZE_MIN, SIZE_MAX));
  fpsInput.addEventListener('change', () => commitNumber(fpsInput, 'fps', FPS_MIN, FPS_MAX));
  $('#sim-size-reset').addEventListener('click', () => {
    Object.assign(state.options, DEFAULT_SIZE);
    widthInput.value = String(DEFAULT_SIZE.width);
    heightInput.value = String(DEFAULT_SIZE.height);
    onOptionsChanged();
  });
  for (const [select, key] of [[scaleSelect, 'scale'], [framesSelect, 'frames'], [ditherSelect, 'dither']]) {
    select.addEventListener('change', () => { state.options[key] = select.value; onOptionsChanged(); });
  }
  function syncSelectTips() {
    for (const select of [scaleSelect, framesSelect, ditherSelect]) select.title = select.selectedOptions[0]?.title || '';
  }
  $('#sim-dither-help').addEventListener('click', () => showMessage({
    title: '디더링이란?',
    text: 'GIF는 한 프레임에 최대 256색만 쓸 수 있습니다. 디더링은 색 경계(밴딩)가 덜 보이도록 작은 점 패턴을 섞는 기법입니다.\n\n• 플로이드-슈타인버그: 부드럽고 자연스러움 (권장)\n• 바이어: 규칙적인 격자 패턴, 선명함\n• 없음: 또렷하지만 색 경계가 생길 수 있음',
  }));
  function onOptionsChanged() {
    const cover = state.options.scale === 'cover';
    for (const canvas of [startCanvas, endCanvas]) canvas.title = cover ? '점선 안쪽이 GIF에 담기는 영역입니다.' : '';
    syncSelectTips();
    syncFields();
    paintPanes();
  }

  // --- 출력 (output_panel.py) ---
  const folderInput = $('#sim-folder'), nameInput = $('#sim-filename'), autoButton = $('#sim-auto-name');
  const generateButton = $('#sim-generate');
  const suggestName = (sel) => `${VIDEO.stem}_${Math.round(sel.start * 1000)}_${Math.round(sel.end * 1000)}.gif`;
  function setUserNamed(value) { state.userNamed = value; autoButton.hidden = !value; }
  function filename() {
    let name = nameInput.value.trim();
    if (name && !name.toLowerCase().endsWith('.gif')) name += '.gif';
    return name;
  }
  const invalidChars = (name) => [...new Set([...name].filter((c) => INVALID_FILENAME_CHARS.includes(c)))].sort().join('');
  nameInput.addEventListener('input', () => {
    const text = nameInput.value.trim();
    setUserNamed(Boolean(state.autoName) && Boolean(text) && text !== state.autoName);
  });
  autoButton.addEventListener('click', () => { setUserNamed(false); nameInput.value = state.autoName; nameInput.focus(); });
  $('#sim-folder-choose').addEventListener('click', () => toast('웹 체험에서는 폴더를 고를 수 없습니다. 앱에서는 폴더 선택 창이 열립니다.'));
  $('#sim-folder-open').addEventListener('click', () => toast('웹 체험에서는 폴더를 열 수 없습니다. 앱에서는 저장 폴더를 탐색기로 엽니다.'));

  function onSelectionChanged() {
    $('#sim-start-time').textContent = formatTime(state.sel.start);
    $('#sim-end-time').textContent = formatTime(state.sel.end);
    state.autoName = suggestName(state.sel);
    if (!state.userNamed) nameInput.value = state.autoName;
    syncFields();
    paintPanes();
  }

  // --- 그리기 예약 ---
  let paintRequest = 0, panesDirty = true;
  function paintPanes() { panesDirty = true; requestPaint(); }
  function requestPaint() {
    if (paintRequest) return;
    paintRequest = requestAnimationFrame(() => {
      paintRequest = 0;
      paintTimeline();
      if (panesDirty) {
        panesDirty = false;
        paintPane(startCanvas, state.sel.start);
        // GIF의 마지막 프레임은 끝 시각 직전 프레임입니다.
        paintPane(endCanvas, Math.max(state.sel.start, Math.min(state.sel.end, VIDEO.duration) - FRAME_STEP));
      }
    });
  }
  function resize() {
    const ratio = dpr();
    const width = Math.max(10, timelineCanvas.clientWidth);
    tl.width = width;
    timelineCanvas.width = Math.round(width * ratio);
    timelineCanvas.height = Math.round(96 * ratio);
    for (const canvas of [startCanvas, endCanvas]) {
      canvas.width = Math.max(16, Math.round(canvas.clientWidth * ratio));
      canvas.height = Math.max(9, Math.round(canvas.clientHeight * ratio));
    }
    thumbs.clear();
    paintPanes();
  }
  if ('ResizeObserver' in window) new ResizeObserver(resize).observe(timelineCanvas);
  else addEventListener('resize', resize);

  // --- GIF 생성 (encoder.py 흐름: [2-pass면 색상 분석 →] 변환 → 결과 창) ---
  const progressRow = $('#sim-progress'), progressBar = $('#sim-progress-bar'), stageLabel = $('#sim-stage');
  const playButton = $('#sim-play');
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const MAX_PIXELS = 320 * 180;

  function setStage(text, fraction) {
    stageLabel.textContent = text;
    progressBar.classList.toggle('indeterminate', fraction === null);
    progressBar.style.setProperty('--p', `${Math.round((fraction ?? 0) * 1000) / 10}%`);
  }
  function setBusy(busy) {
    generateButton.classList.toggle('busy', busy);
    $('span', generateButton).textContent = busy ? '취소' : 'GIF 생성';
    $('use', generateButton).setAttribute('href', busy ? '#fi-dismiss' : '#fi-gif');
    for (const element of [folderInput, $('#sim-folder-choose'), nameInput, autoButton]) element.disabled = busy;
    playButton.disabled = busy;
    progressRow.hidden = !busy;
    if (busy) setStage('', null);
  }

  function planFrames(sel, options) {
    const count = estimateFrames(sel.end - sel.start, options.fps);
    const times = Array.from({ length: count }, (_, i) => sel.start + i / options.fps);
    if (options.frames !== 'dedupe') return times;
    // 중복 제거: 멈춘 타이틀 화면처럼 앞 프레임과 같은 프레임을 뺍니다. 재생 시간도 그만큼 짧아집니다.
    return times.filter((t, i) => i === 0 || !(t < VIDEO.still && times[i - 1] < VIDEO.still));
  }
  function processingSize(width, height) {
    if (width * height <= MAX_PIXELS) return [width, height];
    const f = Math.sqrt(MAX_PIXELS / (width * height));
    return [Math.max(1, Math.round(width * f)), Math.max(1, Math.round(height * f))];
  }

  async function generate() {
    if (state.job) { state.job.cancelled = true; return; }
    const name = filename(), bad = invalidChars(name);
    if (!name || bad) {
      await showMessage({ title: '경고', kind: 'warning', text: `파일 이름에 사용할 수 없는 문자가 있습니다.\n${bad || '∅'}` });
      return;
    }
    const folder = folderInput.value.trim() || '실행 폴더';
    const key = `${folder}\\${name}`.toLowerCase();
    if (state.made.has(key)) {
      const choice = await showMessage({ title: '덮어쓰기', kind: 'warning', text: `같은 이름의 파일이 이미 있습니다.\n${name}\n\n덮어쓰시겠습니까?`,
        buttons: [{ key: 'no', label: '아니요' }, { key: 'yes', label: '예', variant: 'danger' }], defaultKey: 'no' });
      if (choice !== 'yes') return;
    }
    const options = { ...state.options }, sel = { ...state.sel };
    const job = { cancelled: false };
    state.job = job;
    setBusy(true);
    lastLine.textContent = 'GIF 생성 중…';
    const began = performance.now();
    try {
      const times = planFrames(sel, options);
      const [pw, ph] = processingSize(options.width, options.height);
      const work = document.createElement('canvas');
      work.width = pw; work.height = ph;
      const wctx = work.getContext('2d', { willReadFrequently: true });
      // 구간 전체를 훑어 팔레트를 만듭니다. 앱은 보통(1-pass) 이 분석과 변환을 한 번에 하므로 처음부터 변환
      // 진행률을 보여 주고, 크거나 긴 GIF(2-pass)만 '색상 분석 중'을 먼저 보여 줍니다.
      const onePass = estimateFrames(sel.end - sel.start, options.fps) * options.width * options.height <= ONE_PASS_MAX_PIXELS;
      setStage(onePass ? 'GIF 변환 중… 0%' : '색상 분석 중…', onePass ? 0 : null);
      const histogram = new Uint32Array(32768);
      const samples = Math.min(times.length, 40);
      for (let i = 0; i < samples; i++) {
        if (job.cancelled) throw new Error('cancelled');
        paintFrame(wctx, times[Math.floor(i * times.length / samples)], pw, ph, options.scale);
        const data = wctx.getImageData(0, 0, pw, ph).data;
        for (let p = 0; p < data.length; p += 4) histogram[((data[p] >> 3) << 10) | ((data[p + 1] >> 3) << 5) | (data[p + 2] >> 3)]++;
        if (i % 4 === 3) await wait(0);
      }
      const colors = medianCut(histogram, 256);
      const nearest = makeQuantizer(colors);
      await wait(Math.max(0, 600 - (performance.now() - began)));
      // Pass 2: 프레임마다 팔레트와 디더링을 적용합니다. (체험판은 진행 속도를 보기 좋게 맞춥니다.)
      const pace = clamp(times.length * 12, 700, 2600) / times.length;
      const encodeStart = performance.now();
      for (let i = 0; i < times.length; i++) {
        if (job.cancelled) throw new Error('cancelled');
        paintFrame(wctx, times[i], pw, ph, options.scale);
        const image = wctx.getImageData(0, 0, pw, ph);
        ditherImage(image, colors, nearest, options.dither);
        const fraction = (i + 1) / times.length;
        setStage(`GIF 변환 중… ${Math.floor(fraction * 100)}%`, fraction);
        const behind = encodeStart + (i + 1) * pace - performance.now();
        if (behind > 0 || i % 6 === 5) await wait(Math.max(0, behind));
      }
      const elapsed = (performance.now() - began) / 1000;
      state.made.add(key);
      finish();
      const duration = times.length / options.fps;
      const shownFolder = folderInput.value.trim() || '(실행 폴더)';
      log(`[OK] GIF 저장 완료: ${shownFolder}\\${name} (${options.width}×${options.height}, ${times.length}프레임, ${duration.toFixed(2)}초)`);
      lastLine.textContent = `GIF 생성 완료: ${name}`;
      openResult({ name, options, times, colors, nearest, pw, ph, duration, elapsed });
    } catch (error) {
      finish();
      if (job.cancelled) {
        log('[INFO] GIF 생성을 취소했습니다.');
        lastLine.textContent = 'GIF 생성을 취소했습니다.';
      } else {
        log(`[ERR] GIF 생성 실패: ${error.message}`);
        showMessage({ title: '오류', kind: 'error', text: `GIF를 만들지 못했습니다.\n${error.message}` });
      }
    }
    function finish() { state.job = null; setBusy(false); }
  }
  generateButton.addEventListener('click', generate);

  // --- 결과 창 (result_dialog.py) ---
  const resultDialog = $('#sim-result'), resultCanvas = $('#sim-result-canvas'), pauseButton = $('#sim-result-pause');
  const player = { raf: 0, paused: false, index: -1, begin: 0, offset: 0, job: null };
  function openResult(job) {
    const { options, pw, ph } = job;
    resultCanvas.width = pw; resultCanvas.height = ph;
    const factor = Math.max(1, Math.min(Math.floor(480 / options.width), Math.floor(270 / options.height)));
    resultCanvas.style.width = `${options.width * factor}px`;
    $('#sim-result-file').textContent = job.name;
    $('#sim-result-file').title = job.name;
    $('#sim-result-size').textContent = `${options.width} × ${options.height}`;
    $('#sim-result-frames').textContent = String(job.times.length);
    $('#sim-result-duration').textContent = `${job.duration.toFixed(2)}초`;
    $('#sim-result-elapsed').textContent = `${job.elapsed.toFixed(1)}초`;
    const note = $('#sim-result-note');
    note.hidden = pw === options.width;
    note.textContent = `미리보기는 ${pw}×${ph}로 줄여서 보여 줍니다. 앱은 ${options.width}×${options.height} 그대로 만듭니다.`;
    player.job = job;
    player.index = -1;
    player.offset = 0;
    player.begin = performance.now();
    setPaused(motionPreference.matches);
    renderResultFrame(0);
    if (typeof resultDialog.showModal === 'function') resultDialog.showModal();
    else toast(`GIF 생성 완료: ${job.name}`);
  }
  function renderResultFrame(index) {
    const job = player.job;
    if (!job || index === player.index) return;
    player.index = index;
    const ctx = resultCanvas.getContext('2d', { willReadFrequently: true });
    paintFrame(ctx, job.times[index], job.pw, job.ph, job.options.scale);
    const image = ctx.getImageData(0, 0, job.pw, job.ph);
    ditherImage(image, job.colors, job.nearest, job.options.dither);
    ctx.putImageData(image, 0, 0);
  }
  function playTick(now) {
    player.raf = 0;
    const job = player.job;
    if (!job || player.paused || !resultDialog.open) return;
    const elapsed = player.offset + (now - player.begin) / 1000;
    renderResultFrame(Math.floor(elapsed * job.options.fps) % job.times.length);
    player.raf = requestAnimationFrame(playTick);
  }
  function setPaused(paused) {
    player.paused = paused;
    pauseButton.setAttribute('aria-pressed', String(paused));
    pauseButton.setAttribute('aria-label', paused ? '재생' : '일시정지');
    pauseButton.title = paused ? '재생' : '일시정지';
    const glyph = $('svg', pauseButton);
    glyph.setAttribute('class', paused ? 'fi' : 'icon');
    $('use', glyph).setAttribute('href', paused ? '#fi-play' : '#pause');
    if (player.raf) { cancelAnimationFrame(player.raf); player.raf = 0; }
    if (!paused) {
      player.offset = player.job ? Math.max(0, player.index) / player.job.options.fps : 0;
      player.begin = performance.now();
      player.raf = requestAnimationFrame(playTick);
    }
  }
  pauseButton.addEventListener('click', () => setPaused(!player.paused));
  resultDialog.addEventListener('close', () => { if (player.raf) cancelAnimationFrame(player.raf); player.raf = 0; player.job = null; });

  // --- 구간 재생 ---
  const playerDialog = $('#sim-player'), playerCanvas = $('#sim-player-canvas');
  const clip = { raf: 0, begin: 0 };
  function playClip() {
    cancelAnimationFrame(clip.raf);
    const { start, end } = state.sel;
    const ratio = dpr();
    playerCanvas.width = Math.round(playerCanvas.clientWidth * ratio) || 640;
    playerCanvas.height = Math.round(playerCanvas.width * 9 / 16);
    const ctx = playerCanvas.getContext('2d');
    clip.begin = performance.now();
    function frame(now) {
      const t = Math.min(end, start + (now - clip.begin) / 1000);
      paintFrame(ctx, t, playerCanvas.width, playerCanvas.height, 'contain');
      $('#sim-player-progress').style.setProperty('--p', `${(t - start) / (end - start) * 100}%`);
      $('#sim-player-time').textContent = `${formatTime(t)} / ${formatTime(end)}`;
      clip.raf = t < end && playerDialog.open ? requestAnimationFrame(frame) : 0;
    }
    clip.raf = requestAnimationFrame(frame);
  }
  playButton.addEventListener('click', () => {
    if (typeof playerDialog.showModal !== 'function') { toast('이 브라우저에서는 구간 재생 창을 열 수 없습니다.'); return; }
    playerDialog.showModal();
    playClip();
  });
  $('#sim-player-replay').addEventListener('click', playClip);
  playerDialog.addEventListener('close', () => { cancelAnimationFrame(clip.raf); clip.raf = 0; });

  // --- 제목 표시줄과 설정 메뉴 (titlebar.py, menus.py) ---
  const openNote = '웹 체험에서는 샘플 영상만 쓸 수 있습니다.\n내 영상은 Windows 앱에서 ‘비디오 열기’로 열거나 창에 끌어다 놓으세요.';
  $('#sim-open').addEventListener('click', () => showMessage({ title: '비디오 열기', text: openNote }));
  sim.addEventListener('dragover', (event) => { if (event.dataTransfer?.types?.includes('Files')) event.preventDefault(); });
  sim.addEventListener('drop', (event) => { if (event.dataTransfer?.types?.includes('Files')) { event.preventDefault(); showMessage({ title: '비디오 열기', text: openNote }); } });

  const menuButton = $('#sim-menu-button'), menu = $('#sim-menu');
  const menuItems = () => $$('[role^=menuitem]', menu);
  function openMenu(open) {
    menu.hidden = !open;
    menuButton.setAttribute('aria-expanded', String(open));
    if (open) menuItems()[0].focus();
  }
  menuButton.addEventListener('click', () => openMenu(menu.hidden));
  document.addEventListener('pointerdown', (event) => { if (!menu.hidden && !menu.contains(event.target) && !menuButton.contains(event.target)) openMenu(false); });
  menu.addEventListener('keydown', (event) => {
    const items = menuItems(), index = items.indexOf(document.activeElement);
    const moves = { ArrowDown: index + 1, ArrowUp: index - 1, Home: 0, End: items.length - 1 };
    if (event.key in moves) { event.preventDefault(); items[(moves[event.key] + items.length) % items.length].focus(); }
    else if (event.key === 'Escape') { event.preventDefault(); openMenu(false); menuButton.focus(); }
    else if (event.key === 'Tab') openMenu(false);
  });
  const notes = {
    update: ['업데이트', '앱에서는 GitHub의 최신 릴리스를 확인해, 새 버전이 있으면 바뀐 점과 함께 업데이트 창을 띄웁니다. 켤 때도 자동으로 확인합니다.\n\n웹 체험에서는 확인하지 않습니다.'],
    tools: ['도구 업데이트', '앱에서는 ffmpeg 새 버전을 확인해 SHA-256을 검사한 뒤 bin 폴더에 받습니다. 사용 중이라 바로 바꿀 수 없으면 받아 두었다가 다음에 켤 때 적용합니다.'],
    about: ['APEX GIF MAKER 정보', 'Flydigi APEX 시리즈 컨트롤러 스크린용 GIF 메이커\n버전 3.1.0 · 웹 체험판\n\n동영상 처리: FFmpeg (LGPL/GPL)\nUI: Qt for Python / PySide6 (LGPL)\nUI 아이콘: Fluent UI System Icons © Microsoft (MIT)\n글꼴: Pretendard, Pretendard JP, JetBrains Mono (SIL OFL 1.1)'],
  };
  menu.addEventListener('click', (event) => {
    const item = event.target.closest('[role^=menuitem]');
    if (!item) return;
    openMenu(false);
    menuButton.focus();
    if (item.dataset.themeChoice) applyAppTheme(item.dataset.themeChoice);
    else if (item.dataset.language) {
      $$('[data-language]', menu).forEach((other) => other.setAttribute('aria-checked', String(other === item)));
      showMessage({ title: '알림', text: '언어 설정은 프로그램을 다시 시작하면 적용됩니다.\n(웹 체험 화면은 한국어로만 보여 줍니다.)' });
    } else if (item.dataset.toggle) item.setAttribute('aria-checked', String(item.getAttribute('aria-checked') !== 'true'));
    else if (item.dataset.note) { const [title, text] = notes[item.dataset.note]; showMessage({ title, text }); }
  });
  $('#sim-about').addEventListener('click', () => { const [title, text] = notes.about; showMessage({ title, text }); });

  // 앱과 같은 단축키. 브라우저 단축키와 겹치지 않도록 체험판 안에 초점이 있을 때만 받습니다.
  sim.addEventListener('keydown', (event) => {
    if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
    const key = event.key.toLowerCase();
    if (key === 'enter') { event.preventDefault(); if (!state.job) generate(); }
    else if (key === 'p') { event.preventDefault(); if (!playButton.disabled) playButton.click(); }
    else if (key === 'o') { event.preventDefault(); $('#sim-open').click(); }
  });

  // --- 시작 ---
  readPalette();
  state.autoName = suggestName(state.sel);
  nameInput.value = state.autoName;
  syncZoomButtons();
  onOptionsChanged();
  onSelectionChanged();
  log(`[OK] 불러옴: ${VIDEO.name} (1280×720 · 30 fps · ${formatTime(VIDEO.duration)})`);
  resize();
  document.fonts?.ready.then(() => { thumbs.clear(); paintPanes(); });
}

// ---------------------------------------------------------------------------
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
    const releaseUrl = safeUrl(release.html_url, 'release');
    if (release.draft || release.prerelease || !releaseUrl) return;
    const assets = Array.isArray(release.assets) ? release.assets : [];
    const asset = assets.find((item) => /^ApexGIFMaker[^/\\]*\.zip$/i.test(item.name) && safeUrl(item.browser_download_url, 'asset'));
    if (asset) {
      document.querySelectorAll('[data-download]').forEach((link) => { link.href = safeUrl(asset.browser_download_url, 'asset'); });
    }
    const version = typeof release.tag_name === 'string' && /^v?\d+\.\d+\.\d+$/.test(release.tag_name) ? release.tag_name : '';
    if (version) {
      $('#release-badge-text').textContent = `${version} 정식 출시`;
      $('#release-badge').href = releaseUrl;
    }
    $('#release-notes').href = releaseUrl;
    const size = asset && Number.isFinite(asset.size) && asset.size > 0 ? ` · ${(asset.size / 1048576).toFixed(1)} MB` : '';
    const published = Date.parse(release.published_at);
    const date = Number.isFinite(published) ? ` · ${new Date(published).toLocaleDateString('ko-KR')} 공개` : '';
    $('#release-meta').textContent = `${version || '최신 안정 버전'}${size}${date} · Windows 10/11 64비트`;
    const digest = asset && typeof asset.digest === 'string' ? /^sha256:([0-9a-f]{64})$/i.exec(asset.digest) : null;
    if (digest) {
      $('#release-sha-value').textContent = digest[1].toUpperCase();
      $('#release-sha').hidden = false;
    }
  } catch { /* Static, usable fallback is intentional. */ }
  finally { clearTimeout(timer); }
}

setupTheme();
setupSimulator();
setupScreenshot();
syncRelease();
