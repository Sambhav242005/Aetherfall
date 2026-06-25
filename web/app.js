import { DEMO_BOARD, storyToBoard, loadStoryFromApi } from './data.js';

// ---------------------------------------------------------------- constants
const NODE_W = 248;
const PAD = 16, CHIP_H = 22, TITLE_LH = 20, BODY_LH = 17, MIN_H = 92, MAX_BODY_LINES = 6;
const GRID = 28;
const ZOOM_MIN = 0.2, ZOOM_MAX = 2.6;
const STORAGE_KEY = 'aetherfall.board.v1';
const FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, Helvetica, Arial, sans-serif';

// Remembered backend connection (shared by "Load from API…" and the World Bible panel).
const API_DEFAULT = 'http://127.0.0.1:8000';
const API_KEY = 'aetherfall.api.v1';
const lastApi = { base: API_DEFAULT, worldId: '' };
try { const a = JSON.parse(localStorage.getItem(API_KEY)); if (a) { lastApi.base = a.base || API_DEFAULT; lastApi.worldId = a.worldId || ''; } } catch {}
function saveApi() { try { localStorage.setItem(API_KEY, JSON.stringify(lastApi)); } catch {} }

const TYPES = {
  arc:   { label: 'Arc',   ink: '#9a3412', tint: '#f8e6d2', dot: '#c2410c' },
  beat:  { label: 'Beat',  ink: '#115e59', tint: '#d4ede9', dot: '#0f766e' },
  scene: { label: 'Scene', ink: '#5b21b6', tint: '#e7dbfb', dot: '#7c3aed' },
  note:  { label: 'Note',  ink: '#3f4757', tint: '#e6eaf0', dot: '#64748b' },
};
const TYPE_ORDER = ['arc', 'beat', 'scene', 'note'];

// ---------------------------------------------------------------- state
const canvas = document.getElementById('board');
const ctx = canvas.getContext('2d');

const state = {
  nodes: new Map(),                 // id -> node
  edges: new Map(),                 // id -> { id, from, to }
  cam: { x: 0, y: 0, zoom: 1 },     // screen = world * zoom + (x,y)
  tool: 'select',
  sel: new Set(),                   // selected node + edge ids
  hover: null,
  spaceDown: false,
  editing: null,                    // node id being edited
};
let dpr = Math.max(1, window.devicePixelRatio || 1);
let pointer = { x: 0, y: 0 };       // last screen pos
let drag = null;                    // active interaction
let needsRender = false;
let uid = 1;
const nid = (p) => `${p}_${Date.now().toString(36)}${(uid++).toString(36)}`;

// ---------------------------------------------------------------- geometry
const worldToScreen = (wx, wy) => ({ x: wx * state.cam.zoom + state.cam.x, y: wy * state.cam.zoom + state.cam.y });
const screenToWorld = (sx, sy) => ({ x: (sx - state.cam.x) / state.cam.zoom, y: (sy - state.cam.y) / state.cam.zoom });
const portOf = (n) => ({ x: n.x + n.w / 2, y: n.y + n.h });      // outgoing port (bottom)
const inletOf = (n) => ({ x: n.x + n.w / 2, y: n.y });           // incoming (top)

function ctrlPts(a, b) {
  const dy = Math.min(Math.max(Math.abs(b.y - a.y) * 0.5, 32), 130);
  return [a, { x: a.x, y: a.y + dy }, { x: b.x, y: b.y - dy }, b];
}
function bezier(t, p0, p1, p2, p3) {
  const u = 1 - t, tt = t * t, uu = u * u;
  return {
    x: uu * u * p0.x + 3 * uu * t * p1.x + 3 * u * tt * p2.x + tt * t * p3.x,
    y: uu * u * p0.y + 3 * uu * t * p1.y + 3 * u * tt * p2.y + tt * t * p3.y,
  };
}

