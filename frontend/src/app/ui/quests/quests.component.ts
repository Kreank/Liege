// QuestsComponent — Liste aktiver/abgeschlossener/verfügbarer Quests.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM-Stub:   `index.html` Z. 206-214 (`#quests-overlay`).
//   • Renderer:   `app.js` `toggleQuests`, `renderQuests`,
//                 `acceptQuestTemplate`, `claimQuestReward`, `questTurnIn`.
//   • Styles:     `style.css` Z. 543-573.
//
// Backend liefert: `quests`-Signal (Quest[]). Quest hat state, title,
// objectives[], rewards?.
//
// Intents:
//   • accept_quest_template { template_id }      — für available-Quests
//                                                  mit template_id.
//   • claim_quest_reward    { quest_id }         — für completed-Quests
//                                                  ohne NPC-Giver.
//   • quest_turn_in         { quest_id }         — wenn ein NPC-Turn-In
//                                                  möglich ist (giver
//                                                  vorhanden, aber kein
//                                                  separates Dialog-Modal).
//
// Tastatur: `Q` toggelt, `Esc` schließt.

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';

import type { Quest, QuestState } from '../../core/models/quest.model';
import { GameBridgeService } from '../../core/services/game-bridge.service';
import { GameStateService } from '../../core/services/game-state.service';

const STATE_ORDER: Readonly<Record<QuestState, number>> = {
  active: 0,
  completed: 1,
  available: 2,
  failed: 3,
};

@Component({
  selector: 'app-quests',
  standalone: true,
  templateUrl: './quests.component.html',
  styleUrl: './quests.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class QuestsComponent {
  private readonly state = inject(GameStateService);
  private readonly bridge = inject(GameBridgeService);

  readonly visible = signal<boolean>(false);
  /** Welche Quest gerade expanded ist (Detail-Ansicht). */
  readonly expandedId = signal<number | null>(null);

  /** Voriger `visible`-Wert, um die false→true-Flanke im effect zu erkennen. */
  private wasVisible = false;

  constructor() {
    // Auto-Refresh: bei jedem Oeffnen (false→true) die Quest-Liste neu
    // anfordern (Snapshot kann nach Reconnect/verpassten Pushes veralten).
    // Tolerant gegenueber ausbleibender Antwort: der Backend-all_reputation
    // kann fehlschlagen — das blockiert die UI nicht, wir zeigen weiter den
    // letzten Stand.
    effect(() => {
      const open = this.visible();
      if (open && !this.wasVisible) {
        this.bridge.sendIntent({ type: 'list_quests' });
      }
      this.wasVisible = open;
    });
  }

  readonly quests = computed<readonly Quest[]>(() => {
    const q = this.state.quests().slice();
    q.sort((a, b) => (STATE_ORDER[a.state] - STATE_ORDER[b.state]) || a.title.localeCompare(b.title));
    return q;
  });

  @HostListener('document:keydown', ['$event'])
  onKey(ev: KeyboardEvent): void {
    const target = ev.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.key === 'q' || ev.key === 'Q') {
      this.visible.update((v) => !v);
      ev.preventDefault();
    } else if (ev.key === 'Escape' && this.visible()) {
      this.visible.set(false);
      ev.preventDefault();
    }
  }

  close(): void { this.visible.set(false); }

  toggle(q: Quest): void {
    this.expandedId.set(this.expandedId() === q.quest_id ? null : q.quest_id);
  }

  accept(q: Quest, ev: MouseEvent): void {
    ev.stopPropagation();
    if (q.template_id) {
      this.bridge.sendIntent({ type: 'accept_quest_template', template_id: q.template_id });
    } else if (q.giver_npc_id !== undefined) {
      this.bridge.sendIntent({ type: 'accept_quest_from_npc', npc_id: q.giver_npc_id });
    }
  }

  claim(q: Quest, ev: MouseEvent): void {
    ev.stopPropagation();
    this.bridge.sendIntent({ type: 'claim_quest_reward', quest_id: q.quest_id });
  }

  turnIn(q: Quest, ev: MouseEvent): void {
    ev.stopPropagation();
    this.bridge.sendIntent({ type: 'quest_turn_in', quest_id: q.quest_id });
  }

  // Template-Helfer für Reward-Map → Array.
  rewardEntries(q: Quest): readonly { key: string; value: number | string }[] {
    if (!q.rewards) return [];
    return Object.entries(q.rewards).map(([key, value]) => ({ key, value }));
  }
}
