# Aetherfall · Story Board (web)

A self-contained, infinite-canvas storyboard editor for the Stage-1 story system.
No build step — plain HTML5 canvas + ES modules.

## Run

Open over HTTP (ES module imports won't run from `file://`):

```bash
cd web
python -m http.server 8137
# then visit http://127.0.0.1:8137/
```

## Layout

| File | Role |
|---|---|
| `index.html` | Markup, toolbar/panels, canvas element |
| `styles.css` | Warm-paper theme, floating glass chrome |
| `app.js`     | Canvas engine: pan/zoom, nodes, edges, inline editing, persistence |
| `data.js`    | Aetherfall demo board + `arcs→beats→scenes` mapping from the backend API |

## Controls

- **Pan** — hold `Space` (or middle-mouse) and drag, or pick the hand tool (`H`). Trackpad two-finger scroll also pans.
- **Zoom** — `Ctrl`/`⌘` + scroll (or pinch), the `+ / − / Fit` controls, or `Ctrl/⌘ 0` (100%) and `Shift 1` (fit).
- **Select / move** — select tool (`V`); drag a node, or rubber-band an area. `Shift`-click to multi-select.
- **Add node** — node tool (`N`) or double-click empty canvas.
- **Edit** — double-click a node for the inline title/description editor; change a node's type in the inspector.
- **Connect** — drag the dot below a node onto another node, or use the connect tool (`C`).
- **Delete** — select and press `Delete`/`Backspace`.

The board auto-saves to `localStorage`. **Export** downloads JSON; **Demo** reloads the sample;
**Load from API…** pulls a generated story from the backend (`GET /api/ai/story/{world_id}`).