// ---------------------------------------------------------------- text layout
function wrapLines(text, maxW, font) {
  ctx.font = font;
  const out = [];
  for (const para of String(text).split('\n')) {
    const words = para.split(/\s+/).filter(Boolean);
    let line = '';
    for (const w of words) {
      const t = line ? line + ' ' + w : w;
      if (ctx.measureText(t).width > maxW && line) { out.push(line); line = w; }
      else line = t;
    }
    out.push(line);
  }
  return out;
}
function measure(n) {
  const tFont = `650 15px ${FONT}`;
  const bFont = `400 12.5px ${FONT}`;
  n._title = wrapLines(n.title || 'Untitled', NODE_W - PAD * 2, tFont);
  let body = n.body ? wrapLines(n.body, NODE_W - PAD * 2, bFont) : [];
  if (body.length > MAX_BODY_LINES) { body = body.slice(0, MAX_BODY_LINES); body[MAX_BODY_LINES - 1] += '…'; }
  n._body = body;
  n.w = NODE_W;
  n.h = Math.max(MIN_H,
    PAD + CHIP_H + 10 + n._title.length * TITLE_LH + (body.length ? 6 + body.length * BODY_LH : 0) + PAD);
}

// ---------------------------------------------------------------- model ops
function addNode(node) {
  const n = { id: node.id || nid('n'), type: node.type || 'note', title: node.title || '', body: node.body || '', x: node.x || 0, y: node.y || 0 };
  measure(n);
  state.nodes.set(n.id, n);
  return n;
}
function addEdge(from, to) {
  if (from === to || !state.nodes.has(from) || !state.nodes.has(to)) return null;
  for (const e of state.edges.values()) if (e.from === from && e.to === to) return e;
  const e = { id: nid('e'), from, to };
  state.edges.set(e.id, e);
  return e;
}
function deleteSelection() {
  for (const id of state.sel) {
    if (state.nodes.has(id)) {
      state.nodes.delete(id);
      for (const [eid, e] of state.edges) if (e.from === id || e.to === id) state.edges.delete(eid);
    } else state.edges.delete(id);
  }
  state.sel.clear();
  closeEditor();
  schedule(); save();
}
function loadBoard(board, fit = true) {
  state.nodes.clear(); state.edges.clear(); state.sel.clear();
  for (const n of board.nodes) addNode(n);
  for (const e of board.edges) { const x = addEdge(e.from, e.to); if (x && e.id) { state.edges.delete(x.id); x.id = e.id; state.edges.set(x.id, x); } }
  closeEditor();
  if (fit) fitView(); else schedule();
  save(); refreshEmpty();
}

// ---------------------------------------------------------------- hit testing
function nodeAt(wx, wy) {
  const list = [...state.nodes.values()];
  for (let i = list.length - 1; i >= 0; i--) {
    const n = list[i];
    if (wx >= n.x && wx <= n.x + n.w && wy >= n.y && wy <= n.y + n.h) return n;
  }
  return null;
}
function portAt(wx, wy) {
  const r = 9 / state.cam.zoom;
  for (const n of state.nodes.values()) {
    const p = portOf(n);
    if ((wx - p.x) ** 2 + (wy - p.y) ** 2 <= r * r) return n;
  }
  return null;
}
function edgeAt(wx, wy) {
  const tol = 6 / state.cam.zoom;
  for (const e of state.edges.values()) {
    const a = state.nodes.get(e.from), b = state.nodes.get(e.to);
    if (!a || !b) continue;
    const [p0, p1, p2, p3] = ctrlPts(portOf(a), inletOf(b));
    for (let t = 0; t <= 1; t += 0.04) {
      const pt = bezier(t, p0, p1, p2, p3);
      if ((wx - pt.x) ** 2 + (wy - pt.y) ** 2 <= tol * tol) return e;
    }
  }
  return null;
}

// ---------------------------------------------------------------- rendering
function schedule() { if (!needsRender) { needsRender = true; requestAnimationFrame(draw); } }

function resize() {
  dpr = Math.max(1, window.devicePixelRatio || 1);
  canvas.width = Math.floor(innerWidth * dpr);
  canvas.height = Math.floor(innerHeight * dpr);
  canvas.style.width = innerWidth + 'px';
  canvas.style.height = innerHeight + 'px';
  schedule();
}

function draw() {
  needsRender = false;
  const { zoom, x: px, y: py } = state.cam;

  // backdrop + grid (screen space)
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, innerWidth, innerHeight);
  ctx.fillStyle = '#f6f1e7';
  ctx.fillRect(0, 0, innerWidth, innerHeight);
  drawGrid(zoom, px, py);

  // world space
  ctx.setTransform(zoom * dpr, 0, 0, zoom * dpr, px * dpr, py * dpr);
  for (const e of state.edges.values()) drawEdge(e);
  if (drag && drag.mode === 'connect') drawTempEdge(drag);
  for (const n of state.nodes.values()) drawNode(n);

  // overlays (screen space)
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  if (drag && drag.mode === 'marquee') drawMarquee(drag);

  if (state.editing) positionEditor();
}

