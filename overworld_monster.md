# Overworld-Monster für Liege

> **Ziel:** Eigener Pool aggressiver Welt-Mobs — getrennt von **Dungeon-Bestien** (133 `creature_*` aus dem Manifest) und **Wildlife** (`assets/animals/{wildlife,small,livestock,poultry,...}` → harvest-Loot, neutral/scheu).
>
> **Liege-Stil:** RimWorld-Look — strict top-down (90° von oben), warm-fantasy Palette, kein harter Outline, leichte Bodenschatten. Sprite-Größen wie bei den 133-er: `sprites_128/`, gespiegelte `sprites_128_mirrored/`, `icons_64/` für Bestiarium.
>
> **Slug-Convention:** `overworld_<klasse>_<name>` damit beim Sortieren klar ist welcher Pool (Dungeon = `creature_*`, Overworld = `overworld_*`). Beim Asset-Generieren bitte den selben Konturen-/Schatten-Stil wie die `creature_*`-Master-Cutouts halten.

---

## Übersicht — 6 Klassen, 30 Mobs

| Klasse | # | Wo / Wann | Gameplay-Rolle |
|---|---:|---|---|
| Undead | 6 | Nachts überall + dauerhaft an Friedhöfen/Ruinen | "Nachtschicht" — gibt der Welt Tag/Nacht-Druck |
| Goblinoid | 5 | Wald/Berg/Hügel, Tag+Nacht, in Banden | Klassisches Plünder-Volk, Quest-Futter |
| Räuber (Humanoid) | 4 | Straßen, Camps, Stadt-Rand | Lore-Konflikt — sprechende Gegner, droppen Currency |
| Wild-Magie / Fae | 5 | Wald, Wasserläufe, alte Steine — Dämmerung | Atmosphäre, Magie-Hinweise, selten und gefährlich |
| Biome-Apex | 8 | Pro Biome ein "alpha"-Mob | Welt-Bedrohung — single-target Kämpfe, gute Drops |
| Aberrant (Welt-Riss) | 2 | Selten, magische Hotspots | Hint auf Eldritch — leitet später zu Dungeon-Bossen über |

Plus **Disaster-Mobs** und **Lore-Carrier**: bleiben außen vor (eigene Systeme aus dem 133-er Pool — `creature_bloodmoon_revenant`, `creature_silent_pilgrim_white` etc. werden vom Disaster-Worker bzw. dem Welt-Schedule gespawnt).

---

## 1. Undead (6) — Nachts und an Tod-getränkten Orten

> Tag/Nacht-Mechanik (vorhanden in `time_system`): Undead spawnen nachts mit `nightSpawnMultiplier=2.0`, tagsüber nur in Sicht-Linie von Gräbern/Krypten/Ruinen.

### 1.1 `overworld_undead_shambler` — Wandelnder Toter
- **Aussehen:** Halb verfaulter Bauer in zerrissener Tunika, grünlich-graue Haut, herabhängende Arme. Top-down: leicht gekrümmte Pose, fleckiger Bodenschatten.
- **Stats:** HP 35, dmg 6 (melee), speed 0.6 (langsam).
- **Aggro:** territorial 5 Tiles; setzt sich beim Angreifer fest bis tot.
- **Spawn:** überall nachts (außer Stadtgebiet), 2-4 in Gruppe an Friedhöfen.
- **Drops:** `rotten_flesh` (50%), `tattered_cloth` (30%), `bone` (20%).
- **Design-Anker:** RimWorld-Pawn-Größe (~24px Körper-Cluster), schmutzig-grau-grünes Farbschema, **kein** klassisches "Gehirne!"-Klischee — eher schwermütig.

### 1.2 `overworld_undead_skeleton_warrior` — Skelett-Krieger
- **Aussehen:** Vergilbtes Skelett mit verrostetem Kurzschwert + Holzschild-Splitter. Aufrecht, militärische Pose.
- **Stats:** HP 28, dmg 9 (melee, Block-Chance 15%), speed 1.0.
- **Aggro:** hostile auf Sicht (6 Tiles).
- **Spawn:** Friedhof, alte Schlachtfelder, nachts auch Wald.
- **Drops:** `bone` (100%), `rusty_sword` (10%), `skull` (rare 5%).

