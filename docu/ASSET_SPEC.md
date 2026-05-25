# Liege — Asset-Spezifikation

Stand: 2026-05-25

Diese Datei beschreibt was du extern (ChatGPT / Midjourney) generieren musst, damit wir in Phase 4 vom Klötzchen-Look auf RimWorld-Style umstellen können.

## Style-Anker (immer als Vorbedingung im Prompt mitgeben)

> *"top-down view, fantasy game asset, RimWorld-inspired, hand-painted, soft natural lighting, no harsh outlines, warm color palette, slightly desaturated, 64x64 pixels, transparent background"*

**Warum so streng:** Konsistenz. Wenn jedes Tile leicht anders im Stil ist, wirkt die Welt geflickt.

### Midjourney-spezifisch
- `--ar 1:1 --v 6` (oder neueste Version)
- `--style raw` für weniger MJ-typische Verschönerung
- `--seed <fix>` nutzen wo möglich, um Style zu stabilisieren

### ChatGPT (DALL·E 3)
- Style ist schwieriger zu fixieren — generiere alle Tiles in **einer Session**, schicke dem Modell die ersten Ergebnisse als Style-Referenz mit
- Falls möglich: GPT-4 mit Vision nutzen, vorherige Tiles hochladen, "im gleichen Stil weiter"

## Mindest-Liste für Phase-4-Start

### Terrain-Tiles (5 Stück, 64×64)

| Tile | Prompt-Zusatz | Anmerkung |
|------|---------------|-----------|
| Wasser | "calm blue water surface with subtle ripples, top-down" | Soll an angrenzende Wasser-Tiles ohne sichtbare Naht passen → seamless tile! |
| Strand | "sandy beach, light tan, fine grains visible" | Seamless |
| Grasland | "lush green grass, slight variation in shade, scattered tiny flowers" | Seamless |
| Wald | "dense forest canopy from above, dark green trees, hint of brown" | Seamless |
| Berg | "rocky gray mountain stone with darker cracks" | Seamless |

**Wichtig:** Tiles müssen "tileable" sein (Ränder passen nahtlos aneinander). Bei MJ: `--tile` Parameter. Bei DALL·E: explizit "seamless tile" im Prompt.

### Struktur-Sprites (Single-Tiles, 64×64, transparent)

| Sprite | Prompt-Zusatz |
|--------|---------------|
| Lagerfeuer | "burning campfire with stones around, glowing orange embers, top-down view" |
| Marker | "wooden signpost with small red flag, top-down view, shadow on ground" |

### Boden (seamless)

| Sprite | Prompt-Zusatz |
|--------|---------------|
| floor.png | "wooden plank floor, top-down view, **seamless tile, perfectly tileable**, planks running horizontally, no visible tile border" |

⚠️ Wichtig: Bei MJ `--tile` Parameter benutzen. Bei DALL·E "seamless tile" explizit erwähnen und zwei generierte Tiles probehalber nebeneinander legen — die Naht darf nicht sichtbar sein.

### Wände (Auto-Tiling, 12 Sprites)

Eine einzelne Wand ist nicht genug — RimWorld-Look braucht Auto-Tiling: jede Wand schaut auf ihre 4 Nachbarn (N/E/S/W) und wählt das passende Sprite aus 12 Varianten. Bitmask N=1, E=2, S=4, W=8.

Mapping Bitmask → Sprite (für den Code):

| Mask | Bedeutung | Sprite |
|------|-----------|--------|
| 0    | keine Nachbarn (Säule) | `wall_alone` |
| 1, 4, 5 | Verläuft vertikal (N und/oder S) | `wall_v` |
| 2, 8, 10 | Verläuft horizontal (E und/oder W) | `wall_h` |
| 3 (N+E) | L-Ecke unten-links offen | `wall_corner_sw` |
| 6 (S+E) | L-Ecke oben-links offen | `wall_corner_nw` |
| 9 (N+W) | L-Ecke unten-rechts offen | `wall_corner_se` |
| 12 (S+W) | L-Ecke oben-rechts offen | `wall_corner_ne` |
| 7 (N+E+S) | T mit Öffnung nach Westen | `wall_t_w` |
| 11 (N+E+W) | T mit Öffnung nach Süden | `wall_t_s` |
| 13 (N+S+W) | T mit Öffnung nach Osten | `wall_t_e` |
| 14 (E+S+W) | T mit Öffnung nach Norden | `wall_t_n` |
| 15 (alle) | Kreuzung + | `wall_cross` |

**Bestehende `wall.png` wird zu `wall_h.png`** (umbenennen). 11 neue müssen generiert werden — alle im gleichen Steinmauer-Stil wie das aktuelle wall.png:

| Dateiname | Was das Sprite zeigt |
|-----------|----------------------|
| `wall_alone.png` | Eine einzelne Steinsäule mittig im Tile |
| `wall_v.png` | Steinmauer **vertikal** verlaufend (Norden ↔ Süden) — kann eine 90°-Rotation von `wall_h` sein, aber als eigene Datei abgelegt damit der Stil sauber wirkt |
| `wall_corner_nw.png` | L-Form: Mauer kommt von Norden, biegt nach Westen ab (Öffnung nach NW) |
| `wall_corner_ne.png` | L-Form: Mauer von Norden biegt nach Osten (Öffnung nach NE) |
| `wall_corner_sw.png` | L-Form: Mauer von Süden biegt nach Westen (Öffnung nach SW) |
| `wall_corner_se.png` | L-Form: Mauer von Süden biegt nach Osten (Öffnung nach SE) |
| `wall_t_n.png` | T-Stück: horizontal verlaufend, mit Abzweig nach Norden |
| `wall_t_s.png` | T-Stück: horizontal verlaufend, mit Abzweig nach Süden |
| `wall_t_e.png` | T-Stück: vertikal verlaufend, mit Abzweig nach Osten |
| `wall_t_w.png` | T-Stück: vertikal verlaufend, mit Abzweig nach Westen |
| `wall_cross.png` | Vollständige Kreuzung — Mauer in alle 4 Richtungen |

