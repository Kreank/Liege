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
  OnInit,
  Output,
  inject,
  signal,
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

// Admin-only Dev-Effekte für `dev_trigger_event` (data.effect).
// Spiegelt die ~24 Effekt-Namen aus event_worker._apply_event_effect.
const DEV_EFFECTS: readonly string[] = [
  'spawn_bandits',
  'spawn_spiders',
  'spawn_undead',
  'spawn_elites',
  'spawn_raid',
  'spawn_merchant',
  'spawn_caravan',
  'spawn_invasion:0',
  'ruin_spawn',
  'spawn_ore',
  'spawn_herb',
  'drop_coin',
  'drop_items',
  'blood_moon',
  'dying_sun',
  'damage_structures',
  'taint_water',
  'plague_npcs',
  'destroy_farms',
  'burn_area',
  'thunderstorm',
  'toxic_fog',
  'ash_rain',
  'scorching_heat',
  'frog_plague',
];

interface AuthMeResponse {
  readonly username?: string;
  readonly role?: string;
}

@Component({
  selector: 'app-raid-selector',
  standalone: true,
  templateUrl: './raid-selector.component.html',
  styleUrl: './raid-selector.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RaidSelectorComponent implements OnInit {
  private readonly ws = inject(WebSocketService);

  @Input() visible = false;
  @Output() readonly close = new EventEmitter<void>();

  readonly tiers = TIERS;
  readonly devEffects = DEV_EFFECTS;

  // Admin-Gate für die Dev-Effekt-Sektion (analog top-right-links via /auth/me).
  readonly isAdmin = signal<boolean>(false);

  ngOnInit(): void {
    fetch('/auth/me', { credentials: 'same-origin' })
      .then((r) => (r.ok ? (r.json() as Promise<AuthMeResponse>) : null))
      .then((me) => {
        if (me) this.isAdmin.set(me.role === 'admin');
      })
      .catch(() => {
        // Network-Fehler — Dev-Sektion bleibt ausgeblendet.
      });
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.visible) this.close.emit();
  }

  pickTier(tier: number): void {
    const intent: ClientIntent = { type: 'raid_trigger_manual', tier };
    this.ws.send(intent);
    this.close.emit();
  }

  /** Admin-only: löst sofort einen benannten Dev-Event-/Disaster-Effekt aus.
   *  Server gated zusätzlich (role=='admin'); Antwort kommt als Toast +
   *  indirekte Welt-Broadcasts (alle bereits in game-state behandelt). */
  triggerEvent(effect: string): void {
    const intent: ClientIntent = { type: 'dev_trigger_event', effect };
    this.ws.send(intent);
    this.close.emit();
  }
}
