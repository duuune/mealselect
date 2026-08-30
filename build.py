#!/usr/bin/env python3
"""dishes.yaml を検証して dishes.json を生成する。

使い方:
    python build.py            # dishes.yaml -> dishes.json
    python build.py 他.yaml    # 検証対象を差し替え（出力先は同じ dishes.json）

スキーマ違反・id 重複は行番号つきのエラーで exit 1。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "dishes.yaml"
DST = HERE / "dishes.json"


class Dish(BaseModel):
    """料理マスタの1件。dishes.yaml の各要素を厳密に検証する。"""

    model_config = {"extra": "forbid"}  # 未知キー（typo）を弾く

    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")  # スラッグ。一意
    name_ja: str = Field(min_length=1)
    name_local: str | None = None
    cuisine: Literal["ja", "th"]
    effort_min: int = Field(ge=5, le=120)  # 調理時間（分）
    ingredients: list[str] = Field(min_length=1, max_length=10)
    heaviness: int = Field(ge=1, le=5)  # 1(さっぱり)〜5(こってり)
    rarity: Literal[1, 2, 3]  # 1(定番) / 2(知ってるが作らない) / 3(聞いたことない)
    note: str = Field(min_length=1, max_length=40)  # 一行の煽り文

    @field_validator("ingredients")
    @classmethod
    def ingredients_clean(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        for item in v:
            if not item.strip():
                raise ValueError("空の材料名がある")
            if item != item.strip():
                raise ValueError(f"材料名の前後に空白: {item!r}")
            if item in seen:
                raise ValueError(f"材料が重複: {item}")
            seen.add(item)
        return v


class LineLoader(yaml.SafeLoader):
    """各マッピングに __line__ を注入する SafeLoader。エラー報告用。"""


def _construct_mapping(loader: LineLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    mapping = yaml.SafeLoader.construct_mapping(loader, node, deep=deep)
    mapping["__line__"] = node.start_mark.line + 1
    return mapping


LineLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def main() -> int:
    # Windows コンソール（cp932）でもタイ文字入りのエラーを出せるように
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if not SRC.exists():
        print(f"エラー: {SRC} が見つからない", file=sys.stderr)
        return 1

    try:
        data = yaml.load(SRC.read_text(encoding="utf-8"), Loader=LineLoader)
    except yaml.YAMLError as e:
        print(f"{SRC.name}: YAML として読めない:\n{e}", file=sys.stderr)
        return 1

    if not isinstance(data, list):
        print(f"{SRC.name}: トップレベルは料理のリストにすること", file=sys.stderr)
        return 1

    errors: list[str] = []
    dishes: list[Dish] = []
    seen_ids: dict[str, int] = {}

    for i, raw in enumerate(data):
        if not isinstance(raw, dict):
            errors.append(f"{SRC.name}: {i + 1}件目がマッピングではない")
            continue
        line = raw.pop("__line__", "?")
        label = raw.get("id") or f"{i + 1}件目"
        try:
            dish = Dish(**raw)
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(x) for x in err["loc"]) or "(全体)"
                errors.append(f"{SRC.name}:{line}: [{label}] {loc}: {err['msg']}")
            continue
        if dish.id in seen_ids:
            errors.append(
                f"{SRC.name}:{line}: [{dish.id}] id が重複（{seen_ids[dish.id]}行目と同じ）"
            )
            continue
        seen_ids[dish.id] = line if isinstance(line, int) else 0
        dishes.append(dish)

    if errors:
        print(f"検証エラー {len(errors)}件:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    DST.write_text(
        json.dumps([d.model_dump() for d in dishes], ensure_ascii=False, indent=1)
        + "\n",
        encoding="utf-8",
    )

    # 内訳サマリ（仕様どおりかを目視確認するため。強制はしない）
    by_cuisine = Counter(d.cuisine for d in dishes)
    by_rarity = Counter(d.rarity for d in dishes)
    by_effort = Counter(f"{d.effort_min // 10 * 10}分台" for d in dishes)
    uniq_ing = {i for d in dishes for i in d.ingredients}
    print(f"OK: {len(dishes)}品 -> {DST.name}")
    print(f"  cuisine: ja {by_cuisine.get('ja', 0)} / th {by_cuisine.get('th', 0)}")
    print(
        "  rarity:  "
        + " / ".join(f"{r}: {by_rarity.get(r, 0)}" for r in (1, 2, 3))
    )
    print(
        "  effort:  "
        + " / ".join(f"{k} {v}" for k, v in sorted(by_effort.items()))
    )
    print(f"  食材の種類: {len(uniq_ing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
