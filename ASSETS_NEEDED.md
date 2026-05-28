# Asset-Wunschliste

Stand: 2026-05-28. Erstellt nach dem Aufräumen der unbrauchbaren `from_neu_pro`-Packs
(armor, magic, resources komplett gelöscht; monsters/potions stark ausgedünnt).

---

## Allgemeine Stil-Vorgaben

**Konsistenz mit existierenden Packs:**
- Painterly-Style, dunkel-gritty wie `equipment/weapons/professional/inspired_2026_05_27/`
  (Beispiele dort: iron_vigil_longsword, oxhide_execution_axe — solche Optik bitte)
- Inventar-Icons isoliert auf **transparentem Hintergrund** (PNG)
- Lieferung pro Slug in **vier Größen**:
  `masters_512`, `icons_256`, `icons_128`, `icons_64`
- Slugs in `snake_case`, ASCII only
- Jedes Pack bekommt eine `manifest.json` im gleichen Format wie
  `equipment/weapons/professional/inspired_2026_05_27/manifest.json`
  (mit `game_kind_hint`, `description`, `paths`)

**No-Gos (gelernt aus dem Müll-Pack):**
- ❌ KEINE Concept-Art-Renders mit Pergament-/Notebook-Hintergrund
- ❌ KEINE Multi-Asset-Sprite-Sheets (mehrere Items auf einem Bild)
- ❌ KEINE Wasserzeichen oder Branding (Heroes V, MTG-Card-Layouts etc.)
- ❌ KEINE Character-Full-Body-Renders, wenn ein Item-Icon gemeint ist
- ❌ KEINE Strichzeichnung-Skizzen, keine Mono-Themen (z.B. „alles grün")

---

## 1. Tech-Print-Icons (8 Stück) — HOHE PRIORITÄT

**Was:** Konsumierbare Pläne/Schriften, die für 25 Endgame-Research-Nodes als
Crafting-Voraussetzung im Inventar liegen müssen. Aktuell sind alle 8 Platzhalter.

**Format:** 128×128, transparent, im painterly-Stil der Inspired-Pakete

**Konkrete Slugs + Optik:**

| Slug | Optik |
|---|---|
| `mithril_plans` | Aufgerollte Architekturzeichnung mit silbrig schimmernden Markierungen, Schmiede-Hammer-Symbol |
| `dragon_skull` | Verwitterter Drachenschädel, kein Trophäenstandfuß — als Forschungsartefakt |
| `ancient_scroll` | Vergilbte Pergamentrolle mit goldenem Siegel und alter Schrift |
| `gods_tablet` | Steintafel mit eingemeißelten Runen, leicht beschädigt, mit göttlich-goldener Aura |
| `alchemy_codex` | Aufgeschlagenes Alchemie-Buch mit grün-glühenden Formel-Diagrammen |
| `runic_tablet` | Dunkle Basaltplatte mit blau-leuchtenden Runen, kleiner als gods_tablet |
| `healing_codex` | Aufgeschlagenes Heilbuch mit weiß-leuchtenden Symbolen, frische Pergament-Seiten |
| `trade_ledger` | Dickes Hauptbuch mit Lederband, eingedruckten Goldmünzen, Kaufmanns-Stil |

**Wozu:** Forschung benötigt diese Items im Inventar — Backend ist fertig, nur die
Sprites müssen rein. Slot-Pfade in `backend/items.py` sind bereits angelegt.

---

## 2. Armor-Icons (komplettes Set) — HOHE PRIORITÄT

**Was:** Tragbare Rüstungsteile als Inventar-Icons. Das alte Pack hatte
Heroes-V-Wasserzeichen und Concept-Art-Renders statt Icons — komplett unbrauchbar.

**Format:** 128×128, transparent, painterly-Stil. Pro Slot und Tier eigene Variante.

**Slots:** helmet, chestplate, gloves, boots, shield

**Tiers (`backend/items.py` kennt diese 12):**
cloth, fur, leather, copper, iron, silver, gold, mithril, platinum, tungsten,
crystal, adamant

**Pro Slot mindestens 4 Tiers** als Skin-Variation (z.B. iron/silver/mithril/adamant für helmet)

**Optik-Beispiele:**
- `helmet_iron` — geschmiedeter Schaller, klassisch mittelalterlich, leicht verbeult
- `chestplate_iron` — Brustpanzer, Riemen sichtbar, Beulen-Detail
- `gloves_iron` — gepanzerte Handschuhe, Gelenke betont
- `boots_iron` — Sabaton-Stiefel mit Schnallen
- `shield_iron` — Heater-Shield, schlicht, leichter Wappen-Frame
- `helmet_mithril` — wie helmet_iron aber silbrig-bläulich schimmernd, edler
- `chestplate_cloth` — Wams aus Leinen, kein Metall, einfache Schnürung

**Wozu:** Equipment-Slot-System nutzt diese — ohne Sprites sieht der Charakter generisch aus.

---

## 3. Echter Schmuck — Ringe + Amulette (je 8 Skins)

**Was:** Tragbare Ringe und Amulette als Inventar-Icons. Das alte `jewelry/from_neu_pro`
hatte hauptsächlich Tierkreis-Sigille und Wappen-Crests, kein echter Schmuck.

**Format:** 128×128, transparent. Pro Slot 8 Skin-Varianten quer durch die Quality-Tiers.

**Ringe:**
- 4× Metallring mit Edelstein (Rubin, Saphir, Smaragd, Diamant) — Vorderansicht leicht schräg
- 2× Magie-Ring mit Rune/Symbol statt Stein, leicht glühend
- 2× Schlichter Bandring (Gold, Silber) ohne Stein

**Amulette:**
- 4× Anhänger an Kette mit Edelstein-Tropfen (verschiedene Farben)
- 2× Reliquien-Amulett (kleines Buch/Schädel/Kreuz an Kette)
- 2× Magie-Sigil-Amulett (Pentagramm/Rune in Metallrahmen, leichte Aura)

**Wozu:** `equipment/jewelry/` enthält bisher nur `amulet.png` und `ring.png` als
einzelne Platzhalter. Skin-Pool für ring/amulet würde sich anbieten analog zum
Sword/Greatsword-Pool.

---

## 4. Resource-Sprites — Mining & Crafting (komplettes Set)

**Was:** Rohstoffe als Inventar-Stack-Icons. `resources/from_neu_pro` war kompletter Müll
(Concept-Renders, Multi-Sheets, Skizzen) und wurde gelöscht.

**Format:** 128×128, transparent, painterly-Stil

**Liste (je 1 Sprite, sortiert nach Verwendung im Spiel):**

**Holz & Pflanzen:**
- `wood_log` — kurzer Holzscheit mit Rindenstruktur
- `wood_plank` — drei gestapelte Bretter
- `branch` — abgebrochener dünner Ast mit Blättern
- `fiber` — Bündel Pflanzenfasern, mit Schnur gebunden

**Stein:**
- `stone_rock` — unbearbeiteter Stein, klobig
- `stone_block` — quaderförmiger Bauwerksteinblock
- `flint` — kantiger Feuerstein, dunkelgrau
- `clay` — Klumpen Ton, terracotta-farben

**Erze (Roh + Barren je):**
Für copper, iron, silver, gold, mithril, platinum, tungsten, crystal, adamant
- `<metal>_ore` — Stein-Klumpen mit eingebetteten Erz-Adern in passender Farbe
- `<metal>_ingot` — geschmiedeter Barren, glatte Form

**Magisch:**
- `mana_crystal` — leuchtender Kristall-Cluster in Blau
- `arcane_dust` — kleines Säckchen leuchtenden Staub
- `rune_fragment` — Steinbruchstück mit eingravierter Rune

**Tierprodukte:**
- `leather_hide` — gegerbtes Lederstück, faltig
- `fur_pelt` — Tierpelz mit Fellseite oben
- `bone` — verwitterter Knochen
- `feather` — einzelne Feder, leicht gebogen

**Wozu:** Crafting, Inventar, Stack-Display. Aktuell viele Platzhalter oder
Flat-Cartoon-Sprites die nicht zum painterly-Style passen.

---

## 5. Weapon-Skin-Pool-Erweiterung

**Was:** Skin-Varianten für die Kinds die bisher KEINEN Pool haben (siehe
`backend/skin_pools.py`). Aktuell nur `sword` und `greatsword` mit Pool;
`staff`/`wand` werden mit `inspired_arcane` v1+v2 bald versorgt.

**Format:** Wie `inspired_2026_05_27` — jeweils 128/256/512, transparent, painterly.

**Pro Kind mindestens 8 Skin-Varianten:**
- `bow` — verschiedene Holz/Sehnen-Kombos (Eibe, Esche, Mahagoni; Recurve, Longbow)
- `crossbow` — Standard, Schwer, Repetier; verschiedene Bolzen-Magazin-Designs
- `axe` — 1H-Kriegsaxt, Schmiede-Axt, Stahl-Beil, schwere Doppelaxt
- `mace` — Streitkolben (glatt, geriffelt), Morgenstern mit Spitzen, Knochen-Keule
- `dagger` — Stilett, geschwungener Krummdolch, Wurfdolch, Opfer-Klinge
- `spear` — Stoßlanze, Wurfspeer, Hellebardenkopf, Trident-ähnlich
- `scythe` — Erntesense (rustikal), Kampf-Sense (länger), Knochen-Sense
- `throwing_knife` — Sets von 3 Klingen in verschiedenen Formen

**Wozu:** Loot-Drops aus Mob-Kills oder Chests rollen einen Skin aus dem Pool — gibt
Variation im Inventar statt immer dem gleichen Default-Sprite.

---

## 6. Monster-Sprites — Wave-28-Replacements (33 Stück)

**Was:** Niedrigauflösende Sprites aus Welle 28 ersetzen. Stand HANDOFF: User in Arbeit.

**Format:** World-Sprite 96×96 + Icon 128×128 + Master 256×256, transparent

**Monster-Liste** (aus `backend/npcs.py` Tier-1 bis Tier-3, die noch unter
`monsters/world_sprites/legacy_33/` liegen):

Tier 1: rat, bat, slime, slimelet, fae_mite, ember_rat, gloom_moth, thorn_scarab, crystal_tick
Tier 2: wolf, boar, spider, giant_spider, goblin, bandit, skeleton, zombie, fire_imp, frost_sprite, ember_newt, mushroom_imp, thornling
Tier 3: dire_wolf, wolf_alpha, polar_bear, cave_bear, bear, ogre, harpy, gargoyle, crystal_beetle, bone_crawler, cougar, lynx, wolverine, stag, crocodile, cobra

**Stil-Vorgabe:** Wie `monsters/world_sprites/reference_based/` Pack (rockshell_colossus,
mantis_chimera, void_eye_brute etc.) — cleane painterly Sprites, leicht dunkel, klar isoliert.

---

## 7. Spell-Icons (10+ Stück) — MITTLERE PRIORITÄT

**Was:** Eigene Icons für die 10 Spells statt FX-Animation-Frame-Recycling.
Aktuell nutzt `backend/spells.py` Frames aus `animations/professional/combat_magic/`,
was funktioniert aber als Inventar-Icon nicht ideal aussieht.

**Format:** 128×128, transparent, painterly + leichter Glow-Effekt

**Heiler-Spells (5):**
- `heal_minor` — kleine weiße Lichtkugel mit goldenem Kreuz
- `heal_major` — größere Lichtkugel mit Sonnen-Strahlen
- `cure` — grüner Schimmer mit Schlangen-Symbol (Asklepios)
- `holy_shield` — gold-leuchtender Schild mit Kreuz
- `bless` — drei goldene aufsteigende Kugeln

**Magier-Spells (5):**
- `fireball` — rotorange Feuerkugel mit Flammenzunge
- `frost_bolt` — eis-blauer Pfeil mit Frost-Aura
- `lightning_strike` — gezackter gelber Blitz, leicht gekrümmt
- `mana_shield` — blauer Schild mit Rune in der Mitte
- `arcane_missile` — violette Energie-Kugel mit Nebel-Schweif

**Wozu:** Hotbar + Spellbook zeigen aktuell Anim-Frames als Icon. Eigene Icons machen
das UI klarer und weniger redundant.

---

## 8. Potion-Varianten (5+ Stück)

**Was:** Mehr Trank-Sprites als Skin-Variation. Aktuell nur 2 verbliebene gute Sprites
(`a_magic_potion`, `asset_03`).

**Format:** 128×128, transparent, painterly. Klassische Flaschen-Form vorne.

**Liste:**
- `health_potion_small/large` — rote Flüssigkeit, leicht leuchtend, Kork-Verschluss
- `mana_potion_small/large` — blaue Flüssigkeit, magisches Glimmen
- `stamina_potion` — grüne Flüssigkeit, einfacher Krug
- `strength_potion` — orange-rote Flüssigkeit, breite Phiole
- `invisibility_potion` — milchig-transparent, verzerrender Effekt
- `frost_resist_potion` — eis-blaue Flüssigkeit, Reif am Glas
- `poison_potion` — gift-grün, schmale spitze Flasche, evtl. Totenkopf-Etikett
- `speed_potion` — gelb, „spritzige" Flüssigkeit mit Bläschen

**Wozu:** Loot-Tables und Alchemie-Crafting nutzen die Potion-Kinds bereits, aktuell
zeigen viele auf einen Default oder dasselbe Sprite.

---

## 9. UI / Misc — NIEDRIGE PRIORITÄT

- **Quest-Marker-Icons** für die Quest-Board-Rotation (Hauptquest, Daily, Defend, Escort)
- **Faction-Wappen** (ca. 8 Stück) für die jewelry-Sigille-Lücke — können
  Mandala/Wappen-Style sein, das ist im jewelry-Pack nicht das Problem gewesen
- **Currency-Sprites** (Kupfer/Silber/Gold-Münze, Edelstein) — gibt schon `food_ration.png`
  Pfad, aber dedizierte Currency-Icons fehlen

---

## Anti-Sammelliste

**NICHT erneut liefern:**
- Tierkreis-Sigille (haben wir 10, ungenutzt)
- Wappen-Crests im Mobile-UI-Style (haben wir ~20, ungenutzt)
- Concept-Art-Sheets mit Pergament-Hintergrund
- Mono-thematische Sticker-Packs (alles grün, alles violett etc.)

Falls solche Assets kommen, bitte direkt in einen separaten `experimental/`-Ordner
und nicht ins Haupt-Asset-Tree.
