// QuestBoardComponent — Modal-Overlay für `quest_board_open`-Antworten.
//
// Backend-Vertrag (siehe backend/ws/structures.py::use_structure / Branch
// `quest_board`):
//   Server → quest_board_open { board_id, offers: [{template_id, title,
//                                                   description, quest_type,
//                                                   objective, reward, tier}] }
//
// State: GameStateService.activeQuestBoard (H1.6). Wird vom Server gefüllt,
// wenn der Spieler `use_structure` auf ein Quest-Board macht. Schließen wir
// lokal (Esc oder X) — das nächste `quest_board_open`-Frame setzt es neu.
//
// Annahme einer Quest → `accept_quest_template { template_id }`. Backend
// sendet daraufhin `quest_new` und ggf. `npc_spawned` (Kill-Quest-Spawn-
// Garantie). Wir schließen das Board nach erfolgreichem Accept (lokal) —
// der Spieler kann durch erneutes Use noch laufende Angebote nochmal sehen.

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  inject,
} from '@angular/core';

import { GameBridgeService } from '../../core/services/game-bridge.service';
import { GameStateService } from '../../core/services/game-state.service';

interface RewardRow {
  readonly key: string;
  readonly value: number | string;
}

@Component({
  selector: 'app-quest-board',
  standalone: true,
  templateUrl: './quest-board.component.html',
  styleUrl: './quest-board.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class QuestBoardComponent {
  private readonly state = inject(GameStateService);
  private readonly bridge = inject(GameBridgeService);

  readonly board = computed(() => this.state.activeQuestBoard());
  readonly visible = computed<boolean>(() => this.board() !== null);

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.visible()) this.close();
  }

  close(): void {
    this.state.closeQuestBoard();
  }

  accept(templateId: string): void {
    this.bridge.sendIntent({ type: 'accept_quest_template', template_id: templateId });
    // Lokal schließen — Server sendet evtl. ein neues quest_board_open mit
    // reduzierter Liste, wenn der Spieler nochmal interagiert.
    this.close();
  }

  rewardRows(reward: Readonly<Record<string, number | string>> | undefined): readonly RewardRow[] {
    if (!reward) return [];
    return Object.entries(reward).map(([key, value]) => ({ key, value }));
  }

  /** Lesbare Kurzform der Objective-Map: "Töte 3× Wolf", "Sammle 5× Holz", … */
  objectiveLabel(quest_type: string | undefined, objective: Readonly<Record<string, unknown>> | undefined): string {
    if (!objective) return '';
    if (quest_type === 'kill') {
      const kind = objective['creature_kind'] as string | undefined;
      const count = objective['count'] as number | undefined;
      if (kind && count) return `Töte ${count}× ${kind}`;
    }
    if (quest_type === 'fetch' || quest_type === 'gather') {
      const kind = objective['item_kind'] as string | undefined;
      const count = objective['count'] as number | undefined;
      if (kind && count) return `Sammle ${count}× ${kind}`;
    }
    return '';
  }
}
