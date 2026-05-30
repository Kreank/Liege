from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "assets" / "monsters" / "world_sprites" / "generated_longlist"
OUT_ROOT = ROOT / "assets" / "monsters" / "overworld_pool"


MOBS = [
    {
        "id": "overworld_undead_shambler",
        "name": "Wandelnder Toter",
        "class": "undead",
        "source_id": "creature_shambling_corpse",
        "source_note": "direct visual match for slow shambler corpse",
    },
    {
        "id": "overworld_undead_skeleton_warrior",
        "name": "Skelett-Krieger",
        "class": "undead",
        "source_id": "creature_bone_skirmisher",
        "source_note": "skeleton melee fighter with weapon",
    },
    {
        "id": "overworld_undead_skeleton_archer",
        "name": "Skelett-Bogenschütze",
        "class": "undead",
        "source_id": "creature_bone_archer",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_undead_wight_lantern",
        "name": "Laternen-Wight",
        "class": "undead",
        "source_id": "creature_lantern_wight",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_undead_ghoul_stalker",
        "name": "Pirschender Ghul",
        "class": "undead",
        "source_id": "creature_grave_drinker_ghoul",
        "source_note": "ghoul/stalker silhouette",
    },
    {
        "id": "overworld_undead_desert_mummy",
        "name": "Wüsten-Mumie",
        "class": "undead",
        "source_id": "creature_boss_desert_pharaoh_revenant",
        "source_note": "desert mummy/pharaoh revenant, reused as overworld mummy cutout",
    },
    {
        "id": "overworld_goblin_scout",
        "name": "Goblin-Späher",
        "class": "goblinoid",
        "source_id": "creature_grin_goblin_scrapper",
        "source_note": "small goblin scout/scrapper",
    },
    {
        "id": "overworld_goblin_warrior",
        "name": "Goblin-Krieger",
        "class": "goblinoid",
        "source_id": "creature_grin_goblin_warchief",
        "source_note": "armed goblin warrior silhouette",
    },
    {
        "id": "overworld_goblin_shaman",
        "name": "Goblin-Schamane",
        "class": "goblinoid",
        "source_id": "creature_grin_goblin_shaman",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_hobgoblin_legionnaire",
        "name": "Hobgoblin-Legionär",
        "class": "goblinoid",
        "source_id": "creature_hobgoblin_legionnaire",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_orgrim_basher",
        "name": "Orgrim-Schläger",
        "class": "goblinoid",
        "source_id": "creature_orgrim_basher",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_brigand_footpad",
        "name": "Wegelagerer",
        "class": "brigand",
        "source_id": "creature_road_brigand",
        "source_note": "road brigand as footpad",
    },
    {
        "id": "overworld_brigand_archer",
        "name": "Räuber-Bogenschütze",
        "class": "brigand",
        "source_id": "creature_brigand_archer",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_brigand_captain",
        "name": "Räuber-Hauptmann",
        "class": "brigand",
        "source_id": "creature_brigand_captain",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_witch_hunter_renegade",
        "name": "Abtrünniger Hexenjäger",
        "class": "brigand",
        "source_id": "creature_witch_hunter_renegade",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_will_o_wisp",
        "name": "Irrlicht",
        "class": "wild_magic_fae",
        "source_id": "creature_will_o_wisp",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_briar_imp",
        "name": "Dornen-Kobold",
        "class": "wild_magic_fae",
        "source_id": "creature_briar_imp",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_dryad_hunter",
        "name": "Dryaden-Jägerin",
        "class": "wild_magic_fae",
        "source_id": "creature_dryad_hunter",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_mire_drowner",
        "name": "Sumpf-Ziehende",
        "class": "wild_magic_fae",
        "source_id": "creature_mire_drowner",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_swamp_witch_solo",
        "name": "Sumpfhexe",
        "class": "wild_magic_fae",
        "source_id": "creature_swamp_witch",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_apex_thornback_wolf",
        "name": "Dornenrücken-Wolf",
        "class": "biome_apex",
        "source_id": "creature_war_wolf",
        "source_note": "closest existing wolf apex cutout",
    },
    {
        "id": "overworld_apex_silverback_boar",
        "name": "Silberrücken-Eber",
        "class": "biome_apex",
        "source_id": "creature_silverback_boar",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_apex_panther_shade",
        "name": "Schattenpanther",
        "class": "biome_apex",
        "source_id": "creature_panther_shade",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_apex_glacier_lynx",
        "name": "Gletscher-Luchs",
        "class": "biome_apex",
        "source_id": "creature_glacier_lynx",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_apex_dune_strider",
        "name": "Dünenläufer",
        "class": "biome_apex",
        "source_id": "creature_dune_strider",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_apex_swamp_otter_clan",
        "name": "Sumpf-Otter-Clan",
        "class": "biome_apex",
        "source_id": "creature_swamp_otter_clan",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_apex_ridge_drake",
        "name": "Felsdrache",
        "class": "biome_apex",
        "source_id": "creature_ridgeback_drake",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_apex_cliff_kraken_arm",
        "name": "Klippen-Kraken-Arm",
        "class": "biome_apex",
        "source_id": "creature_boss_coast_kraken_arm",
        "source_note": "direct visual match for single tentacle threat",
    },
    {
        "id": "overworld_aberrant_eyeless_pilgrim",
        "name": "Augenloser Pilger",
        "class": "aberrant",
        "source_id": "creature_eyeless_pilgrim",
        "source_note": "direct visual match",
    },
    {
        "id": "overworld_aberrant_star_mote_imp",
        "name": "Sternsplitter-Wesen",
        "class": "aberrant",
        "source_id": "creature_star_mote_imp",
        "source_note": "direct visual match",
    },
]


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def alpha_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    return img.convert("RGBA").getbbox()


