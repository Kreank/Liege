// SpritePool — Pool-Management für Phaser-Game-Objects, die von Signal-
// Listen abhängen.
//
// Pattern: Pro ID-Eintrag in einer Signal-Liste (z. B. `npcsVisible()` →
// jedes NPC hat `id: number`) wollen wir genau ein Sprite. Auf Add ein
// neues, auf Remove ein altes. Statt jeden Frame alles wegzuwerfen und
// neu zu bauen, pflegen wir eine Map ID → Sprite.
//
// `sync()` ist der zentrale Diff-Schritt: füttert eine neue Liste rein,
// erzeugt fehlende Sprites (Factory), entfernt verschwundene
// (`destroy()`), aktualisiert verbliebene (Updater).
//
// Generisch über `ID` (key) und `T` (Domain-Type wie `NPC`,
// `GroundItem`, …). Phaser-Side-Type ist `Phaser.GameObjects.GameObject`
// — wir geben aber den konkreten Typ über das Generic `S` zurück, damit
// Factory + Updater eng typed sind.

export interface SpritePoolHandlers<T, S extends Phaser.GameObjects.GameObject> {
  /** Liefert einen stabilen Key pro Eintrag (z. B. `npc.id`). */
  readonly keyOf: (item: T) => string | number;
  /** Erstellt das Sprite für einen neu erschienenen Eintrag. */
  readonly create: (item: T) => S;
  /** Aktualisiert ein bestehendes Sprite (Position, Frame, Tint, …). */
  readonly update: (sprite: S, item: T) => void;
  /** Optional: Cleanup vor `sprite.destroy()` (Tweens stoppen, etc.). */
  readonly onRemove?: (sprite: S, key: string | number) => void;
}

export class SpritePool<T, S extends Phaser.GameObjects.GameObject> {
  private readonly sprites = new Map<string | number, S>();
  private readonly handlers: SpritePoolHandlers<T, S>;

  constructor(handlers: SpritePoolHandlers<T, S>) {
    this.handlers = handlers;
  }

  /**
   * Diff zwischen aktueller Pool-Belegung und der gewünschten Liste:
   *   • neue Keys → `create()`
   *   • bestehende Keys → `update()`
   *   • verschwundene Keys → `onRemove()?` + `destroy()`
   */
  sync(items: readonly T[]): void {
    const seen = new Set<string | number>();
    for (const item of items) {
      const k = this.handlers.keyOf(item);
      seen.add(k);
      let sprite = this.sprites.get(k);
      if (!sprite) {
        sprite = this.handlers.create(item);
        this.sprites.set(k, sprite);
      }
      this.handlers.update(sprite, item);
    }
    for (const [k, sprite] of this.sprites) {
      if (seen.has(k)) continue;
      this.handlers.onRemove?.(sprite, k);
      sprite.destroy();
      this.sprites.delete(k);
    }
  }

  /** Direkter Zugriff (z. B. um den Spieler-Sprite für Kamera-Follow zu holen). */
  get(key: string | number): S | undefined {
    return this.sprites.get(key);
  }

  /**
   * Entfernt einen Sprite-Eintrag aus der Pool-Map OHNE `destroy()` zu rufen.
   * Caller übernimmt die Lifetime — z. B. für Death-Animations, die nach
   * Ablauf selbst `destroy()` aufrufen. Nachfolgende `sync()`-Calls werden
   * den Key NICHT mehr finden und somit auch kein neues Sprite spawnen
   * (solange der State-Eintrag weg ist).
   */
  detach(key: string | number): S | undefined {
    const s = this.sprites.get(key);
    if (s) this.sprites.delete(key);
    return s;
  }

  /** Alle Sprites entfernen (z. B. bei Scene-Shutdown). */
  destroyAll(): void {
    for (const [k, sprite] of this.sprites) {
      this.handlers.onRemove?.(sprite, k);
      sprite.destroy();
    }
    this.sprites.clear();
  }
}
