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
    "sickle":  {"category": "tool", "name": "Sichel",     "slot": "tool", "sprite": "/assets/tools/sickle.png"},
    # Ressourcen
    "wood":         {"category": "resource", "name": "Holz",          "sprite": "/assets/resources/wood.png"},
    "stone":        {"category": "resource", "name": "Stein",         "sprite": "/assets/resources/stone.png"},
    "iron_ore":     {"category": "resource", "name": "Eisenerz",      "sprite": "/assets/resources/iron_ore.png"},
    "gold_ore":     {"category": "resource", "name": "Golderz",       "sprite": "/assets/resources/gold_ore.png"},
    "silver_ore":   {"category": "resource", "name": "Silbererz",     "sprite": "/assets/resources/silver_ore.png"},
    "mythril_ore":  {"category": "resource", "name": "Mythril",       "sprite": "/assets/resources/mythril_ore.png"},
    # Ingots — Outputs vom Furnace, Inputs für Anvil-Rezepte
    "steel_ingot":   {"category": "resource", "name": "Stahlbarren",   "sprite": "/assets/resources/steel_ingot.png"},
    "iron_ingot":    {"category": "resource", "name": "Eisenbarren",   "sprite": "/assets/resources/iron_ingot.png"},
    "copper_ingot":  {"category": "resource", "name": "Kupferbarren",  "sprite": "/assets/resources/copper_ingot.png"},
    "silver_ingot":  {"category": "resource", "name": "Silberbarren",  "sprite": "/assets/resources/silver_ingot.png"},
    "gold_ingot":    {"category": "resource", "name": "Goldbarren",    "sprite": "/assets/resources/gold_ingot.png"},
    "mithril_ingot": {"category": "resource", "name": "Mithrilbarren", "sprite": "/assets/resources/mithril_ingot.png"},
    "adamant_ingot": {"category": "resource", "name": "Adamantbarren", "sprite": "/assets/resources/adamant_ingot.png"},
    "platinum_ingot":{"category": "resource", "name": "Platinbarren",  "sprite": "/assets/resources/platinum_ingot.png"},
    "tungsten_ingot":{"category": "resource", "name": "Wolframbarren", "sprite": "/assets/resources/tungsten_ingot.png"},
    "crystal_ingot": {"category": "resource", "name": "Kristallbarren","sprite": "/assets/resources/crystal_ingot.png"},
    "crystal":      {"category": "resource", "name": "Kristall",      "sprite": "/assets/resources/crystal.png"},
    "bone":         {"category": "resource", "name": "Knochen",       "sprite": "/assets/resources/bone.png"},
    "cloth":        {"category": "resource", "name": "Stoff",         "sprite": "/assets/resources/cloth.png"},
    "plant_fiber":  {"category": "resource", "name": "Pflanzenfaser", "sprite": "/assets/resources/cloth.png"},
    "leather":      {"category": "resource", "name": "Leder",         "sprite": "/assets/resources/leather.png"},
    # Münzen — von Banditen/NPCs als Loot
    "copper_coin":  {"category": "resource", "name": "Kupfermünze",   "sprite": "/assets/currency/coin_copper.png"},
    "silver_coin":  {"category": "resource", "name": "Silbermünze",   "sprite": "/assets/currency/coin_silver.png"},
    "gold_coin":    {"category": "resource", "name": "Goldmünze",     "sprite": "/assets/currency/coin_gold.png"},
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
    # Material-Feld (für sprite-resolution im Frontend)
    try:
        if "material" in row.keys() and row["material"]:
            out["material"] = row["material"]
    except (KeyError, IndexError):
        pass
    return out


