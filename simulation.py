"""
simulation.py — Core simulation engine.

Pipeline:
  1. Build a NetworkX weighted graph from a floorplan dict.
  2. Resolve room-type targets to actual room node IDs (Dijkstra-ready).
  3. Run each agent's daily schedule through Dijkstra's shortest-path algorithm.
  4. Compute the four required metrics per agent per floorplan.
  5. For the couple: detect simultaneous-access conflicts.

Friction Score formula (explicitly documented as required by the spec):

    friction = Σ_trips [ effective_path_cost(trip) ]
             + long_path_penalty
             + transition_penalty
             + conflict_penalty   (couple only)

Where:
    effective_path_cost(trip) = raw_distance(trip) × agent.speed_factor

    long_path_penalty = Σ_trips [
        max(0, raw_distance - threshold) × penalty_multiplier × speed_factor
    ]

    transition_penalty = n_transitions × agent.transition_penalty

    conflict_penalty = n_conflicts × CONFLICT_PENALTY_WEIGHT
"""

import heapq
import math
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# add project root to path so we can import siblings
sys.path.insert(0, "/home/claude/apartment_agents")

from agents import AgentConfig, CONFLICT_ROOMS, ROOM_TYPE_ALIASES

# Weight applied to each simultaneous-room conflict event (for couple simulation)
CONFLICT_PENALTY_WEIGHT = 3.0


# ─── Graph utilities ──────────────────────────────────────────────────────────

def build_graph(floorplan: dict) -> Dict[str, Dict[str, float]]:
    """Return adjacency dict {node: {neighbour: distance, ...}, ...}."""
    graph: Dict[str, Dict[str, float]] = defaultdict(dict)
    for (u, v, dist) in floorplan["edges"]:
        graph[u][v] = dist
        graph[v][u] = dist
    return dict(graph)


def dijkstra(graph: Dict, start: str, end: str) -> Tuple[float, List[str]]:
    """
    Standard Dijkstra returning (total_distance, path_node_list).
    Returns (inf, []) if no path exists.
    """
    dist = {start: 0.0}
    prev: Dict[str, Optional[str]] = {start: None}
    heap = [(0.0, start)]

    while heap:
        d, u = heapq.heappop(heap)
        if u == end:
            # Reconstruct path
            path = []
            node: Optional[str] = end
            while node is not None:
                path.append(node)
                node = prev[node]
            return d, list(reversed(path))
        if d > dist.get(u, math.inf):
            continue
        for v, w in graph.get(u, {}).items():
            nd = d + w
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    return math.inf, []


# ─── Room resolution ──────────────────────────────────────────────────────────

def resolve_room(floorplan: dict, room_type: str) -> Optional[str]:
    """
    Given a RPLAN room type (e.g. "Kitchen"), return the first matching
    room node ID in the floorplan, or None.
    """
    for room_id, meta in floorplan["rooms"].items():
        if meta["type"] == room_type:
            return room_id
    return None


