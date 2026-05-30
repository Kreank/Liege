// ChatComponent — globaler Spieler-Chat + Slash-Commands für Gruppen.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • Renderer + DOM (IIFE):  `app.js` `setupChatConsole`
//                              (Z. ~10173-10569).
//
// Backend:
//   • `chat { text }` für Welt-Chat. Backend broadcastet
//     `chat { type, from, text }`.
//   • `group_chat { text }` für Party. Broadcast: `group_chat { from, text, kind }`.
//   • Slash-Commands wandeln den Text in andere Intents um, siehe
//     `_handleSlash` weiter unten. Backend-Pendants liegen in
//     `backend/ws/social.py` (group_invite/leave/kick/promote/...) und
//     `backend/ws/raid.py` (raid_trigger_manual).
//
// Was wir bewusst NICHT migrieren:
//   • Dev/Claude-Bridge (admin-only WebSocket `/ws/dev-chat`). Bleibt in
//     F-final liegen — der Refactor-Plan nennt nur den Spieler-Chat als
//     F14-Scope.
//   • Drag-/Minimize-/visualViewport-Tricks aus Legacy — kosmetisch, kann
//     in F-final dazukommen.

import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  ViewChild,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import type { ClientIntent } from '../../core/models/ws-message.model';
import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChatComponent {
  private readonly state = inject(GameStateService);
  private readonly ws = inject(WebSocketService);

  readonly visible = signal<boolean>(true);
  readonly inputText = signal<string>('');

  readonly messages = computed(() => this.state.chatLog());

  @ViewChild('messagesEl') messagesElRef?: ElementRef<HTMLDivElement>;

  constructor() {
    // Auto-Scroll bei neuer Message.
    effect(() => {
      void this.messages();
      queueMicrotask(() => {
        const el = this.messagesElRef?.nativeElement;
        if (el) el.scrollTop = el.scrollHeight;
      });
    });
  }

  toggle(): void { this.visible.update((v) => !v); }

  send(): void {
    const text = this.inputText().trim();
    if (!text) return;
    this.inputText.set('');
    if (text.startsWith('/') && this._handleSlash(text)) return;
    const intent: ClientIntent = { type: 'chat', text };
    this.ws.send(intent);
  }

  onInputKey(ev: KeyboardEvent): void {
    if (ev.key === 'Enter' && !ev.shiftKey) {
      ev.preventDefault();
      this.send();
    }
  }

  /** Wandelt Gruppen-Slash-Commands in den entsprechenden Intent um.
   *  Return `true` wenn behandelt — der Text wird dann nicht als globaler
   *  Chat weitergeleitet. */
  private _handleSlash(text: string): boolean {
    const parts = text.split(/\s+/);
    const cmd = parts[0].toLowerCase();
    const arg = parts.slice(1).join(' ').trim();
    switch (cmd) {
      case '/invite':
      case '/inv': {
        if (!arg) { this._localError('Spielernamen angeben: /invite Name'); return true; }
        this.ws.send({ type: 'group_invite', target: arg });
        return true;
      }
      case '/leave':
        this.ws.send({ type: 'group_leave' });
        return true;
      case '/disband':
        this.ws.send({ type: 'group_disband' });
        return true;
      case '/kick': {
        if (!arg) { this._localError('Spielernamen angeben: /kick Name'); return true; }
        this.ws.send({ type: 'group_kick', target: arg });
        return true;
      }
      case '/promote':
      case '/prom': {
        if (!arg) { this._localError('Spielernamen angeben: /promote Name'); return true; }
        this.ws.send({ type: 'group_promote', target: arg });
        return true;
      }
      case '/lead': {
        if (!arg) { this._localError('Spielernamen angeben: /lead Name'); return true; }
        this.ws.send({ type: 'group_transfer_leader', target: arg });
        return true;
      }
      case '/party':
        this.ws.send({ type: 'group_create_party' });
        return true;
      case '/raid':
      case '/raid20':
        this.ws.send({ type: 'group_convert_to_raid', kind: 'raid_small' });
        return true;
      case '/raid40':
      case '/largeraid':
        this.ws.send({ type: 'group_convert_to_raid', kind: 'raid_large' });
        return true;
      case '/p':
      case '/r':
      case '/g': {
        if (!arg) { this._localError(`${cmd} TEXT — Nachricht an die Gruppe`); return true; }
        this.ws.send({ type: 'group_chat', text: arg });
        return true;
      }
      case '/lootrule': {
        const rule = arg.toLowerCase();
        if (!['ffa', 'need_greed'].includes(rule)) {
          this._localError('/lootrule ffa | need_greed');
          return true;
        }
        this.ws.send({ type: 'set_loot_rule', rule });
        return true;
      }
      case '/raidstart':
      case '/triggerraid': {
        const tier = parseInt(arg, 10) || 1;
        if (tier < 1 || tier > 5) {
          this._localError('/raidstart TIER — TIER 1..5');
          return true;
        }
        this.ws.send({ type: 'raid_trigger_manual', tier });
        return true;
      }
      case '/help':
        this.state.appendChat({
          kind: 'system',
          text:
            '/invite Name · /leave · /kick Name · /promote Name · /lead Name · /disband · ' +
            '/party · /raid (→20) · /raid40 · /p TEXT (Gruppen-Chat) · ' +
            '/raidstart 1..5 (manuelle Raid-Welle) · /lootrule ffa|need_greed',
        });
        return true;
    }
    return false;
  }

  private _localError(msg: string): void {
    this.state.appendChat({ kind: 'error', text: msg });
  }
}
