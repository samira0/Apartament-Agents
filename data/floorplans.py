"""
Floor plan data — 7 synthetic apartments in RPLAN-compatible format.

Each apartment is represented as a graph:
  - nodes: rooms with area (m²) and type
  - edges: connections (doorways) with distance in abstract units

Room types follow RPLAN taxonomy:
  LivingRoom, MasterRoom (bedroom), Kitchen, Bathroom, SecondRoom,
  StudyRoom, BalCony, Storage, Entrance

Distance between rooms = Euclidean distance between room centroids (abstract grid units).
We encode centroid positions so distances are geometrically meaningful.
"""

FLOORPLANS = {
    # ── Apartment 1: classic 1-bedroom, linear layout ──────────────────────────
    "apt_01_1br_linear": {
        "description": "1-bedroom linear layout, 38m²",
        "rooms": {
            "entrance":    {"type": "Entrance",    "area": 4,  "centroid": (1, 3)},
            "kitchen":     {"type": "Kitchen",     "area": 9,  "centroid": (3, 3)},
            "bathroom":    {"type": "Bathroom",    "area": 4,  "centroid": (3, 5)},
            "living_room": {"type": "LivingRoom",  "area": 16, "centroid": (6, 3)},
            "bedroom":     {"type": "MasterRoom",  "area": 12, "centroid": (9, 3)},
        },
        "edges": [
            ("entrance",    "kitchen",     2.0),
            ("kitchen",     "bathroom",    2.0),
            ("kitchen",     "living_room", 3.0),
            ("living_room", "bedroom",     3.0),
        ],
    },

    # ── Apartment 2: 2-bedroom compact with central corridor ───────────────────
    "apt_02_2br_corridor": {
        "description": "2-bedroom with central corridor, 55m²",
        "rooms": {
            "entrance":    {"type": "Entrance",    "area": 5,  "centroid": (0, 4)},
            "corridor":    {"type": "Storage",     "area": 6,  "centroid": (3, 4)},
            "kitchen":     {"type": "Kitchen",     "area": 10, "centroid": (3, 1)},
            "bathroom":    {"type": "Bathroom",    "area": 4,  "centroid": (6, 1)},
            "living_room": {"type": "LivingRoom",  "area": 18, "centroid": (6, 4)},
            "bedroom1":    {"type": "MasterRoom",  "area": 14, "centroid": (3, 7)},
            "bedroom2":    {"type": "SecondRoom",  "area": 10, "centroid": (6, 7)},
        },
        "edges": [
            ("entrance",   "corridor",    3.0),
            ("corridor",   "kitchen",     3.2),
            ("corridor",   "living_room", 3.0),
            ("corridor",   "bedroom1",    3.0),
            ("corridor",   "bedroom2",    3.6),
            ("kitchen",    "bathroom",    3.0),
            ("living_room","bedroom2",    3.0),
        ],
    },

    # ── Apartment 3: studio with open kitchen ──────────────────────────────────
    "apt_03_studio": {
        "description": "Studio / open-plan, 28m²",
        "rooms": {
            "entrance":       {"type": "Entrance",   "area": 3,  "centroid": (0, 2)},
            "open_living_kit": {"type": "LivingRoom", "area": 18, "centroid": (3, 2)},
            "bathroom":       {"type": "Bathroom",   "area": 4,  "centroid": (3, 5)},
            "sleeping_nook":  {"type": "MasterRoom", "area": 8,  "centroid": (6, 2)},
        },
        "edges": [
            ("entrance",        "open_living_kit",  3.0),
            ("open_living_kit", "bathroom",         3.2),
            ("open_living_kit", "sleeping_nook",    3.0),
        ],
    },

    # ── Apartment 4: 2-bedroom with study, awkward layout ─────────────────────
    "apt_04_2br_study": {
        "description": "2-bedroom + study, awkward layout, 65m²",
        "rooms": {
            "entrance":    {"type": "Entrance",   "area": 5,  "centroid": (0, 0)},
            "kitchen":     {"type": "Kitchen",    "area": 11, "centroid": (4, 0)},
            "bathroom":    {"type": "Bathroom",   "area": 5,  "centroid": (8, 0)},
            "living_room": {"type": "LivingRoom", "area": 20, "centroid": (4, 4)},
            "study":       {"type": "StudyRoom",  "area": 9,  "centroid": (8, 4)},
            "bedroom1":    {"type": "MasterRoom", "area": 14, "centroid": (0, 8)},
            "bedroom2":    {"type": "SecondRoom", "area": 10, "centroid": (8, 8)},
        },
        "edges": [
            ("entrance",   "kitchen",     4.0),
            ("entrance",   "living_room", 5.7),   # diagonal, awkward
            ("kitchen",    "bathroom",    4.0),
            ("kitchen",    "living_room", 4.0),
            ("bathroom",   "study",       4.0),
            ("living_room","study",       4.0),
            ("living_room","bedroom1",    5.7),   # long path
            ("study",      "bedroom2",   4.0),
            ("bedroom1",   "bedroom2",   8.0),   # far apart
        ],
    },

    # ── Apartment 5: 3-bedroom family flat, efficient hub ─────────────────────
    "apt_05_3br_efficient": {
        "description": "3-bedroom family flat, efficient hub layout, 80m²",
        "rooms": {
            "entrance":    {"type": "Entrance",   "area": 6,  "centroid": (4, 0)},
            "corridor":    {"type": "Storage",    "area": 7,  "centroid": (4, 3)},
            "kitchen":     {"type": "Kitchen",    "area": 12, "centroid": (1, 3)},
            "bathroom":    {"type": "Bathroom",   "area": 6,  "centroid": (7, 3)},
            "living_room": {"type": "LivingRoom", "area": 22, "centroid": (4, 6)},
            "bedroom1":    {"type": "MasterRoom", "area": 16, "centroid": (1, 6)},
            "bedroom2":    {"type": "SecondRoom", "area": 12, "centroid": (7, 6)},
            "bedroom3":    {"type": "SecondRoom", "area": 10, "centroid": (4, 9)},
        },
        "edges": [
            ("entrance",   "corridor",    3.0),
            ("corridor",   "kitchen",     3.2),
            ("corridor",   "bathroom",    3.2),
            ("corridor",   "living_room", 3.0),
            ("living_room","bedroom1",    3.2),
            ("living_room","bedroom2",    3.2),
            ("living_room","bedroom3",    3.0),
        ],
    },

    # ── Apartment 6: 1-bedroom with balcony, poor bathroom access ─────────────
    "apt_06_1br_balcony": {
        "description": "1-bedroom + balcony, bathroom behind bedroom, 44m²",
        "rooms": {
            "entrance":    {"type": "Entrance",   "area": 4,  "centroid": (0, 3)},
            "kitchen":     {"type": "Kitchen",    "area": 9,  "centroid": (3, 3)},
            "living_room": {"type": "LivingRoom", "area": 15, "centroid": (6, 3)},
            "bedroom":     {"type": "MasterRoom", "area": 12, "centroid": (9, 3)},
            "bathroom":    {"type": "Bathroom",   "area": 4,  "centroid": (9, 6)},  # only via bedroom!
            "balcony":     {"type": "BalCony",    "area": 5,  "centroid": (6, 6)},
        },
        "edges": [
            ("entrance",   "kitchen",     3.0),
            ("kitchen",    "living_room", 3.0),
            ("living_room","bedroom",     3.0),
            ("living_room","balcony",     3.2),
            ("bedroom",    "bathroom",    3.2),   # bathroom only accessible via bedroom
        ],
    },

    # ── Apartment 7: 2-bedroom with dual bathrooms ────────────────────────────
    "apt_07_2br_2bath": {
        "description": "2-bedroom with 2 bathrooms, well-connected, 72m²",
        "rooms": {
            "entrance":    {"type": "Entrance",   "area": 6,  "centroid": (0, 4)},
            "kitchen":     {"type": "Kitchen",    "area": 12, "centroid": (3, 1)},
            "bathroom1":   {"type": "Bathroom",   "area": 5,  "centroid": (3, 7)},
            "living_room": {"type": "LivingRoom", "area": 20, "centroid": (6, 4)},
            "bedroom1":    {"type": "MasterRoom", "area": 15, "centroid": (9, 1)},
            "bathroom2":   {"type": "Bathroom",   "area": 4,  "centroid": (9, 4)},
            "bedroom2":    {"type": "SecondRoom", "area": 12, "centroid": (9, 7)},
        },
        "edges": [
            ("entrance",   "kitchen",     4.2),
            ("entrance",   "living_room", 6.0),
            ("entrance",   "bathroom1",   4.2),  # accessible without going far
            ("kitchen",    "living_room", 3.6),
            ("kitchen",    "bedroom1",    6.0),
            ("living_room","bathroom2",   3.0),
            ("living_room","bedroom1",    3.6),
            ("living_room","bedroom2",    3.6),
            ("bedroom2",   "bathroom1",   3.0),
        ],
    },
}