def resolve_schedule_step(
    floorplan: dict,
    from_type: str,
    to_type: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Map (from_type, to_type) → (from_node, to_node) in this floorplan."""
    # Direct type match first
    src = resolve_room(floorplan, from_type)
    dst = resolve_room(floorplan, to_type)

    # Fallback: if MasterRoom not found, try SecondRoom for bedroom trips
    if src is None:
        for alias_type in ["SecondRoom", "LivingRoom"]:
            if from_type == "MasterRoom":
                src = resolve_room(floorplan, alias_type)
                if src:
                    break
    if dst is None:
        for alias_type in ["SecondRoom", "LivingRoom"]:
            if to_type == "MasterRoom":
                dst = resolve_room(floorplan, alias_type)
                if dst:
                    break

    # StudyRoom fallback: remote worker in flat without study goes to bedroom
    if src is None and from_type == "StudyRoom":
        src = resolve_room(floorplan, "SecondRoom") or resolve_room(floorplan, "MasterRoom")
    if dst is None and to_type == "StudyRoom":
        dst = resolve_room(floorplan, "SecondRoom") or resolve_room(floorplan, "MasterRoom")

    return src, dst


# ─── Single-agent simulation ──────────────────────────────────────────────────

def simulate_agent(
    floorplan: dict,
    agent: AgentConfig,
    graph: Optional[Dict] = None,
) -> dict:
    """
    Run one agent through their daily schedule on the given floorplan.

    Returns a result dict with raw trip data and computed metrics.
    """
    if graph is None:
        graph = build_graph(floorplan)

    trips = []
    total_distance = 0.0
    total_friction = 0.0
    n_transitions = 0
    n_unresolved = 0

    for (from_type, to_type, label) in agent.daily_schedule:
        src, dst = resolve_schedule_step(floorplan, from_type, to_type)

        if src is None or dst is None:
            # Room type not present in this floorplan — skip trip gracefully
            trips.append({
                "label": label,
                "from": from_type, "to": to_type,
                "path": [],
                "raw_distance": 0.0,
                "effective_cost": 0.0,
                "status": "skipped_missing_room",
            })
            n_unresolved += 1
            continue

        if src == dst:
            trips.append({
                "label": label,
                "from": src, "to": dst,
                "path": [src],
                "raw_distance": 0.0,
                "effective_cost": 0.0,
                "status": "same_room",
            })
            continue

        raw_dist, path = dijkstra(graph, src, dst)

        if raw_dist == math.inf:
            trips.append({
                "label": label,
                "from": src, "to": dst,
                "path": [],
                "raw_distance": math.inf,
                "effective_cost": math.inf,
                "status": "no_path",
            })
            n_unresolved += 1
            continue

        # Number of room transitions = path length - 1
        n_transitions += len(path) - 1

        # Effective cost = raw distance × speed factor
        eff_cost = raw_dist * agent.speed_factor

        # Long-path penalty
        excess = max(0.0, raw_dist - agent.long_path_penalty_threshold)
        long_penalty = excess * agent.long_path_penalty_multiplier * agent.speed_factor

        trip_friction = eff_cost + long_penalty

        total_distance += raw_dist
        total_friction += trip_friction

        trips.append({
            "label": label,
            "from": src, "to": dst,
            "path": path,
            "raw_distance": round(raw_dist, 3),
            "effective_cost": round(eff_cost, 3),
            "long_penalty": round(long_penalty, 3),
            "trip_friction": round(trip_friction, 3),
            "status": "ok",
        })

    ok_trips = [t for t in trips if t["status"] == "ok"]
    n_ok = len(ok_trips)

    # Transition penalty (per-transition add-on, e.g. for elderly)
    transition_penalty_total = n_transitions * agent.transition_penalty
    total_friction += transition_penalty_total

    avg_path_length = (total_distance / n_ok) if n_ok > 0 else 0.0

    return {
        "agent": agent.name,
        "trips": trips,
        "metrics": {
            "daily_distance":         round(total_distance, 3),
            "n_transitions":          n_transitions,
            "avg_path_length":        round(avg_path_length, 3),
            "friction_score":         round(total_friction, 3),
            "transition_penalty_total": round(transition_penalty_total, 3),
            "n_skipped_trips":        n_unresolved,
        },
    }


# ─── Couple simulation (conflict detection) ───────────────────────────────────

def simulate_couple(
    floorplan: dict,
    agent_a: AgentConfig,
    agent_b: AgentConfig,
) -> dict:
    """
    Simulate two agents simultaneously. Detects room access conflicts:
    when both agents need the same single-occupancy room (Bathroom, Kitchen)
    at the same schedule step, a conflict is recorded.

    Returns merged result with per-agent metrics + conflict count.
    """
    graph = build_graph(floorplan)

    result_a = simulate_agent(floorplan, agent_a, graph)
    result_b = simulate_agent(floorplan, agent_b, graph)

    # Detect conflicts: compare destinations step-by-step
    n_conflicts = 0
    conflicts = []
    min_steps = min(len(result_a["trips"]), len(result_b["trips"]))

    for i in range(min_steps):
        trip_a = result_a["trips"][i]
        trip_b = result_b["trips"][i]

        if trip_a["status"] != "ok" or trip_b["status"] != "ok":
            continue

        # Both agents heading to same conflict room at same step?
        dst_a = trip_a["to"]
        dst_b = trip_b["to"]

        room_type_a = floorplan["rooms"].get(dst_a, {}).get("type", "")
        room_type_b = floorplan["rooms"].get(dst_b, {}).get("type", "")

        if dst_a == dst_b and room_type_a in CONFLICT_ROOMS:
            n_conflicts += 1
            conflicts.append({
                "step": i,
                "room": dst_a,
                "room_type": room_type_a,
                "label_a": trip_a["label"],
                "label_b": trip_b["label"],
            })

    conflict_penalty = n_conflicts * CONFLICT_PENALTY_WEIGHT

    # Add conflict penalty to each partner's friction score
    result_a["metrics"]["conflict_penalty"] = round(conflict_penalty, 3)
    result_b["metrics"]["conflict_penalty"] = round(conflict_penalty, 3)
    result_a["metrics"]["friction_score"] = round(
        result_a["metrics"]["friction_score"] + conflict_penalty, 3
    )
    result_b["metrics"]["friction_score"] = round(
        result_b["metrics"]["friction_score"] + conflict_penalty, 3
    )

    return {
        "agent_a": result_a,
        "agent_b": result_b,
        "n_conflicts": n_conflicts,
        "conflict_penalty": round(conflict_penalty, 3),
        "conflicts": conflicts,
    }


# ─── Full floorplan simulation ─────────────────────────────────────────────────

def simulate_floorplan(floorplan_id: str, floorplan: dict) -> dict:
    """
    Run all agents (elderly, couple A+B, bachelor) on one floorplan.
    Returns structured results dict.
    """
    from agents import ELDERLY, COUPLE_A, COUPLE_B, BACHELOR

    graph = build_graph(floorplan)

    elderly_result  = simulate_agent(floorplan, ELDERLY, graph)
    couple_result   = simulate_couple(floorplan, COUPLE_A, COUPLE_B)
    bachelor_result = simulate_agent(floorplan, BACHELOR, graph)

    return {
        "floorplan_id":   floorplan_id,
        "description":    floorplan["description"],
        "elderly":        elderly_result,
        "couple":         couple_result,
        "bachelor":       bachelor_result,
    }


def run_all(floorplans: dict) -> List[dict]:
    """Simulate all floorplans and return list of results."""
    return [simulate_floorplan(fid, fp) for fid, fp in floorplans.items()]
