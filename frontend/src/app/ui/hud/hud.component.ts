// HudComponent — kompaktes Heads-Up-Display, das links über dem Phaser-Canvas
// hängt: HP / Mana / Hunger / Durst / Ausdauer plus Koordinaten und
// Connection-Status. Read-only — bindet nur an Signals, sendet keine Intents.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM-Stub:   `index.html` Z. 28-36 (`#ui` + `#status`),
//                 Z. 99-112 (HP/Mana/Hunger/Thirst/Stamina-Bars).
//   • Renderer:   `app.js` `updateUI`, `updateHpBar`, `updateNeedsBar`,
//                 `updateConnStatus`, `_updateBar` (Z. ~3500-4100).
//   • Styles:     `style.css` Z. 13-66 (Bars-Layout/Farben),
//                 Z. 22-25 (`#status`-Position).
//
// Signal-Inputs (aus GameStateService):
//   • `player()`   — hp, max_hp, mana, max_mana, hunger, ..., x, y
//   • `ws.status()` — 'connecting'|'open'|'closed'|'reconnecting'
//
// Stub-bewusste Lücken (TODO F-final): #status-effects-row, Wallet-HUD,
// Body-Parts und Tile-Name werden NICHT hier gerendert — sie hängen an
// separaten Panels und kommen mit den jeweiligen Phasen.

import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';

import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';
import type { ConnectionStatus } from '../../core/models/ws-message.model';

interface BarView {
  readonly cur: number;
  readonly max: number;
  readonly pct: number;
  readonly label: string;
}

const CONN_LABEL: Readonly<Record<ConnectionStatus, string>> = {
  connecting: 'Verbinde…',
  open: 'Verbunden',
  reconnecting: 'Reconnect…',
  closed: 'Getrennt',
};

@Component({
  selector: 'app-hud',
  standalone: true,
  templateUrl: './hud.component.html',
  styleUrl: './hud.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HudComponent {
  private readonly state = inject(GameStateService);
  private readonly ws = inject(WebSocketService);

  readonly visible = computed(() => this.state.player() !== null);

  readonly hp = computed<BarView>(() => this._bar(
    this.state.player()?.hp, this.state.player()?.max_hp,
  ));
  readonly mana = computed<BarView>(() => this._bar(
    this.state.player()?.mana, this.state.player()?.max_mana,
  ));
  readonly hunger = computed<BarView>(() => this._bar(
    this.state.player()?.hunger, this.state.player()?.max_hunger,
  ));
  readonly thirst = computed<BarView>(() => this._bar(
    this.state.player()?.thirst, this.state.player()?.max_thirst,
  ));
  readonly stamina = computed<BarView>(() => this._bar(
    this.state.player()?.stamina, this.state.player()?.max_stamina,
  ));

  readonly coords = computed<string>(() => {
    const p = this.state.player();
    if (!p) return 'x:0 y:0';
    return `x:${Math.round(p.x)} y:${Math.round(p.y)}`;
  });

  readonly connStatus = computed<{ readonly label: string; readonly kind: ConnectionStatus }>(() => {
    const s = this.ws.status();
    return { label: CONN_LABEL[s] ?? s, kind: s };
  });

  private _bar(cur: number | undefined, max: number | undefined): BarView {
    const c = cur ?? 0;
    const m = Math.max(1, max ?? 0);
    const pct = Math.max(0, Math.min(100, Math.round((c / m) * 100)));
    return { cur: Math.round(c), max: Math.round(m), pct, label: `${Math.round(c)} / ${Math.round(m)}` };
  }
}
