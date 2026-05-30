// MinimapComponent — DOM-Canvas, kein Phaser.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM:     `index.html` Z. 231 (`<canvas id="minimap" ...>`).
//   • Renderer: `app.js` `drawMinimap` (Z. 9288-9460).
//   • Styles:   `style.css` Z. 10647ff.
//
// Architektur: Wir nehmen den minimal-funktionalen Kern aus dem Legacy
// (Tile-Layer + Player-Punkt + NPCs + andere Spieler + Strukturen + Dungeons).
// Quest-Markierungen, Event-Marker mit Pulse, Sense-Radius-Logik etc. sind
// reine Visualizations-Erweiterungen — kein State-Ziel der Migration, weil
// das Backend keinen einheitlichen „Quest-Marker"-Snapshot liefert (im
// Legacy wurde das aus mehreren Quellen rekonstruiert). Diese Polish-
// Schichten können in F-final draufgesattelt werden, sobald wir die Quest-
// Marker-State zentral haben.
//
// Re-Draw-Strategie: Wir hängen einen `effect()` auf die fünf relevanten
// Signals (chunks, structures, dungeons, npcsVisible, players + player für
// Kamera-Mitte). Jede Änderung triggert einen Re-Draw — bei 60fps-fließender
// Bewegung ist das angemessen, weil player_moved-Frames vom Backend ~10/s
// kommen, nicht pro Frame.

import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
  ViewChild,
  effect,
  inject,
} from '@angular/core';

import { TILE_BY_ID } from '../../core/data/tiles';
import type { Chunk, DungeonMarker, Structure } from '../../core/models/chunk.model';
import type { NPC } from '../../core/models/npc.model';
import type { OnlinePlayer } from '../../core/models/player.model';
import { GameStateService } from '../../core/services/game-state.service';

const VIEW_W = 64;
const VIEW_H = 44;

/** Pulse-Periode für Quest-Marker (ms). 2026-05-31 — H1.7. */
const PULSE_PERIOD_MS = 1200;

