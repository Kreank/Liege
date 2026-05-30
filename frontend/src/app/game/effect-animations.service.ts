// EffectAnimationsService — registriert Phaser-Animationen für die G4 Multi-
// Frame-Spell-/Disaster-Effekte.
//
// G4 (2026-05-31):
// Bis G3 wurde nur das erste Frame jedes Effects als Static-Sprite gespawnt
// und mit Alpha-Tween geblendet. Mit den 8-12 Frame-Sequenzen in
// `assets/animations/professional/combat_magic/*` und `assets/animations/
// disasters/*` wollen wir echte Anims. Loader hat die Frames als Textures
// unter `effect_anim_<kind>_<NN>` bzw. `disaster_anim_<layer>_<NN>` geladen
// — dieser Service legt daraus pro Kind/Layer eine Phaser-Animation an.
//
// Anim-Key-Konvention:
//   `fx_<kind>`          — Spell-/Combat-Magic-Effekt (one-shot)
//   `fx_disaster_<layer>`— Disaster-Layer (loop)

import { Injectable, inject } from '@angular/core';
import type Phaser from 'phaser';

import { AssetLoaderService } from './asset-loader.service';

@Injectable({ providedIn: 'root' })
export class EffectAnimationsService {
  private readonly assetLoader = inject(AssetLoaderService);

  /** Idempotenz-Tracker pro Scene (Hot-Reload-safe). */
  private readonly registeredScenes = new WeakSet<Phaser.Scene>();

  /**
   * Registriert alle Effect-/Disaster-Anims in der Scene. Wird einmal in
   * `WorldScene.create()` aufgerufen, nachdem `preload()` durch ist.
   */
  createAnimations(scene: Phaser.Scene): void {
    if (this.registeredScenes.has(scene)) return;
    this.registeredScenes.add(scene);

    for (const spec of this.assetLoader.allEffectAnimations()) {
      const animKey = this.effectAnimKey(spec.kind);
      if (scene.anims.exists(animKey)) continue;

      const frames: Phaser.Types.Animations.AnimationFrame[] = [];
      for (let n = 1; n <= spec.frameCount; n++) {
        const texKey = this.assetLoader.effectFrameKey(spec.kind, n);
        if (!scene.textures.exists(texKey)) continue;
        frames.push({ key: texKey });
      }
      if (frames.length === 0) continue;

      scene.anims.create({
        key: animKey,
        frames,
        frameRate: spec.frameRate,
        repeat: 0,
      });
    }

    for (const spec of this.assetLoader.allDisasterLayers()) {
      const animKey = this.disasterAnimKey(spec.key);
      if (scene.anims.exists(animKey)) continue;

      const frames: Phaser.Types.Animations.AnimationFrame[] = [];
      for (let n = 1; n <= spec.frameCount; n++) {
        const texKey = this.assetLoader.disasterFrameKey(spec.key, n);
        if (!scene.textures.exists(texKey)) continue;
        frames.push({ key: texKey });
      }
      if (frames.length === 0) continue;

      scene.anims.create({
        key: animKey,
        frames,
        frameRate: spec.frameRate,
        repeat: -1,
      });
    }
  }

  effectAnimKey(kind: string): string {
    return `fx_${kind}`;
  }

  disasterAnimKey(layerKey: string): string {
    return `fx_disaster_${layerKey}`;
  }

  /** Anzahl tatsächlich registrierter Effect-Animations (Diagnostics). */
  registeredEffectCount(scene: Phaser.Scene): number {
    let count = 0;
    for (const spec of this.assetLoader.allEffectAnimations()) {
      if (scene.anims.exists(this.effectAnimKey(spec.kind))) count++;
    }
    return count;
  }
}
