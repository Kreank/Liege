import db

# Asset-Pfade pro Item-Kind und Metadaten
ITEM_KINDS = {
    # Waffen
    "sword":         {"category": "weapon", "name": "Schwert",       "slot": "weapon", "sprite": "/assets/equipment/weapons/sword.png"},
    "axe":           {"category": "weapon", "name": "Axt",           "slot": "weapon", "sprite": "/assets/equipment/weapons/axe.png"},
    "bow":           {"category": "weapon", "name": "Bogen",         "slot": "weapon", "sprite": "/assets/equipment/weapons/bow.png"},
    "staff":         {"category": "weapon", "name": "Stab",          "slot": "weapon", "sprite": "/assets/equipment/weapons/staff.png"},
    "wand":          {"category": "weapon", "name": "Zauberstab",    "slot": "weapon", "sprite": "/assets/equipment/weapons/wand.png"},
    "greatsword":    {"category": "weapon", "name": "Großschwert",   "slot": "weapon", "sprite": "/assets/equipment/weapons/greatsword.png"},
    "spear":         {"category": "weapon", "name": "Speer",         "slot": "weapon", "sprite": "/assets/equipment/weapons/spear.png"},
    "crossbow":      {"category": "weapon", "name": "Armbrust",      "slot": "weapon", "sprite": "/assets/equipment/weapons/crossbow.png"},
    "throwing_knife":{"category": "weapon", "name": "Wurfmesser",    "slot": "weapon", "sprite": "/assets/equipment/weapons/throwing_knife.png"},
    "mace":          {"category": "weapon", "name": "Streitkolben",  "slot": "weapon", "sprite": "/assets/equipment/weapons/mace.png"},
    "scythe":        {"category": "weapon", "name": "Sense",         "slot": "weapon", "sprite": "/assets/equipment/weapons/scythe.png"},
    "dagger":        {"category": "weapon", "name": "Dolch",         "slot": "weapon", "sprite": "/assets/equipment/weapons/dagger.png"},
    # Rüstung
    "helmet":     {"category": "armor", "name": "Helm",         "slot": "helmet",     "sprite": "/assets/equipment/armor/helmet.png"},
    "chestplate": {"category": "armor", "name": "Brustpanzer",  "slot": "chestplate", "sprite": "/assets/equipment/armor/chestplate.png"},
    "shield":     {"category": "armor", "name": "Schild",       "slot": "shield",     "sprite": "/assets/equipment/armor/shield.png"},
    "boots":      {"category": "armor", "name": "Stiefel",      "slot": "boots",      "sprite": "/assets/equipment/armor/boots.png"},
    # Schmuck
    "ring":   {"category": "jewelry", "name": "Ring",           "slot": "ring",   "sprite": "/assets/equipment/jewelry/ring.png"},
    "amulet": {"category": "jewelry", "name": "Amulett",        "slot": "amulet", "sprite": "/assets/equipment/jewelry/amulet.png"},
    # Consumables
    "health_potion": {"category": "consumable", "name": "Heiltrank",  "sprite": "/assets/consumables/health_potion.png"},
    "mana_potion":   {"category": "consumable", "name": "Manatrank",  "sprite": "/assets/consumables/mana_potion.png"},
    "herb":          {"category": "consumable", "name": "Kraut",      "sprite": "/assets/consumables/herb.png"},
    "torch":         {"category": "consumable", "name": "Fackel",     "sprite": "/assets/consumables/torch.png"},
    "food_ration":   {"category": "food",       "name": "Proviant",   "sprite": "/assets/consumables/food_ration.png"},
    # Food
    "apple":          {"category": "food", "name": "Apfel",       "sprite": "/assets/food/apple.png"},
    "berries":        {"category": "food", "name": "Beeren",      "sprite": "/assets/food/berries.png"},
    "wheat":          {"category": "food", "name": "Weizen",      "sprite": "/assets/food/wheat.png"},
    "bread":          {"category": "food", "name": "Brot",        "sprite": "/assets/food/bread.png"},
    "raw_meat":       {"category": "food", "name": "Rohes Fleisch","sprite": "/assets/food/raw_meat.png"},
    "cooked_meat":    {"category": "food", "name": "Gebratenes Fleisch","sprite": "/assets/food/cooked_meat.png"},
    "fish":           {"category": "food", "name": "Fisch",       "sprite": "/assets/food/fish.png"},
    "mushroom_food":  {"category": "food", "name": "Pilz-Mahl",   "sprite": "/assets/food/mushroom_food.png"},
    # Magic — Spells (über cast_spell castbar)
    "spell_book": {"category": "magic", "name": "Feuerball-Buch", "sprite": "/assets/magic/spell_book.png"},
    "scroll":     {"category": "magic", "name": "Schriftrolle",   "sprite": "/assets/magic/scroll.png"},
    "rune_stone": {"category": "magic", "name": "Heilrune",       "sprite": "/assets/magic/rune_stone.png"},
    # Tools — skill-spezifischer Bonus beim Equipping
    "pickaxe": {"category": "tool", "name": "Spitzhacke", "slot": "tool", "sprite": "/assets/tools/pickaxe.png"},
    "shovel":  {"category": "tool", "name": "Schaufel",   "slot": "tool", "sprite": "/assets/tools/shovel.png"},
    "hammer":  {"category": "tool", "name": "Hammer",     "slot": "tool", "sprite": "/assets/tools/hammer.png"},
    "hoe":     {"category": "tool", "name": "Hacke",      "slot": "tool", "sprite": "/assets/tools/hoe.png"},
    # Ressourcen
    "wood":         {"category": "resource", "name": "Holz",          "sprite": "/assets/resources/wood.png"},
    "stone":        {"category": "resource", "name": "Stein",         "sprite": "/assets/resources/stone.png"},
    "iron_ore":     {"category": "resource", "name": "Eisenerz",      "sprite": "/assets/resources/iron_ore.png"},
    "gold_ore":     {"category": "resource", "name": "Golderz",       "sprite": "/assets/resources/gold_ore.png"},
    "silver_ore":   {"category": "resource", "name": "Silbererz",     "sprite": "/assets/resources/silver_ore.png"},
    "mythril_ore":  {"category": "resource", "name": "Mythril",       "sprite": "/assets/resources/mythril_ore.png"},
    "steel_ingot":  {"category": "resource", "name": "Stahlbarren",   "sprite": "/assets/resources/steel_ingot.png"},
    "crystal":      {"category": "resource", "name": "Kristall",      "sprite": "/assets/resources/crystal.png"},
    "bone":         {"category": "resource", "name": "Knochen",       "sprite": "/assets/resources/bone.png"},
    "cloth":        {"category": "resource", "name": "Stoff",         "sprite": "/assets/resources/cloth.png"},
    "leather":      {"category": "resource", "name": "Leder",         "sprite": "/assets/resources/leather.png"},
}

