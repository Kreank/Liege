// GroupInviteComponent — Pop-up für eingehende Gruppen-Einladungen.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM:     `index.html` Z. 85-95 (`#group-invite-overlay`).
//   • Renderer: `app.js` `showGroupInvite`, `hideGroupInvite` (~6897-6932).
//   • Styles:  `style.css` Z. 1692-1715.
//
// Backend: `group_invite_received` (ws/social.py) liefert
//   { type, invite_id, group_id, from, kind, expires_at }.
//
// Sendet: `group_accept { invite_id }` oder `group_decline { invite_id }`.
//
// State: `partyInvites`-Signal aus GameStateService. Wir zeigen IMMER nur
// die älteste pending Einladung — Legacy verhielt sich identisch (ein
// Overlay zur Zeit). Nach Reaktion wird sie via `consumeInvite()` entfernt
// und das Overlay fällt auf die nächste pending Einladung zurück oder
// schließt sich.

import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
} from '@angular/core';

import type { GroupInvite } from '../../core/models/group.model';
import type { ClientIntent } from '../../core/models/ws-message.model';
import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';

const KIND_LABEL: Readonly<Record<GroupInvite['kind'], string>> = {
  party: 'Party',
  raid_small: 'kleiner Raid-Gruppe',
  raid_large: 'großer Raid-Gruppe',
};

@Component({
  selector: 'app-group-invite',
  standalone: true,
  templateUrl: './group-invite.component.html',
  styleUrl: './group-invite.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GroupInviteComponent {
  private readonly state = inject(GameStateService);
  private readonly ws = inject(WebSocketService);

  readonly invite = computed<GroupInvite | null>(() => {
    const inv = this.state.partyInvites();
    return inv.length > 0 ? inv[0] : null;
  });

  readonly visible = computed<boolean>(() => this.invite() !== null);

  readonly kindLabel = computed<string>(() => {
    const inv = this.invite();
    if (!inv) return 'Gruppe';
    return KIND_LABEL[inv.kind] ?? 'Gruppe';
  });

  accept(): void {
    const inv = this.invite();
    if (!inv) return;
    const intent: ClientIntent = { type: 'group_accept', invite_id: inv.invite_id };
    this.ws.send(intent);
    this.state.consumeInvite(inv.invite_id);
  }

  decline(): void {
    const inv = this.invite();
    if (!inv) return;
    const intent: ClientIntent = { type: 'group_decline', invite_id: inv.invite_id };
    this.ws.send(intent);
    this.state.consumeInvite(inv.invite_id);
  }
}
