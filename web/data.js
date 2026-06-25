// Demo storyboard + mapping from the Stage-1 backend story API onto board nodes.
// Node:  { id, type:'arc'|'beat'|'scene'|'note', title, body, x, y }
// Edge:  { id, from, to }

const NODE_W = 248;

// On-brand Aetherfall sample: one arc -> two beats -> four scenes.
export const DEMO_BOARD = {
  nodes: [
    { id: 'arc_1', type: 'arc', x: 470, y: 60,
      title: 'The Mutated Lake',
      body: 'Wild magic is leaking into Moonlake. Theme: decay. As the water turns, the village must choose what to save.' },

    { id: 'beat_1', type: 'beat', x: 196, y: 360,
      title: 'Act I · Dead Fish at Dawn',
      body: 'A farmer finds the shallows littered with dead fish. Something upstream is wrong.' },
    { id: 'beat_2', type: 'beat', x: 744, y: 360,
      title: 'Act II · The Drowned Shrine',
      body: 'The trail leads to a flooded shrine where an old seal is failing.' },

    { id: 'scene_1', type: 'scene', x: 70, y: 648,
      title: 'Riverbank Discovery',
      body: 'Quiet, eerie. The player inspects the catch and the discoloured water.' },
    { id: 'scene_2', type: 'scene', x: 330, y: 648,
      title: 'Word Reaches the Elder',
      body: 'The elder recalls a pact made before the founding of Moonlake.' },
    { id: 'scene_3', type: 'scene', x: 618, y: 648,
      title: 'Into the Reeds',
      body: 'Tense wade through the marsh; the magic grows thicker underfoot.' },
    { id: 'scene_4', type: 'scene', x: 878, y: 648,
      title: 'The Leaking Seal',
      body: 'Climax. The seal is cracked — repair it, redirect it, or let it break.' },
  ],
  edges: [
    { id: 'e1', from: 'arc_1', to: 'beat_1' },
    { id: 'e2', from: 'arc_1', to: 'beat_2' },
    { id: 'e3', from: 'beat_1', to: 'scene_1' },
    { id: 'e4', from: 'beat_1', to: 'scene_2' },
    { id: 'e5', from: 'beat_2', to: 'scene_3' },
    { id: 'e6', from: 'beat_2', to: 'scene_4' },
  ],
};

function clip(text, n) {
  if (!text) return '';
  text = String(text).replace(/\s+/g, ' ').trim();
  return text.length > n ? text.slice(0, n - 1).trimEnd() + '…' : text;
}

// Convert backend { arcs, beats, scenes } into a laid-out board (tidy tree).
export function storyToBoard(story) {
  const arcs = story.arcs || [];
  const beats = story.beats || [];
  const scenes = story.scenes || [];
  const nodes = [];
  const edges = [];

  const beatsByArc = new Map();
  for (const b of beats) {
    if (!beatsByArc.has(b.arc_id)) beatsByArc.set(b.arc_id, []);
    beatsByArc.get(b.arc_id).push(b);
  }
  const scenesByBeat = new Map();
  for (const s of scenes) {
    if (!scenesByBeat.has(s.beat_id)) scenesByBeat.set(s.beat_id, []);
    scenesByBeat.get(s.beat_id).push(s);
  }

  const GAP_X = 40, COL = NODE_W + GAP_X;
  const Y = { arc: 60, beat: 360, scene: 660 };
  let cursor = 0; // running x in "columns" of leaf scenes

  for (const arc of arcs) {
    const arcBeats = beatsByArc.get(arc.id) || [];
    const arcStart = cursor;

    for (const beat of arcBeats) {
      const beatScenes = scenesByBeat.get(beat.id) || [];
      const beatStart = cursor;

      for (const sc of beatScenes) {
        nodes.push({
          id: sc.id, type: 'scene', x: cursor * COL, y: Y.scene,
          title: clip(sc.title, 60) || 'Scene',
          body: clip(sc.prose, 4000),   // full prose — card clips visually, inspector shows all
        });
        edges.push({ id: `e_${beat.id}_${sc.id}`, from: beat.id, to: sc.id });
        cursor += 1;
      }
      if (beatScenes.length === 0) cursor += 1; // reserve a column

      const beatX = beatScenes.length
        ? ((beatStart + cursor - 1) / 2) * COL
        : beatStart * COL;
      nodes.push({
        id: beat.id, type: 'beat', x: beatX, y: Y.beat,
        title: clip(`Act ${beat.act ?? ''} · ${beat.summary || 'Beat'}`.replace('· ', beat.act ? '· ' : ''), 64),
        body: clip(beat.summary, 2000),
      });
      edges.push({ id: `e_${arc.id}_${beat.id}`, from: arc.id, to: beat.id });
    }
    if (arcBeats.length === 0) cursor += 1;

    const arcX = ((arcStart + Math.max(cursor, arcStart + 1) - 1) / 2) * COL;
    nodes.push({
      id: arc.id, type: 'arc', x: arcX, y: Y.arc,
      title: clip(arc.title, 60) || 'Story Arc',
      body: clip(arc.premise, 2000),
    });
    cursor += 1; // breathing room between arcs
  }

  return { nodes, edges };
}

// Fetch a generated story from the running backend and lay it out.
export async function loadStoryFromApi(baseUrl, worldId) {
  const url = `${baseUrl.replace(/\/$/, '')}/api/ai/story/${encodeURIComponent(worldId)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API ${res.status} ${res.statusText}`);
  const story = await res.json();
  const board = storyToBoard(story);
  if (board.nodes.length === 0) throw new Error('No story found for that world id.');
  return board;
}