function drawGrid(zoom, px, py) {
  const step = GRID * zoom;
  if (step < 16) return;
  const ox = px % step, oy = py % step;
  ctx.fillStyle = 'rgba(35,33,28,0.10)';
  const r = Math.min(1.3, 0.8 + zoom * 0.4);
  for (let x = ox; x < innerWidth; x += step)
    for (let y = oy; y < innerHeight; y += step) {
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
    }
}

function drawEdge(e) {
  const a = state.nodes.get(e.from), b = state.nodes.get(e.to);
  if (!a || !b) return;
  const [p0, p1, p2, p3] = ctrlPts(portOf(a), inletOf(b));
  const selected = state.sel.has(e.id);
  ctx.lineWidth = (selected ? 2.4 : 1.8) / state.cam.zoom;
  ctx.strokeStyle = selected ? '#3b6fe0' : 'rgba(40,38,32,0.62)';
  ctx.beginPath();
  ctx.moveTo(p0.x, p0.y);
  ctx.bezierCurveTo(p1.x, p1.y, p2.x, p2.y, p3.x, p3.y);
  ctx.stroke();
  // arrowhead along the incoming tangent
  const tip = p3, near = bezier(0.94, p0, p1, p2, p3);
  const ang = Math.atan2(tip.y - near.y, tip.x - near.x);
  const s = 9 / state.cam.zoom;
  ctx.fillStyle = ctx.strokeStyle;
  ctx.beginPath();
  ctx.moveTo(tip.x, tip.y);
  ctx.lineTo(tip.x - s * Math.cos(ang - 0.42), tip.y - s * Math.sin(ang - 0.42));
  ctx.lineTo(tip.x - s * Math.cos(ang + 0.42), tip.y - s * Math.sin(ang + 0.42));
  ctx.closePath(); ctx.fill();
}

function drawTempEdge(d) {
  const a = state.nodes.get(d.from);
  const end = d.targetId ? inletOf(state.nodes.get(d.targetId)) : screenToWorld(pointer.x, pointer.y);
  const [p0, p1, p2, p3] = ctrlPts(portOf(a), end);
  ctx.setLineDash([6 / state.cam.zoom, 5 / state.cam.zoom]);
  ctx.lineWidth = 1.8 / state.cam.zoom;
  ctx.strokeStyle = '#3b6fe0';
  ctx.beginPath();
  ctx.moveTo(p0.x, p0.y);
  ctx.bezierCurveTo(p1.x, p1.y, p2.x, p2.y, p3.x, p3.y);
  ctx.stroke();
  ctx.setLineDash([]);
}

function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(x, y, w, h, r);
  else {
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }
}

