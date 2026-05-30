// DialogComponent — NPC-Talk-Modal mit Eingabe + Verlauf + Quest-Button.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM:     `index.html` Z. 383-401 (`#dialog-overlay`).
//   • Renderer: `app.js` `openDialog`, `closeDialog`, `sendDialog`,
//                 `receiveDialogReply`, `appendDialogBubble` (~4510-4869).
//
// Backend: `talk_to_npc { npc_id, message }` → broadcast `npc_reply { npc_id, text }`.
//
// State: `activeDialog`-Signal aus GameStateService. Das Panel ist NICHT
// für das Quest-Button-Rendering zuständig — der Quest-Subteil (Offers/
// Turn-ins) wandert in F-final mit der Quest-Board-Komponente; hier zeigen
// wir nur einen passiven Button, der `query_npc_quests` sendet.

import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

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
  private readonly ws = inject(WebSocketService);

  readonly dialog = computed(() => this.state.activeDialog());
  readonly visible = computed<boolean>(() => this.dialog() !== null);
  readonly draft = signal<string>('');

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

  onInputKey(ev: KeyboardEvent): void {
    if (ev.key === 'Enter') {
      ev.preventDefault();
      this.send();
    }
  }
}