class ItemManager:
    async def spawn_on_ground(self, kind: str, x: int, y: int,
                              material: str | None = None) -> dict | None:
        cfg = ITEM_KINDS.get(kind)
        if cfg is None:
            return None
        row = await db.pool().fetchrow(
            "INSERT INTO items (kind, name, category, x, y, material) "
            "VALUES ($1, $2, $3, $4, $5, $6) "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, material",
            kind, cfg["name"], cfg["category"], x, y, material,
        )
        return _row_to_dict(row)

    async def get_on_ground(self) -> list[dict]:
        rows = await db.pool().fetch(
            "SELECT id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, quantity, material "
            "FROM items WHERE owner IS NULL"
        )
        return [_row_to_dict(r) for r in rows]

    async def get_at(self, x: int, y: int) -> list[dict]:
        rows = await db.pool().fetch(
            "SELECT id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, quantity, material "
            "FROM items WHERE x = $1 AND y = $2 AND owner IS NULL",
            x, y,
        )
        return [_row_to_dict(r) for r in rows]

    async def get_inventory(self, player_name: str) -> list[dict]:
        rows = await db.pool().fetch(
            "SELECT id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, quantity, material "
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
                "equipped_slot, created_at, affixes, unique_name, flavor, quantity, material",
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
            "created_at, affixes, unique_name, flavor, quantity, material",
            item_id, player_name,
        )
        return _row_to_dict(row) if row else None

    async def drop(self, item_id: int, player_name: str, x: int, y: int) -> dict | None:
        row = await db.pool().fetchrow(
            "UPDATE items SET owner = NULL, equipped_slot = NULL, x = $3, y = $4 "
            "WHERE id = $1 AND owner = $2 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, material",
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
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, material",
            item_id, player_name, slot,
        )
        return _row_to_dict(row) if row else None

    async def unequip(self, item_id: int, player_name: str) -> dict | None:
        row = await db.pool().fetchrow(
            "UPDATE items SET equipped_slot = NULL "
            "WHERE id = $1 AND owner = $2 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, material",
            item_id, player_name,
        )
        return _row_to_dict(row) if row else None

    async def consume(self, item_id: int, player_name: str) -> dict | None:
        """Verbraucht EIN Consumable/Food.
        - Stack mit quantity > 1: decrement, Item bleibt mit neuer quantity.
        - Stack mit quantity = 1 (oder non-stack): Row gelöscht.
        Return-Dict bekommt zusätzlich `stack_remaining` (0 = gelöscht, >0 = neue qty)."""
        # Erst: Stack mit quantity > 1 → decrement
        row = await db.pool().fetchrow(
            "UPDATE items SET quantity = quantity - 1 "
            "WHERE id = $1 AND owner = $2 "
            "AND category IN ('consumable', 'food') "
            "AND quantity > 1 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, "
            "created_at, affixes, unique_name, flavor, quantity, material",
            item_id, player_name,
        )
        if row:
            d = _row_to_dict(row)
            d["stack_remaining"] = int(row["quantity"])
            return d
        # Sonst: einzelnes Item (qty = 1 oder non-stack) → delete
        row = await db.pool().fetchrow(
            "DELETE FROM items WHERE id = $1 AND owner = $2 "
            "AND category IN ('consumable', 'food') "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, "
            "created_at, affixes, unique_name, flavor, material",
            item_id, player_name,
        )
        if row:
            d = _row_to_dict(row)
            d["stack_remaining"] = 0
            return d
        return None

    # — Stack-Split / Merge ————————————————————————————————————————————————————

    async def split_stack(self, item_id: int, player_name: str,
                          amount: int) -> tuple[dict, dict] | None:
        """Nimmt `amount` aus einem Stack heraus in eine neue Row.
        Returns (updated_original, new_row) oder None bei ungültiger Operation."""
        if amount < 1:
            return None
        row = await db.pool().fetchrow(
            "SELECT kind, name, category, quality, quantity, equipped_slot, "
            "affixes, unique_name, flavor, material "
            "FROM items WHERE id = $1 AND owner = $2", item_id, player_name,
        )
        if row is None or row["equipped_slot"] is not None:
            return None
        cur_qty = int(row["quantity"] or 1)
        if amount >= cur_qty:
            return None  # Ergäbe leere Original-Row
        updated = await db.pool().fetchrow(
            "UPDATE items SET quantity = quantity - $2 WHERE id = $1 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, "
            "created_at, affixes, unique_name, flavor, quantity, material",
            item_id, amount,
        )
        new_row = await db.pool().fetchrow(
            "INSERT INTO items (kind, name, category, owner, quality, quantity, "
            "material, affixes, unique_name, flavor) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, "
            "created_at, affixes, unique_name, flavor, quantity, material",
            row["kind"], row["name"], row["category"], player_name, row["quality"],
            amount, row["material"], row["affixes"], row["unique_name"], row["flavor"],
        )
        return (_row_to_dict(updated), _row_to_dict(new_row))

    async def merge_stacks(self, player_name: str, kind: str,
                           quality: str = "normal") -> dict | None:
        """Konsolidiert alle Stacks gleichen kinds/qualities ins erste Row bis
        zum Stack-Limit; überschüssige rows bleiben mit Rest-quantity.
        Returns ein zusammenfassendes Dict {merged_rows, deleted_ids, kept_ids} oder None."""
        cfg = ITEM_KINDS.get(kind)
        if cfg is None or not is_stackable(cfg["category"]):
            return None
        limit = stack_limit_for(cfg["category"])
        rows = await db.pool().fetch(
            "SELECT id, quantity FROM items "
            "WHERE owner = $1 AND kind = $2 AND quality = $3 "
            "  AND equipped_slot IS NULL "
            "  AND (affixes IS NULL OR affixes = 'null'::jsonb) "
            "ORDER BY id",
            player_name, kind, quality,
        )
        if len(rows) < 2:
            return None
        # Greedy fill: erste Row als Ziel, weitere Rows hineinleeren bis voll
        target_id = rows[0]["id"]
        target_qty = int(rows[0]["quantity"])
        deleted_ids: list[int] = []
        kept_ids: list[int] = [target_id]
        for r in rows[1:]:
            src_id = r["id"]
            src_qty = int(r["quantity"])
            capacity = limit - target_qty
            if capacity >= src_qty:
                target_qty += src_qty
                deleted_ids.append(src_id)
            elif capacity > 0:
                target_qty = limit
                # target voll-schreiben
                await db.pool().execute(
                    "UPDATE items SET quantity = $2 WHERE id = $1",
                    target_id, target_qty,
                )
                # source bekommt rest
                new_src_qty = src_qty - capacity
                await db.pool().execute(
                    "UPDATE items SET quantity = $2 WHERE id = $1",
                    src_id, new_src_qty,
                )
                # source wird neues target (Rest könnte noch wachsen)
                target_id = src_id
                target_qty = new_src_qty
                kept_ids.append(target_id)
            else:
                # target schon voll — source wird neues target
                target_id = src_id
                target_qty = src_qty
                kept_ids.append(target_id)
        # Final target schreiben
        await db.pool().execute(
            "UPDATE items SET quantity = $2 WHERE id = $1", target_id, target_qty,
        )
        if deleted_ids:
            await db.pool().execute(
                "DELETE FROM items WHERE id = ANY($1::bigint[])", deleted_ids,
            )
        return {"deleted_ids": deleted_ids, "kept_ids": kept_ids}

    # — Chest-Storage —————————————————————————————————————————————————————————

    async def get_chest_contents(self, chest_id: int) -> list[dict]:
        rows = await db.pool().fetch(
            "SELECT id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, quantity, material "
            "FROM items WHERE owner = $1 ORDER BY id",
            f"chest:{chest_id}",
        )
        return [_row_to_dict(r) for r in rows]

    async def transfer_to_chest(self, item_id: int, player_name: str, chest_id: int) -> dict | None:
        row = await db.pool().fetchrow(
            "UPDATE items SET owner = $3, equipped_slot = NULL "
            "WHERE id = $1 AND owner = $2 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, material",
            item_id, player_name, f"chest:{chest_id}",
        )
        return _row_to_dict(row) if row else None

    async def transfer_from_chest(self, item_id: int, chest_id: int, player_name: str) -> dict | None:
        row = await db.pool().fetchrow(
            "UPDATE items SET owner = $3 "
            "WHERE id = $1 AND owner = $2 "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, created_at, affixes, unique_name, flavor, material",
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
                                quality_kind: str = "normal",
                                material: str | None = None) -> dict | None:
        cfg = ITEM_KINDS.get(kind)
        if cfg is None:
            return None
        # Resources haben keine echte Qualität — quality immer 'normal' damit
        # Stack-Merge funktioniert (sonst landen rough-iron-ingots in eigenen
        # Rows statt im Stack mit normal-iron-ingots).
        if cfg["category"] == "resource":
            quality_kind = "normal"
        # Welle 36: Wenn stackable und Quality=normal → in existing stack mergen
        # (Resources/Food/Consumables haben kein material — stack-merge unverändert)
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
                "equipped_slot, created_at, affixes, unique_name, flavor, quantity, material",
                player_name, kind, limit,
            )
            if existing:
                return _row_to_dict(existing)
        row = await db.pool().fetchrow(
            "INSERT INTO items (kind, name, category, owner, quality, quantity, material) "
            "VALUES ($1, $2, $3, $4, $5, 1, $6) "
            "RETURNING id, kind, name, category, quality, x, y, owner, equipped_slot, "
            "created_at, affixes, unique_name, flavor, quantity, material",
            kind, cfg["name"], cfg["category"], player_name, quality_kind, material,
        )
        return _row_to_dict(row)
