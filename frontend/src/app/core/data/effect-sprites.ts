// Auto-generiert aus assets/animations/professional/* + assets/effects/* (Welle render-data, 2026-05-30).
// Effect-Key -> erstes Frame des Anim-Loops (Phaser nutzt es als Static-Sprite-Repraesentation).
// Subagent A's Loader kann diese Pfade direkt verwenden, oder per Konvention die
// restlichen Frames durch _01->_02..._NN substituieren.
//
// G4 (2026-05-31): zusätzlich EFFECT_ANIMATIONS-Map mit Frame-Templates pro
// Effekt. Der AssetLoaderService lädt die Frame-Sequenz als Phaser-Animation,
// `VISUAL_EFFECTS.spawn()` spielt sie einmal ab und zerstört den Sprite.
// Frame-Counts sind aus dem Asset-Stand 2026-05-31 ermittelt — wenn ein Pack
// aktualisiert wird, hier nachziehen (sonst rendert nur das erste Frame).

/** Effect-Key -> absoluter Path zum (ersten) Frame. */
export const EFFECT_SPRITES: Readonly<Record<string, string>> = {
  biome_desert_dust:           '/assets/animations/professional/biomes/desert_dust/desert_dust_01.png',
  biome_desert_heat_haze:      '/assets/animations/professional/biomes/desert_heat_haze/desert_heat_haze_01.png',
  biome_jungle_humidity_motes: '/assets/animations/professional/biomes/jungle_humidity_motes/jungle_humidity_motes_01.png',
  biome_jungle_leaf_drift:     '/assets/animations/professional/biomes/jungle_leaf_drift/jungle_leaf_drift_01.png',
  biome_swamp_mist:            '/assets/animations/professional/biomes/swamp_mist/swamp_mist_01.png',
  biome_volcanic_ash:          '/assets/animations/professional/biomes/volcanic_ash/volcanic_ash_01.png',
  disaster_ash_rain:           '/assets/animations/disasters/ash_rain/ash_flake_falling_anim_01.png',
  disaster_forest_fire:        '/assets/animations/disasters/forest_fire/ember_rise_anim_01.png',
  disaster_locust_swarm:       '/assets/animations/disasters/locust_swarm/locust_swarm_density_high_anim_01.png',
  disaster_scorching_heat:     '/assets/animations/disasters/scorching_heat/heat_shimmer_anim_01.png',
  disaster_thunderstorm:       '/assets/animations/disasters/thunderstorm/lightning_flash_sky_anim_01.png',
  disaster_toxic_fog:          '/assets/animations/disasters/toxic_fog/toxic_bubble_burst_anim_01.png',
  fireball_explosion:          '/assets/animations/professional/combat_magic/fireball_explosion/fireball_explosion_01.png',
  heal_glow:                   '/assets/effects/heal_glow.png',
  heal_pulse:                  '/assets/animations/professional/combat_magic/heal_pulse/heal_pulse_01.png',
  hit_spark:                   '/assets/animations/professional/combat_magic/hit_spark/hit_spark_01.png',
  holy_shield_aura:            '/assets/animations/professional/combat_magic/holy_shield_aura/holy_shield_aura_01.png',
  ice_impact:                  '/assets/animations/professional/combat_magic/ice_impact/ice_impact_01.png',
  ice_shard:                   '/assets/effects/ice_shard.png',
  ice_spell:                   '/assets/animations/professional/combat_magic/ice_spell/ice_spell_01.png',
  lightning_bolt_projectile:   '/assets/animations/professional/combat_magic/lightning_bolt_projectile/lightning_bolt_projectile.png',
  lightning_strike:            '/assets/animations/professional/combat_magic/lightning_strike/lightning_strike_01.png',
  magic_circle:                '/assets/animations/professional/combat_magic/magic_circle/magic_circle_01.png',
  poison_cloud:                '/assets/animations/professional/combat_magic/poison_cloud/poison_cloud_01.png',
  pro_weather_fog_dense:       '/assets/animations/professional/weather/fog_dense/fog_dense_01.png',
  pro_weather_fog_light:       '/assets/animations/professional/weather/fog_light/fog_light_01.png',
  pro_weather_rain_downpour:   '/assets/animations/professional/weather/rain_downpour/rain_downpour_01.png',
  pro_weather_rain_heavy:      '/assets/animations/professional/weather/rain_heavy/rain_heavy_01.png',
  pro_weather_rain_light:      '/assets/animations/professional/weather/rain_light/rain_light_01.png',
  pro_weather_rain_medium:     '/assets/animations/professional/weather/rain_medium/rain_medium_01.png',
  pro_weather_snow_blizzard:   '/assets/animations/professional/weather/snow_blizzard/snow_blizzard_01.png',
  pro_weather_snow_heavy:      '/assets/animations/professional/weather/snow_heavy/snow_heavy_01.png',
  pro_weather_snow_light:      '/assets/animations/professional/weather/snow_light/snow_light_01.png',
  pro_weather_snow_medium:     '/assets/animations/professional/weather/snow_medium/snow_medium_01.png',
  pro_weather_storm_lightning: '/assets/animations/professional/weather/storm_lightning/storm_lightning_01.png',
  shadow:                      '/assets/effects/shadow.png',
  sword_slash_arc:             '/assets/animations/professional/combat_magic/sword_slash_arc/sword_slash_arc_01.png',
  weather_fog_dense:           '/assets/animations/weather/fog_dense_1.png',
  weather_fog_light:           '/assets/animations/weather/fog_light_1.png',
  weather_rain_downpour:       '/assets/animations/weather/rain_downpour_1.png',
  weather_rain_heavy:          '/assets/animations/weather/rain_heavy_1.png',
  weather_rain_light:          '/assets/animations/weather/rain_light_1.png',
  weather_rain_medium:         '/assets/animations/weather/rain_medium_1.png',
  weather_snow_blizzard:       '/assets/animations/weather/snow_blizzard_1.png',
  weather_snow_heavy:          '/assets/animations/weather/snow_heavy_1.png',
  weather_snow_light:          '/assets/animations/weather/snow_light_1.png',
  weather_snow_medium:         '/assets/animations/weather/snow_medium_1.png',
  weather_storm_lightning:     '/assets/animations/weather/storm_lightning_1.png',
  weather_swamp_mist:          '/assets/animations/weather/swamp_mist_1.png',
  wind_slash_spell:            '/assets/animations/professional/combat_magic/wind_slash_spell/wind_slash_icon.png',
};

