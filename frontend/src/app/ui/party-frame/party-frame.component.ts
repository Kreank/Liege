// PartyFrameComponent — Mitglieder-HUD für Party/Raid.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM-Stub:  `index.html` Z. 38-51 (`#party-frame`).
//   • Renderer:  `app.js` `refreshPartyFrame` (Z. ~6784-6837).
//   • Styles:    `style.css` Z. 1657-1726, Mobile-Block Z. 1778-1782.
//
// Backend-Vertrag (`backend/groups.py::group_snapshot`):
//   { id, kind, leader, name, loot_rule, your_role,
//     members: [{name, role, sub_party, online, x, y}] }
//
// Sendet:
//   • `raid_trigger_manual` (Leader-Button → öffnet RaidSelector — siehe
//     F12). Hier reicht ein Output-Event, der Raid-Selector-Overlay
//     öffnet — Toggle steuert die Schwestern-Komponente via Service.
//
// Keine eigene Tastatur-Bindung (Frame ist permanent sichtbar, sobald
// man in einer Gruppe ist).

import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Output,
  computed,
  inject,
} from '@angular/core';

import type { Group, GroupKind, GroupMember } from '../../core/models/group.model';
import { GameStateService } from '../../core/services/game-state.service';

const KIND_LABEL: Readonly<Record<GroupKind, string>> = {
  party: 'Party',
  raid_small: 'Raid (klein)',
  raid_large: 'Raid (groß)',
};

const KIND_MAX: Readonly<Record<GroupKind, number>> = {
  party: 5,
  raid_small: 20,
  raid_large: 40,
};

interface MemberRow {
  readonly name: string;
  readonly displayName: string;
  readonly role: GroupMember['role'];
  readonly roleSymbol: string;
  readonly online: boolean;
  readonly isYou: boolean;
  readonly subParty: number;
}

interface SubSection {
  readonly subParty: number;
  readonly showHeader: boolean;
  readonly rows: readonly MemberRow[];
}

@Component({
  selector: 'app-party-frame',
  standalone: true,
  templateUrl: './party-frame.component.html',
  styleUrl: './party-frame.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PartyFrameComponent {
  private readonly state = inject(GameStateService);

  /** Wird vom Leader-Button gefeuert. In F12 hängt der RaidSelector-Overlay
   *  daran. */
  @Output() readonly openRaidSelector = new EventEmitter<void>();

  readonly group = computed<Group | null>(() => this.state.party());
  readonly visible = computed<boolean>(() => this.group() !== null);

  readonly title = computed<string>(() => {
    const g = this.group();
    if (!g) return 'Gruppe';
    return KIND_LABEL[g.kind] ?? 'Gruppe';
  });

  readonly countLabel = computed<string>(() => {
    const g = this.group();
    if (!g) return '0/0';
    const max = KIND_MAX[g.kind] ?? g.members.length;
    return `${g.members.length}/${max}`;
  });

  readonly isLeader = computed<boolean>(() => {
    const g = this.group();
    if (!g) return false;
    return g.your_role === 'leader';
  });

  readonly sections = computed<readonly SubSection[]>(() => {
    const g = this.group();
    if (!g) return [];
    const my = this._myName();
    const sorted = [...g.members].sort((a, b) => {
      if (a.sub_party !== b.sub_party) return a.sub_party - b.sub_party;
      return this._roleOrder(a.role) - this._roleOrder(b.role);
    });
    const out: SubSection[] = [];
    let cur: { subParty: number; rows: MemberRow[] } | null = null;
    for (const m of sorted) {
      if (!cur || cur.subParty !== m.sub_party) {
        cur = { subParty: m.sub_party, rows: [] };
        out.push({
          subParty: m.sub_party,
          showHeader: g.kind !== 'party',
          rows: cur.rows,
        });
      }
      cur.rows.push(this._toRow(m, my));
    }
    return out;
  });

  triggerRaid(): void {
    this.openRaidSelector.emit();
  }

  private _toRow(m: GroupMember, my: string | null): MemberRow {
    const isYou = my !== null && m.name === my;
    const short = m.name.length > 16 ? m.name.slice(0, 16) : m.name;
    const display = isYou ? `${m.name.slice(0, 12)} (Du)` : short;
    return {
      name: m.name,
      displayName: display,
      role: m.role,
      roleSymbol: m.role === 'leader' ? '★' : m.role === 'assist' ? '◆' : '·',
      online: m.online,
      isYou,
      subParty: m.sub_party,
    };
  }

  private _roleOrder(r: GroupMember['role']): number {
    if (r === 'leader') return 0;
    if (r === 'assist') return 1;
    return 2;
  }

  private _myName(): string | null {
    const p = this.state.player();
    if (!p) return null;
    // Backend liefert `player_id` als String mit dem Spieler-Namen — der TS-
    // Type sagt `number`, an dieser Stelle ist es zur Laufzeit der Name.
    // Wir casten defensiv über String() — vergleichbar mit dem Legacy
    // `MY_ID`-Vergleich.
    return String(p.player_id);
  }
}
