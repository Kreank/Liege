# Fehlende Assets — Liege (Stand 2026-05-27)

Diese Datei listet alle Assets, die im Code referenziert werden oder logisch
folgen, aber **physisch noch fehlen**. Jeder Eintrag hat einen konkreten
Generierungs-Prompt, ein Ziel-Format und den Code-Referenz-Punkt.

Stil-Konstante für Sprites: **Pixel-Art, 64×64 RGBA mit transparentem
Hintergrund**, dark-fantasy medieval, statische Front-Pose, konsistent mit den
bereits vorhandenen `assets/characters/npcs/*.png` (siehe `farmer.png`,
`merchant.png` als Stil-Referenz).

---

## 1. Kritisch: 404-Items (Frontend lädt → broken sprite)

### 1.1 `assets/food/bread.png`
- **Referenz:** `frontend/app.js:701` (`ITEM.bread.path`)
- **Format:** 32×32 PNG, RGBA, transparent
- **Prompt:** `Pixel-art game icon, 32×32, single loaf of rustic baked bread, golden-brown crust with slight darker top, soft shadow underneath, top-down 3/4 view, transparent background, fantasy RPG inventory style, no text, single object`

### 1.2 `assets/food/cooked_meat.png`
- **Referenz:** `frontend/app.js:703` (`ITEM.cooked_meat.path`)
- **Format:** 32×32 PNG, RGBA, transparent
- **Prompt:** `Pixel-art game icon, 32×32, a single cooked turkey leg / drumstick, brown-roasted glistening surface, white bone tip exposed, transparent background, fantasy RPG inventory style, no text, single object`

---

## 2. NPC-Sprites ohne dediziertes Asset (aktuell via Tint-Recycling)

Diese Friendly-Kinds sind im Backend (`backend/npc_worker.py:FRIENDLY_KINDS`)
definiert, haben aber kein eigenes PNG — `frontend/app.js:NPC_SPRITE` recycelt
einen anderen npc-Sprite mit Tint.

### 2.1 `assets/characters/npcs/wanderer.png`
- **Aktuell:** `npc_villager` mit Default-Tint
- **Prompt:** `Pixel-art character sprite, 64×64, RGBA transparent background, lone fantasy wanderer / traveler facing camera, brown weather-worn cloak with hood half-down, simple leather pack on back, walking stick in one hand, leather boots, dust-stained simple clothes underneath, neutral wise expression, dark fantasy medieval style, single static pose, consistent with /assets/characters/npcs/farmer.png style`

### 2.2 `assets/characters/npcs/soldier.png`
- **Aktuell:** `npc_guard` mit Default-Tint (Recycling, Backend `soldier` ist eigener kind)
- **Prompt:** `Pixel-art character sprite, 64×64, RGBA transparent background, professional medieval foot soldier facing camera, polished steel breastplate with shoulder pauldrons (not gilded), kettle helmet on head, longsword scabbard at hip, military tabard with simple heraldry, disciplined posture, dark fantasy medieval style, single static pose, distinct from /assets/characters/npcs/guard.png (which is a town watchman in lighter armor)`

---

## 3. User-gemeldete Fehler (aus Stand 2026-05-27)

Der User hat Fehler in einigen der 16 neuen NPC-Sprites entdeckt. Ersatz wird
gerade parallel produziert. Verdächtige Sprites bei der visuellen Sichtung:

### 3.1 `assets/characters/npcs/hunter.png` (Re-Generation)
- **Problem:** Aktueller Sprite wirkt eher wie kleine Kreatur/Tier als
  menschlicher Jäger.
- **Prompt:** `Pixel-art character sprite, 64×64, RGBA transparent background, human hunter standing upright facing camera, fur-trimmed leather hunting tunic in olive/green, short bow slung across back, quiver of arrows at hip, sturdy boots, weathered cloak, hooded but face visible, dark hair, alert focused expression, dark fantasy medieval style, single static pose, must read as HUMAN at a glance not animal, same scale as /assets/characters/npcs/farmer.png`