/**
 * Beschreibt eine Multi-Frame-Animation für einen Effect-Kind.
 *
 * Frame-Pfad-Konvention:
 *   `${baseUrl}/${prefix}${frame_2digits}.png`
 * Bsp. `baseUrl='/.../fireball_explosion'`, `prefix='fireball_explosion_'`,
 *      `frameCount=12` → 12 Pfade `_01.png` bis `_12.png`.
 *
 * `oneShot=true` (default): Animation spielt einmal, Sprite zerstört sich.
 * `oneShot=false`: läuft solange aktiv (für Aura/Overlay-Effekte).
 */
export interface EffectAnimationSpec {
  readonly kind: string;
  readonly baseUrl: string;
  readonly prefix: string;
  readonly frameCount: number;
  /** Phaser-Anim-Framerate (typisch 10 für combat_magic, 6 für disasters). */
  readonly frameRate: number;
  /** Tile-Skalierung (1.0 = TILE_SIZE × TILE_SIZE). */
  readonly tileScale: number;
}

/**
 * Multi-Frame-Animationen für Spell- und Disaster-Effekte (G4).
 * Pro Eintrag werden alle Frames im Loader registriert; der visual_effect-
 * Handler spielt die `kind`-Animation einmalig am Tile-Center ab.
 */
export const EFFECT_ANIMATIONS: Readonly<Record<string, EffectAnimationSpec>> = {
  // ── Combat-Magic (8-12 Frames @ 10 FPS) ──────────────────────────────
  fireball_explosion: {
    kind: 'fireball_explosion',
    baseUrl: '/assets/animations/professional/combat_magic/fireball_explosion',
    prefix: 'fireball_explosion_',
    frameCount: 12, frameRate: 12, tileScale: 1.8,
  },
  heal_pulse: {
    kind: 'heal_pulse',
    baseUrl: '/assets/animations/professional/combat_magic/heal_pulse',
    prefix: 'heal_pulse_',
    frameCount: 12, frameRate: 10, tileScale: 1.4,
  },
  hit_spark: {
    kind: 'hit_spark',
    baseUrl: '/assets/animations/professional/combat_magic/hit_spark',
    prefix: 'hit_spark_',
    frameCount: 12, frameRate: 18, tileScale: 0.8,
  },
  holy_shield_aura: {
    kind: 'holy_shield_aura',
    baseUrl: '/assets/animations/professional/combat_magic/holy_shield_aura',
    prefix: 'holy_shield_aura_',
    frameCount: 4, frameRate: 6, tileScale: 1.6,
  },
  ice_impact: {
    kind: 'ice_impact',
    baseUrl: '/assets/animations/professional/combat_magic/ice_impact',
    prefix: 'ice_impact_',
    frameCount: 12, frameRate: 12, tileScale: 1.3,
  },
  ice_spell: {
    kind: 'ice_spell',
    baseUrl: '/assets/animations/professional/combat_magic/ice_spell',
    prefix: 'ice_spell_',
    frameCount: 12, frameRate: 12, tileScale: 1.5,
  },
  lightning_strike: {
    kind: 'lightning_strike',
    baseUrl: '/assets/animations/professional/combat_magic/lightning_strike',
    prefix: 'lightning_strike_',
    frameCount: 8, frameRate: 14, tileScale: 1.8,
  },
  magic_circle: {
    kind: 'magic_circle',
    baseUrl: '/assets/animations/professional/combat_magic/magic_circle',
    prefix: 'magic_circle_',
    frameCount: 12, frameRate: 8, tileScale: 1.8,
  },
  poison_cloud: {
    kind: 'poison_cloud',
    baseUrl: '/assets/animations/professional/combat_magic/poison_cloud',
    prefix: 'poison_cloud_',
    frameCount: 12, frameRate: 6, tileScale: 1.8,
  },
  sword_slash_arc: {
    kind: 'sword_slash_arc',
    baseUrl: '/assets/animations/professional/combat_magic/sword_slash_arc',
    prefix: 'sword_slash_arc_',
    frameCount: 12, frameRate: 18, tileScale: 1.4,
  },
  wind_slash_spell: {
    kind: 'wind_slash_spell',
    baseUrl: '/assets/animations/professional/combat_magic/wind_slash_spell',
    prefix: 'wind_slash_spell_',
    frameCount: 8, frameRate: 14, tileScale: 1.4,
  },
};