### 1.3 `overworld_undead_skeleton_archer` — Skelett-Bogenschütze
- **Aussehen:** Wie Warrior, aber gebückte Haltung, vermoderter Bogen, Köcher mit 3 Pfeilen sichtbar.
- **Stats:** HP 22, dmg 11 (ranged 7 Tiles), speed 0.9.
- **Aggro:** hält Distanz, kitet bei Annäherung.
- **Spawn:** Friedhof, Mauer-Ruine, nachts in Wäldern.
- **Drops:** `bone` (100%), `arrow` (30% × 1-3 Stück), `worn_bow` (8%).

### 1.4 `overworld_undead_wight_lantern` — Laternen-Wight
- **Aussehen:** Halb-transparente Mönchsgestalt in dunkler Kutte, **trägt eine verfaulte Laterne** mit blau-grünem Glühlicht. Bodenschatten ist diffus, Sprite leicht durchsichtig (Alpha ~80%).
- **Stats:** HP 50, dmg 12 (cold-touch), speed 0.7, "Lichtkegel verlangsamt im Strahl".
- **Aggro:** wandert Pfade ab, aggro 5 Tiles, flieht nicht.
- **Spawn:** nachts an alten Pfaden + Friedhof.
- **Drops:** `soul_lantern_shard` (15% — Lichtquellen-Crafting), `bone` (50%).
- **Design-Anker:** Laterne ist visuelles Erkennungsmerkmal — auch bei flüchtigem Hinsehen klar als „der mit der Laterne" lesbar.

### 1.5 `overworld_undead_ghoul_stalker` — Pirschender Ghul
- **Aussehen:** Dürr, übermäßig lange Klauen, augenlos, schmutziger Lendenschurz. Krabbelt halb auf vier.
- **Stats:** HP 40, dmg 10 (bleed-DOT 4s), speed 1.4 (schnellster Undead).
- **Aggro:** stealth bis 3 Tiles, dann burst.
- **Spawn:** nachts in Sumpf + verlassenem Dorf.
- **Drops:** `claw_fragment` (40%), `rotten_flesh` (60%), `ghoul_tongue` (rare 8% — Alchemie).

### 1.6 `overworld_undead_desert_mummy` — Wüsten-Mumie
- **Aussehen:** Bandagierte Figur mit sandverkrusteten Wickeln, leicht goldene Verzierungen, leere Augenhöhlen. Bodenschatten bei Wüste optisch heller (Sonne).
- **Stats:** HP 55, dmg 8 (sand-cloud bei Hit — kurzer slow 2s), speed 0.5.
- **Aggro:** wacht aus Sarkophag auf wenn Spieler < 4 Tiles.
- **Spawn:** Wüste, immer (Tag und Nacht), 1-2 pro Pyramiden-Marker.
- **Drops:** `ancient_bandage` (60%), `gold_coin` (3-8 Stück, 40%), `scarab_amulet` (rare 5%).

---

## 2. Goblinoid (5) — Plünder-Volk

> Spawnen in **Banden** mit Mix-Komposition (z.B. 1 Schamane + 2 Krieger + 3 Späher). Banden-Größe steigt mit Spieler-Tier.

### 2.1 `overworld_goblin_scout` — Goblin-Späher
- **Aussehen:** Klein (~18px), gelbe Haut, gestreifte Lendenschurz, eine Hand am Dolch, andere am Mundwinkel (kichert). Spitze Ohren prominent.
- **Stats:** HP 18, dmg 5, speed 1.3 (flink), flieht bei <30% HP zu Bande zurück.
- **Aggro:** hostile 4 Tiles, alarmiert die Bande bei Sicht.
- **Spawn:** Wald + Hügel, 3-5 pro Bande, immer Tag/Nacht.
- **Drops:** `goblin_ear` (90% — Bounty-Trophäe), `bone_dagger` (15%), `copper_coin` (1-3, 30%).

### 2.2 `overworld_goblin_warrior` — Goblin-Krieger
- **Aussehen:** Größer als Späher (~22px), Knochenrüstung, kurzer Spieß. Aggressivere Pose.
- **Stats:** HP 32, dmg 8, speed 1.0.
- **Aggro:** charge bei Sicht, kein flee.
- **Spawn:** mit Späher-Banden, 1-2 pro Bande.
- **Drops:** `goblin_ear` (90%), `bone_spear` (20%), `crude_leather` (15%).