### 3.2 `assets/characters/npcs/woodcutter.png` (Re-Generation)
- **Problem:** Sprite optisch zu klein / undefiniert für Holzfäller-Rolle.
- **Prompt:** `Pixel-art character sprite, 64×64, RGBA transparent background, brawny human woodcutter / lumberjack facing camera, large two-handed felling axe leaning on shoulder, rolled-up linen shirt sleeves showing strong arms, brown work trousers tucked into boots, simple flat cap or bare head with short hair, broad shoulders, calm strong posture, dark fantasy medieval style, single static pose, same scale and proportions as /assets/characters/npcs/blacksmith.png`

### 3.3 Diversifizierung von `bandit.png`, `robber.png`, `thief.png`
- **Problem:** Die drei hostile-Human-Sprites sind aktuell schwer
  unterscheidbar (alle dunkel, vermummt, ähnliche Silhouette).
- **Empfehlung:**
  - **Bandit** = militante Räuber-Bande (rote/braune Lederrüstung, sichtbare
    Waffe, kein Hood — wirkt organisiert)
  - **Robber** = brutaler Wegelagerer (zerlumpte schwere Kleidung, Knüppel/
    Keule statt Klinge, gepolstertes Wams, ungekämmt aber kein Hood)
  - **Thief** = schmaler Schleicher (komplett dunkle enge Lederkleidung mit
    Hood tief im Gesicht, Dolch in Hand, deutlich schmalere Silhouette als
    die beiden anderen)
- **Bandit-Prompt:** `Pixel-art character sprite, 64×64, RGBA transparent background, organized human bandit warrior facing camera, red-and-brown studded leather armor with metal rivets, short sword drawn at side, NO HOOD, visible scarred face with stubble, leather bracers, dark fantasy medieval style, looks militant and armed, single static pose`
- **Robber-Prompt:** `Pixel-art character sprite, 64×64, RGBA transparent background, brutish human highway robber facing camera, layered grey-brown padded leather coat over thick rags, wooden club / cudgel held in fist, NO HOOD, unkempt beard and wild hair, scarred face, broad heavyset build, mud-stained boots, dark fantasy medieval style, single static pose`
- **Thief-Prompt:** `Pixel-art character sprite, 64×64, RGBA transparent background, slender stealthy human thief facing camera, ALL BLACK tight-fitting leather outfit with deep hood covering most of face, only eyes visible, slim dagger held in reverse grip, narrow silhouette distinctly thinner than bandit/robber, soft-soled boots, dark fantasy medieval style, single static pose, must clearly read as different silhouette from bandit and robber`

---

## 4. Optionale Verbesserung — Walk-Cycle-Animationen einbinden

Unter `assets/animations/characters/<kind>/` und `assets/animations/monsters/
<kind>/` existieren bereits vollständige Walk-Cycles (idle_1/2, walk_down/up/
left/right je 1-2 Frames) für **13 Friendly + 50 Hostile Kinds**, die das
Frontend bisher NICHT lädt. Aktuell wird nur ein statisches `idle_1.png` als
NPC-Sprite gerendert.

**Kein neuer Asset nötig — nur Code-Arbeit** (eigener Issue / nächste Welle):
- `frontend/app.js` `spawnNPCSprite` müsste statt `.image()` einen Walk-Cycle
  mit Phaser-Animations registrieren.
- DB hat schon `npcs.last_moved` — Bewegungs-Richtung könnte daraus abgeleitet
  werden.

---

## 5. Optional — NPC-Variants für neue hostile Humans

Aktuell hat nur `bandit` Waffen-Varianten (`bandit_axe.png`, `bandit_bow.png`,
`bandit_dagger.png`, `bandit_spear.png` in `assets/characters/npcs/variants/`).

Damit `robber` und `thief` ebenfalls visuelle Diversität bekommen (Backend
`SPRITE_VARIANTS_BY_KIND` würde dann random eine wählen), wären sinnvoll:

### 5.1 `assets/characters/npcs/variants/robber_club.png`
- **Prompt:** `Pixel-art character sprite, 64×64, RGBA transparent background, the robber from /assets/characters/npcs/robber.png but now holding a heavy spiked wooden cudgel raised in attack pose, same character design, same proportions, dark fantasy medieval style, single static pose`

### 5.2 `assets/characters/npcs/variants/robber_axe.png`
- **Prompt:** `Pixel-art character sprite, 64×64, RGBA transparent background, the robber from /assets/characters/npcs/robber.png but now wielding a one-handed hand axe at the ready, same character design and color palette, dark fantasy medieval style, single static pose`

