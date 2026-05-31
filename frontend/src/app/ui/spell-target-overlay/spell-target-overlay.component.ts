// SpellTargetOverlayComponent — Fullscreen-Click-Intercept-Layer für
// den Spell-Target-Selection-Mode (H2.3).
//
// Workflow:
//   1. Spieler klickt im Spellbook auf einen Spell mit
//      `target_kind ∈ {single, aoe, ground, group, downed}`.
//   2. Spellbook ruft `state.beginSpellTargeting(spell)` auf.
//   3. Dieses Overlay wird sichtbar (visible-Computed), legt sich als
//      Fullscreen-Layer über Phaser-Canvas, deaktiviert das normale
//      Click-Routing der WorldScene und zeigt Crosshair-Cursor + Hint.
//   4. Nächster Click → wir rechnen Bildschirm → Tile-Koordinaten um,
//      suchen ggf. ein NPC auf dem Ziel-Tile und senden `cast_spell`:
//        • `single` / `downed` → `{spell_id, target_npc_id}` falls NPC
//          gefunden, sonst Toast.
//        • `aoe` / `ground`    → `{spell_id, target_x, target_y}`.
//   5. ESC oder Klick außerhalb der Range → `cancelSpellTarget()`.
//
// Koord-Umrechnung: Phaser-Canvas füllt das ganze Viewport. Spielfigur
// ist zentriert (siehe `world-scene.ts::update()`-Kamera-Follow). Wir
// können also aus der Bildschirm-Mitte + Player-Tile + TILE_SIZE die
// Welt-Tile zurückrechnen. Bei mehreren Viewport-Größen funktioniert
// das, solange die Kamera den Spieler immer zentriert hält.
//
// HINWEIS: Das Overlay sitzt auf `z-index: 5000` über allen anderen
// UI-Panels, damit es Clicks zuverlässig vor der Phaser-Canvas
// abfängt (Canvas hat keinen z-index gesetzt → 0 / auto).

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  inject,
} from '@angular/core';

import { TILE_SIZE } from '../../core/data/tiles';
import type { ClientIntent } from '../../core/models/ws-message.model';
import { GameBridgeService } from '../../core/services/game-bridge.service';
import { GameStateService } from '../../core/services/game-state.service';
import { ToastService } from '../../core/services/toast.service';

interface RangeCircleStyle {
  readonly left: string;
  readonly top: string;
  readonly width: string;
  readonly height: string;
}