function drawNode(n) {
  if (state.editing === n.id) return; // overlay editor stands in
  const t = TYPES[n.type] || TYPES.note;
  const selected = state.sel.has(n.id);

  // card + shadow
  ctx.shadowColor = 'rgba(45,38,26,0.16)';
  ctx.shadowBlur = 18; ctx.shadowOffsetY = 7;
  ctx.fillStyle = '#fcfaf4';
  roundRect(n.x, n.y, n.w, n.h, 14); ctx.fill();
  ctx.shadowColor = 'transparent'; ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;

  // border
  ctx.lineWidth = selected ? 2 : 1.4;
  ctx.strokeStyle = selected ? '#3b6fe0' : 'rgba(35,33,28,0.85)';
  roundRect(n.x, n.y, n.w, n.h, 14); ctx.stroke();

  // type chip
  ctx.font = `600 11px ${FONT}`;
  const cw = ctx.measureText(t.label.toUpperCase()).width + 18;
  ctx.fillStyle = t.tint;
  roundRect(n.x + PAD, n.y + PAD, cw, CHIP_H - 4, 9); ctx.fill();
  ctx.fillStyle = t.ink;
  ctx.textBaseline = 'middle';
  ctx.fillText(t.label.toUpperCase(), n.x + PAD + 9, n.y + PAD + (CHIP_H - 4) / 2 + 0.5);

  // title
  ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = '#211f1a';
  ctx.font = `650 15px ${FONT}`;
  let ty = n.y + PAD + CHIP_H + 14;
  for (const line of n._title) { ctx.fillText(line, n.x + PAD, ty); ty += TITLE_LH; }

  // body
  if (n._body.length) {
    ctx.fillStyle = '#5a564e';
    ctx.font = `400 12.5px ${FONT}`;
    ty += 2;
    for (const line of n._body) { ctx.fillText(line, n.x + PAD, ty); ty += BODY_LH; }
  }

  // outgoing port (on hover/selection)
  if (selected || state.hover === n.id) {
    const p = portOf(n);
    ctx.lineWidth = 1.5 / state.cam.zoom;
    ctx.fillStyle = '#fcfaf4';
    ctx.strokeStyle = t.dot;
    ctx.beginPath(); ctx.arc(p.x, p.y, 5 / state.cam.zoom + 1, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();
    ctx.fillStyle = t.dot;
    ctx.beginPath(); ctx.arc(p.x, p.y, 2.4 / state.cam.zoom, 0, Math.PI * 2); ctx.fill();
  }
}

function drawMarquee(d) {
  const x = Math.min(d.x0, pointer.x), y = Math.min(d.y0, pointer.y);
  const w = Math.abs(pointer.x - d.x0), h = Math.abs(pointer.y - d.y0);
  ctx.fillStyle = 'rgba(59,111,224,0.10)';
  ctx.strokeStyle = 'rgba(59,111,224,0.7)';
  ctx.lineWidth = 1;
  ctx.fillRect(x, y, w, h);
  ctx.strokeRect(x + 0.5, y + 0.5, w, h);
}

// ---------------------------------------------------------------- camera ops
function zoomAt(sx, sy, factor) {
  const z = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, state.cam.zoom * factor));
  const w = screenToWorld(sx, sy);
  state.cam.zoom = z;
  state.cam.x = sx - w.x * z;
  state.cam.y = sy - w.y * z;
  updateZoomLabel();
  schedule();
}
function setZoom(z, sx = innerWidth / 2, sy = innerHeight / 2) {
  zoomAt(sx, sy, z / state.cam.zoom);
}
function fitView() {
  const ns = [...state.nodes.values()];
  if (!ns.length) { state.cam = { x: 0, y: 0, zoom: 1 }; updateZoomLabel(); schedule(); return; }
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const n of ns) { minX = Math.min(minX, n.x); minY = Math.min(minY, n.y); maxX = Math.max(maxX, n.x + n.w); maxY = Math.max(maxY, n.y + n.h); }
  const m = 90;
  const zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN,
    Math.min((innerWidth - m * 2) / (maxX - minX), (innerHeight - m * 2) / (maxY - minY), 1.2)));
  state.cam.zoom = zoom;
  state.cam.x = (innerWidth - (maxX + minX) * zoom) / 2;
  state.cam.y = (innerHeight - (maxY + minY) * zoom) / 2;
  updateZoomLabel(); schedule();
}
function updateZoomLabel() { document.getElementById('zoom-level').textContent = Math.round(state.cam.zoom * 100) + '%'; }

// ---------------------------------------------------------------- interaction
function setTool(tool) {
  state.tool = tool;
  document.querySelectorAll('.tool').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.tool === tool)));
  updateCursorClass();
}
function updateCursorClass() {
  canvas.classList.toggle('is-pan', state.tool === 'hand' || state.spaceDown);
  canvas.classList.toggle('is-add', state.tool === 'node');
  canvas.classList.toggle('is-connect', state.tool === 'connect');
}