### 5.3 `assets/characters/npcs/variants/thief_dagger.png`
- **Prompt:** `Pixel-art character sprite, 64×64, RGBA transparent background, the thief from /assets/characters/npcs/thief.png but now holding two slim daggers, one in each hand in reverse grip, same all-black hooded outfit, slim silhouette, dark fantasy medieval style, single static pose`

### 5.4 `assets/characters/npcs/variants/thief_lockpick.png`
- **Prompt:** `Pixel-art character sprite, 64×64, RGBA transparent background, the thief from /assets/characters/npcs/thief.png crouching slightly with a lockpick held delicately in one hand, other hand on hilt of sheathed dagger, same all-black hooded outfit, dark fantasy medieval style, single static pose`

---

## 6. Cleanup — Inkonsistente Asset-Ablage

Diese Dateien sind im Repo, werden aber von keinem Code referenziert.
Vorschlag: konsolidieren oder löschen.

| Datei | Status |
|---|---|
| `assets/characters/bandit.png` | Wird ersetzt durch `assets/characters/npcs/bandit.png`. Legacy, sollte gelöscht werden. |
| `assets/characters/merchant.png` | Duplikat zu `assets/characters/npcs/merchant.png`. Legacy. |
| `assets/characters/soldier.png` | Soldier-Sprite, aber `assets/characters/npcs/soldier.png` fehlt — dieses File **nach `npcs/` verschieben** statt löschen. |
| `assets/characters/villager_female.png` | Sollte nach `assets/characters/npcs/villager_female.png` verschoben werden. |
| `assets/characters/villager_male.png` | Dito → `assets/characters/npcs/villager_male.png`. |
| `assets/characters/player_walk_1.png`, `player_walk_2.png` | Sieht aus wie alte Player-Walk-Frames. Aktuell genutzt? Sonst löschen. |

---

## 7. Wenn du noch Lust hast — visuelle Diversität für Friendly-NPCs

Die folgenden Friendly-Kinds spawnen massenweise in Dörfern und wären mit
female-Varianten viel diverser:

| Vorhandenes Sprite | Vorschlag female-Variant |
|---|---|
| `npcs/farmer.png` | `npcs/farmer_female.png` ✓ (bereits da) |
| `npcs/villager.png` | `npcs/villager_female.png` (existiert in `/characters/` root, müsste umziehen — siehe §6) |
| `npcs/merchant.png` | `npcs/merchant_female.png` (neu) |
| `npcs/baker.png` | `npcs/baker_female.png` (neu) |
| `npcs/healer.png` | `npcs/healer_female.png` (neu) |
| `npcs/scholar.png` | `npcs/scholar_female.png` (neu) |

**Backend würde dann erweitert um:**
```python
SPRITE_VARIANTS_BY_KIND = {
    ...
    "farmer":   ["farmer", "farmer_female"],
    "villager": ["villager", "villager_female"],
    # etc.
}
```

---

## 8. Zustand der bereits genutzten Asset-Pools

Diese sind **vollständig** und brauchen keine Ergänzung:

- ✓ 17 Pro-Monster Sprites (`assets/monsters/world_sprites/reference_based/sprites_96/`)
- ✓ 50 Legacy-Monster idle-Frames (`assets/animations/monsters/*/idle_1.png`)
- ✓ 10 NPC-Variants (`assets/characters/npcs/variants/`)
- ✓ 30 Friendly-NPCs (`assets/characters/npcs/*.png`) — modulo §3 Fehler
- ✓ 6 Player-Presets (`assets/characters/player_presets/`)
- ✓ 84 Item-Paths in ITEM-Map — alle Pfade existieren bis auf bread/cooked_meat (§1)
- ✓ Pro-Waffen (`equipment/weapons/professional/reference_based/icons_128/`)
- ✓ Pro-Armor (`equipment/armor/professional/reference_based/by_rarity/`)
- ✓ 23 World-Polish-Animations
- ✓ Tiles, Strukturen, Props, Tools, Resources, Magic

---

*Generiert am 2026-05-27 nach systematischer Inventur von 850+ Asset-Dateien
gegen Frontend- und Backend-Referenzen.*
