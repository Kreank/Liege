// MobileControlsComponent — Touch-Joystick (Movement) + Action-Buttons (Menüs).
//
// Quellen aus Legacy (`frontend/legacy/`):
//   • Renderer: `app.js` `setupTouchControls` (Z. 10571-10832), `MobileUI`
//                (Z. 349-368), `window.touchInput` (Z. 9971-9992).
//   • Styles:   `style.css` (Touch-bezogene Regeln rund um `#touch-joystick`,
//                `#touch-actions`).
//
// Aktivierung: nur sichtbar wenn das Gerät Touch beherrscht **oder** der
// Viewport schmal ist (< 768 px). Beides via `effect` auf `window.matchMedia`
// + `resize`-Listener.
//
// Bridge-Intents (über `GameBridgeService`):
//   • Joystick → kontinuierlich `sendMove(tileX, tileY)` zur Ziel-Tile, das
//     der Spieler in der gewählten Richtung erreichen soll. Backend macht
//     die Pfadfindung; das Frontend wirft nur das Ziel-Tile rein.
//
// Action-Buttons toggeln vorhandene Angular-Overlays. Wir dispatchen dafür
// synthetische `keydown`-Events am `document` — die Overlays haben jeweils
// einen `@HostListener('document:keydown')` und reagieren bereits darauf
// (siehe `inventory`, `quests`, `skills`, … in `ui/`). Build-Mode geht
// direkt über `bridge.toggleBuildMode()`.
//
// Letzter Eintrag aus `legacy-stubs.ts` (`TODO F-final: Mobile-Touch-
// Joystick + Action-Buttons`) wird mit dieser Phase abgeräumt.

import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  HostListener,
  OnDestroy,
  ViewChild,
  computed,
  inject,
  signal,
} from '@angular/core';

import { GameBridgeService } from '../../core/services/game-bridge.service';
import { GameStateService } from '../../core/services/game-state.service';

/** Schwellwert ab dem wir Touch-Controls einblenden, wenn kein Touch-Pointer
 *  erkannt wurde (z. B. iPad mit angedocktem Keyboard). */
const NARROW_VIEWPORT_PX = 768;

/** Joystick-Visualisierung: Außenring-Größe in CSS-px, Thumb-Größe in px,
 *  maximaler Auslenk-Radius (~Innenradius des Außenrings minus Thumb-Radius). */
const JOYSTICK_OUTER = 140;
const JOYSTICK_THUMB = 60;
const MAX_RADIUS = 55;
const DEAD_ZONE = MAX_RADIUS * 0.15;

/** Send-Intervall für sendMove während aktivem Joystick (ms). 200 ms ≙ 5×/s —
 *  reicht für ein responsives Gefühl, ohne den Server zu fluten. */
const MOVE_TICK_MS = 200;

/** Wie weit voraus wir das Ziel-Tile aus dem Richtungsvektor projizieren
 *  (Anzahl Tiles). Backend pfadfindet zum gewählten Tile — ein moderat
 *  weites Ziel sorgt für „rolling movement", ohne dass das Pathfind-Cap
 *  greift. */
const MOVE_LOOKAHEAD_TILES = 5;

interface ActionButton {
  readonly label: string;
  readonly title: string;
  /** Toggle via synthetisches Keyboard-Event (key wird von den jeweiligen
   *  Components per @HostListener gehört). */
  readonly key?: string;
  /** Spezielle Handler-IDs für Aktionen ohne Hotkey-Entsprechung. */
  readonly action?: 'build' | 'minimap';
}

const BUTTONS: readonly ActionButton[] = [
  { label: 'Inv', title: 'Inventar', key: 'i' },
  { label: 'Bau', title: 'Bauen', action: 'build' },
  { label: 'Q',   title: 'Quests', key: 'q' },
  { label: 'K',   title: 'Skills', key: 'k' },
  { label: 'T',   title: 'Talente', key: 't' },
  { label: 'C',   title: 'Charakter', key: 'c' },
  { label: 'F',   title: 'Faktionen', key: 'f' },
  { label: 'R',   title: 'Forschung', key: 'r' },
  { label: 'P',   title: 'Zauberbuch', key: 'p' },
];

