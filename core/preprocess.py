"""Preprocessing steps 1-4: gates and filters."""
import numpy as np
import pandas as pd

from .models import FilterLog


def gate_age(segments: dict, min_track_age: int = 10) -> tuple:
    """
    Step 1: Remove frames with Track_Age < min_track_age.
    Trajectories with zero remaining frames are discarded.

    Returns (filtered_segments, FilterLog)
    """
    input_count = len(segments)
    filtered = {}
    removed_ids = []

    for seg_id, df in segments.items():
        gated = df[df['Track_Age'] >= min_track_age].copy()
        if len(gated) > 0:
            filtered[seg_id] = gated
        else:
            removed_ids.append(seg_id)

    log = FilterLog(
        step_name='age_gate',
        input_count=input_count,
        output_count=len(filtered),
        removed_ids=removed_ids,
    )
    return filtered, log


def drop_short(segments: dict, min_frames: int = 20) -> tuple:
    """
    Step 2: Discard trajectories with fewer than min_frames frames.

    Returns (filtered_segments, FilterLog)
    """
    input_count = len(segments)
    filtered = {}
    removed_ids = []

    for seg_id, df in segments.items():
        if len(df) >= min_frames:
            filtered[seg_id] = df
        else:
            removed_ids.append(seg_id)

    log = FilterLog(
        step_name='drop_short',
        input_count=input_count,
        output_count=len(filtered),
        removed_ids=removed_ids,
    )
    return filtered, log


def speed_gate(segments: dict, gate_types: list = None,
               threshold_kmh: float = 30.0) -> tuple:
    """
    Step 3: Remove Car/Truck trajectories with mean speed < threshold.
    Only applies to trajectories whose dominant type is in gate_types.

    Returns (filtered_segments, FilterLog)
    """
    if gate_types is None:
        gate_types = [1, 2]

    input_count = len(segments)
    filtered = {}
    removed_ids = []

    for seg_id, df in segments.items():
        # Dominant type
        dom_type = int(df['Type'].mode().iloc[0])

        if dom_type in gate_types:
            # Compute mean relative speed
            speed_kmh = np.sqrt(df['Vx'].values**2 + df['Vy'].values**2) * 3.6
            mean_speed = speed_kmh.mean()
            if mean_speed < threshold_kmh:
                removed_ids.append(seg_id)
                continue

        filtered[seg_id] = df

    log = FilterLog(
        step_name='speed_gate',
        input_count=input_count,
        output_count=len(filtered),
        removed_ids=removed_ids,
    )
    return filtered, log


def duration_filter(segments: dict, thresholds: dict = None) -> tuple:
    """
    Step 4: Filter by minimum duration based on dominant type.

    thresholds: {type_value: min_seconds}, e.g. {1: 5.0, 2: 5.0, 3: 2.0, 4: 2.0, 7: 5.0}

    Returns (filtered_segments, FilterLog)
    """
    if thresholds is None:
        thresholds = {1: 5.0, 2: 5.0, 3: 2.0, 4: 2.0, 7: 5.0}

    input_count = len(segments)
    filtered = {}
    removed_ids = []

    for seg_id, df in segments.items():
        dom_type = int(df['Type'].mode().iloc[0])
        min_dur = thresholds.get(dom_type, 5.0)

        duration = (df['ts'].max() - df['ts'].min()).total_seconds()
        if duration >= min_dur:
            filtered[seg_id] = df
        else:
            removed_ids.append(seg_id)

    log = FilterLog(
        step_name='duration_filter',
        input_count=input_count,
        output_count=len(filtered),
        removed_ids=removed_ids,
    )
    return filtered, log
