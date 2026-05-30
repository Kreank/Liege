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
//   • Client → `character_create      { name, preset }`
//   • Server → `character_created { ... }` + neues `init` mit
//             `needs_character_creation: false` → das `needsCharacterCreation`-
//             Signal flippt automatisch auf false → `visible` wird false.
//
// Presets stammen 1:1 aus `PRESET_WALK_CFG` (core/data/npc-sprites.ts) — die
// 6 vom Asset-Loader vorgeladenen Walk-Cycles. Andere Werte würde der Renderer
// auf `wanderer_cloak` (Default) zurückfallen lassen, also bieten wir nur die
// echten 6 zur Auswahl an.

import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  signal,
} from '@angular/core';

import { GameStateService } from '../../core/services/game-state.service';
import { WebSocketService } from '../../core/services/websocket.service';

interface PresetOption {
  readonly key: string;
  readonly label: string;
  readonly preview: string;
}

const PRESETS: ReadonlyArray<PresetOption> = [
  { key: 'wanderer_cloak', label: 'Wanderer',     preview: '/assets/animations/player_presets/wanderer_cloak/idle_1.png' },
  { key: 'ember_mage',     label: 'Glutmagier',   preview: '/assets/animations/player_presets/ember_mage/idle_1.png' },
  { key: 'iron_delver',    label: 'Eisengräber',  preview: '/assets/animations/player_presets/iron_delver/idle_1.png' },
  { key: 'knife_runner',   label: 'Klingenläufer', preview: '/assets/animations/player_presets/knife_runner/idle_1.png' },
  { key: 'shieldbearer',   label: 'Schildträger', preview: '/assets/animations/player_presets/shieldbearer/idle_1.png' },
  { key: 'wild_ranger',    label: 'Wildhüter',    preview: '/assets/animations/player_presets/wild_ranger/idle_1.png' },
];

type NameStatus = 'idle' | 'checking' | 'ok' | 'taken' | 'invalid';

const MIN_NAME_LEN = 3;
const MAX_NAME_LEN = 24;
/** Client-seitige Vor-Validierung (Backend macht autoritativ noch eine eigene). */
const NAME_RE = /^[A-Za-zÄÖÜäöüß0-9_\- ]+$/;

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

  readonly presets: ReadonlyArray<PresetOption> = PRESETS;

  /** Submit nur wenn Name vom Server bestätigt UND wir nicht gerade senden. */
  readonly canSubmit = computed<boolean>(
    () => this.nameStatus() === 'ok' && !this.creating(),
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
    this.ws.send({ type: 'character_check_name', name: trimmed });
  }

  selectPreset(key: string): void {
    this.selectedPreset.set(key);
  }

  createCharacter(): void {
    if (!this.canSubmit()) return;
    this.creating.set(true);
    this.ws.send({
      type: 'character_create',
      name: this.name(),
      preset: this.selectedPreset(),
    });
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
}