@Component({
  selector: 'app-mobile-controls',
  standalone: true,
  templateUrl: './mobile-controls.component.html',
  styleUrl: './mobile-controls.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MobileControlsComponent implements OnDestroy {
  private readonly bridge = inject(GameBridgeService);
  private readonly state = inject(GameStateService);
  private readonly destroyRef = inject(DestroyRef);

  /** Wird nur gerendert, wenn echte Touch-Geräte oder schmaler Viewport. */
  readonly enabled = signal<boolean>(this.detectMobile());

  /** Joystick aktiv (= Finger liegt drauf). */
  readonly joystickActive = signal<boolean>(false);
  readonly joystickOriginX = signal<number>(0);
  readonly joystickOriginY = signal<number>(0);
  readonly thumbDx = signal<number>(0);
  readonly thumbDy = signal<number>(0);

  readonly outerSize = JOYSTICK_OUTER;
  readonly thumbSize = JOYSTICK_THUMB;
  readonly buttons = BUTTONS;

  /** CSS-Transform der äußeren Kreis-Box. */
  readonly outerTransform = computed<string>(() => {
    const x = this.joystickOriginX() - this.outerSize / 2;
    const y = this.joystickOriginY() - this.outerSize / 2;
    return `translate(${x}px, ${y}px)`;
  });

  /** CSS-Transform des inneren Thumb (relativ zur Mitte des Außenrings). */
  readonly thumbTransform = computed<string>(() => {
    return `translate(${this.thumbDx()}px, ${this.thumbDy()}px)`;
  });

  /** Welcher Touch-Identifier zählt aktuell für den Joystick. -1 = keiner. */
  private activeTouchId = -1;
  /** Letzter `sendMove`-Tick als monotone ms. */
  private lastMoveSentAt = 0;
  /** Letzte gesendete Tile-Position — Dedup wie in der WorldScene. */
  private lastSentTile: { x: number; y: number } | null = null;

  @ViewChild('zone', { static: true })
  private zoneRef!: ElementRef<HTMLDivElement>;

  constructor() {
    const onResize = (): void => this.enabled.set(this.detectMobile());
    window.addEventListener('resize', onResize);
    this.destroyRef.onDestroy(() => window.removeEventListener('resize', onResize));
  }

  ngOnDestroy(): void {
    this.resetJoystick();
  }

  // ─── Visibility-Detection ────────────────────────────────────────────

  private detectMobile(): boolean {
    const touch =
      'ontouchstart' in window ||
      (typeof navigator !== 'undefined' && navigator.maxTouchPoints > 0) ||
      window.matchMedia('(pointer: coarse)').matches;
    const narrow = window.innerWidth < NARROW_VIEWPORT_PX;
    return touch || narrow;
  }

  // ─── Joystick-Touch-Handler (Zone-Element nimmt Touches an) ──────────

  onZoneTouchStart(ev: TouchEvent): void {
    if (this.activeTouchId !== -1) return;
    const t = ev.changedTouches[0];
    if (!t) return;
    ev.preventDefault();
    this.activeTouchId = t.identifier;
    this.joystickOriginX.set(t.clientX);
    this.joystickOriginY.set(t.clientY);
    this.thumbDx.set(0);
    this.thumbDy.set(0);
    this.joystickActive.set(true);
  }

  @HostListener('document:touchmove', ['$event'])
  onDocTouchMove(ev: TouchEvent): void {
    if (this.activeTouchId === -1) return;
    const touch = this.findActiveTouch(ev.touches);
    if (!touch) return;
    ev.preventDefault();
    let dx = touch.clientX - this.joystickOriginX();
    let dy = touch.clientY - this.joystickOriginY();
    const dist = Math.hypot(dx, dy);
    if (dist < DEAD_ZONE) {
      this.thumbDx.set(0);
      this.thumbDy.set(0);
      return;
    }
    if (dist > MAX_RADIUS) {
      dx = (dx / dist) * MAX_RADIUS;
      dy = (dy / dist) * MAX_RADIUS;
    }
    this.thumbDx.set(dx);
    this.thumbDy.set(dy);
    this.maybeSendMove(dx, dy);
  }

  @HostListener('document:touchend', ['$event'])
  @HostListener('document:touchcancel', ['$event'])
  onDocTouchEnd(ev: TouchEvent): void {
    if (this.activeTouchId === -1) return;
    for (let i = 0; i < ev.changedTouches.length; i++) {
      const t = ev.changedTouches[i];
      if (t && t.identifier === this.activeTouchId) {
        this.resetJoystick();
        return;
      }
    }
  }

  @HostListener('window:blur')
  onWindowBlur(): void {
    this.resetJoystick();
  }

  private findActiveTouch(touches: TouchList): Touch | null {
    for (let i = 0; i < touches.length; i++) {
      const t = touches[i];
      if (t && t.identifier === this.activeTouchId) return t;
    }
    return null;
  }

  private resetJoystick(): void {
    this.activeTouchId = -1;
    this.thumbDx.set(0);
    this.thumbDy.set(0);
    this.joystickActive.set(false);
    this.lastSentTile = null;
  }

  /** Aus dem aktuellen Thumb-Vektor ein Ziel-Tile bauen und sendMove feuern. */
  private maybeSendMove(dx: number, dy: number): void {
    const now = performance.now();
    if (now - this.lastMoveSentAt < MOVE_TICK_MS) return;
    const me = this.state.player();
    if (!me) return;
    const mag = Math.hypot(dx, dy);
    if (mag <= 0) return;
    const nx = dx / mag;
    const ny = dy / mag;
    const tileX = Math.round(me.x + nx * MOVE_LOOKAHEAD_TILES);
    const tileY = Math.round(me.y + ny * MOVE_LOOKAHEAD_TILES);
    if (
      this.lastSentTile &&
      this.lastSentTile.x === tileX &&
      this.lastSentTile.y === tileY
    ) {
      return;
    }
    this.lastSentTile = { x: tileX, y: tileY };
    this.lastMoveSentAt = now;
    this.bridge.sendMove(tileX, tileY);
  }

  // ─── Action-Buttons ──────────────────────────────────────────────────

  onButtonTap(ev: Event, btn: ActionButton): void {
    ev.preventDefault();
    ev.stopPropagation();
    if (btn.action === 'build') {
      this.bridge.toggleBuildMode();
      return;
    }
    if (btn.action === 'minimap') {
      // Reserviert — Minimap-Component hat aktuell keinen Toggle-Key.
      return;
    }
    if (!btn.key) return;
    // Synthetisches Keydown-Event in `document`. Die Overlay-Components
    // hören auf `document:keydown` und reagieren bereits richtig. Wir
    // setzen `bubbles: true`, damit die `@HostListener`-Registrierungen
    // den Event erreichen.
    const kev = new KeyboardEvent('keydown', {
      key: btn.key,
      bubbles: true,
      cancelable: true,
    });
    document.dispatchEvent(kev);
  }
}
