// DownedOverlayComponent — Vollbild-Modal während Down-State.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM:     `index.html` Z. 117-124 (`#downed-overlay`).
//   • Renderer: `app.js` `_showDownedOverlay`, `_hideDownedOverlay`,
//                 `forceRespawn` (Z. ~4030-4065).
//   • Styles:  `style.css` Z. 267-293.
//
// Backend: `player_downed { duration_s }` öffnet, `player_respawned` schließt.
//          `force_respawn` (Intent) lässt sofort respawnen.

import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';

import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';

@Component({
  selector: 'app-downed-overlay',
  standalone: true,
  templateUrl: './downed-overlay.component.html',
  styleUrl: './downed-overlay.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DownedOverlayComponent {
  private readonly state = inject(GameStateService);
  private readonly ws = inject(WebSocketService);

  private readonly _tick = signal<number>(Date.now());
  private _timerId: number | null = null;

  readonly visible = computed<boolean>(() => this.state.downedExpiresAt() !== null);

  readonly remainingLabel = computed<string>(() => {
    const exp = this.state.downedExpiresAt();
    if (exp === null) return '0.0s';
    void this._tick();
    const rem = Math.max(0, (exp - Date.now()) / 1000);
    return rem.toFixed(1) + 's';
  });

  constructor() {
    effect(() => {
      if (this.state.downedExpiresAt() !== null) {
        this._startTick();
      } else {
        this._stopTick();
      }
    });
  }

  forceRespawn(): void {
    this.ws.send({ type: 'force_respawn' });
  }

  private _startTick(): void {
    if (this._timerId !== null) return;
    this._timerId = window.setInterval(() => {
      this._tick.set(Date.now());
    }, 100);
  }

  private _stopTick(): void {
    if (this._timerId !== null) {
      window.clearInterval(this._timerId);
      this._timerId = null;
    }
  }
}
