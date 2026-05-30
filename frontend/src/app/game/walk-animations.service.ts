// WalkAnimationsService — definiert Phaser-Animationen für alle Walk-Cycles.
//
// F-render-foundation (2026-05-30):
// Nachdem der `AssetLoaderService` alle Walk-Frames in den Phaser-Texture-
// Cache geladen hat, müssen wir pro Kind × Richtung eine
// `Phaser.Animations.Animation` registrieren. Diese Service-Klasse macht
// das einmalig in `WorldScene.create()` (nach `preload()`).
//
// Anim-Key-Konvention:  `<kind>_walk_<direction>`  bzw.  `<kind>_idle`
// Diese Keys nutzt später die Movement-Tracking-Logik in `SpritePool`/
// `WorldScene`, um pro Frame `sprite.anims.play(walkAnimKey(kind, dir))`
// aufzurufen.

import { Injectable, inject } from '@angular/core';
import type Phaser from 'phaser';

import {
  AssetLoaderService,
  WALK_DIRECTIONS,
  type WalkDirection,
} from './asset-loader.service';

/** Frame-Rate der Walk-Animation (2 FPS = klassischer 2-Frame-Cycle bei
 *  500 ms pro Frame; angenehmer wenn der Mob nicht zu hektisch wackelt). */
const WALK_FRAME_RATE = 4;
/** Idle-Frame-Rate (langsamer als Walk, leichtes Wippen). */
const IDLE_FRAME_RATE = 1;

@Injectable({ providedIn: 'root' })
export class WalkAnimationsService {
  private readonly assetLoader = inject(AssetLoaderService);

  /** Trackt, in welchen Scenes wir die Anims schon registriert haben, um
   *  Double-Register-Warnings zu vermeiden (Hot-Reload, Scene-Restart). */
  private readonly registeredScenes = new WeakSet<Phaser.Scene>();

  /**
   * Registriert alle bekannten Walk-/Idle-Animationen in der Scene.
   * Idempotent pro Scene (zweiter Aufruf ist ein No-op).
   */
  createAnimations(scene: Phaser.Scene): void {
    if (this.registeredScenes.has(scene)) return;
    this.registeredScenes.add(scene);

    for (const kind of this.assetLoader.allWalkCycleKinds()) {
      const spec = this.assetLoader.walkCycleFor(kind);
      if (!spec) continue;

      // 4 Walk-Animations pro Kind.
      for (const dir of WALK_DIRECTIONS) {
        const animKey = this.walkAnimKey(kind, dir);
        if (scene.anims.exists(animKey)) continue;

        const frames: Phaser.Types.Animations.AnimationFrame[] = [];
        for (let n = 1; n <= spec.framesPerDirection; n++) {
          const textureKey = `${spec.keyPrefix}__${dir}_${n}`;
          if (!scene.textures.exists(textureKey)) continue;
          frames.push({ key: textureKey });
        }
        if (frames.length === 0) continue;

        scene.anims.create({
          key: animKey,
          frames,
          frameRate: WALK_FRAME_RATE,
          repeat: -1,
        });
      }

      // 1 Idle-Animation pro Kind (wenn Idle-Frames vorhanden).
      if (spec.hasIdle) {
        const idleKey = this.idleAnimKey(kind);
        if (!scene.anims.exists(idleKey)) {
          const idleFrames: Phaser.Types.Animations.AnimationFrame[] = [];
          for (let n = 1; n <= spec.framesPerDirection; n++) {
            const textureKey = `${spec.keyPrefix}__idle_${n}`;
            if (!scene.textures.exists(textureKey)) continue;
            idleFrames.push({ key: textureKey });
          }
          if (idleFrames.length > 0) {
            scene.anims.create({
              key: idleKey,
              frames: idleFrames,
              frameRate: IDLE_FRAME_RATE,
              repeat: -1,
            });
          }
        }
      }
    }
  }

  /** Anim-Key für Walk-Animation. */
  walkAnimKey(kind: string, direction: WalkDirection): string {
    return `${kind}_walk_${direction}`;
  }

  /** Anim-Key für Idle-Animation. */
  idleAnimKey(kind: string): string {
    return `${kind}_idle`;
  }

  /**
   * Liefert die anzahl tatsächlich registrierter Walk-Animations für
   * Diagnostics (z. B. `console.log` beim Boot).
   */
  registeredAnimCount(scene: Phaser.Scene): number {
    let count = 0;
    for (const kind of this.assetLoader.allWalkCycleKinds()) {
      for (const dir of WALK_DIRECTIONS) {
        if (scene.anims.exists(this.walkAnimKey(kind, dir))) count++;
      }
      if (scene.anims.exists(this.idleAnimKey(kind))) count++;
    }
    return count;
  }
}
