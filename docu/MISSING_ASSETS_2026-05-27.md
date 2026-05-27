# Assets-Status — Liege (Stand 2026-05-27, nach Big-Audit)

Diese Datei dokumentiert den aktuellen Stand der Asset-Verwendung nach dem
großen Asset-Audit-Refactor. Sie beschreibt, was im Spiel genutzt wird, was
als Source-Material/Reserve liegt, und welche Pools für künftige Features
bereit liegen.

**Total PNGs:** 4604
**Genutzt:** ~858 (~19%)
**Source/Reserve:** ~3746 (siehe Aufschlüsselung unten — vieles davon sind
einzelne Animation-Frames, deren Sprite-Sheets bereits genutzt werden, oder
alternative Größen 64/256/512 der 128er Inventar-Icons).

---

## 1. Was komplett implementiert ist

### 1.1 Equipment (Items, Backend + Frontend ITEM-Map)
**Default-Icons aus `assets/professional/original_pack_2026_05_27/icons_128/`**
(hand-painted 128×128 Inventar-Icons):
- 12 Waffen: sword, axe, bow, staff, wand, greatsword, spear, crossbow,
  throwing_knife, mace, scythe, dagger
- 5 Rüstungen: helmet, chestplate, gloves, shield, boots
- 2 Schmuck (jewelry/ring.png + amulet.png — eigene Pfade)

### 1.2 Consumables / Potions
- health_potion, mana_potion, antidote, fire_resist, stamina, herb, torch
  → `original_pack` (premium 128×128)
- greater_health, greater_mana, frost_resist, invisibility, poison, speed,
  strength → `/assets/consumables/potions/` (64×64)
- food_ration, fish, mushroom_food → `/assets/consumables/`, `/assets/food/`

### 1.3 Food + Resources
- bread, cooked_meat (vorher 404, jetzt aus original_pack)
- wood, stone, iron_ore, gold_ore, crystal, bone, cloth, leather → original_pack
- Reste (apple, berries, fruits, seeds, ingots) → `/assets/food/`, `/assets/seeds/`,
  `/assets/resources/`

### 1.4 NPCs / Characters
- 30 Friendly-NPCs (`assets/characters/npcs/*.png`), 10 Variants
- 6 Player-Presets (`assets/characters/player_presets/`)
- Walk-Animations: 8 Friendly (bandit, blacksmith, guard, healer, mage,
  quest_giver, soldier, villager) + 49 Monster — jeweils 10 Frames (idle_1/2 +
  walk_<down|up|left|right>_1/2)

### 1.5 Monster
- 17 Pro-Monster (`assets/monsters/world_sprites/reference_based/sprites_96/`)
- 49 Legacy-Creatures (`assets/animations/monsters/<kind>/idle_1.png`)

### 1.6 Props (Override-Map → original_pack)
- tree_oak, tree_pine, tree_dead, rock_mossy, bush, tall_grass, mushrooms,
  broken_cart, barrel → 128×128 hand-painted
- prop_rune_altar als neuer Sprite-Key (Struktur-Typ noch TODO im Backend)

### 1.7 World-Polish-Animations
- 22 Spritesheets (farming/social/work/feedback/ambient) — via
  `WORLD_POLISH_ANIMS` integriert. Einzelne Frame-PNGs sind Source-Material.

---

## 2. Verfügbar aber nicht im UI genutzt (für künftige Wellen)

### 2.1 Monster-Portraits 768×768 (~17 Files)
- `assets/monsters/professional/portraits_768/*_portrait.png` für alle Pro-
  Monster (kaiju_thornback, grave_wraith, magma_shell_devourer, etc.)
- **Implementations-Idee:** Boss-Encounter-Modal beim ersten Spotten + Pinned-
  Tooltip mit Portrait für detaillierte Mob-Info.

### 2.2 Wetter-Animationen (10 Anims)
- `assets/animations/professional/weather/` — rain (4 Intensitäten),
  snow (4 Intensitäten), fog (2 Intensitäten)
- **Implementations-Idee:** `weather_worker.py` Output mit Frontend-Overlay
  verknüpfen — Regen-Pixel oder Schneefall über dem World-View einblenden.

### 2.3 Wetter-Atmosphäre-Overlays (10 Anims)
- `assets/animations/professional/weather_overlays/` — desert_heat_haze,
  fog overlays, jungle_humidity, etc.
- **Implementations-Idee:** als zusätzliche Layer für Wetter-Effekte, damit
  z.B. "Sturm" nicht nur Regen-Tropfen sondern auch Sicht-Reduktion zeigt.