### 2.3 `overworld_goblin_shaman` — Goblin-Schamane
- **Aussehen:** Federgeschmückter Knochenstab, gemalte Symbole im Gesicht (rot/weiß), kniend wenn idle.
- **Stats:** HP 25, dmg 6 (fire-bolt range 5), heilt Bande +5 HP/3s wenn nicht im Kampf.
- **Aggro:** bleibt hinten in der Bande, casted heals primär.
- **Spawn:** 1 pro Bande, ab Bandengröße 4+.
- **Drops:** `shaman_stick` (40%), `crystal_shard` (25%), `herb_bundle` (50%).

### 2.4 `overworld_hobgoblin_legionnaire` — Hobgoblin-Legionär
- **Aussehen:** Doppelte Goblin-Größe (~34px), grün-grauer Hautton, **echte** Kettenrüstung, langer Speer und Großschild, disziplinierte Pose.
- **Stats:** HP 70, dmg 14 (block-chance 30% mit Schild), speed 0.8.
- **Aggro:** bildet Schildwall mit anderen Hobgoblins in 2 Tiles Reichweite.
- **Spawn:** in Hobgoblin-Camps (eigene Struktur, separat von Goblin-Banden), 2-3 plus 1 Captain.
- **Drops:** `iron_helm` (15%), `iron_spear` (10%), `crude_steel_ingot` (25%), `silver_coin` (5-10, 50%).

### 2.5 `overworld_orgrim_basher` — Orgrim-Schläger
- **Aussehen:** Halbblut Goblin/Ogre (~40px), brutaler Knochenhammer, Narben über das ganze Gesicht. Schwere Tritte erschüttern den Tile (animation).
- **Stats:** HP 110, dmg 22 (knockback 1 Tile), speed 0.7.
- **Aggro:** Boss-Tier — single-target, schlägt durch Block durch (-50% block).
- **Spawn:** SELTEN — 1 in einer Hobgoblin-Camp-Spawn, ~5% pro Camp-Roll.
- **Drops:** `bone_warhammer` (50%), `crude_steel_ingot` (75% × 2-4), `gold_coin` (10-25), `orgrim_skull` (rare 10% — Trophäe für NPC-Geschichte).

---

## 3. Räuber (4) — Humanoid, sprechen Sprache des Spielers

> Können **vor dem Angriff** parlamentieren (Dialog-Branch: bestechen, einschüchtern, Quest-Hook). Wichtig für Lore — droppen Currency + Briefe + Karten.

### 3.1 `overworld_brigand_footpad` — Wegelagerer
- **Aussehen:** Schlecht rasierte Erscheinung, Lederwams, Kapuze, kurzes Schwert. Bodenschatten "menschlich" (ca. wie Player).
- **Stats:** HP 45, dmg 12, speed 1.0.
- **Aggro:** **fordert zuerst 5 Gold** (Dialog), greift wenn abgelehnt oder ignoriert.
- **Spawn:** Straßen-Tiles + Brücken, alleine oder in Paaren, Tag.
- **Drops:** `copper_coin` (5-15), `dagger` (20%), `crude_map_fragment` (rare 5% — führt zu verstecktem Schatz).

### 3.2 `overworld_brigand_archer` — Räuber-Bogenschütze
- **Aussehen:** Wie Footpad, aber mit Bogen + Köcher, hockt im Gebüsch.
- **Stats:** HP 40, dmg 14 (range 8), speed 1.1 — flieht bei Nahkampf.
- **Aggro:** range-snipe, eröffnet aus Hinterhalt.
- **Spawn:** Wald-Rand + Hügel an Straßen, alleine.
- **Drops:** `copper_coin` (8-18), `worn_bow` (15%), `arrow` (1-5, 60%).

### 3.3 `overworld_brigand_captain` — Räuber-Hauptmann
- **Aussehen:** Bessere Lederrüstung mit Metall-Beschlägen, langes Schwert, Helmfeder. Steht erkennbar zentral in der Camp-Struktur.
- **Stats:** HP 95, dmg 18, speed 0.9, "Aura: +15% dmg für alle Räuber in 5 Tiles".
- **Aggro:** hostile auf Sicht, kein Parlament.
- **Spawn:** 1 pro Räuber-Camp (eigene Struktur am Wegrand), mit 3-5 Footpad/Archer.
- **Drops:** `silver_coin` (15-30), `iron_sword` (30%), `leather_armor_piece` (40%), `captain_banner` (rare 8%).

