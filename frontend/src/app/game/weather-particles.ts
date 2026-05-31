// WeatherParticles — Phaser-Particle-Emitter pro Wetter-Kind (H3.14).
//
// Backend sendet `weather {kind, intensity}` (siehe WeatherSnapshot in
// `core/models/time.model.ts`). Wir aktivieren/deaktivieren pro Frame einen
// Phaser-ParticleEmitter, der den sichtbaren Viewport mit Wetter-Partikeln
// füllt:
//
//   • rain      — blau-weiße Tropfen, fallen schräg von oben
//   • snow      — weiße Flocken, langsamer Fall mit Drift
//   • sandstorm — gelb-bräunliche Partikel, horizontaler Wind
//   • clear/<unknown> — Emitter aus
//
// `intensity` (0..1) skaliert die emit-Frequency.
//
// Implementation:
//   • Pro Kind ein eigener Emitter mit eigener Particle-Texture
//     (Fallback: 4×4 weißes Pixel-Rect, generiert in `ensureFallbackTexture`).
//   • Emitter sind an die UI-Camera (scrollFactor=0) gebunden — Partikel
//     bleiben gleichmäßig über dem Viewport verteilt unabhängig vom
//     Kamera-Scroll.
//   • Kind-Wechsel: alter Emitter aus, neuer ein. Bei gleichem Kind nur
//     emit-rate updaten (Intensity-Drift).
//   • `update(weather)` pro Frame; wenn `weather === null` oder
//     `weather.kind === 'clear'` → alle Emitter pausiert.

import Phaser from 'phaser';

/** Render-Depth: über Welt, unter Disaster-Tint (DEPTH_TINT=70 in
 *  disaster-overlay.ts). */
const DEPTH_WEATHER = 60;

/** Fallback-Texture-Key (für Asset-loses Partikel). */
const FALLBACK_TEX_RAIN = '__weather_fb_rain';
const FALLBACK_TEX_SNOW = '__weather_fb_snow';
const FALLBACK_TEX_SAND = '__weather_fb_sand';

/** Konfiguration pro Wetter-Kind. */
interface WeatherCfg {
  /** Texture-Key (mit Fallback-Auto-Generierung). */
  readonly textureKey: string;
  /** Particle-Tint (0xRRGGBB) — wird auf Fallback-White angewendet. */
  readonly tint: number;
  /** Default-Lifespan (ms). */
  readonly lifespan: number;
  /** Geschwindigkeit Y (px/s). Positiv = nach unten. */
  readonly speedY: { min: number; max: number };
  /** Geschwindigkeit X (px/s). Positiv = nach rechts. */
  readonly speedX: { min: number; max: number };
  /** Emit-Rate bei intensity=1 (Particles/Sekunde). */
  readonly maxEmitRate: number;
  /** Scale (Größe relativ zur Texture). */
  readonly scale: { min: number; max: number };
  /** Alpha-Bereich. */
  readonly alpha: { min: number; max: number };
}

const WEATHER_CONFIG: Readonly<Record<string, WeatherCfg>> = {
  rain: {
    textureKey: FALLBACK_TEX_RAIN,
    tint: 0x88aaff,
    lifespan: 900,
    speedY: { min: 600, max: 900 },
    speedX: { min: -100, max: -60 },
    maxEmitRate: 80,
    scale: { min: 0.6, max: 1.1 },
    alpha: { min: 0.5, max: 0.85 },
  },
  snow: {
    textureKey: FALLBACK_TEX_SNOW,
    tint: 0xffffff,
    lifespan: 4500,
    speedY: { min: 50, max: 120 },
    speedX: { min: -40, max: 40 },
    maxEmitRate: 40,
    scale: { min: 0.6, max: 1.4 },
    alpha: { min: 0.65, max: 0.95 },
  },
  sandstorm: {
    textureKey: FALLBACK_TEX_SAND,
    tint: 0xddbb66,
    lifespan: 1400,
    speedY: { min: -20, max: 40 },
    speedX: { min: 350, max: 600 },
    maxEmitRate: 90,
    scale: { min: 0.8, max: 1.5 },
    alpha: { min: 0.4, max: 0.75 },
  },
};

/** Wetter-Kinds, die wir kennen (alles andere = clear / off). */
const KNOWN_KINDS = new Set(Object.keys(WEATHER_CONFIG));

interface EmitterEntry {
  readonly emitter: Phaser.GameObjects.Particles.ParticleEmitter;
}

