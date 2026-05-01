"""
houseexpo_loader.py — Загрузчик реальных планировок из датасета HouseExpo.

Формат HouseExpo JSON (один файл = одна квартира):
{
  "id": "0a1b2c3d",
  "room_num": 6,
  "bbox": {"min": [x1, y1], "max": [x2, y2]},
  "verts": [[x, y], [x, y], ...],        # вершины контура стен (в метрах)
  "room_category": {
      "kitchen":    [[x1,y1,x2,y2], ...],  # bbox каждой комнаты данного типа
      "bedroom":    [[x1,y1,x2,y2], ...],
      "bathroom":   [...],
      "living room":[...],
      ...
  }
}

ВАЖНО: авторы датасета и другие исследователи отмечают, что поле room_category
неточное — типы комнат могут отсутствовать или быть неправильными.
Поэтому загрузчик применяет несколько уровней защиты:
  1. Прямое использование room_category если тип есть
  2. Эвристика по площади bbox для "угадывания" типа
  3. Отбраковка планировок без минимального набора комнат

Pipeline:
  load_houseexpo_json(path)  →  raw dict
  extract_rooms(raw)         →  список комнат с типами и центроидами
  build_adjacency(rooms)     →  рёбра графа (комнаты, чьи bbox соприкасаются)
  to_floorplan(raw, path)    →  dict в формате нашего симулятора
  load_dataset(json_dir, n)  →  {id: floorplan, ...}
"""

import json
import math
import os
import glob
from typing import Dict, List, Optional, Tuple


# ─── Маппинг SUNCG/HouseExpo типов → наши типы ───────────────────────────────
# HouseExpo наследует типы из SUNCG. Ниже все известные варианты написания.
ROOM_TYPE_MAP = {
    # Спальни
    "bedroom":          "MasterRoom",
    "master bedroom":   "MasterRoom",
    "guest room":       "SecondRoom",
    "second bedroom":   "SecondRoom",
    "kid's room":       "SecondRoom",
    "kids room":        "SecondRoom",
    "children room":    "SecondRoom",

    # Кухня
    "kitchen":          "Kitchen",
    "kitchen/dining":   "Kitchen",
    "dining room":      "Kitchen",       # в маленьких квартирах = кухня-столовая
    "dining":           "Kitchen",

    # Ванная / туалет
    "bathroom":         "Bathroom",
    "bath":             "Bathroom",
    "toilet":           "Bathroom",
    "restroom":         "Bathroom",
    "wc":               "Bathroom",
    "powder room":      "Bathroom",
    "laundry room":     "Bathroom",      # часто рядом с ванной

    # Гостиная
    "living room":      "LivingRoom",
    "living":           "LivingRoom",
    "lounge":           "LivingRoom",
    "family room":      "LivingRoom",
    "great room":       "LivingRoom",

    # Кабинет
    "study":            "StudyRoom",
    "office":           "StudyRoom",
    "home office":      "StudyRoom",
    "library":          "StudyRoom",

    # Прихожая
    "entryway":         "Entrance",
    "entry":            "Entrance",
    "foyer":            "Entrance",
    "hall":             "Entrance",
    "hallway":          "Entrance",
    "corridor":         "Entrance",

    # Балкон / терраса
    "balcony":          "BalCony",
    "patio":            "BalCony",
    "terrace":          "BalCony",
    "deck":             "BalCony",
    "porch":            "BalCony",

    # Хранение
    "storage":          "Storage",
    "closet":           "Storage",
    "pantry":           "Storage",
    "utility":          "Storage",
    "garage":           "Storage",
    "mudroom":          "Storage",
}

# Минимальный набор типов комнат для валидной планировки
REQUIRED_TYPES = {"MasterRoom", "Kitchen", "Bathroom"}

# Типы, которые важны для симуляции (остальные игнорируем)
USEFUL_TYPES = {
    "MasterRoom", "SecondRoom", "Kitchen", "Bathroom",
    "LivingRoom", "StudyRoom", "Entrance", "BalCony", "Storage"
}

# Эвристика по площади bbox: если тип неизвестен, угадываем по размеру
# (площадь в м²)
def _guess_type_by_area(area_m2: float, room_idx: int, total_rooms: int) -> str:
    """Грубая эвристика когда тип комнаты неизвестен."""
    if area_m2 < 4.0:
        return "Bathroom"
    elif area_m2 < 8.0:
        return "Entrance" if room_idx == 0 else "Storage"
    elif area_m2 < 14.0:
        return "Kitchen"
    elif area_m2 < 20.0:
        return "MasterRoom" if room_idx < total_rooms // 2 else "SecondRoom"
    else:
        return "LivingRoom"


# ─── Парсинг одного JSON-файла ────────────────────────────────────────────────