### 3.4 `overworld_witch_hunter_renegade` — Abtrünniger Hexenjäger
- **Aussehen:** Schwarzer Mantel, Hut mit breiter Krempe, Armbrust, silberne Insignien. Beunruhigend gepflegt verglichen mit anderen Räubern.
- **Stats:** HP 65, dmg 16 (armor-pierce 30%), speed 0.95, "Anti-Magic: silence-Bolzen verhindert Spells 4s".
- **Aggro:** zielt **bevorzugt auf Spieler mit Magic-Skill ≥ 10** (greift Caster zuerst an).
- **Spawn:** SEHR SELTEN — Solo am Wegrand, ~1 pro 4 Std Welt-Tag.
- **Drops:** `silver_bolt` (3-6), `consecrated_amulet` (15%), `inquisitor_signet` (rare 5% — Lore-Item).

---

## 4. Wild-Magie / Fae (5) — Dämmerung, Wasser, alte Steine

> Spawnen in **magischen Hotspots** (Standing Stones, Quellen, alte Brücken). Tageszeit-getriggert: nur zur "blauen Stunde" (Morgen + Abend ~30 Min Welt-Zeit).

### 4.1 `overworld_will_o_wisp` — Irrlicht
- **Aussehen:** Schwebende blaue Lichtkugel (~16px), umgeben von kleinen Funken. Bewegt sich erratisch.
- **Stats:** HP 12, dmg 4 (cold-burst bei Berührung), speed 1.5, "lockt andere Mobs in Reichweite" (Aggro-Magnet für Undead in 6 Tiles).
- **Aggro:** flieht aktiv vor dem Spieler, **lockt** ihn aber tiefer in den Sumpf.
- **Spawn:** Sumpf + nachts an Tümpeln, 1-3 in Gruppe.
- **Drops:** `wisp_essence` (80% — Alchemie-Zutat), `frost_dust` (40%).
- **Design-Anker:** Sprite **glüht** — wenn der Asset-Renderer Bloom unterstützt, hier nutzen. Sonst additive Layer.

### 4.2 `overworld_briar_imp` — Dornen-Kobold
- **Aussehen:** Kleines Wesen aus Dornen und Pflanzenfaser (~20px), versteckt sich in Hecken (taucht ab wenn man wegschaut).
- **Stats:** HP 20, dmg 7 (thorn-bleed), speed 1.2.
- **Aggro:** Hinterhalt — versteckt bis Spieler 1 Tile vorbei, dann Hit-and-Run.
- **Spawn:** Wald + Hecken-Tiles, 1-2 nahe Pflanzungen.
- **Drops:** `briar_thorn` (60%), `plant_fiber` (40%), `imp_eye` (rare 10%).

### 4.3 `overworld_dryad_hunter` — Dryaden-Jägerin
- **Aussehen:** Schlanke Pflanzen-Frau mit Bogen aus Lebendholz, Haare wie Ranken, Blattkrone. Top-down sieht man die Blätter um den Kopf herum.
- **Stats:** HP 55, dmg 14 (range 7, **Wurzeln immobilisieren 2s**), speed 1.0.
- **Aggro:** territorial — schießt wenn Spieler im "heiligen Hain" (Tile-Cluster mit Standing Stones).
- **Spawn:** Hain-Cluster im tiefen Wald, 1-2.
- **Drops:** `living_wood_bow` (15%), `dryad_sap` (50%), `evergreen_arrow` (1-4, 40%).

### 4.4 `overworld_mire_drowner` — Sumpf-Ziehende
- **Aussehen:** Halb-mensch, halb-Wasser, lange triefende Haare verdecken das Gesicht. Steht im Wasser-Tile knietief.
- **Stats:** HP 65, dmg 11, speed 0.5 auf Land, 1.5 im Wasser. **Zieht Spieler 1 Tile/Sek ins Wasser**.
- **Aggro:** wartet im Wasser-Tile, schlägt zu wenn Spieler benachbart.
- **Spawn:** Sumpf-Tümpel, Fluss-Mündung. 1 pro großer Wasserfläche.
- **Drops:** `mire_pearl` (rare 12%), `damp_cloth` (50%), `drowner_lock_of_hair` (rare 8% — Quest-Item).