@Component({
  selector: 'app-spell-target-overlay',
  standalone: true,
  templateUrl: './spell-target-overlay.component.html',
  styleUrl: './spell-target-overlay.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SpellTargetOverlayComponent {
  private readonly state = inject(GameStateService);
  private readonly bridge = inject(GameBridgeService);
  private readonly toast = inject(ToastService);

  readonly spell = computed(() => this.state.castingSpell());
  readonly visible = computed<boolean>(() => this.spell() !== null);

  /** Hint-Label oben in der Mitte — kontext-spezifisch. */
  readonly hintLabel = computed<string>(() => {
    const s = this.spell();
    if (!s) return '';
    const tk = s.target_kind;
    if (tk === 'single' || tk === 'enemy') {
      return `Wähle Ziel für ${s.name}`;
    }
    if (tk === 'downed') {
      return `Wähle gefallenen Mitspieler für ${s.name}`;
    }
    if (tk === 'aoe' || tk === 'ground' || tk === 'tile') {
      return `Wähle Bodenpunkt für ${s.name}`;
    }
    return `Wähle Ziel für ${s.name}`;
  });

  /** Range-Circle-Größe in Pixeln (Tiles × TILE_SIZE × 2 für Diameter). */
  readonly rangeCircleStyle = computed<RangeCircleStyle | null>(() => {
    const s = this.spell();
    if (!s || !s.range || s.range <= 0) return null;
    const diameterPx = s.range * TILE_SIZE * 2;
    return {
      left: `calc(50% - ${diameterPx / 2}px)`,
      top: `calc(50% - ${diameterPx / 2}px)`,
      width: `${diameterPx}px`,
      height: `${diameterPx}px`,
    };
  });

  // ─── ESC-Cancel ──────────────────────────────────────────────────────
  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.visible()) this.cancel();
  }

  /** Click-Intercept aus dem Template (auf das Overlay-Layer). */
  onOverlayClick(ev: MouseEvent): void {
    ev.preventDefault();
    ev.stopPropagation();
    const spell = this.spell();
    if (!spell) return;

    const tile = this._screenToTile(ev.clientX, ev.clientY);
    if (!tile) {
      this.toast.show('Spielerposition unbekannt — Cast abgebrochen.', 'error');
      this.cancel();
      return;
    }

    // Range-Check (Manhattan-Distanz reicht für die UI-Vorvalidierung;
    // Backend hat die finale Wahrheit und wird ggf. mit Toast ablehnen).
    const me = this.state.player();
    if (me && spell.range && spell.range > 0) {
      const dx = Math.abs(tile.x - me.x);
      const dy = Math.abs(tile.y - me.y);
      const dist = Math.max(dx, dy); // Chebyshev — passt zum Range-Circle.
      if (dist > spell.range) {
        this.toast.show(
          `Außerhalb der Reichweite (${dist} > ${spell.range} Felder).`,
          'warn',
        );
        return; // NICHT canceln — Spieler darf erneut klicken.
      }
    }

    const tk = spell.target_kind;
    if (tk === 'single' || tk === 'enemy') {
      // NPC am Ziel-Tile finden.
      const npc = this.state.npcsVisible().find(
        (n) => n.x === tile.x && n.y === tile.y,
      );
      if (!npc) {
        this.toast.show('Kein Ziel auf diesem Feld.', 'warn');
        return;
      }
      this._sendCast({ spell_id: spell.id, target_npc_id: npc.id });
    } else if (tk === 'downed') {
      // Downed-Player am Ziel-Tile (oder NPC mit `is_downed` Flag).
      // Pragma: aktuell nur NPC-Pick — Downed-Spieler-Pick kommt mit
      // einem separaten Player-Pool-Lookup, sobald `players` State auf
      // `is_downed`-Flag erweitert ist (siehe ai_fragen Eintrag).
      const npc = this.state.npcsVisible().find(
        (n) => n.x === tile.x && n.y === tile.y,
      );
      if (!npc) {
        this.toast.show('Kein gefallener Mitspieler auf diesem Feld.', 'warn');
        return;
      }
      this._sendCast({ spell_id: spell.id, target_npc_id: npc.id });
    } else {
      // aoe / ground / tile → Tile-Target.
      this._sendCast({
        spell_id: spell.id,
        target_x: tile.x,
        target_y: tile.y,
      });
    }
  }

  cancel(): void {
    this.state.cancelSpellTarget();
  }

  // ─── Internals ───────────────────────────────────────────────────────

  private _sendCast(args: {
    readonly spell_id: string;
    readonly target_npc_id?: number;
    readonly target_x?: number;
    readonly target_y?: number;
  }): void {
    const intent: ClientIntent = { type: 'cast_spell', ...args };
    this.bridge.sendIntent(intent);
    this.cancel();
  }

  /** Bildschirm-Pixel → Welt-Tile-Koordinaten. Annahme: Phaser-Canvas
   *  füllt den Viewport, Spieler ist exakt zentriert (siehe Kamera-
   *  Follow in `world-scene.ts::update`). */
  private _screenToTile(
    clientX: number,
    clientY: number,
  ): { readonly x: number; readonly y: number } | null {
    const me = this.state.player();
    if (!me) return null;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    // Pixel-Offset vom Bildschirm-Center.
    const dxPx = clientX - vw / 2;
    const dyPx = clientY - vh / 2;
    // In Tile-Offsets umrechnen.
    const dx = Math.round(dxPx / TILE_SIZE);
    const dy = Math.round(dyPx / TILE_SIZE);
    return { x: me.x + dx, y: me.y + dy };
  }
}