EQUIP_SLOTS = ["weapon", "helmet", "chestplate", "shield", "boots", "ring", "amulet", "tool"]

# Welle 36: stackable Kategorien (gleich-kind-items mergen in einer Row mit quantity)
STACKABLE_CATEGORIES = frozenset({"resource", "food", "consumable", "magic"})

# Issue: Stack-Limits pro Kategorie
STACK_LIMITS = {
    "resource":   500,   # Holz, Stein, Erz, Knochen, Stoff, Leder, Fasern …
    "food":       150,   # Materialien (verarbeitbar)
    "consumable": 25,    # Tränke, Kräuter
    "magic":      25,    # Schriftrollen, Runen
}

def is_stackable(category: str) -> bool:
    return category in STACKABLE_CATEGORIES

def stack_limit_for(category: str) -> int:
    """Maximum quantity einer Stack-Row (überlauf → neue Row)."""
    return STACK_LIMITS.get(category, 1)


def _row_to_dict(row) -> dict:
    out = {
        "id":            row["id"],
        "kind":          row["kind"],
        "name":          row["name"],
        "category":      row["category"],
        "quality":       row["quality"],
        "x":             row["x"],
        "y":             row["y"],
        "owner":         row["owner"],
        "equipped_slot": row["equipped_slot"],
        "created_at":    row["created_at"].isoformat(),
        "quantity":      1,
    }
    try:
        if "quantity" in row.keys() and row["quantity"]:
            out["quantity"] = int(row["quantity"])
    except (KeyError, IndexError):
        pass
    # Welle 19: Affixes + Unique-Naming, falls Spalten existieren
    try:
        if "affixes" in row.keys():
            aff = row["affixes"]
            if aff:
                import json as _json
                out["affixes"] = _json.loads(aff) if isinstance(aff, str) else aff
        if "unique_name" in row.keys() and row["unique_name"]:
            out["unique_name"] = row["unique_name"]
        if "flavor" in row.keys() and row["flavor"]:
            out["flavor"] = row["flavor"]
    except (KeyError, IndexError, TypeError):
        pass
    return out