### 4.5 `overworld_swamp_witch_solo` — Sumpfhexe
- **Aussehen:** Bucklige Gestalt in patchwork-Robe, Holzstab mit Tier-Schädel oben, Kessel vor sich. Wenn idle: rührt den Kessel.
- **Stats:** HP 75, dmg 13 (poison-cloud AoE 3 Tiles, 6s DOT), speed 0.8.
- **Aggro:** wirft Tränke (range 6), bei <40% HP "verwandelt" sich (Bluff) — kurzer Despawn-Reappear-Trick.
- **Spawn:** Sumpf, IMMER solo, an einer eigenen Hütten-Struktur.
- **Drops:** `witch_brew` (50% — Random-Potion), `bone_staff` (20%), `living_toad` (rare 10% — Sammelobjekt).

---

## 5. Biome-Apex (8) — Pro Biome eine alpha-Bedrohung

> Mid-Tier Solo-Monster, mit dickeren HP-Pools, gut sichtbar als „der Gefahren-Mob in dieser Gegend". Repräsentieren das Biome.

### 5.1 `overworld_apex_thornback_wolf` (Wald) — Dornenrücken-Wolf
- **Aussehen:** Wolf mit verholzten Dornen aus dem Rücken (~30px), dunkles Fell, glühende Augen.
- **Stats:** HP 90, dmg 16 (bleed-DOT), speed 1.3.
- **Spawn:** Wald, solo + 1 Welpe selten.
- **Drops:** `wolf_pelt` (100%), `thorn_fang` (40%), `dark_meat` (50%).

### 5.2 `overworld_apex_silverback_boar` (Grasland) — Silberrücken-Eber
- **Aussehen:** Massiver Eber, silbergrauer Borstenkamm, gebogene Stoßzähne.
- **Stats:** HP 110, dmg 18 (charge: 3-tile-line-dash), speed 1.1.
- **Spawn:** Grasland-Hänge, IMMER solo, sehr territorial (8 Tiles).
- **Drops:** `pork_loin` (3-5), `boar_tusk` (60%), `silver_bristle` (30% — Bürsten-Crafting).

### 5.3 `overworld_apex_panther_shade` (Wald/Dämmerung) — Schattenpanther
- **Aussehen:** Schwarzes Großkatzen-Sprite mit lila-bläulicher Aura, kaum sichtbar in Wald-Tiles.
- **Stats:** HP 80, dmg 20 (crit-rate 25%), speed 1.6 (schnellster Mob), **stealth bis 4 Tiles**.
- **Spawn:** tiefer Wald, NUR Dämmerung + Nacht.
- **Drops:** `shadow_pelt` (60%), `panther_claw` (40%), `night_shard` (rare 10%).

### 5.4 `overworld_apex_glacier_lynx` (Schnee) — Gletscher-Luchs
- **Aussehen:** Weiß-blauer Luchs mit eisiger Atem-Wolke (animation).
- **Stats:** HP 75, dmg 14 (frost-debuff: speed -30% für 3s), speed 1.4.
- **Spawn:** Tundra/Schnee, solo.
- **Drops:** `arctic_pelt` (100%), `frost_fang` (30%), `glacier_eye` (rare 8%).

### 5.5 `overworld_apex_dune_strider` (Wüste) — Dünenläufer
- **Aussehen:** Vogel-artig, lange dünne Beine, federloser Hals, sandfarben (~36px hoch).
- **Stats:** HP 70, dmg 13, speed 1.7 (hit-and-run, dreht 90° schnell), "kitet Spieler ohne Range-Waffe ins Leere".
- **Spawn:** Wüste, solo, weit verteilt (1 pro Chunk-Cluster).
- **Drops:** `dune_feather` (3-5), `strider_meat` (40%), `swift_sinew` (20% — Bogen-Crafting).

### 5.6 `overworld_apex_swamp_otter_clan` (Sumpf) — Sumpf-Otter-Clan
- **Aussehen:** Mensch-große Otter (~28px), aufrecht stehend, halten Stein- oder Knochenwerkzeuge — **listig**, nicht nur Bestie.
- **Stats:** Pro Otter HP 35, dmg 8, **spawnt als Trio**.
- **Aggro:** umzingelt den Spieler taktisch, **stiehlt 1 zufälliges Item** wenn Hit landet.
- **Spawn:** Sumpf/Fluss, in 3er-Clan.
- **Drops:** `otter_pelt` (3 × 60%), `polished_stone` (40%), `stolen_pouch` (rare 12% — enthält 5-15 Münzen).

