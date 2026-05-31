// HudComponent — kompaktes Heads-Up-Display, das links über dem Phaser-Canvas
// hängt: HP / Mana / Hunger / Durst / Ausdauer plus Koordinaten und
// Connection-Status. Read-only — bindet nur an Signals, sendet keine Intents.
//
// Wave H1-C erweitert das HUD um:
//   • H1.3  Status-Effects-Reihe (Icons + Resttdauer-Countdown)
//   • H1.4  Wallet-HUD (Gold / Silber / Kupfer aus raw `wallet_copper`)
//   • H1.16 Disaster-Icons (oben Mitte, Tooltip mit Disaster-Kind-Label)
//   • H1.19 Uhr (Tag X · HH:MM + Phase-Icon)
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • DOM-Stub:   `index.html` Z. 28-36 (`#ui` + `#status`),
//                 Z. 99-112 (HP/Mana/Hunger/Thirst/Stamina-Bars),
//                 Z. 119-125 (Wallet),
//                 Z. 138-144 (Status-Effects-Row).
//   • Renderer:   `app.js` `updateUI`, `updateHpBar`, `updateNeedsBar`,
//                 `updateConnStatus`, `_updateBar`,
//                 `updateWalletHud`, `updateStatusEffectsRow`,
//                 `updateTimeHud`, `updateDisasterHud` (Z. ~3500-4100).
//   • Styles:     `style.css` Z. 13-66 (Bars-Layout/Farben),
//                 Z. 22-25 (`#status`-Position).
//
// Signal-Inputs (aus GameStateService):
//   • `player()`         — hp, max_hp, mana, max_mana, hunger, ..., x, y
//   • `statusEffects()`  — readonly StatusEffect[]
//   • `walletCopper()`   — number (raw copper)
//   • `time()`           — TimeSnapshot {day, hour, minute, phase, is_blood_moon}
//   • `activeDisasters()`— ReadonlySet<string> der aktiven Disaster-Kinds
//   • `ws.status()`      — 'connecting'|'open'|'closed'|'reconnecting'
//
// Architektur: alle abgeleiteten Werte als `computed()`, keine eigenen Timer
// oder RAF-Loops im Component. Resttdauer der Status-Effects wird statisch aus
// `remaining_ms` zur Render-Zeit umgerechnet — Backend sendet Updates beim
// `status_effects`-Frame, das reicht für ein Sekunden-genaues Display.

import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';

import { EFFECT_SPRITES } from '../../core/data/effect-sprites';
import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';
import type { StatusEffect } from '../../core/models/player.model';
import type { ConnectionStatus } from '../../core/models/ws-message.model';

interface BarView {
  readonly cur: number;
  readonly max: number;
  readonly pct: number;
  readonly label: string;
}

/** Wallet aufgesplittet in g/s/c (100c = 1s, 100s = 1g). */
interface WalletView {
  readonly gold: number;
  readonly silver: number;
  readonly copper: number;
  readonly totalCopper: number;
}

/** Eine Status-Effect-Zeile fürs HUD (vollständig aufbereitet). */
interface StatusEffectView {
  readonly id: string;
  readonly kind: string;
  readonly label: string;
  readonly iconUrl: string | null;
  /** "12s" / "1m20" / undefined wenn permanent. */
  readonly remainingLabel: string | undefined;
  readonly stacks: number | undefined;
}

/** Eine Disaster-Icon-Zeile fürs HUD. */
interface DisasterView {
  readonly kind: string;
  readonly label: string;
  readonly iconUrl: string | null;
}

/** Uhr-Komposition fürs Time-Widget. */
interface ClockView {
  readonly day: number;
  readonly hhmm: string;
  readonly phaseIcon: string;
  readonly bloodMoon: boolean;
}

const CONN_LABEL: Readonly<Record<ConnectionStatus, string>> = {
  connecting: 'Verbinde…',
  open: 'Verbunden',
  reconnecting: 'Reconnect…',
  closed: 'Getrennt',
};

/** Status-Effect-Kind → Deutsches Label (Fallback: kind). Wir spiegeln die
 *  bekannten Backend-Effekte (sync mit backend/effects.py STATUS_EFFECTS). */