**Style-Anker für alle 11**: identische Steinart, gleiche Farbe, gleiche Beleuchtung wie das bestehende `wall_h.png`. Idealerweise als Set in **einer** MJ/ChatGPT-Session generieren mit dem ersten Bild als Referenz.

**Generation-Prompt-Beispiel (anpassen pro Variante):**

> *"top-down view, stone wall segment, RimWorld-inspired, hand-painted, same gray stone style as reference image, [VARIATION-BESCHREIBUNG], 64x64 pixels, transparent background, soft shadow on the south side"*

Wo `[VARIATION-BESCHREIBUNG]` z.B. ist:
- `wall_alone`: "single isolated stone column"
- `wall_v`: "wall running vertically (top to bottom)"
- `wall_corner_nw`: "L-shaped corner, wall extending up and left, opening towards the north-west"
- `wall_t_n`: "T-junction, horizontal wall with branch going up"
- `wall_cross`: "cross-shaped wall junction, extending in all four directions"

### Spieler-Sprite (Charakter, 64×64 oder 96×96)

Ein einzelnes Charakter-Sprite, **top-down**, mit kleinem Schatten unter sich. Vier Richtungen wären ideal (oben, unten, links, rechts), aber für den Start reicht **eine generische Richtung** (z.B. Spieler von oben mit angedeuteter Schulter). Walk-Animation kommt später.

Prompt:
> *"top-down view of a fantasy adventurer character, simple medieval clothing, small soft shadow beneath, centered in frame, no background"*

### Schatten-Sprite (klein, 48×16, semi-transparent)

> *"horizontal soft black shadow ellipse, semi-transparent, soft edges, no character"*

Wird unter Spieler und Strukturen geblitzt für "Tiefe".

## Format und Dateinamen

Aktueller Ablageort (vom Code getrennt, sauber):

```
assets/                          ← Projekt-Root
├── tiles/
│   ├── water.png
│   ├── sand.png
│   ├── grass.png
│   ├── forest.png
│   └── mountain.png
├── structures/
│   ├── wall.png
│   ├── floor.png
│   ├── campfire.png
│   └── marker.png
├── characters/
│   └── player.png
└── effects/
    └── shadow.png
```

In Phase 4 wird ein StaticFiles-Mount im Backend auf `../assets/` zeigen, dann sind die Bilder unter `/assets/...` im Browser erreichbar.

- **PNG mit Alpha-Kanal** (transparenter Hintergrund wo nötig)
- **64×64 px** für Tiles und Strukturen
- **Spieler-Sprite** kann größer sein (z.B. 96×96), wird beim Render skaliert/positioniert

## Optional ab Phase 4 (Items)

Diese kommen erst, wenn die Item-Mechanik implementiert ist. Spec dafür folgt dann pro Item-Typ (Waffe, Rüstung, Trank etc.).

## Was passiert wenn der Style später wechselt?

Falls der lokale SD-Setup (Phase 4) einen leicht anderen Look produziert, sind diese externen Assets möglicherweise zu ersetzen. Bewahre die Prompts auf — damit kannst du nachgenerieren.

---

**Status-Tracking:**

Grundausstattung (Phase 4a — fertig):

- [x] water.png — 64×64 RGBA
- [x] sand.png — 64×64 RGBA
- [x] grass.png — 64×64 RGBA
- [x] forest.png — 64×64 RGBA
- [x] mountain.png — 64×64 RGBA
- [x] campfire.png — 64×64 RGBA
- [x] marker.png — 64×64 RGBA
- [x] player.png — 96×96 RGBA
- [x] shadow.png — 48×16 RGBA

Wand-Auto-Tiling + seamless Floor (offen):

- [ ] `wall_h.png` (das bestehende `wall.png` umbenennen — kein neues Asset nötig)
- [ ] `wall_v.png`
- [ ] `wall_alone.png`
- [ ] `wall_corner_nw.png`
- [ ] `wall_corner_ne.png`
- [ ] `wall_corner_sw.png`
- [ ] `wall_corner_se.png`
- [ ] `wall_t_n.png`
- [ ] `wall_t_s.png`
- [ ] `wall_t_e.png`
- [ ] `wall_t_w.png`
- [ ] `wall_cross.png`
- [ ] `floor.png` (re-generieren als seamless tile, alte Version überschreiben)

Items (Phase 4b) — kommen erst wenn Item-Mechanik dran ist.

---

## Welle 2026-05-25 (3): Deko-Props

25 neue Assets unter `assets/props/`:

**`props/nature/` (12):**
- tree_oak, tree_pine, tree_dead (Bäume)
- bush, tall_grass, flowers, mushrooms (Pflanzen)
- tree_stump, fallen_log (Holzreste)
- rock_small, rock_large, rock_mossy (Felsen)

**`props/water/` (5):**
- lily_pads, reeds (Wasserpflanzen)
- dock_straight, wooden_bridge (Wasser-Bauten)
- shipwreck (Schiffswrack)

**`props/settlement/` (5):**
- broken_cart (Karren)
- barrel, crate, sack (Behälter)
- fence (Zaun)

**`props/ruins/` (3):**
- ruin_pillar (Säule)
- rubble (Trümmer)
- statue_broken (Statue)

Integration: alle als platzierbare Strukturen mit blocking-Flag je nach Größe (Bäume/Felsen/Karren blocken; Gras/Blumen/Pilze/Schilf/Trümmer sind durchlaufbar).

Total Asset-Stand: **125 Dateien**.