/**
 * Disaster-Animationen — separate Map, weil ein Disaster mehrere Layer-Anims
 * (z. B. Wolken + Funken + Rauch beim forest_fire) hat. Werden vom
 * DisasterOverlay als Particle-Source/Tile-Overlay genutzt.
 *
 * Frame-Pfad-Konvention abweichend: `${prefix}${frame_2digits}.png` direkt
 * unter `disasters/<dir>/`.
 */
export interface DisasterLayerSpec {
  readonly key: string;
  readonly baseUrl: string;
  readonly prefix: string;
  readonly frameCount: number;
  readonly frameRate: number;
}

export const DISASTER_LAYERS: Readonly<Record<string, readonly DisasterLayerSpec[]>> = {
  // Bloodmoon / dying_sun nutzen reinen Camera-Tint, kein Frame-Layer.
  pestilence: [
    // toxic_fog Bubble-Burst-Anim — wird als Tile-spawn-Anim genutzt.
    {
      key: 'pestilence_bubble',
      baseUrl: '/assets/animations/disasters/toxic_fog',
      prefix: 'toxic_bubble_burst_anim_',
      frameCount: 4, frameRate: 6,
    },
    {
      key: 'pestilence_drift',
      baseUrl: '/assets/animations/disasters/toxic_fog',
      prefix: 'toxic_fog_drift_overlay_anim_',
      frameCount: 6, frameRate: 6,
    },
  ],
  wildfire: [
    {
      key: 'wildfire_flame',
      baseUrl: '/assets/animations/disasters/forest_fire',
      prefix: 'flame_lick_anim_',
      frameCount: 6, frameRate: 12,
    },
    {
      key: 'wildfire_ember',
      baseUrl: '/assets/animations/disasters/forest_fire',
      prefix: 'ember_rise_anim_',
      frameCount: 4, frameRate: 8,
    },
    {
      key: 'wildfire_smoke',
      baseUrl: '/assets/animations/disasters/forest_fire',
      prefix: 'smoke_plume_thick_anim_',
      frameCount: 6, frameRate: 6,
    },
  ],
  thunderstorm: [
    {
      key: 'thunderstorm_strike',
      baseUrl: '/assets/animations/disasters/thunderstorm',
      prefix: 'lightning_strike_ground_anim_',
      frameCount: 5, frameRate: 16,
    },
    {
      key: 'thunderstorm_flash',
      baseUrl: '/assets/animations/disasters/thunderstorm',
      prefix: 'lightning_flash_sky_anim_',
      frameCount: 3, frameRate: 12,
    },
  ],
  ash_rain: [
    {
      key: 'ash_rain_flake',
      baseUrl: '/assets/animations/disasters/ash_rain',
      prefix: 'ash_flake_falling_anim_',
      frameCount: 4, frameRate: 6,
    },
  ],
  scorching_heat: [
    {
      key: 'scorching_heat_shimmer',
      baseUrl: '/assets/animations/disasters/scorching_heat',
      prefix: 'heat_shimmer_anim_',
      frameCount: 4, frameRate: 8,
    },
  ],
  locust_swarm: [
    {
      key: 'locust_swarm_density',
      baseUrl: '/assets/animations/disasters/locust_swarm',
      prefix: 'locust_swarm_density_high_anim_',
      frameCount: 6, frameRate: 10,
    },
  ],
};