### 5.7 `overworld_apex_ridge_drake` (Berg) — Felsdrache
- **Aussehen:** Flügellos, reptilien-artige Brust, Säurespeicher sichtbar im Hals (~40px).
- **Stats:** HP 130, dmg 20 (acid-DOT, korrodiert getragene Rüstung -1 quality bei mehrfachen Hits), speed 0.9.
- **Spawn:** Berg-Klippen, solo, **respawn nur alle 6h Welt-Zeit**.
- **Drops:** `drake_scale` (100% × 3-5), `acid_gland` (50%), `drake_horn` (rare 15%).

### 5.8 `overworld_apex_cliff_kraken_arm` (Küste) — Klippen-Kraken-Arm
- **Aussehen:** Nur **ein** großer Tentakel sichtbar (~40px lang) aus dem Wasser, schleimig violett. Rest unter Wasser (nur Andeutung in der Pixel-Wölbung).
- **Stats:** HP 150, dmg 22 (grab-pull 2 Tiles ins Wasser), speed 0.0 (tile-anchored).
- **Aggro:** schlägt nur wenn Spieler in 4 Tiles vom Strand-Tile.
- **Spawn:** Küsten-Klippe, 1 pro Küsten-Cluster, sehr selten.
- **Drops:** `kraken_ink` (100%), `tentacle_meat` (3-6), `pearl_great` (rare 20%).

---

## 6. Aberrant / Welt-Riss (2) — Hint zu Dungeon-Bossen

> Sehr selten, deutlich sichtbar „nicht von hier". Spawnen wenn Welt-Magic-Pool hoch ist (Storyteller-Trigger). Sterben in eindrucksvoller Animation (gibt der Welt ein „seltsamer Moment"-Event).

### 6.1 `overworld_aberrant_eyeless_pilgrim` — Augenloser Pilger
- **Aussehen:** Mensch in pilger-Robe ohne Augen — **dritte Pupille auf der Stirn**. Geht sehr aufrecht, gleichmäßig.
- **Stats:** HP 60, dmg 12, speed 1.0, "**Sieht durch Wände**" — Stealth-Skill wirkt nicht.
- **Aggro:** geht direkt auf Spieler zu, ohne Pause, durch alles.
- **Spawn:** überall, ~1 pro 6h Welt-Zeit, despawnt nach 30min wenn nicht gefunden.
- **Drops:** `forehead_eye` (rare 100% — Lore-Item, einmaliges Tagebuch-Eintrag), `pilgrim_robe` (50%), `silver_coin` (10-20).

