// CharacterCreateComponent — Erst-Login-Pflicht-Modal.
//
// Beim ersten Verbinden eines neuen Accounts schickt das Backend in der
// `init`-Payload `needs_character_creation: true`. Solange dieses Flag
// gesetzt ist, kann der Spieler weder laufen noch interagieren — also blockt
// das Modal alle anderen Panels (z-index 9999, kein Schließen-Button).
//
// Backend-Vertrag (siehe ws/character.py):
//   • Client → `character_check_name { name }`
//   • Server → `character_name_check  { name, available, reason }`
//   • Client → `character_create      { name, preset, allocated? }`
//     - `allocated` (optional dict): Pre-Allocation der Initial-Pool-Punkte.
//       Backend akzeptiert das Feld; nicht-allokierte Punkte bleiben im
//       `unspent`-Pool und können später via `allocate_attr` verteilt werden.
//   • Server → `character_created { ... }` + neues `init` mit
//             `needs_character_creation: false` → das `needsCharacterCreation`-
//             Signal flippt automatisch auf false → `visible` wird false.
//
// Presets stammen 1:1 aus `PRESET_WALK_CFG` (core/data/npc-sprites.ts) — die
// 6 vom Asset-Loader vorgeladenen Walk-Cycles. Andere Werte würde der Renderer
// auf `wanderer_cloak` (Default) zurückfallen lassen, also bieten wir nur die
// echten 6 zur Auswahl an.
//
// Step-Flow (H1.1, 2026-05-31):
//   Step 1 — Name + Preset.    [„Weiter" → Step 2]
//   Step 2 — Attribute (6×).    [„Charakter erstellen" → submit + close]
// Pool defaultet auf 5 Punkte (Backend-Default in services/player_state.py);
// nicht-verteilte Punkte landen im server-seitigen `unspent`-Pool und bleiben
// nach dem Modal-Close im Character-Panel (Taste C) für später verfügbar.

import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';

import type { PlayerAttributes } from '../../core/models/player.model';
import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';

interface PresetOption {
  readonly key: string;
  readonly label: string;
  readonly preview: string;
}

interface AttrMeta {
  readonly key: keyof Omit<PlayerAttributes, 'unspent'>;
  readonly label: string;
  readonly desc: string;
}

const PRESETS: ReadonlyArray<PresetOption> = [
  { key: 'wanderer_cloak', label: 'Wanderer',     preview: '/assets/animations/player_presets/wanderer_cloak/idle_1.png' },
  { key: 'ember_mage',     label: 'Glutmagier',   preview: '/assets/animations/player_presets/ember_mage/idle_1.png' },
  { key: 'iron_delver',    label: 'Eisengräber',  preview: '/assets/animations/player_presets/iron_delver/idle_1.png' },
  { key: 'knife_runner',   label: 'Klingenläufer', preview: '/assets/animations/player_presets/knife_runner/idle_1.png' },
  { key: 'shieldbearer',   label: 'Schildträger', preview: '/assets/animations/player_presets/shieldbearer/idle_1.png' },
  { key: 'wild_ranger',    label: 'Wildhüter',    preview: '/assets/animations/player_presets/wild_ranger/idle_1.png' },
];

const ATTR_META: ReadonlyArray<AttrMeta> = [
  { key: 'strength',     label: '💪 Stärke',       desc: 'Schaden + Tragelast' },
  { key: 'dexterity',    label: '🎯 Geschick',     desc: 'Crit + Angriffstempo' },
  { key: 'intelligence', label: '🧠 Intelligenz',  desc: 'Manapool + Zauber' },
  { key: 'constitution', label: '❤️ Konstitution', desc: 'HP + Ausdauer' },
  { key: 'wisdom',       label: '🕯️ Weisheit',     desc: 'Mana-Regen + Resistenzen' },
  { key: 'charisma',     label: '🎭 Charisma',     desc: 'Preise + Quests' },
];

type NameStatus = 'idle' | 'checking' | 'ok' | 'taken' | 'invalid';

const MIN_NAME_LEN = 3;
const MAX_NAME_LEN = 24;
/** Default-Pool, falls Backend-Init `attributes.unspent` nicht liefert.
 *  Hartcodiert auf 5 weil das der Backend-Default in services/player_state.py
 *  ist (siehe `INITIAL_UNSPENT_POINTS`). */
const DEFAULT_POOL = 5;
/** Client-seitige Vor-Validierung (Backend macht autoritativ noch eine eigene). */
const NAME_RE = /^[A-Za-zÄÖÜäöüß0-9_\- ]+$/;

type AttrKey = AttrMeta['key'];
type AllocationMap = Readonly<Record<AttrKey, number>>;

const EMPTY_ALLOC: AllocationMap = {
  strength: 0,
  dexterity: 0,
  intelligence: 0,
  constitution: 0,
  wisdom: 0,
  charisma: 0,
};