export class WeatherParticles {
  private readonly scene: Phaser.Scene;
  /** Aktive Emitter pro Kind. */
  private readonly emitters = new Map<string, EmitterEntry>();
  /** Aktueller Kind (zum Diffen). */
  private currentKind: string | null = null;
  /** Aktuelle Intensity (zum Diffen). */
  private currentIntensity = 0;

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
    this.ensureFallbackTextures();
  }

  /**
   * Pro Frame: aus aktuellem `weather()`-Signal Kind + Intensity ziehen,
   * Emitter aktivieren / pausieren / re-konfigurieren.
   *
   * Wenn `weather` null oder `kind === 'clear'` → alle pausieren.
   */
  update(weather: { readonly kind: string; readonly intensity: number } | null): void {
    const rawKind = weather?.kind ?? 'clear';
    const intensity = Math.max(0, Math.min(1, weather?.intensity ?? 0));
    const targetKind = KNOWN_KINDS.has(rawKind) ? rawKind : 'clear';

    if (targetKind === this.currentKind && intensity === this.currentIntensity) return;

    if (targetKind !== this.currentKind) {
      // Alten Emitter pausieren.
      if (this.currentKind) {
        const prev = this.emitters.get(this.currentKind);
        prev?.emitter.stop();
      }
      this.currentKind = targetKind;
    }

    this.currentIntensity = intensity;

    if (targetKind === 'clear' || intensity <= 0) {
      // Alles aus.
      return;
    }

    // Emitter ensure + start / update rate.
    const entry = this.ensureEmitter(targetKind);
    if (!entry) return;
    const cfg = WEATHER_CONFIG[targetKind];
    if (!cfg) return;
    const rate = Math.max(1, Math.round(cfg.maxEmitRate * intensity));
    // Phaser-3.60-API: `frequency` = ms zwischen Emissions (kleiner = mehr).
    // `quantity` = Emits pro Tick. Wir setzen `frequency = 1000 / rate`.
    entry.emitter.frequency = Math.max(8, Math.floor(1000 / rate));
    entry.emitter.start();
  }

  /** Scene-Shutdown — alle Emitter stoppen + zerstören. */
  destroy(): void {
    for (const e of this.emitters.values()) {
      e.emitter.stop();
      e.emitter.destroy();
    }
    this.emitters.clear();
    this.currentKind = null;
    this.currentIntensity = 0;
  }

  // ─── Internals ──────────────────────────────────────────────────────

  /** Stellt sicher, dass die Fallback-Texturen (kleine farbige Rechtecke)
   *  im Texture-Cache existieren. Echte Wetter-Assets könnten später über
   *  AssetLoader ergänzt werden; bis dahin nutzen wir die generierten
   *  Texturen, getintet via `tint`-Property im Emitter. */
  private ensureFallbackTextures(): void {
    const make = (key: string, w: number, h: number): void => {
      if (this.scene.textures.exists(key)) return;
      const g = this.scene.add.graphics({ x: 0, y: 0 });
      g.fillStyle(0xffffff, 1);
      g.fillRect(0, 0, w, h);
      g.generateTexture(key, w, h);
      g.destroy();
    };
    // Tropfen — schmal und länglich.
    make(FALLBACK_TEX_RAIN, 2, 8);
    // Flocke — kleines Quadrat.
    make(FALLBACK_TEX_SNOW, 3, 3);
    // Sand — kleines Quadrat.
    make(FALLBACK_TEX_SAND, 2, 2);
  }

  /** Erzeugt (oder liefert vorhandenen) Emitter für `kind`. */
  private ensureEmitter(kind: string): EmitterEntry | null {
    const existing = this.emitters.get(kind);
    if (existing) return existing;
    const cfg = WEATHER_CONFIG[kind];
    if (!cfg) return null;

    const cam = this.scene.cameras.main;
    // Emit-Bereich: über der ganzen Viewport-Breite, knapp oberhalb des
    // Viewports (damit Partikel nicht plötzlich im Bild auftauchen).
    // Bei sandstorm: links neben dem Viewport (horizontaler Wind nach rechts).
    const emitArea =
      kind === 'sandstorm'
        ? { x: -40, y: 0, w: 40, h: cam.height }
        : { x: 0, y: -40, w: cam.width, h: 40 };

    const emitter = this.scene.add.particles(0, 0, cfg.textureKey, {
      x: { min: emitArea.x, max: emitArea.x + emitArea.w },
      y: { min: emitArea.y, max: emitArea.y + emitArea.h },
      lifespan: cfg.lifespan,
      speedX: cfg.speedX,
      speedY: cfg.speedY,
      scale: cfg.scale,
      alpha: cfg.alpha,
      tint: cfg.tint,
      frequency: 50,
      quantity: 1,
      blendMode: 'NORMAL',
      // Sofort starten? Nein — `update()` ruft `start()`.
      emitting: false,
    });
    emitter.setDepth(DEPTH_WEATHER);
    emitter.setScrollFactor(0);

    // Resize-Listener: Emit-Bereich an neuen Viewport anpassen.
    const onResize = (): void => {
      const newArea =
        kind === 'sandstorm'
          ? { x: -40, y: 0, w: 40, h: cam.height }
          : { x: 0, y: -40, w: cam.width, h: 40 };
      // Phaser-Emitter-Config: setEmitZone bzw. setPosition. Da wir die x/y
      // direkt als min/max im Constructor gesetzt haben, müssen wir die
      // Range-Werte neu setzen. Phaser 3.60: `setConfig` updated alles.
      emitter.setConfig({
        x: { min: newArea.x, max: newArea.x + newArea.w },
        y: { min: newArea.y, max: newArea.y + newArea.h },
      });
    };
    this.scene.scale.on(Phaser.Scale.Events.RESIZE, onResize);
    // Beim Emitter-Destroy: Listener wegräumen.
    emitter.once(Phaser.GameObjects.Events.DESTROY, () => {
      this.scene.scale.off(Phaser.Scale.Events.RESIZE, onResize);
    });

    const entry: EmitterEntry = { emitter };
    this.emitters.set(kind, entry);
    return entry;
  }
}
