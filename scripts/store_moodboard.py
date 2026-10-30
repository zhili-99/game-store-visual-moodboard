#!/usr/bin/env python3
"""Scan game-store images and render a text analysis plus visual moodboard.

Requires Python 3.9+ and Pillow. The script is intentionally deterministic:
automatic scanning supplies evidence; semantic labels come from analysis JSON.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import math
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError as exc:  # pragma: no cover - dependency message
    raise SystemExit("Pillow is required. Install it with: python -m pip install Pillow") from exc


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
BG = "#F5F6F8"
CARD = "#FFFFFF"
TEXT = "#121722"
MUTED = "#6E7685"
BORDER = "#E1E4E8"
ACCENT = "#B425A5"


def natural_key(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def hex_color(rgb: tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % rgb


def parse_hex(value: str, fallback: str = "#808080") -> tuple[int, int, int]:
    text = str(value or fallback).strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", text):
        text = fallback.lstrip("#")
    return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))


def discover_images(inputs: Iterable[str]) -> list[Path]:
    found: list[Path] = []
    for raw in inputs:
        path = Path(raw).expanduser()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            found.append(path.resolve())
        elif path.is_dir():
            found.extend(
                p.resolve()
                for p in path.rglob("*")
                if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
            )
        else:
            raise FileNotFoundError(f"Input does not exist or is not a supported image: {path}")
    return sorted(set(found), key=lambda p: natural_key(str(p)))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def extract_palette(path: Path, colors: int = 10) -> list[dict[str, Any]]:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((192, 192), Image.Resampling.LANCZOS)
        quantized = image.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).convert("RGB")
        counts = quantized.getcolors(maxcolors=colors * 4) or []
        total = max(1, quantized.width * quantized.height)
        result = [
            {"hex": hex_color(rgb), "ratio": round(count / total, 4)}
            for count, rgb in sorted(counts, key=lambda item: item[0], reverse=True)
        ]
    return result


def aggregate_palette(images: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    buckets: dict[tuple[int, int, int], float] = defaultdict(float)
    if not images:
        return []
    for image in images:
        for entry in image.get("palette", []):
            r, g, b = parse_hex(entry["hex"])
            key = tuple(min(255, (channel // 32) * 32 + 16) for channel in (r, g, b))
            buckets[key] += float(entry.get("ratio", 0)) / len(images)
    total = sum(buckets.values()) or 1.0
    return [
        {"hex": hex_color(rgb), "ratio": round(weight / total, 4)}
        for rgb, weight in sorted(buckets.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]


def font_candidates(bold: bool = False) -> list[Path]:
    windows = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    names = ["msyhbd.ttc", "simhei.ttf", "arialbd.ttf"] if bold else ["msyh.ttc", "simsun.ttc", "arial.ttf"]
    candidates = [windows / name for name in names]
    candidates += [
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    return candidates


def load_font(size: int, bold: bool = False, explicit: str | None = None) -> ImageFont.FreeTypeFont:
    candidates = [Path(explicit)] if explicit else []
    candidates.extend(font_candidates(bold))
    for path in candidates:
        if path and path.exists():
            try:
                return ImageFont.truetype(str(path), size=size, index=0)
            except OSError:
                continue
    raise RuntimeError("No usable TrueType font found. Pass --font with a CJK-capable TTF/TTC file.")


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> float:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9#%/.+\-–—]+|\s+|.", str(text), flags=re.UNICODE)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for token in tokenize(text):
        candidate = current + token
        if current and text_width(draw, candidate, font) > width:
            lines.append(current.rstrip())
            current = token.lstrip()
            if text_width(draw, current, font) > width:
                for char in current:
                    candidate = current[:0] + char
                    if current and text_width(draw, current + char, font) > width:
                        lines.append(current)
                        current = char
                    else:
                        current += char
        else:
            current = candidate
    if current.strip() or not lines:
        lines.append(current.rstrip())
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: str | tuple[int, int, int],
    width: int,
    line_gap: int = 5,
    max_lines: int | None = None,
) -> int:
    x, y = xy
    lines = wrap_text(draw, text, font, width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and text_width(draw, last + "…", font) > width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    box = draw.textbbox((0, 0), "国Ag", font=font)
    line_height = box[3] - box[1] + line_gap
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def rounded_image(path: Path, size: tuple[int, int], radius: int = 16) -> Image.Image:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        fitted = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    result = Image.new("RGB", size, CARD)
    result.paste(fitted, mask=mask)
    return result


def rounded_rect(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, radius: int = 24) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def make_contact_sheet(scan: dict[str, Any], output: Path, font_path: str | None = None) -> None:
    images = scan["unique_images"][:12]
    columns = min(4, max(1, len(images)))
    rows = math.ceil(len(images) / columns)
    tile_w, tile_h = 340, 580
    margin, gap = 28, 18
    width = margin * 2 + columns * tile_w + (columns - 1) * gap
    height = 92 + margin + rows * tile_h + (rows - 1) * gap + margin
    canvas = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(30, True, font_path)
    label_font = load_font(17, False, font_path)
    draw.text((margin, 26), f"Contact sheet · {scan['unique_count']} unique / {scan['file_count']} files", font=title_font, fill=TEXT)
    for index, entry in enumerate(images):
        row, col = divmod(index, columns)
        x = margin + col * (tile_w + gap)
        y = 92 + margin + row * (tile_h + gap)
        rounded_rect(draw, (x, y, x + tile_w, y + tile_h), CARD, 18)
        thumb = rounded_image(Path(entry["path"]), (tile_w - 24, tile_h - 72), 12)
        canvas.paste(thumb, (x + 12, y + 12))
        label = f"{index:02d} · {Path(entry['path']).name}"
        draw_wrapped(draw, (x + 14, y + tile_h - 50), label, label_font, MUTED, tile_w - 28, max_lines=1)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, "PNG", optimize=True)


def command_scan(args: argparse.Namespace) -> int:
    paths = discover_images(args.inputs)
    if not paths:
        raise SystemExit("No supported images found.")
    groups: dict[str, list[Path]] = defaultdict(list)
    for path in paths:
        groups[sha256_file(path)].append(path)
    unique_paths = [members[0] for _, members in sorted(groups.items(), key=lambda item: natural_key(str(item[1][0])))]
    images: list[dict[str, Any]] = []
    for path in unique_paths:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source)
            width, height = image.size
        images.append(
            {
                "path": str(path),
                "name": path.name,
                "width": width,
                "height": height,
                "orientation": "portrait" if height > width else "landscape" if width > height else "square",
                "sha256": sha256_file(path),
                "palette": extract_palette(path, args.colors),
            }
        )
    duplicates = [
        {"representative": str(members[0]), "copies": [str(path) for path in members[1:]]}
        for members in groups.values()
        if len(members) > 1
    ]
    scan = {
        "file_count": len(paths),
        "unique_count": len(images),
        "duplicate_count": len(paths) - len(images),
        "duplicates": duplicates,
        "unique_images": images,
        "aggregate_palette": aggregate_palette(images),
    }
    output = Path(args.out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(scan, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.contact_sheet:
        make_contact_sheet(scan, Path(args.contact_sheet).resolve(), args.font)
    print(f"Scanned {len(paths)} files -> {len(images)} unique images")
    print(output)
    return 0


class MoodboardRenderer:
    def __init__(self, scan: dict[str, Any], analysis: dict[str, Any], font_path: str | None = None):
        self.scan = scan
        self.a = analysis
        self.font_path = font_path
        self.width = 1600
        self.margin = 28
        self.gap = 20
        self.fonts = {
            "title": load_font(34, True, font_path),
            "h2": load_font(24, True, font_path),
            "h3": load_font(19, True, font_path),
            "body": load_font(17, False, font_path),
            "small": load_font(14, False, font_path),
            "small_bold": load_font(14, True, font_path),
            "hex": load_font(16, True, font_path),
        }

    def validate(self) -> None:
        required = ["title", "subtitle", "positioning", "representatives", "palette", "zones", "rules", "formula"]
        missing = [key for key in required if key not in self.a]
        if missing:
            raise ValueError("analysis.json missing required keys: " + ", ".join(missing))
        positioning = self.a["positioning"]
        if not isinstance(positioning, dict):
            raise ValueError("analysis.json positioning must be an object")
        positioning_missing = [key for key in ("statement", "description") if not positioning.get(key)]
        if positioning_missing:
            raise ValueError("analysis.json positioning missing required keys: " + ", ".join(positioning_missing))
        images = self.scan.get("unique_images", [])
        for representative in self.a["representatives"]:
            index = int(representative["source_index"])
            if index < 0 or index >= len(images):
                raise ValueError(f"Representative source_index out of range: {index}")

    def card(self, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str) -> tuple[int, int, int, int]:
        rounded_rect(draw, box, CARD, 22)
        x1, y1, x2, y2 = box
        draw.text((x1 + 20, y1 + 16), title, font=self.fonts["h2"], fill=TEXT)
        return x1 + 20, y1 + 58, x2 - 20, y2 - 20

    def render(self) -> Image.Image:
        self.validate()
        reps = self.a["representatives"][:12]
        columns = min(4, max(1, len(reps)))
        rows = math.ceil(len(reps) / columns)
        left_w = 1010
        right_w = self.width - self.margin * 2 - self.gap - left_w
        inner_w = left_w - 40
        thumb_gap = 12
        thumb_w = (inner_w - thumb_gap * (columns - 1)) // columns
        thumb_h = round(thumb_w * 16 / 9)
        lanes_h = max(1, len(self.a.get("lanes", []))) * 64
        top_h = 76 + rows * (thumb_h + 42) + max(78, lanes_h) + 28
        rule_rows = math.ceil(len(self.a.get("rules", [])) / 3)
        bottom_h = max(560, 190 + rule_rows * 135)
        header_h = 112
        positioning_h = 218
        height = self.margin + header_h + positioning_h + self.gap + top_h + self.gap + bottom_h + self.margin
        canvas = Image.new("RGB", (self.width, height), BG)
        draw = ImageDraw.Draw(canvas)

        # Header
        draw.text((self.margin, 22), "GAME STORE · VISUAL DNA", font=self.fonts["small_bold"], fill=ACCENT)
        draw.text((self.margin, 48), self.a["title"], font=self.fonts["title"], fill=TEXT)
        subtitle = self.a.get("subtitle", "")
        draw_wrapped(draw, (760, 52), subtitle, self.fonts["body"], MUTED, self.width - 760 - self.margin, max_lines=2)

        # Positioning and description
        positioning = self.a["positioning"]
        positioning_y = self.margin + header_h
        positioning_box = (self.margin, positioning_y, self.width - self.margin, positioning_y + positioning_h)
        px1, py1, px2, py2 = self.card(draw, positioning_box, "情绪板定位与描述")
        meta_w = 450
        copy_w = px2 - px1 - meta_w - 32
        statement = positioning.get("statement", "")
        statement_bottom = draw_wrapped(draw, (px1, py1), statement, self.fonts["h3"], TEXT, copy_w, max_lines=2)
        draw_wrapped(
            draw,
            (px1, statement_bottom + 12),
            positioning.get("description", ""),
            self.fonts["body"],
            MUTED,
            copy_w,
            max_lines=4,
        )
        meta_x = px2 - meta_w
        meta_y = py1
        meta_items = [
            ("品类定位", positioning.get("category", "")),
            ("受众感受", positioning.get("audience", "")),
            ("核心情绪", positioning.get("emotional_goal", "")),
            ("视觉承诺", positioning.get("visual_promise", "")),
        ]
        for label, value in meta_items:
            if not value:
                continue
            draw.text((meta_x, meta_y), label, font=self.fonts["small_bold"], fill=ACCENT)
            meta_y = draw_wrapped(draw, (meta_x + 76, meta_y), str(value), self.fonts["small"], TEXT, meta_w - 76, max_lines=2) + 8

        top_y = positioning_y + positioning_h + self.gap
        left_box = (self.margin, top_y, self.margin + left_w, top_y + top_h)
        right_box = (self.margin + left_w + self.gap, top_y, self.width - self.margin, top_y + top_h)

        # Samples
        lx1, ly1, lx2, ly2 = self.card(draw, left_box, "样本情绪序列")
        for idx, rep in enumerate(reps):
            row, col = divmod(idx, columns)
            x = lx1 + col * (thumb_w + thumb_gap)
            y = ly1 + row * (thumb_h + 42)
            source = self.scan["unique_images"][int(rep["source_index"])]
            thumb = rounded_image(Path(source["path"]), (thumb_w, thumb_h), 12)
            canvas.paste(thumb, (x, y))
            draw_wrapped(draw, (x, y + thumb_h + 7), rep.get("label", source["name"]), self.fonts["small"], TEXT, thumb_w - 32, max_lines=1)
            number = f"{int(rep['source_index']) + 1:02d}"
            draw.text((x + thumb_w - 26, y + thumb_h + 7), number, font=self.fonts["small"], fill=MUTED)
        lane_y = ly1 + rows * (thumb_h + 42) + 6
        for lane in self.a.get("lanes", []):
            colors = lane.get("colors", ["#37C6F1", "#7ED040"])
            c1 = colors[0] if colors else "#37C6F1"
            c2 = colors[1] if len(colors) > 1 else c1
            draw.rounded_rectangle((lx1, lane_y + 5, lx1 + 12, lane_y + 48), radius=6, fill=c1)
            draw.rectangle((lx1, lane_y + 26, lx1 + 12, lane_y + 42), fill=c2)
            draw.text((lx1 + 24, lane_y), lane.get("name", "视觉线"), font=self.fonts["h3"], fill=TEXT)
            draw_wrapped(draw, (lx1 + 24, lane_y + 25), lane.get("description", ""), self.fonts["small"], MUTED, lx2 - lx1 - 40, max_lines=2)
            lane_y += 64

        # Palette and mood
        rx1, ry1, rx2, ry2 = self.card(draw, right_box, "核心色板")
        swatches = self.a.get("palette", [])[:10]
        swatch_cols = 2
        swatch_gap = 12
        swatch_w = (rx2 - rx1 - swatch_gap) // 2
        swatch_h = 92
        for idx, swatch in enumerate(swatches):
            row, col = divmod(idx, swatch_cols)
            x = rx1 + col * (swatch_w + swatch_gap)
            y = ry1 + row * swatch_h
            color = swatch.get("hex", "#808080")
            fg = "#FFFFFF" if swatch.get("text", "light") == "light" else "#172033"
            draw.rounded_rectangle((x, y, x + 84, y + 58), radius=10, fill=color)
            draw.text((x + 7, y + 19), color.upper(), font=self.fonts["small_bold"], fill=fg)
            draw.text((x + 96, y + 3), swatch.get("name", "颜色"), font=self.fonts["body"], fill=TEXT)
            detail = " · ".join(part for part in [swatch.get("usage", ""), swatch.get("share", "")] if part)
            draw_wrapped(draw, (x + 96, y + 31), detail, self.fonts["small"], MUTED, swatch_w - 100, max_lines=2)
        palette_rows = math.ceil(len(swatches) / 2)
        info_y = ry1 + palette_rows * swatch_h + 12
        draw.line((rx1, info_y, rx2, info_y), fill=BORDER, width=2)
        info_y += 18
        keywords = "  ·  ".join(self.a.get("mood_keywords", []))
        if keywords:
            draw.text((rx1, info_y), "情绪", font=self.fonts["small_bold"], fill=ACCENT)
            info_y = draw_wrapped(draw, (rx1 + 48, info_y), keywords, self.fonts["small"], TEXT, rx2 - rx1 - 48, max_lines=2) + 10
        sample_note = self.a.get("sample_note") or f"{self.scan.get('file_count', 0)} 个文件，去重后 {self.scan.get('unique_count', 0)} 张有效样本"
        draw.text((rx1, info_y), "样本", font=self.fonts["small_bold"], fill=ACCENT)
        info_y = draw_wrapped(draw, (rx1 + 48, info_y), sample_note, self.fonts["small"], TEXT, rx2 - rx1 - 48, max_lines=3) + 10
        if self.a.get("conclusion"):
            draw.text((rx1, info_y), "结论", font=self.fonts["small_bold"], fill=ACCENT)
            draw_wrapped(draw, (rx1 + 48, info_y), self.a["conclusion"], self.fonts["small"], TEXT, rx2 - rx1 - 48, max_lines=5)

        # Bottom cards
        bottom_y = top_y + top_h + self.gap
        zone_w = 570
        zone_box = (self.margin, bottom_y, self.margin + zone_w, bottom_y + bottom_h)
        rules_box = (self.margin + zone_w + self.gap, bottom_y, self.width - self.margin, bottom_y + bottom_h)
        zx1, zy1, zx2, zy2 = self.card(draw, zone_box, "画面区域")
        zones = self.a.get("zones", [])
        phone_x, phone_y, phone_w, phone_h = zx1, zy1 + 4, 150, 350
        total = len(zones) or 1
        current_y = phone_y
        for idx, zone in enumerate(zones):
            if idx == len(zones) - 1:
                h = phone_y + phone_h - current_y
            else:
                parsed = re.search(r"(\d+)", str(zone.get("range", "")))
                value = int(parsed.group(1)) if parsed else round(100 / total)
                h = max(42, round(phone_h * value / 100))
            h = min(h, phone_y + phone_h - current_y)
            fill = zone.get("color", "#808080")
            fg = "#FFFFFF" if zone.get("text", "dark") == "light" else "#172033"
            draw.rectangle((phone_x, current_y, phone_x + phone_w, current_y + h), fill=fill)
            label = f"{zone.get('name', '区域')}\n{zone.get('range', '')}"
            lines = label.split("\n")
            baseline = current_y + max(4, h // 2 - 18)
            for line in lines:
                tw = text_width(draw, line, self.fonts["small"])
                draw.text((phone_x + (phone_w - tw) / 2, baseline), line, font=self.fonts["small"], fill=fg)
                baseline += 19
            current_y += h
        draw.rounded_rectangle((phone_x, phone_y, phone_x + phone_w, phone_y + phone_h), radius=22, outline=BORDER, width=2)
        note_x = phone_x + phone_w + 18
        note_y = phone_y
        for index, zone in enumerate(zones[:5], 1):
            draw.text((note_x, note_y), f"{index:02d}", font=self.fonts["small_bold"], fill=ACCENT)
            draw.text((note_x + 44, note_y), zone.get("name", "区域"), font=self.fonts["h3"], fill=TEXT)
            note_y = draw_wrapped(draw, (note_x + 44, note_y + 28), zone.get("description", ""), self.fonts["small"], MUTED, zx2 - note_x - 44, max_lines=3) + 12
        allocation_y = max(phone_y + phone_h + 24, note_y + 10)
        allocation = self.a.get("allocation", [])
        allocation_total = sum(max(0, float(item.get("value", 0))) for item in allocation) or 1
        bar_x, bar_w, bar_h = zx1, zx2 - zx1, 28
        cursor = bar_x
        for idx, item in enumerate(allocation):
            value = max(0, float(item.get("value", 0)))
            segment = round(bar_w * value / allocation_total) if idx < len(allocation) - 1 else bar_x + bar_w - cursor
            draw.rectangle((cursor, allocation_y, cursor + segment, allocation_y + bar_h), fill=item.get("color", "#808080"))
            label = f"{value:g}%"
            fg = "#FFFFFF" if sum(parse_hex(item.get("color", "#808080"))) < 360 else "#172033"
            tw = text_width(draw, label, self.fonts["small_bold"])
            if segment > tw + 10:
                draw.text((cursor + (segment - tw) / 2, allocation_y + 5), label, font=self.fonts["small_bold"], fill=fg)
            cursor += segment
        draw.rounded_rectangle((bar_x, allocation_y, bar_x + bar_w, allocation_y + bar_h), radius=10, outline=BORDER, width=1)
        labels = "   ".join(item.get("label", "") for item in allocation)
        draw_wrapped(draw, (bar_x, allocation_y + 36), labels, self.fonts["small"], MUTED, bar_w, max_lines=2)
        draw.text((bar_x, allocation_y + 70), f"配色分配：{self.a.get('allocation_note', 'recommended')}", font=self.fonts["small"], fill=MUTED)

        # Style rules and formula
        gx1, gy1, gx2, gy2 = self.card(draw, rules_box, "风格语法")
        rule_cols = 3
        rule_gap = 16
        rule_w = (gx2 - gx1 - rule_gap * 2) // 3
        rules = self.a.get("rules", [])
        for idx, rule in enumerate(rules):
            row, col = divmod(idx, rule_cols)
            x = gx1 + col * (rule_w + rule_gap)
            y = gy1 + row * 135
            draw.line((x, y, x + rule_w, y), fill=BORDER, width=2)
            draw.text((x, y + 14), rule.get("name", "规则"), font=self.fonts["h3"], fill=TEXT)
            draw_wrapped(draw, (x, y + 48), rule.get("description", ""), self.fonts["body"], MUTED, rule_w, max_lines=4)
        formula_y = gy1 + math.ceil(max(1, len(rules)) / 3) * 135 + 18
        draw.line((gx1, formula_y, gx2, formula_y), fill=BORDER, width=2)
        formula_y += 24
        x = gx1
        for idx, part in enumerate(self.a.get("formula", [])):
            label = str(part)
            w = min(210, int(text_width(draw, label, self.fonts["small"]) + 24))
            if x + w > gx2:
                x = gx1
                formula_y += 46
            draw.rounded_rectangle((x, formula_y, x + w, formula_y + 34), radius=9, fill="#ECEEF1")
            draw.text((x + 12, formula_y + 8), label, font=self.fonts["small"], fill=MUTED)
            x += w + 10
            if idx < len(self.a.get("formula", [])) - 1:
                draw.text((x, formula_y + 7), "+", font=self.fonts["small_bold"], fill=ACCENT)
                x += 24
        result = self.a.get("formula_result", "可复用的商店图视觉事件")
        result_y = formula_y + 52
        draw.text((gx1, result_y), "视觉公式", font=self.fonts["small_bold"], fill=ACCENT)
        draw_wrapped(draw, (gx1 + 74, result_y), result, self.fonts["h3"], TEXT, gx2 - gx1 - 74, max_lines=2)

        return canvas


def write_html_wrapper(png_path: Path, html_path: Path, title: str) -> None:
    data = base64.b64encode(png_path.read_bytes()).decode("ascii")
    document = f"""<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{html.escape(title)}</title>
