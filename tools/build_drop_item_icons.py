"""Build-Skript für Monster-Drop-Icons (146 Items, Welle 35).

Liest die Slug-Liste aus `backend/monster_drop_items.py` (implizit gespiegelt
in der `DROPS`-Tabelle unten), zieht für jedes Item entweder ein bestehendes
Asset aus den Pools (Equipment, Lore, Monsters, Original-Pack) oder rendert
einen kategorie-gefärbten Placeholder mit Initial. Output landet als
128×128 transparent-rand PNG in `assets/items/monster_drops/<slug>.png`.

Pipeline:
  - `copy`        — Source direkt auf 128×128 fitten (Alpha-Trim + Padding).
  - `tint`        — Source nach 128×128 + Multiply mit Farbe (für Varianten
                    wie rusty_sword, frost_fang, shadow_pelt).
  - `crop`        — vor copy ein Rect aus Source ausschneiden (für Monster-
                    Trophäen wo wir z. B. nur den Kopf wollen).
  - `placeholder` — solid color box, transparente Ecken, 1-Buchstaben-Initial.

Manifest: `assets/items/monster_drops/manifest.json`
Contact:  `assets/items/monster_drops/contacts/drop_items_contact.jpg`
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "assets" / "items" / "monster_drops"

# Pool-Pfade (alle relativ zu ROOT).
P_ORIG = ROOT / "assets" / "professional" / "original_pack_2026_05_27" / "icons_128"
P_LORE = ROOT / "assets" / "professional" / "additional_assets_2026_05_29_v2" / "lore_items" / "icons_128"
P_ADD = ROOT / "assets" / "professional" / "additional_assets_2026_05_29_v2" / "icons_128"
P_WEAP = ROOT / "assets" / "equipment" / "weapons" / "professional" / "reference_based" / "icons_128"
P_ARMOR = ROOT / "assets" / "equipment" / "armor" / "professional" / "reference_based" / "icons_128"
P_JEW = ROOT / "assets" / "equipment" / "jewelry" / "professional" / "from_neu_pro" / "icons_128"
P_JEW_BASE = ROOT / "assets" / "equipment" / "jewelry"
P_MOBS = ROOT / "assets" / "monsters" / "world_sprites" / "generated_longlist" / "icons_64"


# ──────────────────────────────────────────────────────────────────────────────
# Kategorie-Palette für Placeholder + Tints
# ──────────────────────────────────────────────────────────────────────────────
CAT_COLOR = {
    "material":   "#7a6a5a",  # graubraun
    "food":       "#a55a3c",  # rotbraun
    "weapon":     "#5a5a5a",  # grau
    "armor":      "#6a6a8a",  # graublau
    "magic":      "#7a3aaa",  # lila
    "lore":       "#aa9a3a",  # gold
    "trophy":     "#aa3a3a",  # rot
    "jewelry":    "#aa8a3a",  # gelb-gold
    "ammo":       "#5a4a3a",  # braun
    "quest":      "#3aaa6a",  # grün
    "gem":        "#3a8aaa",  # türkis
    "consumable": "#aa6a3a",  # orange
}


# ──────────────────────────────────────────────────────────────────────────────
# DROP-MAPPING — 146 Items.
# Für jedes Item:
#   id        — Slug (matcht monster_drop_items.py)
#   name      — Anzeige-Name
#   category  — Inventar-Kategorie
#   source    — relativ-Pfad zur Source-Datei (oder None für Placeholder)
#   transform — "copy", "tint:#rrggbb", "crop:l,t,r,b", "placeholder:LETTER"
#   note      — kurze Begründung für die Wahl
# ──────────────────────────────────────────────────────────────────────────────
DROPS: list[dict] = [
    # ── 1. MATERIALS – Felle/Knochen/Häute ──
    {"id": "wolf_pelt", "name": "Wolfsfell", "category": "material",
     "source": P_ORIG / "leather_roll.png", "transform": "tint:#8a7a5a",
     "note": "leather_roll mit warmem braun-Tint = Wolfsfell-Rolle"},
    {"id": "arctic_pelt", "name": "Arktis-Fell", "category": "material",
     "source": P_ORIG / "leather_roll.png", "transform": "tint:#d8e8ee",
     "note": "leather_roll mit kühlem weiß-blau-Tint"},
    {"id": "shadow_pelt", "name": "Schatten-Fell", "category": "material",
     "source": P_ORIG / "leather_roll.png", "transform": "tint:#3a3a4a",
     "note": "leather_roll mit dunklem schiefer-Tint"},
    {"id": "otter_pelt", "name": "Otter-Fell", "category": "material",
     "source": P_ORIG / "leather_roll.png", "transform": "tint:#6a5a3a",
     "note": "leather_roll mit warmem dunkel-ocker"},
    {"id": "crude_leather", "name": "Rohes Leder", "category": "material",
     "source": P_ORIG / "leather_roll.png", "transform": "copy",
     "note": "direkter Match: leather_roll = rohes Leder"},
    {"id": "skull", "name": "Schädel", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "copy",
     "note": "bone_fragments als Schädel-Sammlung"},
    {"id": "sinew", "name": "Sehne", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#c8a878",
     "note": "Knochen-Sehne, leicht hautfarben getintet"},
    {"id": "swift_sinew", "name": "Flinke Sehne", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#aac890",
     "note": "Sehne mit grünlichem Schimmer (magisch)"},
    {"id": "fang", "name": "Fangzahn", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#f0e8d0",
     "note": "Knochen-Bruchstücke hell als Zähne"},
    {"id": "horn", "name": "Horn", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#a87a4a",
     "note": "Knochen warm-braun = Horn"},
    {"id": "thorn_fang", "name": "Dornen-Fang", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#705a3a",
     "note": "dunkler braun-grünlich für Dornen-Wesen"},
    {"id": "frost_fang", "name": "Frost-Fang", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#a8d8e8",
     "note": "Knochen mit Frost-Cyan"},
    {"id": "panther_claw", "name": "Panther-Klaue", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#2a2a2a",
     "note": "dunkle Klauen"},
    {"id": "claw_fragment", "name": "Klauen-Splitter", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#6a5a4a",
     "note": "bruchstücke generisch"},
    {"id": "boar_tusk", "name": "Eber-Stoßzahn", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#e8d8b0",
     "note": "Elfenbein-Töne"},
    {"id": "silver_bristle", "name": "Silber-Borste", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#c8d0d8",
     "note": "Silber-helle Borsten"},
    {"id": "iron_horn", "name": "Eisen-Horn", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#5a5a6a",
     "note": "Eisen-grau Horn"},
    {"id": "corrupted_antler", "name": "Verderbtes Geweih", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#5a3a6a",
     "note": "verderbtes lila-grau"},
    {"id": "titan_antler", "name": "Titan-Geweih", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#b0a060",
     "note": "Titan-Geweih golden-bronze"},
    {"id": "titan_femur", "name": "Titan-Oberschenkel", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#d0c890",
     "note": "Riesenknochen, helles Elfenbein"},
    {"id": "giant_femur", "name": "Riesen-Oberschenkel", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#b0a890",
     "note": "Riesen-Knochen alt-elfenbein"},
    {"id": "spider_eye", "name": "Spinnen-Auge", "category": "material",
     "source": P_ORIG / "giant_spider.png", "transform": "copy",
     "note": "giant_spider Source nutzt das Spider-Asset"},
    {"id": "vampire_fang", "name": "Vampir-Reißzahn", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#f0e0d0",
     "note": "Reißzähne hell"},
    {"id": "dune_feather", "name": "Dünen-Feder", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#d8b878",
     "note": "warmes sandgelb für Wüstenfeder"},
    {"id": "roc_feather", "name": "Roc-Feder", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#a89070",
     "note": "Roc gross-feder dunkelocker"},
    {"id": "roc_talon", "name": "Roc-Kralle", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#3a2a1a",
     "note": "Roc-Kralle dunkelbraun"},
    {"id": "wing_membrane", "name": "Flügelhaut", "category": "material",
     "source": P_ORIG / "leather_roll.png", "transform": "tint:#5a4a6a",
     "note": "Flügelhaut leder-lila"},
    # Stoff
    {"id": "tattered_cloth", "name": "Zerrissener Stoff", "category": "material",
     "source": P_ORIG / "cloth_bolt.png", "transform": "tint:#8a7a6a",
     "note": "cloth_bolt mit grau-braun-Tint = zerrissen"},
    {"id": "damp_cloth", "name": "Klamme Stoffbahn", "category": "material",
     "source": P_ORIG / "cloth_bolt.png", "transform": "tint:#6a7a7a",
     "note": "cloth_bolt mit feucht-grünlich"},
    {"id": "ancient_silk", "name": "Antike Seide", "category": "material",
     "source": P_ORIG / "cloth_bolt.png", "transform": "tint:#c8a868",
     "note": "cloth_bolt mit antikem gold-beige"},
    {"id": "ancient_bandage", "name": "Antike Bandage", "category": "material",
     "source": P_ORIG / "cloth_bolt.png", "transform": "tint:#a89870",
     "note": "Mumien-Bandage gelblich-vergilbt"},
    {"id": "dream_silk", "name": "Traumseide", "category": "material",
     "source": P_ORIG / "cloth_bolt.png", "transform": "tint:#a878d8",
     "note": "Traumseide schimmerndes lila"},
    # Erze
    {"id": "crude_steel_ingot", "name": "Roher Stahlbarren", "category": "material",
     "source": P_ORIG / "iron_ore.png", "transform": "copy",
     "note": "iron_ore = roher Stahl-Klumpen"},
    {"id": "mythril_ingot", "name": "Mythril-Barren", "category": "material",
     "source": P_ORIG / "iron_ore.png", "transform": "tint:#a8c8e0",
     "note": "iron_ore mit silber-blau für Mythril"},
    {"id": "starfall_ingot", "name": "Sternenfall-Barren", "category": "material",
     "source": P_ORIG / "iron_ore.png", "transform": "tint:#9a8ad8",
     "note": "iron_ore mit kosmischem lila-blau"},
    {"id": "polished_stone", "name": "Polierter Stein", "category": "material",
     "source": P_ORIG / "rough_stone.png", "transform": "copy",
     "note": "rough_stone als polished_stone"},
    {"id": "salt_lump", "name": "Salzklumpen", "category": "material",
     "source": P_ORIG / "rough_stone.png", "transform": "tint:#f0f0e8",
     "note": "rough_stone mit weiß-creme-Tint = Salz"},
    # Spezial-Mats
    {"id": "naga_scale", "name": "Naga-Schuppe", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#5aa890",
     "note": "blue_crystal als grünliche Schuppe"},
    {"id": "wyrm_scale", "name": "Wyrm-Schuppe", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#9a6a3a",
     "note": "blue_crystal mit Wyrm-bronze"},
    {"id": "worm_chitin", "name": "Wurm-Chitin", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#8a6a3a",
     "note": "Knochen-bruch als Chitin-Bruch ocker"},
    {"id": "kelpie_mane", "name": "Kelpie-Mähne", "category": "material",
     "source": P_ORIG / "leather_roll.png", "transform": "tint:#3a6a7a",
     "note": "Leder-bahn als nasse blau-grüne Mähne"},
    {"id": "kraken_ink", "name": "Kraken-Tinte", "category": "material",
     "source": P_ORIG / "mana_potion.png", "transform": "tint:#2a2a3a",
     "note": "mana_potion mit fast-schwarz für Tinte"},
    {"id": "plant_fiber", "name": "Pflanzenfaser", "category": "material",
     "source": P_ORIG / "tall_grass_tuft.png", "transform": "copy",
     "note": "tall_grass_tuft = Pflanzenfaser direkt"},
    {"id": "briar_thorn", "name": "Dorn aus dem Gestrüpp", "category": "material",
     "source": P_ORIG / "tall_grass_tuft.png", "transform": "tint:#4a3a2a",
     "note": "tall_grass mit dunklem braun = Dornen-Strauch"},
    {"id": "thornmaw_seed", "name": "Thornmaw-Samen", "category": "material",
     "source": P_ORIG / "mushroom_cluster.png", "transform": "tint:#6a3a4a",
     "note": "mushroom als düsterer dornen-samen"},
    {"id": "clockwork_gear", "name": "Uhrwerk-Zahnrad", "category": "material",
     "source": P_ORIG / "rune_altar.png", "transform": "tint:#a89060",
     "note": "rune_altar mit bronze für Zahnrad"},

    # ── 2. FOOD ──
    {"id": "rotten_flesh", "name": "Faules Fleisch", "category": "food",
     "source": P_ORIG / "cooked_meat.png", "transform": "tint:#6a5a3a",
     "note": "cooked_meat mit fauler grün-brauner Tönung"},
    {"id": "dark_meat", "name": "Dunkles Fleisch", "category": "food",
     "source": P_ORIG / "cooked_meat.png", "transform": "tint:#5a2a1a",
     "note": "cooked_meat mit dunkel-rotem Tint"},
    {"id": "pork_loin", "name": "Schweinerücken", "category": "food",
     "source": P_ORIG / "cooked_meat.png", "transform": "copy",
     "note": "cooked_meat direkt als Schweine-Stück"},
    {"id": "strider_meat", "name": "Strider-Filet", "category": "food",
     "source": P_ORIG / "cooked_meat.png", "transform": "tint:#d8a878",
     "note": "cooked_meat heller, hell-rosa für mageres Filet"},
    {"id": "tentacle_meat", "name": "Tentakel-Fleisch", "category": "food",
     "source": P_ORIG / "cooked_meat.png", "transform": "tint:#9a5a8a",
     "note": "cooked_meat mit krak-lila"},
    {"id": "herb_bundle", "name": "Kräuterbündel", "category": "food",
     "source": P_ORIG / "herb_bundle.png", "transform": "copy",
     "note": "direkter Match: herb_bundle"},

    # ── 3. DRAGON_PARTS ──
    {"id": "drake_scale", "name": "Drachen-Schuppe", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#8a3a3a",
     "note": "blue_crystal als rot-bronze Drachenschuppe"},
    {"id": "drake_horn", "name": "Drachen-Horn", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#3a2a2a",
     "note": "bone_fragments als dunkles Drachen-Horn"},
    {"id": "dragon_tooth", "name": "Drachenzahn", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#f8e8c8",
     "note": "bone_fragments als großer heller Drachenzahn"},
    {"id": "dragon_horn", "name": "Großes Drachen-Horn", "category": "material",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#7a5a3a",
     "note": "bone als großes goldenes Drachenhorn"},
    {"id": "dragon_heart", "name": "Drachenherz", "category": "trophy",
     "source": P_ORIG / "health_potion.png", "transform": "tint:#aa1a1a",
     "note": "health_potion intensives rot pulsierend"},
    {"id": "fire_gland", "name": "Feuer-Drüse", "category": "material",
     "source": P_ORIG / "fire_resist_potion.png", "transform": "copy",
     "note": "fire_resist_potion = Feuer-Essenz-Drüse"},
    {"id": "frost_gland", "name": "Frost-Drüse", "category": "material",
     "source": P_ORIG / "mana_potion.png", "transform": "tint:#7ad0e8",
     "note": "mana_potion eis-cyan getintet"},
    {"id": "acid_gland", "name": "Säure-Drüse", "category": "material",
     "source": P_ORIG / "mana_potion.png", "transform": "tint:#9ad84a",
     "note": "mana_potion ätzend-grün"},
    {"id": "poison_gland", "name": "Gift-Drüse", "category": "material",
     "source": P_ORIG / "antidote_potion.png", "transform": "tint:#6aaa3a",
     "note": "antidote_potion als gift-grüne Drüse"},
    {"id": "storm_gland", "name": "Sturm-Drüse", "category": "material",
     "source": P_ORIG / "mana_potion.png", "transform": "tint:#a8a8e8",
     "note": "mana_potion mit blitz-lavendel"},
    {"id": "emerald_egg", "name": "Smaragd-Ei", "category": "trophy",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#3aa86a",
     "note": "blue_crystal als smaragdgrünes Ei"},

    # ── 4. ESSENCES / MAGIC ──
    {"id": "essence_arcane", "name": "Arkane Essenz", "category": "material",
     "source": P_ORIG / "mana_potion.png", "transform": "tint:#a868e8",
     "note": "mana_potion als arkane Essenz lila"},
    {"id": "essence_fire", "name": "Feuer-Essenz", "category": "material",
     "source": P_ORIG / "fire_resist_potion.png", "transform": "tint:#e85a2a",
     "note": "fire_resist mit intensiverer feuer-orange"},
    {"id": "essence_frost", "name": "Frost-Essenz", "category": "material",
     "source": P_ORIG / "mana_potion.png", "transform": "tint:#7ad8f0",
     "note": "mana_potion mit eis-cyan"},
    {"id": "essence_water", "name": "Wasser-Essenz", "category": "material",
     "source": P_ORIG / "water_flask.png", "transform": "copy",
     "note": "water_flask direkt als Wasser-Essenz"},
    {"id": "essence_lightning", "name": "Blitz-Essenz", "category": "material",
     "source": P_ORIG / "mana_potion.png", "transform": "tint:#f0e858",
     "note": "mana_potion mit blitz-gelb"},
    {"id": "essence_storm", "name": "Sturm-Essenz", "category": "material",
     "source": P_ORIG / "mana_potion.png", "transform": "tint:#7a8aa8",
     "note": "mana_potion mit sturm-grau-blau"},
    {"id": "soul_essence", "name": "Seelen-Essenz", "category": "material",
     "source": P_ORIG / "mana_potion.png", "transform": "tint:#cae8d0",
     "note": "mana_potion mit geister-weiß-grün"},
    {"id": "void_essence", "name": "Leere-Essenz", "category": "material",
     "source": P_ORIG / "mana_potion.png", "transform": "tint:#2a1a3a",
     "note": "mana_potion mit fast-schwarz lila"},
    {"id": "sleep_essence", "name": "Schlaf-Essenz", "category": "material",
     "source": P_ORIG / "mana_potion.png", "transform": "tint:#8a8ac8",
     "note": "mana_potion mit traum-lavendel"},
    {"id": "wisp_essence", "name": "Irrlicht-Essenz", "category": "material",
     "source": P_ORIG / "mana_potion.png", "transform": "tint:#9af0a8",
     "note": "mana_potion mit irrlicht-mintgrün"},
    {"id": "frost_dust", "name": "Frost-Staub", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#cae8f8",
     "note": "blue_crystal als feinpulvriger Frost"},
    {"id": "astral_dust", "name": "Astral-Staub", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#c8a8f8",
     "note": "blue_crystal als kosmischer Staub"},
    {"id": "dryad_sap", "name": "Dryaden-Saft", "category": "material",
     "source": P_ORIG / "mana_potion.png", "transform": "tint:#7ac850",
     "note": "mana_potion mit pflanzen-grün"},
    {"id": "ghoul_tongue", "name": "Ghul-Zunge", "category": "material",
     "source": P_ORIG / "cooked_meat.png", "transform": "tint:#7a3a4a",
     "note": "cooked_meat mit untot-violett"},
    {"id": "imp_eye", "name": "Kobold-Auge", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#e83a3a",
     "note": "blue_crystal als rotes Imp-Auge"},
    {"id": "aberrant_eye", "name": "Aberrantes Auge", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#aa68ca",
     "note": "blue_crystal als verstörtes Auge"},
    {"id": "forehead_eye", "name": "Stirn-Auge", "category": "lore",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#daca7a",
     "note": "blue_crystal als goldenes seherauge"},
    {"id": "fire_core", "name": "Feuer-Kern", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#e87a2a",
     "note": "blue_crystal als feurig-orange Kern"},
    {"id": "granite_core", "name": "Granit-Kern", "category": "material",
     "source": P_ORIG / "rough_stone.png", "transform": "tint:#5a5a6a",
     "note": "rough_stone als grauer Kern"},
    {"id": "glowing_core", "name": "Glühender Kern", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#f8d878",
     "note": "blue_crystal als hellgelb-glühend"},
    {"id": "magma_heart", "name": "Magma-Herz", "category": "trophy",
     "source": P_ORIG / "health_potion.png", "transform": "tint:#e83a1a",
     "note": "health_potion intensives feuerrot"},
    {"id": "avalanche_core", "name": "Lawinen-Kern", "category": "trophy",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#d0e8f0",
     "note": "blue_crystal als eis-weiß Kern"},
    {"id": "ossuary_core", "name": "Ossuar-Kern", "category": "trophy",
     "source": P_ORIG / "bone_fragments.png", "transform": "tint:#e8d8b0",
     "note": "bone_fragments als ossuar-elfenbein"},
    {"id": "phylactery_shard", "name": "Phylakterie-Splitter", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#2a4a6a",
     "note": "blue_crystal als dunkler lich-splitter"},
    {"id": "old_god_shard", "name": "Alter-Gott-Splitter", "category": "lore",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#5a3a7a",
     "note": "blue_crystal als alter-gott-lila"},
    {"id": "sanity_shard", "name": "Verstand-Splitter", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#a8a8d8",
     "note": "blue_crystal als bleiche verstand-scherbe"},
    {"id": "impossible_angle", "name": "Unmöglicher Winkel", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#3a2a4a",
     "note": "blue_crystal als nicht-euklidisches lila-schwarz"},
    {"id": "storm_glass", "name": "Sturm-Glas", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#9aa8c8",
     "note": "blue_crystal als sturm-glas grau-violett"},
    {"id": "soul_lantern_shard", "name": "Seelenlaternen-Scherbe", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#daca6a",
     "note": "blue_crystal als laternen-gelb"},
    {"id": "night_shard", "name": "Nacht-Splitter", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#1a1a3a",
     "note": "blue_crystal als nacht-schwarz-blau"},
    {"id": "glacier_eye", "name": "Gletscher-Auge", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#a8e0f0",
     "note": "blue_crystal als hell-eisblau"},

    # ── 5. GEMS / PEARLS ──
    {"id": "pearl_great", "name": "Große Perle", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#f0e8d8",
     "note": "blue_crystal als großes perlweiß"},
    {"id": "mire_pearl", "name": "Morast-Perle", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#6a7a5a",
     "note": "blue_crystal als trüb-grüne Sumpf-Perle"},
    {"id": "river_pearl", "name": "Fluss-Perle", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#a8d0e0",
     "note": "blue_crystal als hellblaue Fluss-Perle"},
    {"id": "brine_pearl", "name": "Sole-Perle", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#c8d8d0",
     "note": "blue_crystal als grünlich-graue Salz-Perle"},
    {"id": "crystal_shard", "name": "Kristall-Splitter", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "copy",
     "note": "blue_crystal direkt als Kristall-Splitter"},
    {"id": "sand_crystal", "name": "Sand-Kristall", "category": "material",
     "source": P_ORIG / "blue_crystal.png", "transform": "tint:#daba6a",
     "note": "blue_crystal als sandiger goldkristall"},

    # ── 6. WEAPONS ──
    {"id": "rusty_sword", "name": "Verrostetes Schwert", "category": "weapon",
     "source": P_WEAP / "plain_aruming_sword.png", "transform": "tint:#8a5a3a",
     "note": "plain_aruming_sword mit rost-tint"},
    {"id": "iron_sword", "name": "Eisenschwert", "category": "weapon",
     "source": P_WEAP / "plain_aruming_sword.png", "transform": "copy",
     "note": "plain_aruming_sword direkt = iron sword"},
    {"id": "iron_spear", "name": "Eisenspeer", "category": "weapon",
     "source": P_WEAP / "plain_war_spear.png", "transform": "copy",
     "note": "plain_war_spear direkt"},
    {"id": "bone_dagger", "name": "Knochendolch", "category": "weapon",
     "source": P_WEAP / "hooked_ritual_dagger.png", "transform": "tint:#e8d8b0",
     "note": "hooked_ritual_dagger mit elfenbein für Knochen"},
    {"id": "bone_spear", "name": "Knochenspeer", "category": "weapon",
     "source": P_WEAP / "plain_war_spear.png", "transform": "tint:#e8d8b0",
     "note": "war_spear mit elfenbein für Knochenspeer"},
    {"id": "bone_staff", "name": "Knochenstab", "category": "weapon",
     "source": P_WEAP / "red_oak_staff.png", "transform": "tint:#e8d8b0",
     "note": "staff mit elfenbein-tint"},
    {"id": "bone_warhammer", "name": "Knochen-Streithammer", "category": "weapon",
     "source": P_ORIG / "iron_mace.png", "transform": "tint:#e8d8b0",
     "note": "iron_mace mit elfenbein für Knochenhammer"},
    {"id": "shaman_stick", "name": "Schamanen-Stock", "category": "weapon",
     "source": P_WEAP / "red_oak_staff.png", "transform": "tint:#7a5a3a",
     "note": "red_oak_staff dunkler braun für primitiv"},
    {"id": "worn_bow", "name": "Abgenutzter Bogen", "category": "weapon",
     "source": P_WEAP / "ashwood_recurve_bow.png", "transform": "tint:#7a6a5a",
     "note": "ashwood mit abgenutzt-grau"},
    {"id": "living_wood_bow", "name": "Lebendholz-Bogen", "category": "weapon",
     "source": P_WEAP / "goldleaf_bow.png", "transform": "tint:#5aa850",
     "note": "goldleaf_bow mit lebend-grün"},
    {"id": "demon_forge_hammer", "name": "Dämonen-Schmiedehammer", "category": "weapon",
     "source": P_ORIG / "iron_mace.png", "transform": "tint:#aa3a1a",
     "note": "iron_mace mit dämonen-rot-glühend"},

    # ── 7. ARMOR ──
    {"id": "iron_helm", "name": "Eisenhelm", "category": "armor",
     "source": P_ORIG / "crested_hoplite_helm.png", "transform": "copy",
     "note": "crested_hoplite_helm direkt"},
    {"id": "leather_armor_piece", "name": "Lederrüstungs-Teil", "category": "armor",
     "source": P_ORIG / "leather_vest.png", "transform": "copy",
     "note": "leather_vest direkt"},
    {"id": "noble_cloak", "name": "Adels-Umhang", "category": "armor",
     "source": P_ARMOR / "green_hooded_mantle.png", "transform": "tint:#7a3a3a",
     "note": "green_hooded_mantle als adels-roter Umhang"},
    {"id": "pilgrim_robe", "name": "Pilger-Robe", "category": "armor",
     "source": P_ARMOR / "green_hooded_mantle.png", "transform": "tint:#a8a090",
     "note": "green_hooded_mantle als pilger-graubeige"},
    {"id": "pharaoh_mask", "name": "Pharaonen-Maske", "category": "armor",
     "source": P_ORIG / "crested_hoplite_helm.png", "transform": "tint:#d8b048",
     "note": "helm mit pharaonen-gold"},
    {"id": "undying_crown", "name": "Untote Krone", "category": "armor",
     "source": P_ORIG / "crested_hoplite_helm.png", "transform": "tint:#3a3a4a",
     "note": "helm mit untot-grau"},
    {"id": "witchking_crown", "name": "Hexenkönig-Krone", "category": "armor",
     "source": P_ORIG / "crested_hoplite_helm.png", "transform": "tint:#3a2a5a",
     "note": "helm mit hexenkönig-lila"},
    {"id": "warchief_crown", "name": "Kriegshäuptlings-Krone", "category": "armor",
     "source": P_ORIG / "crested_hoplite_helm.png", "transform": "tint:#7a3a2a",
     "note": "helm mit warchief-bronze-rot"},

    # ── 8. JEWELRY ──
    {"id": "consecrated_amulet", "name": "Geweihtes Amulett", "category": "jewelry",
     "source": P_JEW / "amulets_magic_fantasy_stylized_textures_game.png", "transform": "tint:#f0e0a0",
     "note": "amulet asset mit goldenem geweiht-tint"},
    {"id": "scarab_amulet", "name": "Skarabäus-Amulett", "category": "jewelry",
     "source": P_JEW / "amulets_magic_fantasy_stylized_textures_game_02.png", "transform": "tint:#5aa848",
     "note": "amulet mit skarabäus-grün"},
    {"id": "blood_chalice", "name": "Blut-Kelch", "category": "jewelry",
     "source": P_ORIG / "mana_potion.png", "transform": "tint:#aa1a1a",
     "note": "mana_potion als blut-roter Kelch"},
    {"id": "inquisitor_signet", "name": "Inquisitor-Siegel", "category": "jewelry",
     "source": P_JEW / "dark_fantasy_ring_relic_epic_rpg_artifact_co.png", "transform": "tint:#d0c060",
     "note": "ring mit inquisitor-gold"},
    {"id": "crypt_signet", "name": "Krypta-Siegel", "category": "jewelry",
     "source": P_JEW / "dark_fantasy_ring_relic_epic_rpg_artifact_co.png", "transform": "tint:#4a4a5a",
     "note": "ring mit krypta-grau"},
    {"id": "traitor_signet", "name": "Verräter-Siegel", "category": "jewelry",
     "source": P_JEW / "dark_fantasy_ring_relic_epic_rpg_artifact_co.png", "transform": "tint:#7a2a2a",
     "note": "ring mit verräter-dunkelrot"},

    # ── 9. AMMO ──
    {"id": "arrow", "name": "Pfeil", "category": "ammo",
     "source": P_WEAP / "plain_war_spear.png", "transform": "tint:#8a6a3a",
     "note": "war_spear mini als Pfeil-Bündel"},
    {"id": "evergreen_arrow", "name": "Immergrün-Pfeil", "category": "ammo",
     "source": P_WEAP / "plain_war_spear.png", "transform": "tint:#3a8a3a",
     "note": "war_spear mit evergreen-grün"},
    {"id": "silver_bolt", "name": "Silber-Bolzen", "category": "ammo",
     "source": P_WEAP / "plain_war_spear.png", "transform": "tint:#c8c8d0",
     "note": "war_spear mit silber-tint"},

    # ── 10. TROPHIES / QUEST ──
    {"id": "goblin_ear", "name": "Goblin-Ohr", "category": "trophy",
     "source": P_ORIG / "goblin_raider_bust.png", "transform": "copy",
     "note": "goblin_raider_bust als Goblin-Trophäe"},
    {"id": "orgrim_skull", "name": "Orgrim-Schädel", "category": "trophy",
     "source": P_ORIG / "skeletal_warrior_bust.png", "transform": "tint:#8a7a6a",
     "note": "skeletal_warrior_bust als Orgrim-Schädel-Trophäe"},
    {"id": "captain_banner", "name": "Hauptmann-Banner", "category": "trophy",
     "source": P_ORIG / "cloth_bolt.png", "transform": "tint:#aa3a3a",
     "note": "cloth_bolt als blut-rotes Banner"},
    {"id": "boss_trophy", "name": "Boss-Trophäe", "category": "trophy",
     "source": P_ORIG / "necromancer_bust.png", "transform": "copy",
     "note": "necromancer_bust als generische Boss-Trophäe"},
    {"id": "crude_map_fragment", "name": "Karten-Fragment", "category": "quest",
     "source": P_LORE / "dungeon_map.png", "transform": "copy",
     "note": "dungeon_map direkt = Karten-Fragment"},
    {"id": "drowner_lock_of_hair", "name": "Ziehenden-Haarlocke", "category": "quest",
     "source": P_ORIG / "leather_roll.png", "transform": "tint:#3a4a3a",
     "note": "leather_roll als nasses dunkelgrünes Haar"},
    {"id": "living_toad", "name": "Lebende Kröte", "category": "quest",
     "source": P_MOBS / "creature_bog_toad_icon_64.png", "transform": "copy",
     "note": "bog_toad icon als lebende Kröte"},
    {"id": "messenger_capsule", "name": "Boten-Kapsel", "category": "quest",
     "source": P_LORE / "kings_seal.png", "transform": "copy",
     "note": "kings_seal als versiegelte Boten-Kapsel"},
    {"id": "stolen_pouch", "name": "Gestohlener Beutel", "category": "quest",
     "source": P_ORIG / "coin_stack.png", "transform": "tint:#8a6a3a",
     "note": "coin_stack mit beutel-braun"},
    {"id": "well_idol", "name": "Brunnen-Idol", "category": "quest",
     "source": P_ORIG / "rune_altar.png", "transform": "tint:#5a6a7a",
     "note": "rune_altar als wasser-stein-idol"},
    {"id": "plague_phial", "name": "Pest-Phiole", "category": "quest",
     "source": P_ORIG / "antidote_potion.png", "transform": "tint:#aaaa3a",
     "note": "antidote_potion als pest-gelb-grün"},

    # ── 11. CONSUMABLES ──
    {"id": "witch_brew", "name": "Hexenbräu", "category": "consumable",
     "source": P_ORIG / "mana_potion.png", "transform": "tint:#5a3a6a",
     "note": "mana_potion als hexenbräu-dunkellila"},

    # ── 12. LORE ──
    {"id": "lore_fragment", "name": "Lore-Fragment", "category": "lore",
     "source": P_LORE / "research_scroll.png", "transform": "copy",
     "note": "research_scroll direkt"},
    {"id": "unique_lore_item", "name": "Einzigartiges Lore-Stück", "category": "lore",
     "source": P_LORE / "research_tome.png", "transform": "copy",
     "note": "research_tome als einzigartiges lore-buch"},
    {"id": "white_pilgrim_token", "name": "Weißer Pilger-Stein", "category": "lore",
     "source": P_LORE / "kings_seal.png", "transform": "tint:#f0f0e8",
     "note": "kings_seal mit weiß-tint"},
    {"id": "tech_print", "name": "Tech-Druck", "category": "lore",
     "source": P_LORE / "research_scroll.png", "transform": "tint:#a8c8d8",
     "note": "research_scroll mit tech-blau-grau"},
    {"id": "dark_grimoire", "name": "Dunkles Grimoire", "category": "lore",
     "source": P_LORE / "research_tome.png", "transform": "tint:#3a2a4a",
     "note": "research_tome mit dunkellila"},
    {"id": "ancient_treasure", "name": "Antiker Schatz", "category": "lore",
     "source": P_ORIG / "coin_stack.png", "transform": "tint:#d8c060",
     "note": "coin_stack mit antik-gold tint"},
    {"id": "star_mote_shard", "name": "Stern-Splitter", "category": "lore",
     "source": P_LORE / "rift_lore.png", "transform": "copy",
     "note": "rift_lore direkt als Stern-Splitter"},
]


# ──────────────────────────────────────────────────────────────────────────────
# PIL Helpers
# ──────────────────────────────────────────────────────────────────────────────
def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def hex_to_rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def alpha_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    return img.convert("RGBA").getbbox()


def fit_canvas(img: Image.Image, size: int = 128, padding: int = 8) -> Image.Image:
    img = img.convert("RGBA")
    bbox = alpha_bbox(img)
    if bbox:
        img = img.crop(bbox)
    max_side = size - padding * 2
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((size - img.width) // 2, (size - img.height) // 2))
    return canvas


def apply_tint(img: Image.Image, tint_hex: str) -> Image.Image:
    """Multiply RGB-Kanäle mit Tint, Alpha bleibt erhalten.

    Sorgt dafür dass Details (Schatten/Highlights) erhalten bleiben, aber
    der Grundton in Richtung Tint verschoben wird.
    """
    img = img.convert("RGBA")
    r, g, b, a = img.split()
    tr, tg, tb = hex_to_rgb(tint_hex)

    # Lookup-Tables für Multiply: out = in * tint / 255
    lut_r = [(i * tr) // 255 for i in range(256)]
    lut_g = [(i * tg) // 255 for i in range(256)]
    lut_b = [(i * tb) // 255 for i in range(256)]

    r = r.point(lut_r)
    g = g.point(lut_g)
    b = b.point(lut_b)
    return Image.merge("RGBA", (r, g, b, a))


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "arial.ttf",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def render_placeholder(name: str, category: str, size: int = 128) -> Image.Image:
    """Solid-color box mit Initial, transparente Ecken (8px Padding)."""
    bg_hex = CAT_COLOR.get(category, "#5a5a5a")
    bg = hex_to_rgb(bg_hex)
    pad = 8
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Hintergrund-Box mit gerundeten Ecken
    draw.rounded_rectangle((pad, pad, size - pad, size - pad),
                            radius=10, fill=(*bg, 230),
                            outline=(20, 20, 20, 230), width=2)
    # Initial
    initial = (name or "?").strip()[0].upper()
    font = load_font(60)
    bbox = draw.textbbox((0, 0), initial, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1]
    # Schatten
    draw.text((tx + 2, ty + 2), initial, font=font, fill=(0, 0, 0, 180))
    draw.text((tx, ty), initial, font=font, fill=(245, 240, 225, 255))
    return img


def build_one(drop: dict) -> tuple[Path, str]:
    """Generiert PNG für einen Drop, returnt (out_path, used_source_or_'placeholder')."""
    transform = drop.get("transform", "copy")
    source: Path | None = drop.get("source")
    out_path = OUT_ROOT / f"{drop['id']}.png"

    if transform.startswith("placeholder") or source is None or not source.exists():
        img = render_placeholder(drop["name"], drop["category"])
        used = "placeholder"
    else:
        img = Image.open(source)
        # crop:left,top,right,bottom (optional vor copy/tint)
        if transform.startswith("crop:"):
            parts = transform.split(":", 1)[1]
            l, t, r, b = (int(x) for x in parts.split(","))
            img = img.crop((l, t, r, b))
            transform = "copy"  # nach crop default copy
        img = fit_canvas(img, 128, padding=8)
        if transform.startswith("tint:"):
            img = apply_tint(img, transform.split(":", 1)[1])
        used = rel(source)
    img.save(out_path)
    return out_path, used


def build_contact(items: list[dict]) -> Path:
    cols = 12
    cell = 128
    label_h = 22
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + label_h)), (28, 28, 28))
    draw = ImageDraw.Draw(sheet)
    font = load_font(11)
    for idx, item in enumerate(items):
        x = (idx % cols) * cell
        y = (idx // cols) * (cell + label_h)
        bg = Image.new("RGBA", (cell, cell), (42, 42, 42, 255))
        sprite = Image.open(ROOT / item["generated_path"]).convert("RGBA")
        bg.alpha_composite(sprite, (0, 0))
        sheet.paste(bg.convert("RGB"), (x, y))
        label = item["id"][:18]
        draw.text((x + 4, y + cell + 4), label, font=font, fill=(225, 225, 225))
    out = OUT_ROOT / "contacts" / "drop_items_contact.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)
    return out


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "contacts").mkdir(parents=True, exist_ok=True)

    seen_ids: set[str] = set()
    placeholder_count = 0
    derived_count = 0
    missing_sources: list[str] = []
    manifest_items: list[dict] = []

    for drop in DROPS:
        if drop["id"] in seen_ids:
            raise SystemExit(f"Duplicate id: {drop['id']}")
        seen_ids.add(drop["id"])

        src = drop.get("source")
        if src is not None and not src.exists():
            missing_sources.append(f"{drop['id']}: {src}")

        out_path, used = build_one(drop)
        if used == "placeholder":
            placeholder_count += 1
        else:
            derived_count += 1

        manifest_items.append({
            "id": drop["id"],
            "name": drop["name"],
            "category": drop["category"],
            "source": used,
            "transform": drop.get("transform", "copy"),
            "note": drop.get("note", ""),
            "generated_path": rel(out_path),
        })

    contact_path = build_contact(manifest_items)
    manifest = {
        "generated": "2026-05-30",
        "asset_type": "monster_drop_items",
        "source_request": "146 Slugs aus backend/monster_drop_items.py (Welle 35)",
        "count": len(manifest_items),
        "derived_from_existing": derived_count,
        "placeholders": placeholder_count,
        "contact": rel(contact_path),
        "items": manifest_items,
    }
    (OUT_ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[drop-icons] generated={len(manifest_items)} derived={derived_count} placeholders={placeholder_count}")
    if missing_sources:
        print(f"[drop-icons] WARN: {len(missing_sources)} sources missing (fell back to placeholder):")
        for m in missing_sources:
            print(f"  - {m}")
    print(f"[drop-icons] contact: {contact_path}")


if __name__ == "__main__":
    main()