canvas.addEventListener('pointerdown', (ev) => {
  canvas.setPointerCapture(ev.pointerId);
  pointer = { x: ev.clientX, y: ev.clientY };
  if (state.editing) closeEditor();   // commit & dismiss any open inline editor
  const w = screenToWorld(ev.clientX, ev.clientY);
  const panning = state.spaceDown || state.tool === 'hand' || ev.button === 1;

  if (panning) {
    drag = { mode: 'pan', x0: ev.clientX, y0: ev.clientY, camX: state.cam.x, camY: state.cam.y };
    canvas.classList.add('is-grabbing');
    return;
  }
  if (ev.button !== 0) return;

  if (state.tool === 'node') {
    const n = addNode({ type: 'note', x: w.x - NODE_W / 2, y: w.y - 40 });
    selectOnly(n.id); openEditor(n.id); setTool('select'); save();
    return;
  }

  const portNode = portAt(w.x, w.y);
  if (portNode && (state.tool === 'select' || state.tool === 'connect')) {
    drag = { mode: 'connect', from: portNode.id, targetId: null };
    schedule(); return;
  }

  const hit = nodeAt(w.x, w.y);
  if (state.tool === 'connect') {
    if (hit) drag = { mode: 'connect', from: hit.id, targetId: null };
    return;
  }

  if (hit) {
    if (ev.shiftKey) { state.sel.has(hit.id) ? state.sel.delete(hit.id) : state.sel.add(hit.id); }
    else if (!state.sel.has(hit.id)) selectOnly(hit.id);
    drag = {
      mode: 'move', moved: false,
      start: w,
      origins: new Map([...state.sel].filter(id => state.nodes.has(id)).map(id => {
        const n = state.nodes.get(id); return [id, { x: n.x, y: n.y }];
      })),
    };
    refreshInspector(); schedule(); return;
  }

  const edge = edgeAt(w.x, w.y);
  if (edge) { selectOnly(edge.id); schedule(); return; }

  // empty: marquee select
  if (!ev.shiftKey) { state.sel.clear(); refreshInspector(); }
  drag = { mode: 'marquee', x0: ev.clientX, y0: ev.clientY, base: new Set(state.sel) };
  closeEditor(); schedule();
});

canvas.addEventListener('pointermove', (ev) => {
  pointer = { x: ev.clientX, y: ev.clientY };
  const w = screenToWorld(ev.clientX, ev.clientY);

  if (!drag) {
    const h = nodeAt(w.x, w.y);
    const id = h ? h.id : null;
    if (id !== state.hover) { state.hover = id; schedule(); }
    return;
  }

  if (drag.mode === 'pan') {
    state.cam.x = drag.camX + (ev.clientX - drag.x0);
    state.cam.y = drag.camY + (ev.clientY - drag.y0);
    schedule();
  } else if (drag.mode === 'move') {
    const dx = w.x - drag.start.x, dy = w.y - drag.start.y;
    if (Math.abs(dx) + Math.abs(dy) > 0.5) drag.moved = true;
    for (const [id, o] of drag.origins) { const n = state.nodes.get(id); n.x = o.x + dx; n.y = o.y + dy; }
    schedule();
  } else if (drag.mode === 'connect') {
    const tgt = nodeAt(w.x, w.y);
    drag.targetId = tgt && tgt.id !== drag.from ? tgt.id : null;
    schedule();
  } else if (drag.mode === 'marquee') {
    const x = Math.min(drag.x0, ev.clientX), y = Math.min(drag.y0, ev.clientY);
    const x2 = Math.max(drag.x0, ev.clientX), y2 = Math.max(drag.y0, ev.clientY);
    const a = screenToWorld(x, y), b = screenToWorld(x2, y2);
    state.sel = new Set(drag.base);
    for (const n of state.nodes.values())
      if (n.x + n.w >= a.x && n.x <= b.x && n.y + n.h >= a.y && n.y <= b.y) state.sel.add(n.id);
    refreshInspector(); schedule();
  }
});

canvas.addEventListener('pointerup', (ev) => {
  canvas.classList.remove('is-grabbing');
  if (drag && drag.mode === 'connect' && drag.targetId) { addEdge(drag.from, drag.targetId); save(); }
  if (drag && drag.mode === 'move' && drag.moved) save();
  drag = null;
  schedule();
});

canvas.addEventListener('dblclick', (ev) => {
  const w = screenToWorld(ev.clientX, ev.clientY);
  const hit = nodeAt(w.x, w.y);
  if (hit) { selectOnly(hit.id); openEditor(hit.id); }
  else { const n = addNode({ type: 'note', x: w.x - NODE_W / 2, y: w.y - 40 }); selectOnly(n.id); openEditor(n.id); save(); }
});

canvas.addEventListener('wheel', (ev) => {
  ev.preventDefault();
  if (ev.ctrlKey || ev.metaKey) {
    zoomAt(ev.clientX, ev.clientY, Math.exp(-ev.deltaY * 0.0016));
  } else {
    state.cam.x -= ev.deltaX; state.cam.y -= ev.deltaY; schedule();
  }
  if (state.editing) closeEditor();
}, { passive: false });