def fit_canvas(img: Image.Image, size: int, padding: int = 8) -> Image.Image:
    img = img.convert("RGBA")
    bbox = alpha_bbox(img)
    if bbox:
        img = img.crop(bbox)
    max_side = size - padding * 2
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((size - img.width) // 2, (size - img.height) // 2))
    return canvas


def build_contact(items: list[dict]) -> None:
    cols = 6
    cell = 128
    label_h = 24
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + label_h)), (28, 28, 28))
    draw = ImageDraw.Draw(sheet)
    for idx, item in enumerate(items):
        x = (idx % cols) * cell
        y = (idx // cols) * (cell + label_h)
        bg = Image.new("RGBA", (cell, cell), (42, 42, 42, 255))
        sprite = Image.open(ROOT / item["sprite_128"]).convert("RGBA")
        bg.alpha_composite(sprite, (0, 0))
        sheet.paste(bg.convert("RGB"), (x, y))
        draw.text((x + 4, y + cell + 4), item["id"].replace("overworld_", "")[:20], fill=(225, 225, 225))
    out = OUT_ROOT / "contacts" / "overworld_pool_contact.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=92)


def main() -> None:
    source_manifest = json.loads((SOURCE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    source_items = {item["id"]: item for item in source_manifest["items"]}

    for folder in ("fixed_cutouts_512", "sprites_128", "sprites_128_mirrored", "sprites_96", "icons_64", "contacts"):
        (OUT_ROOT / folder).mkdir(parents=True, exist_ok=True)

    manifest_items = []
    for mob in MOBS:
        source = source_items[mob["source_id"]]
        master_src = ROOT / source["fixed_cutout_512"]
        master = fit_canvas(Image.open(master_src), 512, padding=24)

        fixed_path = OUT_ROOT / "fixed_cutouts_512" / f"{mob['id']}_fixed_512.png"
        sprite_128_path = OUT_ROOT / "sprites_128" / f"{mob['id']}_world_128.png"
        sprite_west_path = OUT_ROOT / "sprites_128_mirrored" / f"{mob['id']}_world_128_west.png"
        sprite_96_path = OUT_ROOT / "sprites_96" / f"{mob['id']}_world_96.png"
        icon_64_path = OUT_ROOT / "icons_64" / f"{mob['id']}_icon_64.png"

        master.save(fixed_path)
        sprite_128 = fit_canvas(master, 128, padding=4)
        sprite_128.save(sprite_128_path)
        sprite_128.transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(sprite_west_path)
        fit_canvas(master, 96, padding=3).save(sprite_96_path)
        fit_canvas(master, 64, padding=2).save(icon_64_path)

        manifest_items.append(
            {
                "id": mob["id"],
                "name": mob["name"],
                "class": mob["class"],
                "source_id": mob["source_id"],
                "source_note": mob["source_note"],
                "fixed_cutout_512": rel(fixed_path),
                "sprite_128": rel(sprite_128_path),
                "sprite_128_mirrored": rel(sprite_west_path),
                "sprite_96": rel(sprite_96_path),
                "icon_64": rel(icon_64_path),
                "style": "derived from generated_longlist monster world sprites; transparent PNG, top-down/RimWorld-inspired warm fantasy cutout",
            }
        )

    build_contact(manifest_items)
    manifest = {
        "generated": "2026-05-30",
        "asset_type": "overworld_monster_pool",
        "source_request": "overworld_monster.md",
        "source_manifest": "assets/monsters/world_sprites/generated_longlist/manifest.json",
        "count": len(manifest_items),
        "sizes": ["512x512 fixed cutout", "128x128", "128x128 mirrored west", "96x96", "64x64 icon"],
        "contacts": [rel(OUT_ROOT / "contacts" / "overworld_pool_contact.jpg")],
        "items": manifest_items,
    }
    (OUT_ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