<style>html,body{{margin:0;background:#181A20}}body{{display:grid;place-items:start center;padding:24px;box-sizing:border-box}}img{{display:block;width:min(1600px,100%);height:auto;box-shadow:0 16px 60px #0008}}</style></head>
<body><img alt=\"{html.escape(title)}\" src=\"data:image/png;base64,{data}\"></body></html>"""
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(document, encoding="utf-8")


def markdown_cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def write_text_analysis(scan: dict[str, Any], analysis: dict[str, Any], report_path: Path) -> None:
    positioning = analysis.get("positioning", {})
    sample_note = analysis.get("sample_note") or (
        f"{scan.get('file_count', 0)} 个文件，去重后 {scan.get('unique_count', 0)} 张有效样本"
    )
    lines = [
        f"# {analysis.get('title', '游戏商店图视觉分析')}",
        "",
        f"> {analysis.get('subtitle', '')}",
        "",
        "## 1. 情绪板定位",
        "",
        f"**定位结论：** {positioning.get('statement', '')}",
        "",
        positioning.get("description", ""),
        "",
    ]
    positioning_rows = [
        ("品类定位", positioning.get("category", "")),
        ("目标受众感受", positioning.get("audience", "")),
        ("核心情绪", positioning.get("emotional_goal", "")),
        ("视觉承诺", positioning.get("visual_promise", "")),
    ]
    for label, value in positioning_rows:
        if value:
            lines.append(f"- **{label}：** {value}")
    lines.extend(["", "## 2. 样本与视觉路线", "", f"- **样本范围：** {sample_note}"])
    keywords = "、".join(str(item) for item in analysis.get("mood_keywords", []))
    if keywords:
        lines.append(f"- **情绪关键词：** {keywords}")
    for lane in analysis.get("lanes", []):
        lines.append(f"- **{lane.get('name', '视觉路线')}：** {lane.get('description', '')}")

    lines.extend(["", "## 3. 配色分析", "", "| 色彩 | 色值 | 角色与用途 | 占比 |", "| --- | --- | --- | --- |"])
    for item in analysis.get("palette", []):
        lines.append(
            f"| {markdown_cell(item.get('name'))} | `{markdown_cell(item.get('hex'))}` | "
            f"{markdown_cell(item.get('usage'))} | {markdown_cell(item.get('share'))} |"
        )

    lines.extend(["", "## 4. 画面区域", "", "| 区域 | 范围 | 作用 |", "| --- | --- | --- |"])
    for zone in analysis.get("zones", []):
        lines.append(
            f"| {markdown_cell(zone.get('name'))} | {markdown_cell(zone.get('range'))} | "
            f"{markdown_cell(zone.get('description'))} |"
        )

    lines.extend(["", "## 5. 风格语法", ""])
    for rule in analysis.get("rules", []):
        lines.append(f"- **{rule.get('name', '规则')}：** {rule.get('description', '')}")

    formula = " + ".join(str(item) for item in analysis.get("formula", []))
    result = analysis.get("formula_result", "可复用的商店图视觉事件")
    lines.extend(
        [
            "",
            "## 6. 可复用视觉公式",
            "",
            f"`{formula}` → **{result}**",
            "",
            "## 7. 最终结论",
            "",
            analysis.get("conclusion", positioning.get("statement", "")),
            "",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def command_render(args: argparse.Namespace) -> int:
    scan = json.loads(Path(args.scan).read_text(encoding="utf-8-sig"))
    analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8-sig"))
    renderer = MoodboardRenderer(scan, analysis, args.font)
    image = renderer.render()
    output = Path(args.out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "PNG", optimize=True)
    if args.html:
        write_html_wrapper(output, Path(args.html).resolve(), analysis.get("title", "Game Store Visual Moodboard"))
    if args.report:
        report = Path(args.report).resolve()
        write_text_analysis(scan, analysis, report)
        print(report)
    print(output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Inventory, hash-deduplicate, and extract dominant colors")
    scan.add_argument("inputs", nargs="+", help="Image files or directories")
    scan.add_argument("--out", required=True, help="Output scan JSON")
    scan.add_argument("--contact-sheet", help="Optional contact-sheet PNG")
    scan.add_argument("--colors", type=int, default=10, choices=range(4, 17), metavar="4-16")
    scan.add_argument("--font", help="Optional TTF/TTC font for contact sheet")
    scan.set_defaults(func=command_scan)

    render = subparsers.add_parser("render", help="Render a visual moodboard from scan and semantic analysis JSON")
    render.add_argument("--scan", required=True, help="Scan JSON from the scan command")
    render.add_argument("--analysis", required=True, help="Semantic analysis JSON")
    render.add_argument("--out", required=True, help="Output PNG")
    render.add_argument("--report", help="Output Markdown text analysis")
    render.add_argument("--html", help="Optional standalone HTML wrapper")
    render.add_argument("--font", help="Optional TTF/TTC font")
    render.set_defaults(func=command_render)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (FileNotFoundError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