const STATUS_EFFECT_LABEL: Readonly<Record<string, string>> = {
  poisoned: 'Vergiftet',
  burning: 'Brennend',
  frozen: 'Eingefroren',
  blessed: 'Gesegnet',
  cursed: 'Verflucht',
  stunned: 'Betäubt',
  bleeding: 'Blutung',
  well_rested: 'Ausgeruht',
  heal_over_time: 'Heilung',
  haste: 'Hast',
  slowed: 'Verlangsamt',
  shielded: 'Geschützt',
  drunk: 'Betrunken',
};

/** Status-Effect-Kind → EFFECT_SPRITES-Key. Wenn kein direkter Match, dann
 *  via Heuristik: kind selbst, dann `<kind>_cloud`, dann `<kind>_aura`. */
const STATUS_EFFECT_ICON_MAP: Readonly<Record<string, string>> = {
  poisoned: 'poison_cloud',
  burning: 'fireball_explosion',
  frozen: 'ice_impact',
  blessed: 'holy_shield_aura',
  shielded: 'holy_shield_aura',
  heal_over_time: 'heal_glow',
  cursed: 'magic_circle',
  bleeding: 'hit_spark',
};

/** Disaster-Kind → Deutsches UI-Label (sync mit GameStateService-Helper). */
const DISASTER_LABEL: Readonly<Record<string, string>> = {
  bloodmoon: 'Blutmond',
  dying_sun: 'Sterbende Sonne',
  thunderstorm: 'Gewittersturm',
  scorching_heat: 'Sengende Hitze',
  ash_rain: 'Aschenregen',
  wildfire: 'Waldbrand',
  pestilence: 'Pestilenz',
  locust_swarm: 'Heuschreckenschwarm',
  toxic_fog: 'Giftnebel',
};

/** Disaster-Kind → EFFECT_SPRITES-Key. */
const DISASTER_ICON_MAP: Readonly<Record<string, string>> = {
  bloodmoon: 'magic_circle',
  dying_sun: 'fireball_explosion',
  thunderstorm: 'lightning_strike',
  scorching_heat: 'disaster_scorching_heat',
  ash_rain: 'disaster_ash_rain',
  wildfire: 'disaster_forest_fire',
  pestilence: 'disaster_toxic_fog',
  locust_swarm: 'disaster_locust_swarm',
  toxic_fog: 'disaster_toxic_fog',
};

/** Phase → Emoji. Bloodmoon wird im Template separat behandelt (rot getintet). */
const PHASE_ICON: Readonly<Record<string, string>> = {
  dawn:  '🌅',
  day:   '☀️',
  dusk:  '🌇',
  night: '🌙',
};