class ItemManager:
    async def spawn_on_ground(self, kind: str, x: int, y: int) -> dict | None:
        cfg = ITEM_KINDS.get(kind)
        if cfg is None:
            return None
        row = await db.pool().fetchrow(
            "INSERT INTO items (kind, name, category, x, y) "
            "VALUES ($1, $2, $3, $4, $5) "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor",
            kind, cfg["name"], cfg["category"], x, y,
        )
        return _row_to_dict(row)

    async def get_on_ground(self) -> list[dict]:
        rows = await db.pool().fetch(
            "SELECT id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, quantity "
            "FROM items WHERE owner IS NULL"
        )
        return [_row_to_dict(r) for r in rows]

    async def get_at(self, x: int, y: int) -> list[dict]:
        rows = await db.pool().fetch(
            "SELECT id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, quantity "
            "FROM items WHERE x = $1 AND y = $2 AND owner IS NULL",
            x, y,
        )
        return [_row_to_dict(r) for r in rows]

    async def get_inventory(self, player_name: str) -> list[dict]:
        rows = await db.pool().fetch(
            "SELECT id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, quantity "
            "FROM items WHERE owner = $1 ORDER BY id",
            player_name,
        )
        return [_row_to_dict(r) for r in rows]

    async def pickup(self, item_id: int, player_name: str) -> dict | None:
        # Erst das Ground-Item laden, um zu prüfen ob stackable
        ground = await db.pool().fetchrow(
            "SELECT kind, category, quality, quantity FROM items "
            "WHERE id = $1 AND owner IS NULL", item_id,
        )
        if ground is None:
            return None
        # Wenn stackable & quality=normal → in existing stack mergen (Stack-Limit beachten)
        if is_stackable(ground["category"]) and ground["quality"] == "normal":
            limit = stack_limit_for(ground["category"])
            existing = await db.pool().fetchrow(
                "UPDATE items SET quantity = quantity + $3 "
                "WHERE id = (SELECT id FROM items WHERE owner = $1 AND kind = $2 "
                "  AND quality = 'normal' AND equipped_slot IS NULL "
                "  AND (affixes IS NULL OR affixes = 'null'::jsonb) "
                "  AND quantity + $3 <= $4 "
                "  ORDER BY id LIMIT 1) "
                "RETURNING id, kind, name, category, quality, x, y, owner, "
                "equipped_slot, created_at, affixes, unique_name, flavor, quantity",
                player_name, ground["kind"], int(ground["quantity"] or 1), limit,
            )
            if existing:
                # Ground-Item löschen
                await db.pool().execute("DELETE FROM items WHERE id = $1", item_id)
                return _row_to_dict(existing)
        # Sonst normale Pickup
        row = await db.pool().fetchrow(
            "UPDATE items SET x = NULL, y = NULL, owner = $2 "
            "WHERE id = $1 AND owner IS NULL "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, "
            "created_at, affixes, unique_name, flavor, quantity",
            item_id, player_name,
        )
        return _row_to_dict(row) if row else None

    async def drop(self, item_id: int, player_name: str, x: int, y: int) -> dict | None:
        row = await db.pool().fetchrow(
            "UPDATE items SET owner = NULL, equipped_slot = NULL, x = $3, y = $4 "
            "WHERE id = $1 AND owner = $2 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor",
            item_id, player_name, x, y,
        )
        return _row_to_dict(row) if row else None

    async def equip(self, item_id: int, player_name: str) -> dict | None:
        # Welcher Slot? Aus item.kind ableiten
        item = await db.pool().fetchrow(
            "SELECT kind FROM items WHERE id = $1 AND owner = $2",
            item_id, player_name,
        )
        if item is None:
            return None
        cfg = ITEM_KINDS.get(item["kind"])
        if cfg is None or "slot" not in cfg:
            return None
        slot = cfg["slot"]
        # Vorher anderen Item im gleichen Slot ausziehen
        await db.pool().execute(
            "UPDATE items SET equipped_slot = NULL "
            "WHERE owner = $1 AND equipped_slot = $2",
            player_name, slot,
        )
        row = await db.pool().fetchrow(
            "UPDATE items SET equipped_slot = $3 "
            "WHERE id = $1 AND owner = $2 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor",
            item_id, player_name, slot,
        )
        return _row_to_dict(row) if row else None

    async def unequip(self, item_id: int, player_name: str) -> dict | None:
        row = await db.pool().fetchrow(
            "UPDATE items SET equipped_slot = NULL "
            "WHERE id = $1 AND owner = $2 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor",
            item_id, player_name,
        )
        return _row_to_dict(row) if row else None

    async def consume(self, item_id: int, player_name: str) -> dict | None:
        """Verbraucht ein Consumable/Food — Item wird gelöscht."""
        row = await db.pool().fetchrow(
            "DELETE FROM items WHERE id = $1 AND owner = $2 "
            "AND category IN ('consumable', 'food') "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor",
            item_id, player_name,
        )
        return _row_to_dict(row) if row else None

    # — Chest-Storage —————————————————————————————————————————————————————————

    async def get_chest_contents(self, chest_id: int) -> list[dict]:
        rows = await db.pool().fetch(
            "SELECT id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, quantity "
            "FROM items WHERE owner = $1 ORDER BY id",
            f"chest:{chest_id}",
        )
        return [_row_to_dict(r) for r in rows]

    async def transfer_to_chest(self, item_id: int, player_name: str, chest_id: int) -> dict | None:
        row = await db.pool().fetchrow(
            "UPDATE items SET owner = $3, equipped_slot = NULL "
            "WHERE id = $1 AND owner = $2 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor",
            item_id, player_name, f"chest:{chest_id}",
        )
        return _row_to_dict(row) if row else None

    async def transfer_from_chest(self, item_id: int, chest_id: int, player_name: str) -> dict | None:
        row = await db.pool().fetchrow(
            "UPDATE items SET owner = $3 "
            "WHERE id = $1 AND owner = $2 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor",
            item_id, f"chest:{chest_id}", player_name,
        )
        return _row_to_dict(row) if row else None

    # — Crafting ——————————————————————————————————————————————————————————————

    async def count_owned_by_kind(self, player_name: str) -> dict[str, int]:
        """Anzahl Items pro Kind im Inventar (mit Stacking: SUM(quantity))."""
        rows = await db.pool().fetch(
            "SELECT kind, SUM(quantity)::INTEGER AS c FROM items "
            "WHERE owner = $1 AND equipped_slot IS NULL GROUP BY kind",
            player_name,
        )
        return {r["kind"]: int(r["c"]) for r in rows}

    async def consume_one(self, player_name: str, kind: str) -> bool:
        """Verbraucht EIN Item dieses Kinds. Stacking-aware: bei stackable Items
        wird quantity-=1, bei nicht-stackable die Row gelöscht."""
        # Erst stack mit quantity > 1 finden und verringern
        row = await db.pool().fetchrow(
            "UPDATE items SET quantity = quantity - 1 "
            "WHERE id = (SELECT id FROM items WHERE owner = $1 AND kind = $2 "
            "  AND equipped_slot IS NULL AND quantity > 1 ORDER BY id LIMIT 1) "
            "RETURNING id",
            player_name, kind,
        )
        if row:
            return True
        # Sonst Row mit quantity = 1 löschen
        row = await db.pool().fetchrow(
            "DELETE FROM items WHERE id = ("
            "  SELECT id FROM items WHERE owner = $1 AND kind = $2 "
            "  AND equipped_slot IS NULL ORDER BY id LIMIT 1"
            ") RETURNING id",
            player_name, kind,
        )
        return row is not None

    async def create_for_player(self, kind: str, player_name: str,
                                quality_kind: str = "normal") -> dict | None:
        cfg = ITEM_KINDS.get(kind)
        if cfg is None:
            return None
        # Welle 36: Wenn stackable und Quality=normal → in existing stack mergen
        if is_stackable(cfg["category"]) and quality_kind == "normal":
            limit = stack_limit_for(cfg["category"])
            existing = await db.pool().fetchrow(
                "UPDATE items SET quantity = quantity + 1 "
                "WHERE id = (SELECT id FROM items WHERE owner = $1 AND kind = $2 "
                "  AND quality = 'normal' AND equipped_slot IS NULL "
                "  AND (affixes IS NULL OR affixes = 'null'::jsonb) "
                "  AND quantity < $3 "
                "  ORDER BY id LIMIT 1) "
                "RETURNING id, kind, name, category, quality, x, y, owner, "
                "equipped_slot, created_at, affixes, unique_name, flavor, quantity",
                player_name, kind, limit,
            )
            if existing:
                return _row_to_dict(existing)
        row = await db.pool().fetchrow(
            "INSERT INTO items (kind, name, category, owner, quality, quantity) "
            "VALUES ($1, $2, $3, $4, $5, 1) "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, "
            "created_at, affixes, unique_name, flavor, quantity",
            kind, cfg["name"], cfg["category"], player_name, quality_kind,
        )
        return _row_to_dict(row)
