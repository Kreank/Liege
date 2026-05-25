# Liege — Asset-Bedarfsliste

Diese Datei listet Assets, die durch implementierte Mechanik impliziert werden, aber noch nicht in `/mnt/dev/Privat/Liege/assets/` existieren. Aktuell laufen sie mit Workarounds (Tint, Fallback-Sprite). Wenn User ein Asset generiert → Eintrag entfernen und Workaround durch echtes Sprite ersetzen.

**Prioritäten:**
- **P0** — blockiert sichtbares Gameplay-Element, Workaround sehr sichtbar als "fehlt"
- **P1** — wäre eine spürbare Verbesserung, aber Workaround ist akzeptabel
- **P2** — Polish, kommt mit späteren Wellen

---

## Stand 2026-05-25 (Welle: Chunked World, Welt-Respawn, Händler, Dörfer, Tagesabläufe, Dungeons)

### Währungssystem (Welle: Händler)

| Pfad | Priorität | Beschreibung | Workaround |
|------|-----------|--------------|------------|
| `assets/currency/coin_copper.png` | P0 | Kupfermünze, 32×32, golden-bronze | nutze `gold_ore` als 1-Münze |
| `assets/currency/coin_silver.png` | P0 | Silbermünze, 32×32, silbern | nutze `silver_ore` als 10-Münzen |
| `assets/currency/coin_gold.png` | P0 | Goldmünze, 32×32, glänzend gold | nutze `gold_ore` als 100-Münzen |

### NPC-Sprites (Welle: Dörfer + Händler)

| Pfad | Priorität | Beschreibung | Workaround |
|------|-----------|--------------|------------|
| ~~`assets/characters/npcs/merchant.png`~~ | ✅ | Händler — integriert (Welle 21) |
| ~~`assets/characters/npcs/blacksmith.png`~~ | ✅ | Schmied — integriert (Welle 21) |
| ~~`assets/characters/npcs/farmer.png`~~ | ✅ | Bauer — integriert (Welle 21) |
| ~~`assets/characters/npcs/villager.png`~~ | ✅ | Dorfbewohner — integriert (Welle 21) |
| ~~`assets/characters/npcs/guard.png`~~ | ✅ | Wache — integriert (Welle 21) |
| ~~`assets/characters/npcs/healer.png`~~ | ✅ | Heiler — integriert (Welle 21) |
| ~~`assets/characters/npcs/mage.png`~~ | ✅ | Magier — integriert (Welle 21) |
| ~~`assets/characters/npcs/quest_giver.png`~~ | ✅ | Quest-Auftraggeber — integriert (Welle 21) |
| `assets/characters/npcs/bandit.png` | P1 | Räuber dunkel maskiert — aktuell `monster_bandit` ist da, evtl. separate Friendly-Variante | aktuell `monster_bandit` |
| `assets/characters/npcs/bard.png` | P1 | Barde mit Laute | aktuell `char_player` mit Tint |
| `assets/characters/npcs/scholar.png` | P1 | Gelehrter mit Buch | nutzt `npc_mage` als Workaround |
| `assets/characters/npcs/hermit.png` | P2 | Einsiedler | aktuell `char_player` mit Tint |
| `assets/characters/npcs/wanderer.png` | P2 | Wanderer mit Reise-Stock | nutzt `npc_villager` als Workaround |

### Boss-Mobs (Welle: Event-Spawn)

| Pfad | Priorität | Beschreibung | Workaround |
|------|-----------|--------------|------------|
| ~~`assets/monsters/ogre.png`~~ | ✅ | Großer Ogre — integriert |
| ~~`assets/monsters/necromancer.png`~~ | ✅ | Nekromant — integriert |
| ~~`assets/monsters/dragon_whelp.png`~~ | ✅ | Kleiner Drache — integriert |
| `assets/monsters/treant.png` | P2 | Baum-Wesen | — |
| `assets/monsters/giant_spider.png` | P2 | Größere Spinne als Boss-Variante | — |
| `assets/monsters/wolf_alpha.png` | P2 | Alpha-Wolf, größer/dunkler | — |

### Dorf-Strukturen (Welle: Dörfer + Lager)

| Pfad | Priorität | Beschreibung | Workaround |
|------|-----------|--------------|------------|
| `assets/buildings/house_small.png` | P1 | Kleines Bauernhaus, 96×96, mit Dach + Tür | aktuell aus wall+floor+door zusammengesetzt |
| `assets/buildings/house_large.png` | P1 | Größeres Haus, 128×128 | dito |
| `assets/buildings/blacksmith.png` | P1 | Schmiede-Front mit Schornstein | dito |
| `assets/buildings/shop.png` | P1 | Laden-Front mit Schild | dito |
| `assets/buildings/tower_guard.png` | P2 | Wachturm | aktuell aus walls/stairs zusammengesetzt |
| `assets/buildings/door_wood.png` | P0 | Begehbare Holztür (Animation auf/zu wäre nice) | aktuell `floor` als Türlücke |
| `assets/buildings/door_iron.png` | P1 | Eisentür | dito |
| `assets/buildings/sign_village.png` | P2 | Dorfschild | aktuell `marker` |
| `assets/buildings/banner_faction.png` | P2 | Fraktion-Banner | — |

