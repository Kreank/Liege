// BuildContextMenuComponent — Repair/Upgrade/Demolish-Popup für eigene
// Strukturen (H2.17).
//
// Trigger: World-Scene setzt `bridge.structureTarget({x,y,type,...})` beim
// Rechts-Klick auf eine eigene zerstörbare Struktur (Wall, Door, Tower, …).
// Komponente zeigt sich automatisch (kein Hotkey) und positioniert sich
// fix oben-mitte (Viewport-zentriert) — bewusste Entscheidung gegen
// cursor-relative Positionierung, weil World-Scene die Cursor-Position
// nicht stabil über die Bridge meldet. Cursor-relative Positionierung
// kann eine spätere Polish-Welle ergänzen.
//
// Actions:
//   • Reparieren  → `repair_structure {x,y}`
//   • Aufwerten   → `upgrade_structure {x,y}`
//   • Abreißen    → `remove_structure {x,y}`
//   • Esc / „×"   → schließen ohne Action
//
// Material-Kosten werden nicht im Frontend berechnet (Backend hat die
// Recipe-Daten); HP-Anzeige zeigt nur den aktuellen Stand. Backend antwortet
// mit `structure_repaired` / `structure_upgraded` / `structure_removed`,
// World-Scene rendert den Sprite-Swap.

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  inject,
} from '@angular/core';

import { STRUCTURE } from '../../core/data/structures';
import { GameBridgeService } from '../../core/services/game-bridge.service';

@Component({
  selector: 'app-build-context-menu',
  standalone: true,
  templateUrl: './build-context-menu.component.html',
  styleUrl: './build-context-menu.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BuildContextMenuComponent {
  private readonly bridge = inject(GameBridgeService);

  readonly target = computed(() => this.bridge.structureTarget());
  readonly visible = computed<boolean>(() => this.target() !== null);

  readonly displayName = computed<string>(() => {
    const t = this.target();
    if (!t) return '';
    return STRUCTURE[t.type]?.name ?? t.type;
  });

  /** True wenn das nächst-bessere Material existiert (sonst Button greyed). */
  readonly upgradable = computed<boolean>(() => {
    const t = this.target();
    if (!t) return false;
    const mat = t.material ?? 'straw';
    return mat === 'straw' || mat === 'wood' || mat === 'stone';
  });

  /** Lesbare Ziel-Material-Bezeichnung für den Upgrade-Button. */
  readonly upgradeTargetLabel = computed<string>(() => {
    const t = this.target();
    if (!t) return '';
    const mat = t.material ?? 'straw';
    if (mat === 'straw') return 'Holz';
    if (mat === 'wood') return 'Stein';
    if (mat === 'stone') return 'Verstärkter Stein';
    return '–';
  });

  /** HP-Anzeige (z. B. „42 / 80"). Leer wenn unbekannt. */
  readonly hpLabel = computed<string>(() => {
    const t = this.target();
    if (!t || t.hp == null || t.max_hp == null) return '';
    return `${t.hp} / ${t.max_hp}`;
  });

  /** True wenn die Struktur beschädigt ist (Repair sinnvoll). */
  readonly damaged = computed<boolean>(() => {
    const t = this.target();
    if (!t || t.hp == null || t.max_hp == null) return true; // konservativ
    return t.hp < t.max_hp;
  });

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.visible()) this.close();
  }

  close(): void {
    this.bridge.setStructureTarget(null);
  }

  repair(): void {
    const t = this.target();
    if (!t) return;
    this.bridge.sendRepairStructure(t.x, t.y);
    this.close();
  }

  upgrade(): void {
    const t = this.target();
    if (!t) return;
    this.bridge.sendUpgradeStructure(t.x, t.y);
    this.close();
  }

  demolish(): void {
    const t = this.target();
    if (!t) return;
    this.bridge.sendRemoveStructure(t.x, t.y);
    this.close();
  }
}
