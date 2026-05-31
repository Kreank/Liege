// MobTooltipComponent — globaler Hover-/Klick-Tooltip für NPCs auf der Welt-
// Karte (H3.8 — Welle H3-C).
//
// Spiegel zum ItemTooltipComponent: liest `TooltipService.activeMob`, rendert
// die Mob-Info am gemerkten (x,y). Inhalt:
//   • Anzeige-Name (NPC.name oder Lookup über NPC_SPRITE.label)
//   • Kind (technischer Slug)
//   • HP / Max-HP (falls Backend liefert)
//   • Tier-Anzeige (T1-T5) — Schwierigkeits-Indikator
//   • Level-Anzeige (falls vorhanden)
//   • Gruppen-Buff-Hinweis wenn `scaled_for_party_size`/`scaled_hp_pct`
//     gesetzt sind (future-proof; aktuell liefert das Backend das noch nicht).
//
// Wird in app.html eingebunden (Subagent D — siehe Antwort an Lead).
// Triggert wird der Tooltip aus der WorldScene (Phaser → setInteractive auf
// NPC-Sprites) und vom Bestiary-Panel im UI-Layer.

import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
} from '@angular/core';

import { NPC_SPRITE } from '../../core/data/npc-sprites';
import { TooltipService } from '../../core/services/tooltip.service';

/** Tier → Farbe (Anlehnung an WoW-Item-Quality, aber tiefer gesättigt
 *  damit es vor dunklem Spielfeld lesbar bleibt). T1=grün ungefährlich,
 *  T5=rot tödlich. */
const TIER_COLOR: Readonly<Record<number, string>> = {
  1: '#74c365',
  2: '#a3b94b',
  3: '#e7c44b',
  4: '#e87f3a',
  5: '#d94545',
};

@Component({
  selector: 'app-mob-tooltip',
  standalone: true,
  templateUrl: './mob-tooltip.component.html',
  styleUrl: './mob-tooltip.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MobTooltipComponent {
  private readonly tooltip = inject(TooltipService);

  readonly payload = computed(() => this.tooltip.activeMob());
  readonly visible = computed<boolean>(() => this.payload() !== null);
  readonly pinned = computed<boolean>(() => this.payload()?.pinned ?? false);

  /** Anzeige-Name: NPC.name (Individual) bevorzugt, sonst NPC_SPRITE-Label,
   *  sonst kind als Fallback. */
  readonly displayName = computed<string>(() => {
    const p = this.payload();
    if (!p) return '';
    const n = p.npc;
    if (n.name) return n.name;
    const meta = NPC_SPRITE[n.kind];
    return meta?.label ?? n.kind;
  });

  /** Kind-Slug — als Sekundärzeile, nur wenn er sich vom displayName
   *  unterscheidet (Individual-Namen). */
  readonly kindLabel = computed<string | null>(() => {
    const p = this.payload();
    if (!p) return null;
    const n = p.npc;
    if (!n.name) return null; // displayName ist eh schon der kind-Label
    const meta = NPC_SPRITE[n.kind];
    return meta?.label ?? n.kind;
  });

  readonly hpText = computed<string | null>(() => {
    const p = this.payload();
    if (!p) return null;
    const { hp, max_hp } = p.npc;
    if (hp == null || max_hp == null) return null;
    return `${hp} / ${max_hp}`;
  });

  readonly tier = computed<number | null>(() => this.payload()?.npc.tier ?? null);
  readonly tierColor = computed<string>(() => {
    const t = this.tier();
    return t != null ? TIER_COLOR[t] ?? '#c8b88a' : '#c8b88a';
  });
  readonly level = computed<number | null>(() => this.payload()?.npc.level ?? null);

  /** „(+25 % HP für 3er-Gruppe)" — nur wenn beide Felder vorhanden. */
  readonly scalingLabel = computed<string | null>(() => {
    const p = this.payload();
    if (!p) return null;
    const partySize = p.npc.scaled_for_party_size;
    const hpPct = p.npc.scaled_hp_pct;
    if (partySize == null || partySize <= 1) return null;
    if (hpPct != null && hpPct > 0) {
      return `Gruppen-Buff +${hpPct} % HP (für ${partySize}er-Gruppe)`;
    }
    return `Skaliert für ${partySize}er-Gruppe`;
  });

  readonly hostile = computed<boolean>(() => this.payload()?.npc.hostile === true);

  readonly positionStyle = computed<{ left: string; top: string }>(() => {
    const p = this.payload();
    if (!p) return { left: '-9999px', top: '-9999px' };
    const winW = typeof window !== 'undefined' ? window.innerWidth : 1024;
    const left = Math.min(winW - 260, p.x + 14);
    const top = Math.max(10, p.y - 8);
    return { left: left + 'px', top: top + 'px' };
  });

  closePinned(): void { this.tooltip.unpin(); }
}