def load_houseexpo_json(filepath: str) -> Optional[dict]:
    """Загружает и возвращает сырой dict из JSON-файла HouseExpo."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"  [warn] Не удалось прочитать {filepath}: {e}")
        return None


def _bbox_to_centroid_and_area(bbox: list) -> Tuple[Tuple[float, float], float]:
    """
    bbox может быть:
      [x1, y1, x2, y2]           — плоский список
      [[x1, y1], [x2, y2]]       — список пар
    Возвращает (centroid_xy, area_m2).
    """
    if isinstance(bbox[0], (list, tuple)):
        x1, y1 = bbox[0]
        x2, y2 = bbox[1]
    else:
        x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]

    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    area = abs((x2 - x1) * (y2 - y1))
    return (cx, cy), area


def extract_rooms(raw: dict) -> List[dict]:
    """
    Извлекает список комнат из сырого HouseExpo dict.
    Каждая комната: {id, type, centroid, area, bbox}
    """
    rooms = []
    room_category = raw.get("room_category", {})

    if not room_category:
        return rooms

    room_idx = 0
    total_rooms = sum(len(v) for v in room_category.values())

    for raw_type, bboxes in room_category.items():
        # Нормализуем тип
        normalized = ROOM_TYPE_MAP.get(raw_type.lower().strip())

        # Если тип не в словаре — пробуем частичное совпадение
        if normalized is None:
            for key, val in ROOM_TYPE_MAP.items():
                if key in raw_type.lower():
                    normalized = val
                    break

        for i, bbox in enumerate(bboxes):
            centroid, area = _bbox_to_centroid_and_area(bbox)

            # Если тип всё ещё неизвестен — используем эвристику
            if normalized is None:
                normalized = _guess_type_by_area(area, room_idx, total_rooms)

            # Пропускаем комнаты вне полезного набора
            if normalized not in USEFUL_TYPES:
                room_idx += 1
                continue

            # Уникальный ID: тип + порядковый номер среди комнат данного типа
            suffix = "" if len(bboxes) == 1 else f"_{i+1}"
            # Для второй спальни меняем тип
            if normalized == "MasterRoom" and i > 0:
                normalized = "SecondRoom"

            room_id = f"{raw_type.replace(' ', '_').lower()}{suffix}"

            rooms.append({
                "id":       room_id,
                "type":     normalized,
                "centroid": centroid,
                "area":     round(area, 2),
                "bbox":     bbox,
            })
            room_idx += 1

    return rooms


def build_adjacency(rooms: List[dict], gap_threshold: float = 1.5) -> List[Tuple[str, str, float]]:
    """
    Строит рёбра графа: две комнаты соединены если их bbox'ы
    соприкасаются или находятся близко (gap_threshold в метрах).

    Возвращает список (room_id_a, room_id_b, euclidean_distance).
    """
    edges = []
    n = len(rooms)

    for i in range(n):
        for j in range(i + 1, n):
            ra, rb = rooms[i], rooms[j]

            # Расстояние между центроидами
            dx = ra["centroid"][0] - rb["centroid"][0]
            dy = ra["centroid"][1] - rb["centroid"][1]
            dist = math.sqrt(dx * dx + dy * dy)

            # Проверяем proximity bbox'ов
            def get_bbox_flat(room):
                b = room["bbox"]
                if isinstance(b[0], (list, tuple)):
                    return b[0][0], b[0][1], b[1][0], b[1][1]
                return b[0], b[1], b[2], b[3]

            ax1, ay1, ax2, ay2 = get_bbox_flat(ra)
            bx1, by1, bx2, by2 = get_bbox_flat(rb)

            # Зазор по X и Y
            gap_x = max(0, max(ax1, bx1) - min(ax2, bx2))
            gap_y = max(0, max(ay1, by1) - min(ay2, by2))

            # Комнаты смежны если зазор меньше порога
            if gap_x <= gap_threshold and gap_y <= gap_threshold:
                edges.append((ra["id"], rb["id"], round(dist, 3)))

    return edges


def to_floorplan(raw: dict, filepath: str) -> Optional[dict]:
    """
    Конвертирует сырой HouseExpo dict → формат нашего симулятора.
    Возвращает None если планировка не прошла валидацию.
    """
    house_id = raw.get("id", os.path.splitext(os.path.basename(filepath))[0])

    rooms_list = extract_rooms(raw)
    if not rooms_list:
        return None

    # Проверяем наличие минимально необходимых типов
    found_types = {r["type"] for r in rooms_list}
    missing = REQUIRED_TYPES - found_types
    if missing:
        return None  # Не хватает спальни / кухни / ванной

    edges = build_adjacency(rooms_list)
    if len(edges) < 2:
        return None  # Граф слишком разрозненный

    # Формируем rooms dict в нашем формате
    rooms_dict = {}
    for r in rooms_list:
        rooms_dict[r["id"]] = {
            "type":     r["type"],
            "area":     r["area"],
            "centroid": r["centroid"],
        }

    # Краткое описание
    type_counts = {}
    for r in rooms_list:
        type_counts[r["type"]] = type_counts.get(r["type"], 0) + 1
    desc_parts = []
    if "MasterRoom" in type_counts:
        total_br = type_counts.get("MasterRoom", 0) + type_counts.get("SecondRoom", 0)
        desc_parts.append(f"{total_br}-bedroom")
    if "StudyRoom" in type_counts:
        desc_parts.append("+ study")
    if type_counts.get("Bathroom", 0) > 1:
        desc_parts.append(f"{type_counts['Bathroom']} baths")
    desc_parts.append(f"HouseExpo #{house_id[:8]}")

    return {
        "description": " ".join(desc_parts),
        "source":      "HouseExpo",
        "house_id":    house_id,
        "rooms":       rooms_dict,
        "edges":       edges,
    }


# ─── Загрузка датасета ────────────────────────────────────────────────────────

def load_dataset(
    json_dir: str,
    n: int = 7,
    min_rooms: int = 4,
    max_rooms: int = 10,
    verbose: bool = True,
) -> Dict[str, dict]:
    """
    Загружает n валидных планировок из папки с JSON-файлами HouseExpo.

    Параметры:
      json_dir  — путь к папке ./HouseExpo/json/
      n         — сколько планировок нужно (для ТЗ: 5-7)
      min_rooms — минимум комнат (отсеиваем совсем маленькие)
      max_rooms — максимум комнат (отсеиваем огромные дома)
      verbose   — печатать прогресс

    Возвращает dict {floorplan_id: floorplan_dict}
    """
    pattern = os.path.join(json_dir, "*.json")
    all_files = sorted(glob.glob(pattern))

    if not all_files:
        raise FileNotFoundError(
            f"JSON-файлы не найдены в '{json_dir}'.\n"
            f"Убедись что путь верный. Ожидается структура:\n"
            f"  HouseExpo/\n"
            f"    json/\n"
            f"      0a1b2c3d.json\n"
            f"      ...\n"
            f"Скачай датасет: git clone https://github.com/TeaganLi/HouseExpo"
        )

    if verbose:
        print(f"Найдено JSON-файлов: {len(all_files)}")
        print(f"Ищем {n} планировок с {min_rooms}–{max_rooms} комнатами...\n")

    floorplans = {}
    checked = 0
    skipped_reasons = {"no_file": 0, "parse_error": 0, "missing_rooms": 0,
                       "too_few_rooms": 0, "too_many_rooms": 0, "bad_graph": 0}

    for filepath in all_files:
        if len(floorplans) >= n:
            break

        checked += 1
        raw = load_houseexpo_json(filepath)
        if raw is None:
            skipped_reasons["parse_error"] += 1
            continue

        room_num = raw.get("room_num", 0)
        if room_num < min_rooms:
            skipped_reasons["too_few_rooms"] += 1
            continue
        if room_num > max_rooms:
            skipped_reasons["too_many_rooms"] += 1
            continue

        fp = to_floorplan(raw, filepath)
        if fp is None:
            skipped_reasons["missing_rooms"] += 1
            continue

        actual_rooms = len(fp["rooms"])
        if actual_rooms < min_rooms:
            skipped_reasons["too_few_rooms"] += 1
            continue

        fp_id = f"he_{fp['house_id'][:8]}"
        floorplans[fp_id] = fp

        if verbose:
            print(f"  ✓ {fp_id}  |  комнат: {actual_rooms}  |  рёбер: {len(fp['edges'])}  |  {fp['description']}")

    if verbose:
        print(f"\nПроверено файлов: {checked}")
        print(f"Загружено планировок: {len(floorplans)}/{n}")
        if any(v > 0 for v in skipped_reasons.values()):
            print(f"Пропущено: {skipped_reasons}")

    if len(floorplans) < n:
        print(f"\n[!] Удалось загрузить только {len(floorplans)} из {n} запрошенных планировок.")
        print(f"    Попробуй уменьшить min_rooms или увеличить max_rooms.")

    return floorplans


# ─── Быстрая проверка одного файла ───────────────────────────────────────────

def inspect_json(filepath: str) -> None:
    """Печатает структуру одного JSON-файла HouseExpo — для отладки."""
    raw = load_houseexpo_json(filepath)
    if raw is None:
        print("Не удалось загрузить файл.")
        return

    print(f"ID:        {raw.get('id')}")
    print(f"room_num:  {raw.get('room_num')}")
    print(f"bbox:      {raw.get('bbox')}")
    print(f"verts:     {len(raw.get('verts', []))} вершин")
    print(f"room_category:")
    for rtype, bboxes in raw.get("room_category", {}).items():
        print(f"  {rtype!r:20} → {len(bboxes)} экземпляров")

    rooms = extract_rooms(raw)
    print(f"\nПосле extract_rooms: {len(rooms)} комнат")
    for r in rooms:
        print(f"  {r['id']:30} type={r['type']:12} area={r['area']:.1f}m²  centroid={r['centroid']}")

    edges = build_adjacency(rooms)
    print(f"\nРёбра графа ({len(edges)}):")
    for u, v, d in edges:
        print(f"  {u} ↔ {v}  dist={d:.2f}m")
