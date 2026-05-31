// QuestRewardComponent — Belohnungs-Modal beim Quest-Abschluss (H3.4).
//
// Trigger-Vertrag (siehe `docu/WS_PROTOCOL.md` Z. 717-749):
//   • Server → `quest_closed {quest_id}`                  — finaler Marker
//   • Server → `inventory_add {item}` …                   — pro Item-Reward
//   • Server → `wallet_update {copper, delta?}`           — Coin-Reward
//   • Server → `skill_xp {skill, xp_gained, …}`           — XP-Reward
//
// Backend liefert `quest_closed` ohne Reward-Payload — der Reward zerfällt
// in `inventory_add` / `wallet_update` / `skill_xp` (alle im selben Tick).
// Wir samplen:
//   1. Beim Eintreffen von `quest_closed` lesen wir die noch im
//      `state.quests()` stehende Quest. Ein eigener Cache (`questCache`)
//      hält die letzte Quest-Liste, damit wir nicht von der Subscriber-
//      Reihenfolge mit GameState abhängen (GameState filtert die Quest
//      direkt nach dem `quest_closed` raus).
//   2. Wir öffnen ein 350ms-Aggregations-Fenster — innerhalb dessen alle
//      `inventory_add` / `wallet_update.delta` / `skill_xp` als Reward-
//      Bestandteile gebucht werden. Nach Ablauf wird das Modal sichtbar.
//   3. Item-Sprites kommen aus dem `ITEM`-Catalog; unbekannte Items fallen
//      auf einen generischen Frage-Icon-Placeholder.
//
// UX:
//   • Items appearen sequentiell mit 120ms Delay (visualReadyCount-Signal
//     wird per setTimeout-Kette hochgezählt). Coin- und XP-Zeile erscheinen
//     nach den Items.
//   • Schließen per „Schließen"-Button, ESC oder Klick auf Backdrop.
//   • Mehrfach-Quest-Aggregation: wenn während des Aggregations-Fensters
//     eine zweite `quest_closed` kommt, queuen wir sie und zeigen sie
//     sequentiell nach Close des aktuellen Modals.
//
// Integration: In `app.html` MUSS `<app-quest-reward></app-quest-reward>`
// platziert werden (Subagent D). Component kann an beliebiger Stelle stehen,
// ist self-contained Overlay (position:fixed).

import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  HostListener,
  OnInit,
  effect,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { ITEM } from '../../core/data/items';
import type { Quest } from '../../core/models/quest.model';
import type { ServerMessage } from '../../core/models/ws-message.model';
import { GameBridgeService } from '../../core/services/game-bridge.service';
import { GameStateService } from '../../core/services/game-state.service';

/** Aggregations-Fenster nach `quest_closed`, in dem `inventory_add` /
 *  `wallet_update` / `skill_xp` als Reward-Bestandteile zählen. */
const AGGREGATION_WINDOW_MS = 350;

/** Verzögerung zwischen sichtbaren Item-Zeilen (sequentielles Reveal). */
const SEQUENTIAL_REVEAL_MS = 120;

/** Vorgegebene Fallback-XP-Quelle, falls Backend nicht liefert (Anzeige-only). */
type RewardItem = {
  readonly kind: string;
  readonly name: string;
  readonly spritePath: string | null;
  readonly count: number;
};

type RewardXp = {
  readonly skill: string;
  readonly amount: number;
};

interface RewardSummary {
  readonly questId: number;
  readonly questTitle: string;
  readonly items: readonly RewardItem[];
  readonly coinDelta: number;
  readonly xp: readonly RewardXp[];
}

/** Während des Aggregations-Fensters mutable Accumulator-Struktur. */
interface RewardAccumulator {
  questId: number;
  questTitle: string;
  itemCounts: Map<string, number>;
  coinDelta: number;
  xp: Map<string, number>;
  expiresAtMs: number;
}

