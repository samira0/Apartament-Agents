"""
agents.py — Agent definitions and daily scenario schedules.

Each agent has:
  - name, description
  - daily_schedule: ordered list of (from_room_type, to_room_type, label) trips
  - friction_weights: parameters for Friction Score calculation
  - speed_factor: multiplier for effective distance (>1 = slower / more costly)
"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class AgentConfig:
    name: str
    description: str
    # Each trip: (from_room_type, to_room_type, activity_label)
    daily_schedule: List[Tuple[str, str, str]]
    speed_factor: float = 1.0          # >1 means movement is more costly
    long_path_penalty_threshold: float = 6.0   # distance above which penalty kicks in
    long_path_penalty_multiplier: float = 1.0  # extra multiplier for long paths
    transition_penalty: float = 0.0    # per-transition penalty added to friction


# ─── Canonical room-type aliases ──────────────────────────────────────────────
# Maps human-readable activity targets → RPLAN room type keys
ROOM_TYPE_ALIASES = {
    "bedroom":    ["MasterRoom", "SecondRoom", "StudyRoom"],
    "kitchen":    ["Kitchen"],
    "bathroom":   ["Bathroom"],
    "living_room":["LivingRoom"],
    "study":      ["StudyRoom", "SecondRoom"],
    "entrance":   ["Entrance"],
    "balcony":    ["BalCony"],
}


# ─── Agent 1: Elderly person (70+) ────────────────────────────────────────────
ELDERLY = AgentConfig(
    name="Elderly (70+)",
    description=(
        "Moves slowly, penalised by long routes and many transitions. "
        "Needs bathroom access that doesn't require passing through many rooms."
    ),
    daily_schedule=[
        # Morning
        ("MasterRoom",  "Kitchen",    "breakfast"),
        ("Kitchen",     "Bathroom",   "morning hygiene"),
        # Mid-day
        ("Bathroom",    "LivingRoom", "rest / TV"),
        ("LivingRoom",  "Kitchen",    "lunch"),
        ("Kitchen",     "LivingRoom", "post-lunch rest"),
        # Afternoon outing
        ("LivingRoom",  "Entrance",   "leave apartment"),
        ("Entrance",    "LivingRoom", "return home"),
        # Evening
        ("LivingRoom",  "Bathroom",   "evening hygiene"),
        ("Bathroom",    "MasterRoom", "go to bed"),
    ],
    speed_factor=1.5,                  # every step costs 1.5× more
    long_path_penalty_threshold=5.0,   # more sensitive to long paths
    long_path_penalty_multiplier=2.0,  # strong penalty for long paths
    transition_penalty=0.5,            # each transition costs extra
)


# ─── Agent 2: Young couple ─────────────────────────────────────────────────────
# Two agents share the flat; we track them separately and flag simultaneous
# access conflicts on single-access rooms (Bathroom, Kitchen).

COUPLE_A = AgentConfig(
    name="Couple — Partner A",
    description="Part of young couple. Morning rush, shared spaces create conflicts.",
    daily_schedule=[
        # Morning rush
        ("MasterRoom",  "Bathroom",   "morning shower"),
        ("Bathroom",    "Kitchen",    "breakfast prep"),
        ("Kitchen",     "Entrance",   "leave for work"),
        # Evening
        ("Entrance",    "Kitchen",    "cooking together"),
        ("Kitchen",     "LivingRoom", "dinner & relax"),
        ("LivingRoom",  "Bathroom",   "evening hygiene"),
        ("Bathroom",    "MasterRoom", "bedtime"),
    ],
    speed_factor=1.0,
)

COUPLE_B = AgentConfig(
    name="Couple — Partner B",
    description="Part of young couple. Slightly offset morning schedule.",
    daily_schedule=[
        # Morning rush — offset by one step
        ("MasterRoom",  "Kitchen",    "quick breakfast"),
        ("Kitchen",     "Bathroom",   "morning hygiene"),
        ("Bathroom",    "Entrance",   "leave for work"),
        # Evening (arrives slightly later)
        ("Entrance",    "LivingRoom", "decompress"),
        ("LivingRoom",  "Kitchen",    "cooking together"),
        ("Kitchen",     "Bathroom",   "evening hygiene"),
        ("Bathroom",    "MasterRoom", "bedtime"),
    ],
    speed_factor=1.0,
)

# Rooms where simultaneous occupancy causes a conflict/wait
CONFLICT_ROOMS = {"Bathroom", "Kitchen"}


# ─── Agent 3: Remote-working bachelor ─────────────────────────────────────────
BACHELOR = AgentConfig(
    name="Remote-worker Bachelor",
    description=(
        "Works from home. Makes many short trips: study↔kitchen and study↔bathroom. "
        "Cares most about proximity of study to kitchen and bathroom."
    ),
    daily_schedule=[
        # Morning
        ("MasterRoom",  "Bathroom",   "morning shower"),
        ("Bathroom",    "Kitchen",    "breakfast"),
        ("Kitchen",     "StudyRoom",  "start work"),
        # Work day — multiple micro-trips
        ("StudyRoom",   "Kitchen",    "coffee break 1"),
        ("Kitchen",     "StudyRoom",  "back to work 1"),
        ("StudyRoom",   "Bathroom",   "bathroom break 1"),
        ("Bathroom",    "StudyRoom",  "back to work 2"),
        ("StudyRoom",   "Kitchen",    "lunch"),
        ("Kitchen",     "StudyRoom",  "back to work 3"),
        ("StudyRoom",   "Bathroom",   "bathroom break 2"),
        ("Bathroom",    "StudyRoom",  "back to work 4"),
        ("StudyRoom",   "Kitchen",    "coffee break 2"),
        ("Kitchen",     "StudyRoom",  "back to work 5"),
        # Evening
        ("StudyRoom",   "Kitchen",    "cook dinner"),
        ("Kitchen",     "LivingRoom", "relax"),
        ("LivingRoom",  "MasterRoom", "bedtime"),
    ],
    speed_factor=1.0,
    long_path_penalty_threshold=6.0,
    long_path_penalty_multiplier=1.2,
    transition_penalty=0.0,
)


ALL_AGENTS = [ELDERLY, COUPLE_A, COUPLE_B, BACHELOR]
COUPLE_AGENTS = [COUPLE_A, COUPLE_B]
