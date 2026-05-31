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

  /** H2.7 — Live-Vote-Counts (Need/Greed/Pass). Null bevor der erste Vote
   *  reinkommt → Template rendert dann „Warte auf Stimmen…". */
  readonly voteCounts = computed(() => this.state.lootRollVoteCounts());

  /** Loot-Rule der eigenen Gruppe — wird im Overlay-Header als Kontext-
   *  Hinweis angezeigt (Spieler weiß, warum er gerade Need/Greed wählen
   *  darf). */
  readonly lootRuleLabel = computed<string>(() => {
    const g = this.state.party();
    if (!g) return '';
    return _lootRuleLabel(g.loot_rule);
  });

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
    // Bei neuem Roll: eigene Stimme zurücksetzen, damit Vote-Buttons
    // wieder enabled sind.
    effect(() => {
      const r = this.state.activeLootRoll();
      if (r) {
        this._myVote.set(null);
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
    // H2.7 — NICHT mehr lokal `clearLootRoll` triggern: das Overlay soll
    // bis zum `loot_roll_resolved` sichtbar bleiben, damit der Spieler
    // den Vote-Verlauf der Gruppe live sehen kann. Wir schalten lokal
    // die Aktions-Buttons aus, indem wir den eigenen Stimm-Status
    // halten (siehe `myVote`).
    this._myVote.set(kind);
  }

  /** Tracking der eigenen Stimme — damit Buttons nach Vote disabled
   *  werden. Backend lehnt einen 2. Vote ohnehin per `loot_vote_error`
   *  ab, aber das UI signalisiert es schon vorher. */
  private readonly _myVote = signal<Vote | null>(null);
  readonly myVote = computed<Vote | null>(() => {
    const r = this.roll();
    if (!r) return null;
    return this._myVote();
  });

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

/** Backend-Vertrag → Deutsche UI-Bezeichnung. */
function _lootRuleLabel(rule: string): string {
  switch (rule) {
    case 'free_for_all':      return 'FFA';
    case 'need_before_greed': return 'Need/Greed';
    case 'leader_decides':    return 'Master-Loot';
    case 'round_robin':       return 'Round-Robin';
    default:                  return rule;
  }
}
