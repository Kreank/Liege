// ContainerActionOverlayComponent — Fullscreen-Click-Intercept-Layer für
// Container-Tile-Aktionen (H2.6).
//
// Aktiviert sich, sobald `GameStateService.containerAction` gesetzt ist
// (vom Chest-Panel über `beginContainerAction(...)`). Funktioniert
// strukturell wie das `<app-spell-target-overlay>`:
//   • Nächster Click → Bildschirm → Tile-Koord (basierend auf Player-
//     Zentrierung der Phaser-Kamera).
//   • Range-Check (Backend erlaubt max 1 Tile Chebyshev für Container-
//     Aktionen — siehe `backend/ws/structures.py::handle_fill_container`).
//   • Intent senden: `fill_container {item_id, x, y}` oder
//     `water_plant {item_id, x, y}`.
//   • ESC oder Klick außerhalb der Reichweite → Toast, kein Cancel.
//
// Visuelles Feedback: kleinere Vignette als Spell-Mode (weniger
// einschüchternd, weil Container-Aktionen Alltagsfunktion sind).

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
  selector: 'app-container-action-overlay',
  standalone: true,
  templateUrl: './container-action-overlay.component.html',
  styleUrl: './container-action-overlay.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ContainerActionOverlayComponent {
  private readonly state = inject(GameStateService);
  private readonly bridge = inject(GameBridgeService);
  private readonly toast = inject(ToastService);

  /** Backend-Range für Container-Aktionen (Chebyshev ≤ 1 — direkt
   *  angrenzendes Tile inkl. Diagonalen). */
  private static readonly ACTION_RANGE = 1;

  readonly action = computed(() => this.state.containerAction());
  readonly visible = computed<boolean>(() => this.action() !== null);

  readonly hintLabel = computed<string>(() => {
    const a = this.action();
    if (!a) return '';
    if (a.action === 'fill_container') {
      return `${a.item_name} an Wasser/Brunnen auffüllen`;
    }
    return `${a.item_name} auf Acker leeren (gießen)`;
  });

  readonly rangeCircleStyle = computed<RangeCircleStyle>(() => {
    const diameterPx =
      ContainerActionOverlayComponent.ACTION_RANGE * TILE_SIZE * 2;
    return {
      left: `calc(50% - ${diameterPx / 2}px)`,
      top: `calc(50% - ${diameterPx / 2}px)`,
      width: `${diameterPx}px`,
      height: `${diameterPx}px`,
    };
  });

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.visible()) this.cancel();
  }

  onOverlayClick(ev: MouseEvent): void {
    ev.preventDefault();
    ev.stopPropagation();
    const a = this.action();
    if (!a) return;

    const tile = this._screenToTile(ev.clientX, ev.clientY);
    if (!tile) {
      this.toast.show('Spielerposition unbekannt — Aktion abgebrochen.', 'error');
      this.cancel();
      return;
    }

    const me = this.state.player();
    if (me) {
      const dx = Math.abs(tile.x - me.x);
      const dy = Math.abs(tile.y - me.y);
      const dist = Math.max(dx, dy);
      if (dist > ContainerActionOverlayComponent.ACTION_RANGE) {
        this.toast.show('Zu weit weg — Ziel muss angrenzend sein.', 'warn');
        return;
      }
    }

    const intent: ClientIntent = {
      type: a.action,
      item_id: a.item_id,
      x: tile.x,
      y: tile.y,
    };
    this.bridge.sendIntent(intent);
    this.cancel();
  }

  cancel(): void {
    this.state.cancelContainerAction();
  }

  private _screenToTile(
    clientX: number,
    clientY: number,
  ): { readonly x: number; readonly y: number } | null {
    const me = this.state.player();
    if (!me) return null;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const dxPx = clientX - vw / 2;
    const dyPx = clientY - vh / 2;
    const dx = Math.round(dxPx / TILE_SIZE);
    const dy = Math.round(dyPx / TILE_SIZE);
    return { x: me.x + dx, y: me.y + dy };
  }
}