addEventListener('keydown', (ev) => {
  if (state.editing) { if (ev.key === 'Escape') closeEditor(); return; }
  const tag = (ev.target && ev.target.tagName) || '';
  if (tag === 'INPUT' || tag === 'TEXTAREA') return;

  if (ev.code === 'Space' && !state.spaceDown) { state.spaceDown = true; updateCursorClass(); }
  else if (ev.key === 'v' || ev.key === 'V') setTool('select');
  else if (ev.key === 'h' || ev.key === 'H') setTool('hand');
  else if (ev.key === 'n' || ev.key === 'N') setTool('node');
  else if (ev.key === 'c' || ev.key === 'C') setTool('connect');
  else if (ev.key === 'Delete' || ev.key === 'Backspace') { if (state.sel.size) { ev.preventDefault(); deleteSelection(); } }
  else if (ev.key === 'Escape') { state.sel.clear(); refreshInspector(); schedule(); }
  else if ((ev.ctrlKey || ev.metaKey) && ev.key === '0') { ev.preventDefault(); setZoom(1); }
  else if ((ev.shiftKey && ev.key === '1') || ((ev.ctrlKey || ev.metaKey) && ev.key === '1')) { ev.preventDefault(); fitView(); }
  else if ((ev.ctrlKey || ev.metaKey) && (ev.key === 'a' || ev.key === 'A')) { ev.preventDefault(); state.sel = new Set(state.nodes.keys()); refreshInspector(); schedule(); }
});
addEventListener('keyup', (ev) => { if (ev.code === 'Space') { state.spaceDown = false; updateCursorClass(); } });

// ---------------------------------------------------------------- selection helpers
function selectOnly(id) { state.sel = new Set([id]); refreshInspector(); }

function refreshInspector() {
  const insp = document.getElementById('inspector');
  const nodeIds = [...state.sel].filter(id => state.nodes.has(id));
  if (nodeIds.length !== 1) { insp.hidden = true; return; }
  const n = state.nodes.get(nodeIds[0]);
  insp.hidden = false;
  const chips = document.getElementById('insp-types');
  chips.innerHTML = '';
  for (const key of TYPE_ORDER) {
    const t = TYPES[key];
    const b = document.createElement('button');
    b.className = 'chip-btn';
    b.textContent = t.label;
    b.setAttribute('aria-pressed', String(n.type === key));
    if (n.type === key) b.style.background = t.dot;
    b.onclick = () => { n.type = key; measure(n); refreshInspector(); schedule(); save(); };
    chips.appendChild(b);
  }
  let inC = 0, outC = 0;
  for (const e of state.edges.values()) { if (e.to === n.id) inC++; if (e.from === n.id) outC++; }
  document.getElementById('insp-conn').textContent = `${inC} in · ${outC} out`;

  // full text of the selected node (cards clip visually; this shows everything)
  const detail = document.getElementById('insp-detail');
  detail.innerHTML = '';
  const dt = document.createElement('span');
  dt.className = 'd-title';
  dt.textContent = n.title || 'Untitled';
  detail.appendChild(dt);
  const db = document.createElement('span');
  if (n.body && n.body.trim()) { db.className = 'd-body'; db.textContent = n.body; }
  else { db.className = 'd-empty'; db.textContent = 'No description.'; }
  detail.appendChild(db);
}

// ---------------------------------------------------------------- inline editor
const editorEl = document.getElementById('editor');
const titleEl = document.getElementById('editor-title');
const bodyEl = document.getElementById('editor-body');

function openEditor(id) {
  const n = state.nodes.get(id); if (!n) return;
  state.editing = id;
  titleEl.value = n.title; bodyEl.value = n.body;
  editorEl.hidden = false;
  positionEditor();
  schedule();
  requestAnimationFrame(() => { titleEl.focus(); titleEl.select(); });
}
function commitEditor() {
  const n = state.nodes.get(state.editing); if (!n) return;
  n.title = titleEl.value; n.body = bodyEl.value; measure(n);
}
function closeEditor() {
  if (!state.editing) return;
  commitEditor();
  state.editing = null;
  editorEl.hidden = true;
  save(); schedule();
}
function positionEditor() {
  const n = state.nodes.get(state.editing); if (!n) return;
  const s = worldToScreen(n.x, n.y);
  const z = state.cam.zoom;
  editorEl.style.left = s.x + 'px';
  editorEl.style.top = s.y + 'px';
  editorEl.style.width = n.w * z + 'px';
  editorEl.style.minHeight = n.h * z + 'px';
  editorEl.style.transform = `scale(1)`;
  titleEl.style.fontSize = 15 * z + 'px';
  bodyEl.style.fontSize = 12.5 * z + 'px';
  editorEl.style.padding = 14 * z + 'px ' + 15 * z + 'px';
  editorEl.style.borderRadius = 14 * z + 'px';
  bodyEl.style.minHeight = 3 * BODY_LH * z + 'px';
}
titleEl.addEventListener('input', () => { commitEditor(); schedule(); });
bodyEl.addEventListener('input', () => { commitEditor(); positionEditor(); schedule(); });
titleEl.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); bodyEl.focus(); } if (e.key === 'Escape') closeEditor(); });
editorEl.addEventListener('focusout', () => { setTimeout(() => { if (!editorEl.contains(document.activeElement)) closeEditor(); }, 0); });