@Component({
  selector: 'app-character-create',
  standalone: true,
  templateUrl: './character-create.component.html',
  styleUrl: './character-create.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CharacterCreateComponent {
  private readonly state = inject(GameStateService);
  private readonly ws = inject(WebSocketService);

  /** Sichtbar solange der Server `needs_character_creation: true` meldet.
   *  Wird durch das nächste `init` (nach `character_created`) automatisch
   *  unsichtbar — kein manuelles Schließen nötig (und auch nicht erlaubt). */
  readonly visible = computed<boolean>(() => this.state.needsCharacterCreation());

  readonly name = signal<string>('');
  readonly nameStatus = signal<NameStatus>('idle');
  readonly nameError = signal<string>('');
  readonly selectedPreset = signal<string>(PRESETS[0].key);
  readonly creating = signal<boolean>(false);

  /** Step 1 = Name+Preset, Step 2 = Attribute. */
  readonly step = signal<1 | 2>(1);

  /** Pro-Attribut allokierte Bonus-Punkte (zusätzlich zum Backend-Baseline).
   *  Werden mit `character_create` mitgeschickt; Server validiert die Summe
   *  gegen `unspent` und ignoriert Überzüge. */
  readonly allocated = signal<AllocationMap>(EMPTY_ALLOC);

  /** Backend liefert im `init`-Frame ggf. `attributes.unspent` — wir lesen
   *  das, sonst Default 5. Liest reaktiv: wenn der `init`-Frame mit Pool
   *  noch nachkommt, springt das Modal automatisch an. */
  readonly pool = computed<number>(() => {
    const a = this.state.attributes() ?? this.state.player()?.attributes ?? null;
    return a?.unspent ?? DEFAULT_POOL;
  });

  readonly spent = computed<number>(() => {
    const a = this.allocated();
    return ATTR_META.reduce((sum, m) => sum + (a[m.key] ?? 0), 0);
  });

  readonly remaining = computed<number>(() => this.pool() - this.spent());

  readonly attrMeta: ReadonlyArray<AttrMeta> = ATTR_META;
  readonly presets: ReadonlyArray<PresetOption> = PRESETS;

  /** Submit nur wenn Name vom Server bestätigt UND wir nicht gerade senden. */
  readonly canProceed = computed<boolean>(
    () => this.nameStatus() === 'ok' && !this.creating(),
  );

  readonly canSubmit = computed<boolean>(
    () => this.canProceed() && this.step() === 2 && this.remaining() >= 0,
  );

  constructor() {
    // Lifetime: Component lebt root-singleton-artig (durch app.html immer
    // gerendert). Subscribe ohne explizites Unsubscribe ist hier okay.
    this.ws.messages$.subscribe((msg) => {
      if (msg.type === 'character_name_check') {
        const checkedName = msg['name'] as string | undefined;
        // Nur Antwort akzeptieren, die zum aktuell getippten Namen passt —
        // sonst überschreibt eine späte Antwort ein neueres Edit.
        if (checkedName && checkedName !== this.name()) return;
        const available = msg['available'] === true;
        if (available) {
          this.nameStatus.set('ok');
          this.nameError.set('');
        } else {
          this.nameStatus.set('taken');
          this.nameError.set(
            (msg['reason'] as string | undefined) ?? 'Name nicht verfügbar',
          );
        }
      } else if (msg.type === 'character_created') {
        // Kein State-Reset hier — das neue `init` setzt `needs_character_creation`
        // auf false und das Modal verschwindet von alleine. Wir lassen das
        // creating-Flag nur fallen, damit der Submit-Button beim nächsten Open
        // (theoretisch) wieder benutzbar wäre.
        this.creating.set(false);
      }
    });
  }

  onNameInput(value: string): void {
    const trimmed = value.trim();
    this.name.set(trimmed);
    this.nameError.set('');
    if (trimmed.length === 0) {
      this.nameStatus.set('idle');
      return;
    }
    if (trimmed.length < MIN_NAME_LEN) {
      this.nameStatus.set('invalid');
      this.nameError.set(`Mindestens ${MIN_NAME_LEN} Zeichen`);
      return;
    }
    if (trimmed.length > MAX_NAME_LEN) {
      this.nameStatus.set('invalid');
      this.nameError.set(`Höchstens ${MAX_NAME_LEN} Zeichen`);
      return;
    }
    if (!NAME_RE.test(trimmed)) {
      this.nameStatus.set('invalid');
      this.nameError.set('Nur Buchstaben, Zahlen, Leer-, Binde- und Unterstrich.');
      return;
    }
    this.nameStatus.set('checking');
    // Backend liest `display_name`; `name` als Alias mitsenden für robust.
    this.ws.send({ type: 'character_check_name', display_name: trimmed, name: trimmed });
  }

  selectPreset(key: string): void {
    this.selectedPreset.set(key);
  }

  proceedToStep2(): void {
    if (!this.canProceed()) return;
    this.step.set(2);
  }

  backToStep1(): void {
    this.step.set(1);
  }

  adjust(key: AttrKey, delta: number): void {
    const cur = this.allocated();
    const next = (cur[key] ?? 0) + delta;
    if (next < 0) return;
    if (delta > 0 && this.remaining() <= 0) return;
    this.allocated.set({ ...cur, [key]: next });
  }

  resetAllocation(): void {
    this.allocated.set(EMPTY_ALLOC);
  }

  createCharacter(): void {
    if (!this.canSubmit()) return;
    this.creating.set(true);
    // Allokation nur senden, wenn der Spieler mind. 1 Punkt verteilt hat.
    // Backend akzeptiert das Feld auch leer/missing — kein Pflichtfeld.
    const alloc = this.allocated();
    if (this.spent() > 0) {
      this.ws.send({
        type: 'character_create',
        display_name: this.name(),
        name: this.name(),
        preset: this.selectedPreset(),
        allocated: { ...alloc },
      });
    } else {
      this.ws.send({
        type: 'character_create',
        display_name: this.name(),
        name: this.name(),
        preset: this.selectedPreset(),
      });
    }
  }

  /** Icon neben dem Namensfeld — kompakte visuelle Statusrückmeldung. */
  statusIcon(): string {
    switch (this.nameStatus()) {
      case 'ok':       return '✓';
      case 'checking': return '⏳';
      case 'taken':
      case 'invalid':  return '✗';
      default:         return '';
    }
  }

  /** Template-Helper — liest aktuellen Allokations-Wert für ein Attribut. */
  valueOf(key: AttrKey): number {
    return this.allocated()[key] ?? 0;
  }
}
