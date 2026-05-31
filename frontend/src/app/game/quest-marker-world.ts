// QuestMarkerWorld — pulsierende Quest-Marker über Ziel-NPCs (H3.5).
//
// Zeigt einen goldenen Stern/Pfeil über jedem NPC, der das Ziel einer aktiven
// Quest des Spielers ist. Im Frontend-Quest-Model gibt es kein
// `target_x`/`target_y`; wir matchen über `target_npc_id` (Deliver/Turn-In)
// bzw. `giver_npc_id` (Quest-Geber für Turn-In sichtbar machen). Falls
// Backend später dem Quest-Frame ein direktes Tile-Target hinzufügt, lesen
// wir es defensiv mit (siehe `tilesFromQuests`).
//
// Range-Check: nur wenn der Ziel-NPC im aktuellen `npcsVisible()`-Snapshot
// vorhanden ist. Off-screen-Marker werden nicht gerendert.
//
// Render:
//   • Pro Quest-Ziel ein gold-gelbes "!"-Sprite (Phaser-Text + Glow-BG).
//   • Bobbing-Animation per `sin(elapsed)` — vertikales Bouncen + leichtes
//     Pulse-Scaling für den Halo-Hintergrund.
//   • Depth über NPCs und Player (höchste Spiel-Welt-Tiefe).
//
// Lifecycle:
//   • `update(quests, npcs)` pro Frame — Marker werden inkrementell synced:
//     neue Quest-Targets → spawn, weggefallene → destroy.
//   • `destroyAll()` beim Scene-Shutdown.

import Phaser from 'phaser';

import type { NPC } from '../core/models/npc.model';
import type { Quest } from '../core/models/quest.model';
import { TILE_SIZE } from '../core/data/tiles';

/** Render-Depth: über allem in der Spiel-Welt, unter UI-Combat-FX. */
const DEPTH_MARKER = 55;
/** Bob-Amplitude (px). */
const BOB_AMPLITUDE = 5;
/** Bob-Geschwindigkeit (rad/ms). */
const BOB_SPEED = 0.004;
/** Pulse-Skala der Glow-Aura (min..max). */
const PULSE_MIN = 0.85;
const PULSE_MAX = 1.15;
/** Vertikaler Offset vom NPC-Center (negativ = nach oben). */
const MARKER_OFFSET_Y = -TILE_SIZE / 2 - 18;

/** Quest-Target-Eintrag (vom Caller berechnet). */
interface QuestTarget {
  /** Eindeutiger Marker-Key — kombiniert Quest-ID + NPC-ID, damit ein NPC
   *  mit mehreren Quests mehrere Marker bekommt (selten, aber denkbar). */
  readonly key: string;
  /** Ziel-NPC-Position (Tile). */
  readonly x: number;
  readonly y: number;
  /** Marker-Typ — beeinflusst Farbe/Symbol:
   *   • 'turnin'  — gold-gelb mit "?" (Quest abgeben / abholen)
   *   • 'kill'    — orange-rot mit "!" (Quest-Mob)
   *   • 'collect' — grün mit "!" (zukünftig, derzeit ungenutzt) */
  readonly kind: 'turnin' | 'kill' | 'collect';
}

interface MarkerState {
  /** Container hält Text + Glow zusammen. */
  readonly container: Phaser.GameObjects.Container;
  readonly glow: Phaser.GameObjects.Arc;
  readonly text: Phaser.GameObjects.Text;
  /** Letzte gerenderte Pos (Diff-Check). */
  lastX: number;
  lastY: number;
}

/** Visual-Konfiguration pro Marker-Kind. */
const VISUALS: Readonly<Record<QuestTarget['kind'], {
  readonly symbol: string;
  readonly color: string;
  readonly glow: number;
}>> = {
  turnin:  { symbol: '?', color: '#ffe060', glow: 0xffd040 },
  kill:    { symbol: '!', color: '#ff7733', glow: 0xff5522 },
  collect: { symbol: '!', color: '#77ff77', glow: 0x44dd44 },
};