// ---------------------------------------------------------------- persistence
let saveT = null;
function save() {
  clearTimeout(saveT);
  saveT = setTimeout(() => {
    const data = {
      nodes: [...state.nodes.values()].map(({ id, type, title, body, x, y }) => ({ id, type, title, body, x, y })),
      edges: [...state.edges.values()],
      cam: state.cam,
    };
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)); } catch {}
    refreshEmpty();
  }, 250);
}
function restore() {
  let raw; try { raw = localStorage.getItem(STORAGE_KEY); } catch {}
  if (!raw) return false;
  try {
    const data = JSON.parse(raw);
    for (const n of data.nodes) addNode(n);
    for (const e of data.edges) { const x = addEdge(e.from, e.to); if (x && e.id) { state.edges.delete(x.id); x.id = e.id; state.edges.set(x.id, x); } }
    if (data.cam) { state.cam = data.cam; updateZoomLabel(); }
    return state.nodes.size > 0;
  } catch { return false; }
}
function refreshEmpty() { document.getElementById('empty').hidden = state.nodes.size > 0; }

// ---------------------------------------------------------------- toolbar wiring
document.querySelectorAll('.tool').forEach(b => b.addEventListener('click', () => setTool(b.dataset.tool)));
document.getElementById('zoom-in').onclick = () => zoomAt(innerWidth / 2, innerHeight / 2, 1.2);
document.getElementById('zoom-out').onclick = () => zoomAt(innerWidth / 2, innerHeight / 2, 1 / 1.2);
document.getElementById('zoom-level').onclick = () => setZoom(1);
document.getElementById('zoom-fit').onclick = fitView;
document.getElementById('insp-delete').onclick = deleteSelection;
document.getElementById('act-demo').onclick = () => loadBoard(structuredClone(DEMO_BOARD));
document.getElementById('empty-demo').onclick = () => loadBoard(structuredClone(DEMO_BOARD));
document.getElementById('act-clear').onclick = () => {
  if (state.nodes.size && !confirm('Clear the board? This cannot be undone.')) return;
  state.nodes.clear(); state.edges.clear(); state.sel.clear(); closeEditor();
  save(); refreshInspector(); refreshEmpty(); schedule();
};
document.getElementById('act-export').onclick = () => {
  const data = { nodes: [...state.nodes.values()].map(({ id, type, title, body, x, y }) => ({ id, type, title, body, x, y })), edges: [...state.edges.values()] };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'aetherfall-storyboard.json';
  a.click();
  URL.revokeObjectURL(a.href);
};
document.getElementById('act-load').onclick = async () => {
  const base = prompt('Backend base URL', lastApi.base);
  if (!base) return;
  const world = prompt('World id', lastApi.worldId);
  if (!world) return;
  lastApi.base = base.trim(); lastApi.worldId = world.trim(); saveApi();
  try {
    const board = await loadStoryFromApi(lastApi.base, lastApi.worldId);
    loadBoard(board);
  } catch (err) { alert('Could not load story: ' + err.message); }
};

// ---------------------------------------------------------------- world bible panel
const bibleEl = document.getElementById('bible');
const bibleBase = document.getElementById('bible-base');
const bibleWorld = document.getElementById('bible-world');
const bibleStatus = document.getElementById('bible-status');
const LAYER_KEYS = ['sky', 'surface', 'underground', 'deep', 'ocean'];
const bField = (f) => bibleEl.querySelector(`[data-f="${f}"]`);
const bLayer = (k) => bibleEl.querySelector(`[data-l="${k}"]`);

