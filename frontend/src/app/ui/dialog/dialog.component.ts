// DialogComponent — NPC-Talk-Modal mit Eingabe + Verlauf + Quest-Button.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM:     `index.html` Z. 383-401 (`#dialog-overlay`).
//   • Renderer: `app.js` `openDialog`, `closeDialog`, `sendDialog`,
//                 `receiveDialogReply`, `appendDialogBubble` (~4510-4869).
//
// Backend: `talk_to_npc { npc_id, message }` → broadcast `npc_reply { npc_id, text }`.
//
// State: `activeDialog`-Signal aus GameStateService. H1.8 — Click auf
// friendly NPC öffnet das Modal LOKAL (kein WS-Frame), erst beim ersten
// Send schickt das Panel `talk_to_npc`. Quest-Button löst `query_npc_quests`
// aus; Antwort landet in `activeNpcQuestStatus` und rendert hier als
// „Verfügbare Quests"-Sektion.

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { GameBridgeService } from '../../core/services/game-bridge.service';
import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';

@Component({
  selector: 'app-dialog',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './dialog.component.html',
  styleUrl: './dialog.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DialogComponent {
  private readonly state = inject(GameStateService);
  private readonly bridge = inject(GameBridgeService);
  private readonly ws = inject(WebSocketService);

  readonly dialog = computed(() => this.state.activeDialog());
  readonly visible = computed<boolean>(() => this.dialog() !== null);
  readonly draft = signal<string>('');

  /** Nur anzeigen, wenn der Quest-Status zum aktuellen NPC gehört. Sonst
   *  könnte ein älterer Query (anderer NPC) hier kurz aufflackern. */
  readonly questStatus = computed(() => {
    const d = this.dialog();
    const qs = this.state.activeNpcQuestStatus();
    if (!d || !qs || qs.npc_id !== d.npc_id) return null;
    return qs;
  });

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.visible()) this.close();
  }

  close(): void {
    this.state.closeDialog();
  }

  send(): void {
    const d = this.dialog();
    if (!d || d.waiting) return;
    const text = this.draft().trim();
    if (!text) return;
    this.draft.set('');
    this.state.appendDialogBubble('user', text);
    this.state.appendDialogBubble('npc', '…', { typing: true });
    this.state.setDialogWaiting(true);
    this.ws.send({
      type: 'talk_to_npc',
      npc_id: d.npc_id,
      message: text,
    });
  }

  askQuest(): void {
    const d = this.dialog();
    if (!d) return;
    this.ws.send({ type: 'query_npc_quests', npc_id: d.npc_id });
  }

  acceptOffer(templateId: string): void {
    const d = this.dialog();
    if (!d) return;
    this.bridge.sendIntent({
      type: 'accept_quest_template',
      template_id: templateId,
      npc_id: d.npc_id,
    });
    // Optimistisch: Offer aus dem lokalen Status entfernen, damit der
    // „Annehmen"-Button verschwindet. Backend sendet ohnehin ein neues
    // `quests_update` (das `activeNpcQuestStatus` ist als public-writable
    // Signal exponiert, weil es nur ein UI-Cache ist).
    const qs = this.state.activeNpcQuestStatus();
    if (qs) {
      this.state.activeNpcQuestStatus.set({
        ...qs,
        offers: qs.offers.filter((o) => o.template_id !== templateId),
      });
    }
  }

  turnIn(questId: number): void {
    const d = this.dialog();
    if (!d) return;
    this.bridge.sendIntent({
      type: 'quest_turn_in',
      quest_id: questId,
      npc_id: d.npc_id,
    });
  }

  onInputKey(ev: KeyboardEvent): void {
    if (ev.key === 'Enter') {
      ev.preventDefault();
      this.send();
    }
  }
}