export class QuestMarkerWorld {
  private readonly scene: Phaser.Scene;
  private readonly markers = new Map<string, MarkerState>();

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
  }

  /**
   * Pro Frame: aus Quests + npcsVisible die aktuellen Targets bauen,
   * Marker-Pool inkrementell synchronisieren + animieren.
   */
  update(quests: readonly Quest[], npcs: readonly NPC[], elapsedMs: number): void {
    const targets = tilesFromQuests(quests, npcs);

    // Diff: neue Marker spawnen, alte entfernen.
    const seenKeys = new Set<string>();
    for (const t of targets) {
      seenKeys.add(t.key);
      let m = this.markers.get(t.key);
      if (!m) {
        m = this.spawnMarker(t);
        this.markers.set(t.key, m);
      } else if (m.lastX !== t.x || m.lastY !== t.y) {
        // NPC bewegt → Marker mitnehmen.
        m.lastX = t.x;
        m.lastY = t.y;
      }
    }
    for (const [key, m] of this.markers) {
      if (!seenKeys.has(key)) {
        m.container.destroy(true);
        this.markers.delete(key);
      }
    }

    // Animation: Bob (vertikales Sinus) + Pulse (Glow-Scale).
    const bobOffset = Math.sin(elapsedMs * BOB_SPEED) * BOB_AMPLITUDE;
    const pulseScale =
      PULSE_MIN + (PULSE_MAX - PULSE_MIN) * (0.5 + 0.5 * Math.sin(elapsedMs * BOB_SPEED * 1.4));
    for (const m of this.markers.values()) {
      const cx = m.lastX * TILE_SIZE + TILE_SIZE / 2;
      const cy = m.lastY * TILE_SIZE + TILE_SIZE / 2 + MARKER_OFFSET_Y + bobOffset;
      m.container.setPosition(cx, cy);
      m.glow.setScale(pulseScale);
    }
  }

  /** Alle Marker abräumen (Scene-Shutdown). */
  destroyAll(): void {
    for (const m of this.markers.values()) {
      m.container.destroy(true);
    }
    this.markers.clear();
  }

  // ─── Internals ──────────────────────────────────────────────────────

  private spawnMarker(t: QuestTarget): MarkerState {
    const vis = VISUALS[t.kind];
    const container = this.scene.add.container(0, 0);
    container.setDepth(DEPTH_MARKER);

    // Glow-Halo hinter dem Symbol.
    const glow = this.scene.add.circle(0, 0, 10, vis.glow, 0.35);
    glow.setStrokeStyle(2, vis.glow, 0.8);

    // Symbol-Text (kein Sprite-Asset nötig — Glyph reicht).
    const text = this.scene.add.text(0, 0, vis.symbol, {
      fontFamily: 'Arial, sans-serif',
      fontSize: '18px',
      fontStyle: 'bold',
      color: vis.color,
      stroke: '#000000',
      strokeThickness: 3,
    });
    text.setOrigin(0.5, 0.5);

    container.add([glow, text]);
    return {
      container,
      glow,
      text,
      lastX: t.x,
      lastY: t.y,
    };
  }
}

/**
 * Aus der aktuellen Quest-Liste + den sichtbaren NPCs eine Liste von
 * Tile-Targets bauen. Nur Quests im State `active` werden berücksichtigt.
 * Wir prüfen drei Felder:
 *   1. `target_npc_id` — explizites Ziel (Deliver/Turn-In).
 *   2. `giver_npc_id` bei `state === 'completed'` — Spieler soll zurück
 *      zum Geber für Reward-Claim.
 *   3. Defensives `target_x`/`target_y` aus dem rohen Objekt — falls
 *      Backend die Felder später ergänzt, werden sie automatisch genutzt.
 *      Tile-Targets ohne zugeordneten NPC werden NICHT vom Sichtfilter
 *      ausgeschlossen (sie sind direkt eine Tile-Position).
 */
function tilesFromQuests(
  quests: readonly Quest[],
  npcs: readonly NPC[],
): readonly QuestTarget[] {
  if (quests.length === 0) return [];

  // NPC-Lookup für O(1)-Pos-Bestimmung.
  const npcById = new Map<number, NPC>();
  for (const n of npcs) npcById.set(n.id, n);

  const out: QuestTarget[] = [];
  for (const q of quests) {
    if (q.state !== 'active' && q.state !== 'completed') continue;

    // (1) Turn-In-Marker: completed → giver (Reward-Claim), active mit
    //     target_npc_id → Deliver-Target.
    if (q.state === 'completed' && q.giver_npc_id != null) {
      const npc = npcById.get(q.giver_npc_id);
      if (npc) {
        out.push({
          key: `q${q.quest_id}-turnin-${q.giver_npc_id}`,
          x: npc.x,
          y: npc.y,
          kind: 'turnin',
        });
      }
      continue;
    }

    if (q.target_npc_id != null) {
      const npc = npcById.get(q.target_npc_id);
      if (npc) {
        // Wenn alle Objectives erfüllt aber state immer noch active → turnin.
        const allDone = q.objectives.every((o) => o.done);
        out.push({
          key: `q${q.quest_id}-target-${q.target_npc_id}`,
          x: npc.x,
          y: npc.y,
          kind: allDone ? 'turnin' : 'kill',
        });
      }
    }

    // (2) Defensiv: direkter Tile-Target im Quest-Objekt? Backend könnte
    //     `target_x`/`target_y` zukünftig ergänzen — wir lesen sie ohne
    //     `any`-Cast über Index-Access mit Type-Guard.
    const qRaw = q as unknown as { readonly target_x?: unknown; readonly target_y?: unknown };
    const tx = qRaw.target_x;
    const ty = qRaw.target_y;
    if (typeof tx === 'number' && typeof ty === 'number') {
      out.push({
        key: `q${q.quest_id}-tile-${tx}-${ty}`,
        x: tx,
        y: ty,
        kind: 'kill',
      });
    }
  }
  return out;
}