function bibleUrl() {
  const base = (bibleBase.value || API_DEFAULT).trim().replace(/\/$/, '');
  return `${base}/api/ai/world/${encodeURIComponent(bibleWorld.value.trim())}/bible`;
}
function syncApiFromBible() {
  lastApi.base = (bibleBase.value || API_DEFAULT).trim();
  lastApi.worldId = bibleWorld.value.trim();
  saveApi();
}
function fillBible(b) {
  for (const f of ['premise', 'aether_system', 'the_fall', 'history', 'peoples', 'factions_overview', 'tone'])
    bField(f).value = b[f] || '';
  bField('themes').value = (b.themes || []).join(', ');
  const L = b.layers || {};
  for (const k of LAYER_KEYS) bLayer(k).value = L[k] || '';
  bibleStatus.textContent = b.source ? `loaded · source: ${b.source} · ${b.status || 'draft'}` : '';
}
function readBible() {
  const layers = {};
  for (const k of LAYER_KEYS) { const v = bLayer(k).value.trim(); if (v) layers[k] = v; }
  return {
    world_id: bibleWorld.value.trim(),
    premise: bField('premise').value, aether_system: bField('aether_system').value,
    the_fall: bField('the_fall').value, history: bField('history').value, layers,
    peoples: bField('peoples').value, factions_overview: bField('factions_overview').value,
    themes: bField('themes').value.split(',').map(s => s.trim()).filter(Boolean),
    tone: bField('tone').value,
  };
}
function bibleBusy(on) { bibleEl.querySelector('.bible-card').classList.toggle('bible-busy', on); }

async function bibleFetch() {
  if (!bibleWorld.value.trim()) { bibleStatus.textContent = 'Enter a world id first.'; return; }
  syncApiFromBible(); bibleBusy(true); bibleStatus.textContent = 'Fetching…';
  try {
    const res = await fetch(bibleUrl());
    if (res.status === 404) { bibleStatus.textContent = 'No bible saved yet — click ✦ AI Generate.'; return; }
    if (!res.ok) throw new Error(`API ${res.status}`);
    fillBible(await res.json());
  } catch (err) { bibleStatus.textContent = 'Fetch failed: ' + err.message; }
  finally { bibleBusy(false); }
}
async function bibleGenerate() {
  if (!bibleWorld.value.trim()) { bibleStatus.textContent = 'Enter a world id first.'; return; }
  syncApiFromBible(); bibleBusy(true); bibleStatus.textContent = 'AI is drafting the bible… (can take a minute)';
  try {
    const res = await fetch(bibleUrl() + '/generate', { method: 'POST' });
    if (!res.ok) throw new Error(`API ${res.status}`);
    fillBible(await res.json());
    bibleStatus.textContent = 'AI draft ready — review, edit, then Save.';
  } catch (err) { bibleStatus.textContent = 'Generate failed: ' + err.message; }
  finally { bibleBusy(false); }
}
async function bibleSave() {
  if (!bibleWorld.value.trim()) { bibleStatus.textContent = 'Enter a world id first.'; return; }
  syncApiFromBible(); bibleBusy(true); bibleStatus.textContent = 'Saving…';
  try {
    const res = await fetch(bibleUrl(), {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(readBible()),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    fillBible(await res.json());
    bibleStatus.textContent = 'Saved as canon (source: human).';
  } catch (err) { bibleStatus.textContent = 'Save failed: ' + err.message; }
  finally { bibleBusy(false); }
}
function openBible() {
  bibleEl.hidden = false;
  if (!bibleBase.value) bibleBase.value = lastApi.base;
  if (!bibleWorld.value && lastApi.worldId) bibleWorld.value = lastApi.worldId;
  bibleStatus.textContent = '';
  if (bibleWorld.value.trim()) bibleFetch();
}
function closeBible() { bibleEl.hidden = true; }

document.getElementById('act-bible').onclick = openBible;
document.getElementById('bible-close').onclick = closeBible;
document.getElementById('bible-fetch').onclick = bibleFetch;
document.getElementById('bible-generate').onclick = bibleGenerate;
document.getElementById('bible-save').onclick = bibleSave;
bibleEl.addEventListener('pointerdown', (e) => { if (e.target === bibleEl) closeBible(); });
addEventListener('keydown', (e) => { if (e.key === 'Escape' && !bibleEl.hidden) closeBible(); });

// ---------------------------------------------------------------- boot
addEventListener('resize', resize);
resize();
setTool('select');
if (!restore()) loadBoard(structuredClone(DEMO_BOARD));
else { refreshEmpty(); schedule(); }
updateZoomLabel();