@Component({
  selector: 'app-hud',
  standalone: true,
  templateUrl: './hud.component.html',
  styleUrl: './hud.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HudComponent {
  private readonly state = inject(GameStateService);
  private readonly ws = inject(WebSocketService);

  readonly visible = computed(() => this.state.player() !== null);

  readonly hp = computed<BarView>(() => this._bar(
    this.state.player()?.hp, this.state.player()?.max_hp,
  ));
  readonly mana = computed<BarView>(() => this._bar(
    this.state.player()?.mana, this.state.player()?.max_mana,
  ));
  readonly hunger = computed<BarView>(() => this._bar(
    this.state.player()?.hunger, this.state.player()?.max_hunger,
  ));
  readonly thirst = computed<BarView>(() => this._bar(
    this.state.player()?.thirst, this.state.player()?.max_thirst,
  ));
  readonly stamina = computed<BarView>(() => this._bar(
    this.state.player()?.stamina, this.state.player()?.max_stamina,
  ));

  readonly coords = computed<string>(() => {
    const p = this.state.player();
    if (!p) return 'x:0 y:0';
    return `x:${Math.round(p.x)} y:${Math.round(p.y)}`;
  });

  readonly connStatus = computed<{ readonly label: string; readonly kind: ConnectionStatus }>(() => {
    const s = this.ws.status();
    return { label: CONN_LABEL[s] ?? s, kind: s };
  });

  // ─── H1.3 — Status-Effects ────────────────────────────────────────────

  readonly statusEffects = computed<readonly StatusEffectView[]>(() => {
    const effects = this.state.statusEffects();
    return effects.map((e) => this._effectView(e));
  });

  // ─── H1.4 — Wallet ────────────────────────────────────────────────────

  readonly wallet = computed<WalletView>(() => {
    const total = Math.max(0, Math.floor(this.state.walletCopper()));
    const gold = Math.floor(total / 10000);
    const silver = Math.floor((total % 10000) / 100);
    const copper = total % 100;
    return { gold, silver, copper, totalCopper: total };
  });

  // ─── H1.19 — Uhr / Time ───────────────────────────────────────────────

  readonly clock = computed<ClockView | null>(() => {
    const t = this.state.time();
    if (!t) return null;
    const hh = String(Math.max(0, Math.min(23, Math.floor(t.hour)))).padStart(2, '0');
    const mm = String(Math.max(0, Math.min(59, Math.floor(t.minute)))).padStart(2, '0');
    const phase = t.phase ?? this._phaseFromHour(t.hour);
    return {
      day: Math.max(1, Math.floor(t.day)),
      hhmm: `${hh}:${mm}`,
      phaseIcon: PHASE_ICON[phase] ?? '⏱',
      bloodMoon: t.is_blood_moon === true,
    };
  });

  // ─── H1.16 — Disaster-Icons ───────────────────────────────────────────

  readonly disasters = computed<readonly DisasterView[]>(() => {
    const active = this.state.activeDisasters();
    return [...active].map((kind) => ({
      kind,
      label: DISASTER_LABEL[kind] ?? kind,
      iconUrl: this._lookupIcon(DISASTER_ICON_MAP[kind] ?? `disaster_${kind}`)
        ?? this._lookupIcon(kind),
    }));
  });

  // ─── Helpers ──────────────────────────────────────────────────────────

  private _bar(cur: number | undefined, max: number | undefined): BarView {
    const c = cur ?? 0;
    const m = Math.max(1, max ?? 0);
    const pct = Math.max(0, Math.min(100, Math.round((c / m) * 100)));
    return { cur: Math.round(c), max: Math.round(m), pct, label: `${Math.round(c)} / ${Math.round(m)}` };
  }

  private _effectView(e: StatusEffect): StatusEffectView {
    const kind = e.kind;
    const label = e.label ?? STATUS_EFFECT_LABEL[kind] ?? kind;
    const iconKey =
      STATUS_EFFECT_ICON_MAP[kind] ??
      (EFFECT_SPRITES[kind] ? kind : undefined) ??
      (EFFECT_SPRITES[`${kind}_cloud`] ? `${kind}_cloud` : undefined) ??
      (EFFECT_SPRITES[`${kind}_aura`] ? `${kind}_aura` : undefined);
    const iconUrl = iconKey ? EFFECT_SPRITES[iconKey] ?? null : null;
    return {
      id: e.id,
      kind,
      label,
      iconUrl,
      remainingLabel: this._fmtRemaining(e.remaining_ms),
      stacks: e.stacks && e.stacks > 1 ? e.stacks : undefined,
    };
  }

  private _lookupIcon(key: string | undefined): string | null {
    if (!key) return null;
    return EFFECT_SPRITES[key] ?? null;
  }

  private _fmtRemaining(ms: number | undefined): string | undefined {
    if (ms == null || ms <= 0) return undefined;
    const totalS = Math.round(ms / 1000);
    if (totalS < 60) return `${totalS}s`;
    const m = Math.floor(totalS / 60);
    const s = totalS % 60;
    return s === 0 ? `${m}m` : `${m}m${String(s).padStart(2, '0')}`;
  }

  private _phaseFromHour(h: number): 'dawn' | 'day' | 'dusk' | 'night' {
    if (h >= 5 && h < 8)   return 'dawn';
    if (h >= 8 && h < 18)  return 'day';
    if (h >= 18 && h < 21) return 'dusk';
    return 'night';
  }

  trackEffect(_idx: number, e: StatusEffectView): string { return e.id; }
  trackDisaster(_idx: number, d: DisasterView): string { return d.kind; }
}
