// LootRollComponent — Need/Greed/Pass-Overlay.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM:     `index.html` Z. 53-65 (`#loot-roll-overlay`).
//   • Renderer: `app.js` `showLootRoll`, `hideLootRoll` (Z. ~6848-6895).
//   • Styles:  `style.css` Z. 1727-1749.
//
// Backend: `loot_roll_started` (loot_rolls.py) liefert
//   { type, roll_id, item: {kind, quantity?, quality?}, expires_in_s }.
// `loot_roll_resolved` schließt das Overlay.
//
// Sendet: `loot_vote { roll_id, vote: 'need'|'greed'|'pass' }`.

import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { ITEM } from '../../core/data/items';
import type { ItemDef } from '../../core/models/item.model';
import type { ClientIntent } from '../../core/models/ws-message.model';
import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';

type Vote = 'need' | 'greed' | 'pass';

@Component({
  selector: 'app-loot-roll',
  standalone: true,
  templateUrl: './loot-roll.component.html',
  styleUrl: './loot-roll.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LootRollComponent implements OnInit {
  private readonly state = inject(GameStateService);
  private readonly ws = inject(WebSocketService);
  private readonly destroyRef = inject(DestroyRef);

  /** Tickt jede Sekunde, damit der Countdown nicht stehenbleibt. */
  private readonly _tick = signal<number>(Date.now());
  private _timerId: number | null = null;

  readonly roll = computed(() => this.state.activeLootRoll());
  readonly visible = computed<boolean>(() => this.roll() !== null);

  readonly itemLabel = computed<string>(() => {
    const r = this.roll();
    if (!r) return '';
    const def: ItemDef | undefined = ITEM[r.item.kind];
    const name = def?.name ?? r.item.kind;
    const qual = r.item.quality && r.item.quality !== 'normal'
      ? ` (${r.item.quality})`
      : '';
    return `${name}${qual}`;
  });

  readonly remainingS = computed<number>(() => {
    const r = this.roll();
    if (!r) return 0;
    void this._tick();
    const elapsed = Math.floor((Date.now() - r.started_at_ms) / 1000);
    return Math.max(0, r.expires_in_s - elapsed);
  });

  constructor() {
    // Auto-Tick-Effect — startet/stoppt das Intervall je Roll-Status.
    effect(() => {
      const r = this.state.activeLootRoll();
      if (r) {
        this._startTimer();
      } else {
        this._stopTimer();
      }
    });
  }

  ngOnInit(): void {
    // Bei Component-Destroy aufräumen.
    this.destroyRef.onDestroy(() => this._stopTimer());
    // takeUntilDestroyed wird hier nicht benötigt — kein Subscription.
    // Beibehalten als Importable-Beispiel.
    void takeUntilDestroyed;
  }

  vote(kind: Vote): void {
    const r = this.roll();
    if (!r) return;
    const intent: ClientIntent = {
      type: 'loot_vote',
      roll_id: r.roll_id,
      vote: kind,
    };
    this.ws.send(intent);
    this.state.clearLootRoll();
  }

  private _startTimer(): void {
    if (this._timerId !== null) return;
    this._timerId = window.setInterval(() => {
      this._tick.set(Date.now());
      if (this.remainingS() <= 0) {
        this.state.clearLootRoll();
      }
    }, 1000);
  }

  private _stopTimer(): void {
    if (this._timerId !== null) {
      window.clearInterval(this._timerId);
      this._timerId = null;
    }
  }
}