### 2.4 Biome-Ambient-Effekte (6 Anims)
- `assets/animations/professional/biomes/` — desert_dust, desert_heat_haze,
  jungle_humidity_motes, jungle_leaf_drift, swamp_mist, volcanic_ash
- **Implementations-Idee:** trigger bei Biome-Wechsel oder als permanenter
  Ambient-Layer in Biom-spezifischen Chunks.

### 2.5 Combat-Magic-Animations (8 Effekte)
- `assets/animations/professional/combat_magic/` — fireball_explosion,
  heal_pulse, hit_spark, ice_impact, lightning_strike, magic_circle,
  poison_cloud, sword_slash_arc
- **Implementations-Idee:** kann die existing `/assets/animations/spells/`
  und `/assets/animations/attacks/` Spell-Effects ersetzen — vermutlich
  höhere Qualität.

### 2.6 Pro-Equipment Rarity-Variants (~250 Files)
- `equipment/weapons/professional/reference_based/rarity_v2/<rarity>/*.png`
- `equipment/armor/professional/reference_based/by_rarity/*/`
- Werden via `PRO_WEAPON_MAP` + `PRO_ARMOR_MAP` referenziert. Die meisten
  Slugs sind dort eingetragen, einige bleiben für künftige Rarity-Erweiterung
  (z.B. `plain_war_spear` Pfad existiert in Map aber File fehlt — 404 im Log).

### 2.7 Resources Professional + Magic Professional + Items Professional
- ~700 Asset-Files in `resources/professional/`, `magic/professional/`,
  `items/professional/` — Source-Pool für künftige Item-Rarity-Variants oder
  alternative Recipes.

---

## 3. Source-Material (bewusst behalten, nicht löschen)

Diese Files sind ungenutzt vom Code, aber wichtig als Source/Reference:

### 3.1 Spritesheet-Source-Frames (~831 Files)
- Einzelne Frame-PNGs unter `assets/animations/professional/world_polish/`,
  `/weather/`, `/biomes/`, `/combat_magic/`, `/weather_overlays/`. Die fertigen
  Sheets werden geladen, einzelne Frames dienen als Edit-Source.

### 3.2 Alternative Größen-Pools (~600 Files)
- `original_pack_2026_05_27/icons_64/`, `/icons_256/`, `/masters_512/` —
  alternative Auflösungen, falls UI andere Größen braucht (Tooltip 256,
  Header 512). Aktuell wird nur 128 genutzt.
- Gleiches Muster bei `consumables/potions/`.

### 3.3 Contact-Sheets (~6 Files)
- `*_contact.jpg` — Übersichts-Vorschauen der gesamten Asset-Pools, für die
  visuelle Orientierung. Behalten.

---

## 4. Bekannte 404s (im Backend-Log)

### 4.1 `equipment/weapons/professional/reference_based/rarity_v2/common/plain_war_spear.png`
- `PRO_WEAPON_MAP.spear.common = 'plain_war_spear'` — File existiert nicht
  unter rarity_v2/common/.
- **Fix:** entweder File generieren ODER Map-Eintrag auf existierendes
  rarity_v2-File ändern (z.B. `default` Eintrag nutzen).

---

## 5. Erledigte Cleanup-Operationen

- 5 Top-Down-Animation-Folder gelöscht (farmer, merchant, player,
  villager_male, villager_female) — Stil-inkompatibel mit neuen Front-View-NPCs.
- 172 IP-violation Files entfernt (Helluva Boss, Excalibur/Fate, HOMM5,
  Roblox-Insignien, NFT-Plants, Sci-Fi-Scythe).

---

## 6. Roadmap für vollständige Asset-Auslastung

In Priorität (was am wenigsten Aufwand für am meisten Visual-Impact bringt):

1. **Weather-Overlay-Integration** — `weather_worker` Status (`rain_heavy`,
   `snow_blizzard` etc.) als Overlay-Spritesheet im Frontend rendern. ~1 Tag.
2. **Biome-Ambient-Layer** — bei Biom-Wechsel passenden Ambient-Spritesheet
   als Camera-Overlay aktivieren. ~1 Tag.
3. **Combat-Magic-Replacement** — `/assets/animations/spells/` und `/attacks/`
   durch `/professional/combat_magic/` ersetzen, ggf. höher aufgelöst. ~½ Tag.
4. **Monster-Portrait-Modal** — bei Klick auf Boss-Mob ein Portrait-Modal
   zeigen mit 768×768 Bild + Stats + Lore. ~½ Tag.
5. **Rune-Altar als Struktur** — `prop_rune_altar` ist preloaded, aber kein
   STRUCTURE-Typ. Im Backend + Frontend registrieren + Ritual-Mechanik
   nachziehen. ~½ Tag.
