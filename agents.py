"""
У каждого агента есть:
  - name, description
  - daily_schedule: список (from_room_type, to_room_type, label) маршрутов
  - friction_weights: параметра для расчета Friction Score
  - speed_factor: множитель для более эффективных маршрутов (>1 = медленнее / дороже)
"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class AgentConfig:
    name: str
    description: str
    # Маршруты: (from_room_type, to_room_type, activity_label)
    daily_schedule: List[Tuple[str, str, str]]
    speed_factor: float = 1.0  
    long_path_penalty_threshold: float = 6.0 
    long_path_penalty_multiplier: float = 1.0  
    transition_penalty: float = 0.0   


# Канонические названия типов помещений
ROOM_TYPE_ALIASES = {
    "bedroom":    ["MasterRoom", "SecondRoom", "StudyRoom"],
    "kitchen":    ["Kitchen"],
    "bathroom":   ["Bathroom"],
    "living_room":["LivingRoom"],
    "study":      ["StudyRoom", "SecondRoom"],
    "entrance":   ["Entrance"],
    "balcony":    ["BalCony"],
}


# Агент 1: Пожилой человек (70+)
ELDERLY = AgentConfig(
    name="Elderly (70+)",
    description=(
        "Движения медленные, что является недостатком, если маршрут длинный и с большим количеством переходов. "
        "Необходимо наличие доступа к ванной комнате, не требующего прохождения через множество комнат."
    ),
    daily_schedule=[
        # Утро
        ("MasterRoom",  "Kitchen",    "breakfast"),
        ("Kitchen",     "Bathroom",   "morning hygiene"),
        # Полдень
        ("Bathroom",    "LivingRoom", "rest / TV"),
        ("LivingRoom",  "Kitchen",    "lunch"),
        ("Kitchen",     "LivingRoom", "post-lunch rest"),
        # Послеобеденный выход
        ("LivingRoom",  "Entrance",   "leave apartment"),
        ("Entrance",    "LivingRoom", "return home"),
        # Вечер
        ("LivingRoom",  "Bathroom",   "evening hygiene"),
        ("Bathroom",    "MasterRoom", "go to bed"),
    ],
    speed_factor=1.5,                  
    long_path_penalty_threshold=5.0,   
    long_path_penalty_multiplier=2.0,  
    transition_penalty=0.5,            
)


# Агент 2: Молодая пара
# В квартире проживают два агента; отслеживаем их действия по отдельности и отмечаем одновременные действия.
# Конфликты доступа в помещениях с одним входом (ванная комната, кухня).

COUPLE_A = AgentConfig(
    name="Пара — Партнер 1",
    description="Утренняя спешка, общие пространства создают конфликты.",
    daily_schedule=[
        # Утренняя спешка
        ("MasterRoom",  "Bathroom",   "morning shower"),
        ("Bathroom",    "Kitchen",    "breakfast prep"),
        ("Kitchen",     "Entrance",   "leave for work"),
        # Вечер
        ("Entrance",    "Kitchen",    "cooking together"),
        ("Kitchen",     "LivingRoom", "dinner & relax"),
        ("LivingRoom",  "Bathroom",   "evening hygiene"),
        ("Bathroom",    "MasterRoom", "bedtime"),
    ],
    speed_factor=1.0,
)

COUPLE_B = AgentConfig(
    name="Пара — Партнер 2",
    description="Немного смещенное утреннее расписание.",
    daily_schedule=[
        # Утренняя спешка — компенсируется одним шагом
        ("MasterRoom",  "Kitchen",    "quick breakfast"),
        ("Kitchen",     "Bathroom",   "morning hygiene"),
        ("Bathroom",    "Entrance",   "leave for work"),
        # Вечер (прибытие немного позже)
        ("Entrance",    "LivingRoom", "decompress"),
        ("LivingRoom",  "Kitchen",    "cooking together"),
        ("Kitchen",     "Bathroom",   "evening hygiene"),
        ("Bathroom",    "MasterRoom", "bedtime"),
    ],
    speed_factor=1.0,
)

# Комнаты, где одновременное нахождение приводит к конфликту/ожиданию
CONFLICT_ROOMS = {"Bathroom", "Kitchen"}


#  Агент 3: Холостяк, работающий удаленно
BACHELOR = AgentConfig(
    name="Remote-worker Bachelor",
    description=(
        "Работает из дома. Совершает много коротких переходов: кабинет ↔ кухня и кабинет ↔ ванная комната. "
        "Для него наиболее важен близость кабинета к кухне и ванной комнате."
    ),
    daily_schedule=[
        # Утро
        ("MasterRoom",  "Bathroom",   "morning shower"),
        ("Bathroom",    "Kitchen",    "breakfast"),
        ("Kitchen",     "StudyRoom",  "start work"),
        # Рабочий день - много коротких передвижений 
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
        # Вечер
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