### 6.2 `overworld_aberrant_star_mote_imp` — Sternsplitter-Wesen
- **Aussehen:** Klein (~18px), glühend wie Asteroid-Splitter, schwebt 1 Tile über Boden, leuchtende Spur.
- **Stats:** HP 30, dmg 10 (range-magic 5 Tiles), speed 1.2, **stirbt in Explosion** (3 Tile AoE, 15 dmg).
- **Spawn:** SEHR SELTEN — 1 pro Meteoriten-Event (existing in `event_worker` als „Disaster: Sternenfall"), 2-3 Stück.
- **Drops:** `star_mote_shard` (100%), `astral_dust` (50%), `glowing_core` (rare 25% — Magie-Crafting).

---

## Biome-Verteilung — Schnell-Übersicht

| Biome | Tag-Mobs | Nacht-Mobs | Apex |
|---|---|---|---|
| **Grasland** | Goblin-Späher, Räuber-Footpad | + Shambler, Skelett-Warrior | Silberrücken-Eber |
| **Wald** | Goblin-Bande (Späher+Warrior+Shaman), Räuber-Archer, Briar-Imp | + Panther-Shade, Skelett-Archer, Dryad (Dämmerung) | Dornenrücken-Wolf, Panther-Shade |
| **Dschungel** | Goblin-Bande (groß), Briar-Imp | + Ghul-Stalker | Dornenrücken-Wolf |
| **Sumpf** | Sumpfhexe (solo), Mire-Drowner | + Ghul, Will-o-Wisp | Sumpf-Otter-Clan |
| **Wüste** | Räuber-Footpad/-Archer | + Mumie (auch tagsüber), Shambler | Dünenläufer |
| **Schnee** | Hobgoblin-Camp | + Skelett-Warrior, Shambler | Gletscher-Luchs |
| **Berg** | Hobgoblin-Legionär, Orgrim (rare) | + Wight-Lantern | Felsdrache |
| **Küste** | (kein Standard) | + Will-o-Wisp | Klippen-Kraken-Arm |
| **Straße** | Räuber-Camp (Captain + Footpad + Archer) | + Hexenjäger (rare) | — |

> **Strukturen mit Spawns:** Friedhof, Räuber-Camp, Hobgoblin-Camp, Standing Stones, Sumpf-Hütte, Pyramide. Müssen ggf. ergänzt werden im `structures.py` / Worldgen, falls noch nicht existent.

---

## Asset-Pipeline-Vorschlag

**Pro Mob brauchen wir analog zu den 133 `creature_*`:**
- `fixed_cutouts_512/overworld_<slug>_fixed_512.png` — Master-Cutout, transparenter Hintergrund
- `sprites_128/overworld_<slug>_world_128.png` — In-Game-Sprite, top-down
- `sprites_128_mirrored/overworld_<slug>_world_128_west.png` — gespiegelt für West-Richtung
- `icons_64/overworld_<slug>_icon_64.png` — Bestiarium / Tooltip
- Manifest-Eintrag in `assets/monsters/overworld_pool/manifest.json` (parallel zur Dungeon-Manifest-Struktur)

**SD-Prompt-Bausteine (festhalten für Konsistenz):**
- Stil-Anker: `"hand-painted top-down fantasy creature, RimWorld-inspired, soft shadows, no harsh outlines, muted warm fantasy palette"`
- Pose: `"viewed from straight above, full body visible, centered, transparent background"`
- Größe: 512×512 für Master, dann downsampled zu 128 und 64
- Konsistenz-Token: kopiere die Style-Tokens aus dem bestehenden 133-er Pool (falls dokumentiert, sonst aus einem Sample-Cutout reverse-engineerd)

---

## Backend-Integration — was sich ändern muss

1. **`backend/npc_worker.py` `CREATURE_SPAWN_PROFILE`** — komplett auf neue Slugs umstellen. Alte 71 Kinds (skeleton, bear, goblin, ...) ersetzen durch die `overworld_*`.
2. **`backend/combat.py` `CREATURE_DAMAGE`** — Damage-Werte pro neuem Slug ergänzen.
3. **`backend/combat.py` `NEUTRAL_CREATURE_KINDS`** — Wildlife bleibt drin (deer, hare, fox …), neue Mobs sind hostile.
4. **Tag/Nacht-Bias:** neuer Spawn-Hook in `npc_worker.respawn_loop` der `nightSpawnMultiplier` anwendet — `time_system.snapshot()` liefert `phase`.
5. **Drop-Tabellen:** pro Slug ein Eintrag in `loot.py` (oder neue `loot_overworld.py`).
6. **`frontend/src/app/core/data/npc-sprites.ts`** — Sprite-Mapping pro neuem Slug.
7. **Bestiarium** — `overworld_*` als zweite Sektion neben Dungeon-Bestien.

---

## Was wir bewusst NICHT aufnehmen

- **Drachen-Verwandtschaft** (Section 9 Dungeon-Pool) — bleibt Dungeon-Endgame.
- **Eldritch T4-T5 Bosse** (Section 7) — bleiben Dungeon.
- **Setting-spezifische Bosse** (Section 10 — boss_volcano, boss_swamp_witchking, …) — bleiben Dungeon-Bosse.
- **Disaster-Mobs** (Section 11) — bleiben über `disaster_state` getriggert (bloodmoon_revenant, plague_carrier, storm_caller, …).
- **Lore-Carrier** (Section 12) — bleiben einmalige Welt-Spawns mit eigenem Schedule.
- **Reittiere** (Section 13) — kommen als zähmbare friendly NPCs aus einem separaten Pool (animals/livestock + Section-13-Manifest).
- **Wildlife** (`assets/animals/wildlife,small,livestock,poultry,swarms`) — bleibt was es ist: passive Tiere mit harvest-Drops (Fleisch, Fell, Federn).

---

## Total

- **30 Overworld-Mobs** (6 + 5 + 4 + 5 + 8 + 2)
- + 133 Dungeon-Bestien (`creature_*`, schon vorhanden)
- + Wildlife (schon vorhanden, separat)
- + Disaster/Lore/Reittiere (eigene Systeme)

Drei klar getrennte Pools. Spieler erkennen am Slug-Präfix sofort woher der Mob kommt.