@Component({
  selector: 'app-minimap',
  standalone: true,
  templateUrl: './minimap.component.html',
  styleUrl: './minimap.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MinimapComponent implements AfterViewInit, OnDestroy {
  private readonly state = inject(GameStateService);

  @ViewChild('minimap', { static: true })
  private canvasRef!: ElementRef<HTMLCanvasElement>;

  private ctx: CanvasRenderingContext2D | null = null;
  private chunkLookup = new Map<string, Chunk>();
  /** Chunks-Identity-Ref — pflegen das Lookup nur, wenn sich die Liste ändert. */
  private lastChunksRef: readonly Chunk[] | null = null;
  private destroyed = false;
  /** RAF-Handle für den Pulse-Loop — null wenn keine aktiven Quest-Marker da
   *  sind (spart CPU, wenn niemand eine Quest hat). */
  private pulseRaf: number | null = null;

  constructor() {
    // Bei Signal-Updates neu zeichnen. Phaser-FPS-Schutz: wir hängen NICHT
    // im Phaser-Tick, sondern reagieren reaktiv. Die involvierten Signals
    // sind alle „grob" (Patches pro Backend-Event).
    effect(() => {
      // Subscribe — wir tracken alle Signals, die das Bild beeinflussen.
      this.state.chunks();
      this.state.structures();
      this.state.dungeons();
      this.state.npcsVisible();
      this.state.players();
      this.state.player();
      this.state.quests();
      this._scheduleDraw();
      this._ensurePulseLoop();
    });
  }

  ngAfterViewInit(): void {
    this.ctx = this.canvasRef.nativeElement.getContext('2d');
    this._draw();
    this._ensurePulseLoop();
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    if (this.pulseRaf !== null) {
      cancelAnimationFrame(this.pulseRaf);
      this.pulseRaf = null;
    }
  }

  /** Startet den Pulse-Loop nur wenn aktive Quest-Marker vorhanden sind.
   *  Reduziert CPU-Last bei leerer Quest-Liste auf signal-driven Draws. */
  private _ensurePulseLoop(): void {
    if (this.destroyed) return;
    const hasMarkers = this._questMarkers().length > 0;
    if (hasMarkers && this.pulseRaf === null) {
      const tick = (): void => {
        if (this.destroyed) return;
        this._draw();
        if (this._questMarkers().length > 0) {
          this.pulseRaf = requestAnimationFrame(tick);
        } else {
          this.pulseRaf = null;
        }
      };
      this.pulseRaf = requestAnimationFrame(tick);
    }
  }

  /** Ermittelt aktive Quest-Marker:
   *   • Turn-In-Marker (gelber Stern) für Completed-Quests mit giver_npc_id
   *     oder target_npc_id, deren NPC sichtbar ist.
   *   • Kill-Highlight-Set (Set von creature_kinds) für aktive Kill-Quests
   *     mit unerfüllter Objective. */
  private _questMarkers(): readonly { x: number; y: number; kind: 'turnin' }[] {
    const quests = this.state.quests();
    if (quests.length === 0) return [];
    const npcs = this.state.npcsVisible();
    const out: { x: number; y: number; kind: 'turnin' }[] = [];
    for (const q of quests) {
      if (q.state !== 'completed' && q.state !== 'active') continue;
      // Turn-In oder Deliver: NPC-Ziel auf Karte hervorheben.
      const targetId = q.state === 'completed'
        ? (q.giver_npc_id ?? q.target_npc_id)
        : (q.target_npc_id);
      if (targetId == null) continue;
      const npc = npcs.find((n) => n.id === targetId);
      if (!npc) continue;
      out.push({ x: npc.x, y: npc.y, kind: 'turnin' });
    }
    return out;
  }

  /** Set von creature_kinds, die für aktive Kill-Quests highlighted werden. */
  private _killTargetKinds(): ReadonlySet<string> {
    const quests = this.state.quests();
    const set = new Set<string>();
    for (const q of quests) {
      if (q.state !== 'active') continue;
      for (const o of q.objectives) {
        if (o.done) continue;
        // Backend-Objective-Slug: für Kill-Quests heißt das Target-Feld
        // `creature_kind`, das landet im frontend Quest-Objective als `target`.
        // (siehe quests.py::create_from_template: objective.creature_kind,
        //  und ws/quests.py serialisiert es als objectives[{kind, target}]).
        if (o.target) set.add(o.target);
      }
    }
    return set;
  }

  private _scheduleDraw(): void {
    if (this.destroyed || !this.ctx) return;
    // `effect`s laufen außerhalb von rAF — wir verzögern den Draw auf einen
    // Animation-Frame, damit gehäufte Signal-Updates in derselben Tick einen
    // einzigen Draw triggern.
    requestAnimationFrame(() => this._draw());
  }

  private _rebuildChunkLookup(chunks: readonly Chunk[]): void {
    if (chunks === this.lastChunksRef) return;
    this.lastChunksRef = chunks;
    this.chunkLookup.clear();
    for (const c of chunks) this.chunkLookup.set(`${c.cx},${c.cy}`, c);
  }

  private _tileAt(wx: number, wy: number, chunkSize: number): number | null {
    if (chunkSize <= 0) return null;
    const cx = Math.floor(wx / chunkSize);
    const cy = Math.floor(wy / chunkSize);
    const ch = this.chunkLookup.get(`${cx},${cy}`);
    if (!ch) return null;
    const lx = wx - cx * chunkSize;
    const ly = wy - cy * chunkSize;
    const row = ch.tiles[ly];
    if (!row) return null;
    const v = row[lx];
    return typeof v === 'number' ? v : null;
  }

  private _draw(): void {
    if (this.destroyed || !this.ctx) return;
    const ctx = this.ctx;
    const canvas = this.canvasRef.nativeElement;
    const me = this.state.player();
    ctx.fillStyle = '#0a0a0f';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    if (!me) return;

    const chunks = this.state.chunks();
    this._rebuildChunkLookup(chunks);
    const chunkSize = this.state.chunkSize();

    const scaleX = canvas.width / VIEW_W;
    const scaleY = canvas.height / VIEW_H;
    const ox = me.x - VIEW_W / 2;
    const oy = me.y - VIEW_H / 2;

    // Tile-Layer
    for (let dy = 0; dy < VIEW_H; dy++) {
      for (let dx = 0; dx < VIEW_W; dx++) {
        const wx = Math.floor(ox + dx);
        const wy = Math.floor(oy + dy);
        const t = this._tileAt(wx, wy, chunkSize);
        if (t === null) continue;
        const cfg = TILE_BY_ID[t];
        if (!cfg) continue;
        ctx.fillStyle = cfg.miniColor;
        ctx.fillRect(
          Math.floor(dx * scaleX),
          Math.floor(dy * scaleY),
          Math.ceil(scaleX),
          Math.ceil(scaleY),
        );
      }
    }

    // Strukturen — kleine bräunliche Punkte
    const dotSize = Math.max(2, Math.floor(Math.min(scaleX, scaleY)));
    ctx.fillStyle = '#886644';
    for (const s of this.state.structures() as readonly Structure[]) {
      const px = (s.x - ox) * scaleX;
      const py = (s.y - oy) * scaleY;
      if (px < 0 || py < 0 || px >= canvas.width || py >= canvas.height) continue;
      ctx.fillRect(Math.floor(px), Math.floor(py), Math.max(1, dotSize - 1), Math.max(1, dotSize - 1));
    }

    // NPCs — Creature = rot, sonst gelb (Legacy-Heuristik vereinfacht ohne
    // CREATURE_KINDS-Set: wir nutzen `hostile`-Flag, das die NPC-Modelle
    // bereits führen). H1.7: Kill-Quest-Targets bekommen eine helle Aura.
    const killKinds = this._killTargetKinds();
    for (const n of this.state.npcsVisible() as readonly NPC[]) {
      const px = (n.x - ox) * scaleX;
      const py = (n.y - oy) * scaleY;
      if (px < 0 || py < 0 || px >= canvas.width || py >= canvas.height) continue;
      if (killKinds.has(n.kind)) {
        // Quest-Target-Highlight: cyan-grünlicher Punkt (deutlich von hostile/
        // friendly unterscheidbar). Größer als normal.
        ctx.fillStyle = '#80ffe0';
        ctx.fillRect(Math.floor(px) - 2, Math.floor(py) - 2, dotSize + 2, dotSize + 2);
      } else {
        ctx.fillStyle = n.hostile ? '#e84040' : '#ffe070';
        ctx.fillRect(Math.floor(px) - 1, Math.floor(py) - 1, dotSize, dotSize);
      }
    }

    // Andere Spieler
    const players = this.state.players() as Readonly<Record<string, OnlinePlayer>>;
    for (const p of Object.values(players)) {
      if (p.player_id === me.player_id) continue;
      const px = (p.x - ox) * scaleX;
      const py = (p.y - oy) * scaleY;
      if (px < 0 || py < 0 || px >= canvas.width || py >= canvas.height) continue;
      ctx.fillStyle = '#a0c8ff';
      ctx.fillRect(Math.floor(px) - 1, Math.floor(py) - 1, dotSize, dotSize);
    }

    // Dungeons (Sense-Radius nicht modelliert — wir zeigen alle bekannten
    // Marker direkt; Legacy verbarg sie außerhalb 70-Tile Cheby — minor
    // polish, gehört nach F-final).
    ctx.fillStyle = '#c060ff';
    for (const d of this.state.dungeons() as readonly DungeonMarker[]) {
      const px = (d.x - ox) * scaleX;
      const py = (d.y - oy) * scaleY;
      if (px < 0 || py < 0 || px >= canvas.width || py >= canvas.height) continue;
      ctx.fillRect(Math.floor(px) - 2, Math.floor(py) - 2, dotSize + 1, dotSize + 1);
    }

    // Quest-Marker (H1.7) — gelber Stern mit Sinus-Pulse über Turn-In-NPCs.
    // Render NACH allen NPCs, damit der Marker oben liegt.
    const markers = this._questMarkers();
    if (markers.length > 0) {
      const now = performance.now();
      const phase = (now % PULSE_PERIOD_MS) / PULSE_PERIOD_MS;
      const pulse = 1 + 0.2 * Math.sin(phase * Math.PI * 2);
      ctx.save();
      for (const m of markers) {
        const mx = (m.x - ox) * scaleX;
        const my = (m.y - oy) * scaleY;
        if (mx < 0 || my < 0 || mx >= canvas.width || my >= canvas.height) continue;
        const size = Math.max(3, dotSize + 2) * pulse;
        // Outer-Glow
        ctx.fillStyle = 'rgba(255, 220, 80, 0.35)';
        ctx.beginPath();
        ctx.arc(mx, my, size * 1.6, 0, Math.PI * 2);
        ctx.fill();
        // Stern-Body
        ctx.fillStyle = '#ffe060';
        this._drawStar(ctx, mx, my, size, 5);
      }
      ctx.restore();
    }

    // Eigener Spieler — heller Punkt in der Mitte
    const px = (me.x - ox) * scaleX;
    const py = (me.y - oy) * scaleY;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(Math.floor(px) - 2, Math.floor(py) - 2, dotSize + 2, dotSize + 2);
  }

  /** Zeichnet einen 5-zackigen Stern als gefüllten Path. */
  private _drawStar(
    ctx: CanvasRenderingContext2D,
    cx: number,
    cy: number,
    radius: number,
    points: number,
  ): void {
    const inner = radius * 0.45;
    ctx.beginPath();
    for (let i = 0; i < points * 2; i++) {
      const r = i % 2 === 0 ? radius : inner;
      const a = (Math.PI * 2 * i) / (points * 2) - Math.PI / 2;
      const x = cx + Math.cos(a) * r;
      const y = cy + Math.sin(a) * r;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fill();
  }
}