@Component({
  selector: 'app-quest-reward',
  standalone: true,
  templateUrl: './quest-reward.component.html',
  styleUrl: './quest-reward.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class QuestRewardComponent implements OnInit {
  private readonly state = inject(GameStateService);
  private readonly bridge = inject(GameBridgeService);
  private readonly destroyRef = inject(DestroyRef);

  /** Aktuell sichtbares Reward-Summary (null = Modal zu). */
  readonly current = signal<RewardSummary | null>(null);

  /** Wieviele Reward-Items wurden bereits sichtbar gemacht (Reveal-Kette). */
  readonly visibleCount = signal<number>(0);

  /** Ob die Coin/XP-Zeile schon sichtbar ist (kommt nach den Items). */
  readonly summaryRevealed = signal<boolean>(false);

  /** Aktiver Aggregator (während des 350ms-Fensters). */
  private active: RewardAccumulator | null = null;
  /** Timer-Handle für den Window-Close. */
  private flushTimer: ReturnType<typeof setTimeout> | null = null;
  /** FIFO-Queue für aufeinanderfolgende Rewards (zweite Quest während ein Modal offen ist). */
  private readonly queue: RewardSummary[] = [];

  /** Cache der zuletzt gesehenen Quests (für `quest_closed`-Lookup nach
   *  GameState-Removal). Aktualisiert sich reaktiv via effect. */
  private questCache = new Map<number, Quest>();

  /** Reveal-Timer-Kette — wird beim Close gecleared, damit kein Late-Tick
   *  in ein bereits geschlossenes Modal schreibt. */
  private revealTimers: ReturnType<typeof setTimeout>[] = [];

  constructor() {
    // Quest-Cache live halten — Effect läuft bei jeder Änderung der Quest-Liste.
    effect(() => {
      const quests = this.state.quests();
      const next = new Map<number, Quest>();
      for (const q of quests) next.set(q.quest_id, q);
      this.questCache = next;
    });

    this.destroyRef.onDestroy(() => {
      if (this.flushTimer !== null) clearTimeout(this.flushTimer);
      this._clearRevealTimers();
    });
  }

  ngOnInit(): void {
    this.bridge.messages$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((msg) => this._onMessage(msg));
  }

  // ── Tastatur / Click-Handler ─────────────────────────────────────────

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.current() !== null) this.close();
  }

  close(): void {
    this._clearRevealTimers();
    this.current.set(null);
    this.visibleCount.set(0);
    this.summaryRevealed.set(false);
    // Nächste gequeue-te Reward anzeigen.
    const next = this.queue.shift();
    if (next) this._showSummary(next);
  }

  // ── Message-Pipeline ─────────────────────────────────────────────────

  private _onMessage(msg: ServerMessage): void {
    switch (msg.type) {
      case 'quest_closed':
        this._onQuestClosed(msg);
        break;
      case 'inventory_add':
        this._onInventoryAdd(msg);
        break;
      case 'wallet_update':
        this._onWalletUpdate(msg);
        break;
      case 'skill_xp':
        this._onSkillXp(msg);
        break;
      default:
        break;
    }
  }

  private _onQuestClosed(msg: ServerMessage): void {
    const questId = (msg as { quest_id?: number }).quest_id;
    if (typeof questId !== 'number') return;

    // Quest-Titel & Reward-Hint: aus Cache holen (GameState filtert die Quest
    // direkt nach diesem Frame raus, der Cache ist die letzte Source of Truth).
    const cached = this.questCache.get(questId);
    const inlineQuest = (msg as { quest?: Quest }).quest;
    const title =
      cached?.title ??
      inlineQuest?.title ??
      (msg as { title?: string }).title ??
      'Quest';

    // Falls schon ein Aggregator läuft für denselben quest_id — ignorieren
    // (Backend sendet `quest_closed` einmal pro Quest).
    if (this.active && this.active.questId === questId) return;

    // Wenn ein anderer Aggregator läuft, flushen wir den jetzt forciert,
    // bevor wir den neuen starten — sonst landen die folgenden Frames im
    // falschen Bucket.
    if (this.active) this._flushActive();

    this.active = {
      questId,
      questTitle: title,
      itemCounts: new Map<string, number>(),
      coinDelta: 0,
      xp: new Map<string, number>(),
      expiresAtMs: Date.now() + AGGREGATION_WINDOW_MS,
    };
    if (this.flushTimer !== null) clearTimeout(this.flushTimer);
    this.flushTimer = setTimeout(() => this._flushActive(), AGGREGATION_WINDOW_MS);
  }

  private _onInventoryAdd(msg: ServerMessage): void {
    if (!this.active) return;
    // Backend sendet inventory_add unterschiedlich strukturiert je nach Pfad:
    //   • { item: {kind, ...}, count? }
    //   • { kind, count? }
    // Wir handeln defensiv beide Formen.
    const inv = msg as {
      item?: { kind?: string; count?: number };
      kind?: string;
      count?: number;
    };
    const kind = inv.item?.kind ?? inv.kind;
    if (typeof kind !== 'string' || kind.length === 0) return;
    const count = inv.item?.count ?? inv.count ?? 1;
    if (typeof count !== 'number' || count <= 0) return;
    this.active.itemCounts.set(kind, (this.active.itemCounts.get(kind) ?? 0) + count);
  }

  private _onWalletUpdate(msg: ServerMessage): void {
    if (!this.active) return;
    const wu = msg as { delta?: number; copper?: number };
    // `delta` ist der Pro-Frame-Zuwachs (Backend sendet das beim Reward).
    // Falls nicht vorhanden, ignorieren — sonst würden wir den Wallet-Stand
    // als Reward verbuchen.
    if (typeof wu.delta !== 'number') return;
    this.active.coinDelta += wu.delta;
  }

  private _onSkillXp(msg: ServerMessage): void {
    if (!this.active) return;
    const sx = msg as {
      skill?: string;
      xp_gained?: number;
      amount?: number;
    };
    const skill = sx.skill;
    if (typeof skill !== 'string' || skill.length === 0) return;
    const amount = sx.xp_gained ?? sx.amount;
    if (typeof amount !== 'number' || amount <= 0) return;
    this.active.xp.set(skill, (this.active.xp.get(skill) ?? 0) + amount);
  }

  private _flushActive(): void {
    if (this.flushTimer !== null) {
      clearTimeout(this.flushTimer);
      this.flushTimer = null;
    }
    const acc = this.active;
    this.active = null;
    if (!acc) return;

    // Keine Reward-Bestandteile gesammelt → kein Modal (z. B. Quest ohne Reward).
    const itemEntries = Array.from(acc.itemCounts.entries());
    const xpEntries = Array.from(acc.xp.entries());
    if (itemEntries.length === 0 && acc.coinDelta === 0 && xpEntries.length === 0) {
      return;
    }

    const items: RewardItem[] = itemEntries.map(([kind, count]) => {
      const def = ITEM[kind];
      return {
        kind,
        name: def?.name ?? kind,
        spritePath: def?.path ?? null,
        count,
      };
    });
    const xp: RewardXp[] = xpEntries.map(([skill, amount]) => ({ skill, amount }));
    const summary: RewardSummary = {
      questId: acc.questId,
      questTitle: acc.questTitle,
      items,
      coinDelta: acc.coinDelta,
      xp,
    };

    if (this.current() !== null) {
      // Modal ist gerade noch offen — neue Reward in die Queue.
      this.queue.push(summary);
    } else {
      this._showSummary(summary);
    }
  }

  private _showSummary(summary: RewardSummary): void {
    this._clearRevealTimers();
    this.current.set(summary);
    this.visibleCount.set(0);
    this.summaryRevealed.set(false);

    // Sequentielles Reveal — Item N nach N*120ms.
    for (let i = 0; i < summary.items.length; i++) {
      const t = setTimeout(() => {
        // Modal könnte mittlerweile geschlossen sein (User-Close).
        if (this.current() !== summary) return;
        this.visibleCount.set(i + 1);
      }, (i + 1) * SEQUENTIAL_REVEAL_MS);
      this.revealTimers.push(t);
    }
    // Coin/XP-Zeile nach allen Items.
    const summaryDelay = (summary.items.length + 1) * SEQUENTIAL_REVEAL_MS;
    const ts = setTimeout(() => {
      if (this.current() !== summary) return;
      this.summaryRevealed.set(true);
    }, summaryDelay);
    this.revealTimers.push(ts);
  }

  private _clearRevealTimers(): void {
    for (const t of this.revealTimers) clearTimeout(t);
    this.revealTimers = [];
  }

  // ── Template-Helfer ──────────────────────────────────────────────────

  /** Wandelt eine Skill-ID in eine deutsche Anzeigeform (Capitalize). */
  skillLabel(skill: string): string {
    return skill.charAt(0).toUpperCase() + skill.slice(1);
  }

  /** Coin-Anzeige in Gold/Silber/Kupfer (1g = 100s = 10000c). */
  coinParts(copper: number): readonly { value: number; symbol: string }[] {
    const total = Math.max(0, Math.floor(copper));
    const g = Math.floor(total / 10000);
    const s = Math.floor((total % 10000) / 100);
    const c = total % 100;
    const out: { value: number; symbol: string }[] = [];
    if (g > 0) out.push({ value: g, symbol: 'g' });
    if (s > 0) out.push({ value: s, symbol: 's' });
    if (c > 0 || out.length === 0) out.push({ value: c, symbol: 'c' });
    return out;
  }
}
