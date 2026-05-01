"""
metrics.py — Extract, aggregate and compare simulation metrics.

Produces:
  - per-agent per-floorplan metric tables
  - aggregate "comfort score" (inverse of friction) for ranking
  - helpers for DataFrame construction (used in the notebook)
"""

import math
import pandas as pd
from typing import List


# ─── Extraction helpers ───────────────────────────────────────────────────────

def extract_agent_row(floorplan_id: str, description: str, agent_label: str, metrics: dict) -> dict:
    return {
        "floorplan":       floorplan_id,
        "description":     description,
        "agent":           agent_label,
        "daily_distance":  metrics.get("daily_distance", 0),
        "n_transitions":   metrics.get("n_transitions", 0),
        "avg_path_length": metrics.get("avg_path_length", 0),
        "friction_score":  metrics.get("friction_score", 0),
        "n_skipped":       metrics.get("n_skipped_trips", 0),
    }


def results_to_dataframe(all_results: List[dict]) -> pd.DataFrame:
    """
    Flatten all simulation results into a tidy DataFrame.
    One row = one (floorplan × agent) combination.
    """
    rows = []
    for res in all_results:
        fid  = res["floorplan_id"]
        desc = res["description"]

        # Elderly
        rows.append(extract_agent_row(
            fid, desc, "Elderly (70+)",
            res["elderly"]["metrics"]
        ))

        # Couple — average the two partners
        ma = res["couple"]["agent_a"]["metrics"]
        mb = res["couple"]["agent_b"]["metrics"]
        avg_metrics = {
            "daily_distance":  (ma["daily_distance"]  + mb["daily_distance"])  / 2,
            "n_transitions":   (ma["n_transitions"]   + mb["n_transitions"])   / 2,
            "avg_path_length": (ma["avg_path_length"] + mb["avg_path_length"]) / 2,
            "friction_score":  (ma["friction_score"]  + mb["friction_score"])  / 2,
            "n_skipped_trips": (ma["n_skipped_trips"] + mb["n_skipped_trips"]) / 2,
        }
        rows.append(extract_agent_row(fid, desc, "Young Couple (avg)", avg_metrics))

        # Bachelor
        rows.append(extract_agent_row(
            fid, desc, "Remote-worker Bachelor",
            res["bachelor"]["metrics"]
        ))

    df = pd.DataFrame(rows)
    return df


def add_comfort_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Comfort Score = 100 / (1 + normalised_friction)

    Normalise friction within each agent group so scores are comparable
    across agents with different absolute friction ranges.
    Scores closer to 100 = more comfortable.
    """
    df = df.copy()
    df["comfort_score"] = 0.0

    for agent in df["agent"].unique():
        mask = df["agent"] == agent
        f = df.loc[mask, "friction_score"]
        f_min, f_max = f.min(), f.max()
        if f_max > f_min:
            norm = (f - f_min) / (f_max - f_min)
        else:
            norm = pd.Series(0.0, index=f.index)
        df.loc[mask, "comfort_score"] = (100 / (1 + norm)).round(1)

    return df


def floorplan_ranking(df: pd.DataFrame) -> pd.DataFrame:
    """
    Average comfort score across all agents per floorplan → overall ranking.
    """
    ranking = (
        df.groupby(["floorplan", "description"])["comfort_score"]
        .mean()
        .reset_index()
        .rename(columns={"comfort_score": "avg_comfort_score"})
        .sort_values("avg_comfort_score", ascending=False)
        .reset_index(drop=True)
    )
    ranking.index += 1  # rank from 1
    ranking["avg_comfort_score"] = ranking["avg_comfort_score"].round(1)
    return ranking
