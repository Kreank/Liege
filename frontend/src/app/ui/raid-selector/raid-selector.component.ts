// RaidSelectorComponent — 5-Stufen-Tier-Selektor für Raids.
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM:     `index.html` Z. 67-83.
//   • Renderer: `app.js` `openRaidSelector`, `closeRaidSelector` (~6839ff).
//   • Styles:  `style.css` Z. 1751-1776.
//
// Backend: `raid_trigger_manual { tier: 1..5 }` →
//   broadcast `raid_started` an Gruppe, oder `raid_error { reason }`.
//
// Toggle: das Overlay wird von außen via `visible`-Input gesteuert
// (App-Component hört auf `openRaidSelector`-Event aus PartyFrame).

import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  HostListener,
  Input,
  Output,
  inject,
} from '@angular/core';

import type { ClientIntent } from '../../core/models/ws-message.model';
import { WebSocketService } from '../../core/services/websocket.service';

interface RaidTier {
  readonly tier: number;
  readonly label: string;
}

const TIERS: readonly RaidTier[] = [
  { tier: 1, label: 'T1 · Plünderer-Welle · 5 Mobs' },
  { tier: 2, label: 'T2 · Räuber-Bande · 10 Mobs · 5% Boss' },
  { tier: 3, label: 'T3 · Stamm-Überfall · 15 Mobs · 15% Boss' },
  { tier: 4, label: 'T4 · Kriegszug · 20 Mobs · 25% Boss' },
  { tier: 5, label: 'T5 · Belagerung · 30 Mobs · 40% Boss' },
];

@Component({
  selector: 'app-raid-selector',
  standalone: true,
  templateUrl: './raid-selector.component.html',
  styleUrl: './raid-selector.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RaidSelectorComponent {
  private readonly ws = inject(WebSocketService);

  @Input() visible = false;
  @Output() readonly close = new EventEmitter<void>();

  readonly tiers = TIERS;

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.visible) this.close.emit();
  }

  pickTier(tier: number): void {
    const intent: ClientIntent = { type: 'raid_trigger_manual', tier };
    this.ws.send(intent);
    this.close.emit();
  }
}