### Magic-Effekte (Welle: Spell-Polish)

| Pfad | Priorität | Beschreibung | Workaround |
|------|-----------|--------------|------------|
| `assets/effects/fireball_explosion.png` | P1 | Großer Feuerball-Aufschlag | aktuell `hit_spark` |
| `assets/effects/ice_shard.png` | P2 | Eis-Splitter | — (noch kein Ice-Spell) |
| `assets/effects/lightning_strike.png` | P2 | Blitz-Effekt | — |
| `assets/effects/magic_circle.png` | P2 | Beschwörungskreis (Boden) | — |

### Tree-Wachstumsphasen (Welle: Welt-Respawn / Acker)

| Pfad | Priorität | Beschreibung | Workaround |
|------|-----------|--------------|------------|
| `assets/props/nature/sapling.png` | P1 | Junger Setzling, 32×32 | aktuell direkt `tree_oak` |
| `assets/props/nature/tree_young.png` | P2 | Mittelgroßer Baum | aktuell direkt `tree_oak` |
| `assets/props/nature/wheat_seedling.png` | P2 | Wachstumsstufe Acker | aktuell `farm_plot` bleibt gleich bis Ernte |
| `assets/props/nature/wheat_grown.png` | P2 | Reif | dito |

### Food-Items (Welle: Wirtschaft / Bauern)

| Pfad | Priorität | Beschreibung | Workaround |
|------|-----------|--------------|------------|
| ~~`assets/food/apple.png`~~ | ✅ | Apfel — integriert (Welle 2) |
| ~~`assets/food/berries.png`~~ | ✅ | Beeren — integriert |
| ~~`assets/food/wheat.png`~~ | ✅ | Weizen — integriert |
| ~~`assets/food/raw_meat.png`~~ | ✅ | Rohes Fleisch — integriert |
| ~~`assets/food/fish.png`~~ | ✅ | Fisch — integriert |
| ~~`assets/food/mushroom_food.png`~~ | ✅ | Pilz-Mahl — integriert |
| `assets/food/bread.png` | **P0** | Brotlaib — IST als Item definiert, Asset fehlt, gibt 404 im Frontend | aktuell broken image |
| `assets/food/cooked_meat.png` | **P0** | Gebratenes Fleisch — dito, 404 | aktuell broken image |
| `assets/food/water_flask.png` | P2 | Wasserflasche | — |

### Tier-Weapon-Variationen (Welle: Item-Tier-System, später)

| Pfad | Priorität | Beschreibung | Workaround |
|------|-----------|--------------|------------|
| `assets/equipment/weapons/sword_iron.png` | P2 | Eisen-Schwert | aktuell `sword` |
| `assets/equipment/weapons/sword_steel.png` | P2 | Stahl-Schwert | aktuell `sword` |
| `assets/equipment/weapons/sword_mythril.png` | P2 | Mythril-Schwert | aktuell `sword` |

### Dungeon-Erweiterung (Welle: echte Dungeons)

| Pfad | Priorität | Beschreibung | Workaround |
|------|-----------|--------------|------------|
| `assets/dungeons/stairs_up.png` | P0 | Treppe nach oben (Exit) | aktuell `stairs_down` doppelt genutzt |
| `assets/dungeons/treasure_chest.png` | P1 | Schatztruhe, glänzend | aktuell `struct_chest` |
| `assets/dungeons/altar.png` | P2 | Steinaltar (Mini-Boss/Quest) | — |
| `assets/dungeons/dungeon_floor_dark.png` | P2 | Variation, düsterer | aktuell `dungeon_floor` |
| `assets/dungeons/dungeon_wall_mossy.png` | P2 | Variation Dungeon-Wand | aktuell `dungeon_wall` |

### Walk-Animation (Welle: Player-Polish)

| Pfad | Priorität | Beschreibung | Workaround |
|------|-----------|--------------|------------|
| `assets/characters/player_walk_1.png` | P2 | Walk-Frame 1 | aktuell statisch `player.png` mit Bounce-Tween |
| `assets/characters/player_walk_2.png` | P2 | Walk-Frame 2 | dito |

---

## Was passiert wenn ein Asset hier eingetragen ist

1. Code nutzt aktuell den Workaround
2. Wenn `assets/<pfad>` erscheint:
   - Code wird angepasst (Sprite-Key ersetzt, Tint entfernt etc.)
   - Eintrag aus dieser Liste löschen
3. User pflegt parallel `ASSET_SPEC.md` mit dem was er generiert hat
