"""Seven-rule trajectory segmentation (Rules A-G)."""
import numpy as np
import pandas as pd


def segment_trajectories(
    df: pd.DataFrame,
    wrap_high: int = 250,
    wrap_low: int = 5,
    gap_threshold_ms: float = 500.0,
    min_traj_frames: int = 20,
    spatial_split_enabled: bool = False,
    max_track_speed: float = 50.0,
    pos_jump_threshold: float = 5.0,
) -> dict:
    """
    Segment raw radar tracks using 7 rules (A-G).

    Parameters
    ----------
    df : DataFrame with columns [ID, Track_Age, ts, Dx, Dy] sorted by [ID, ts].
    wrap_high : uint8 wraparound upper threshold (Rule B).
    wrap_low : uint8 wraparound lower threshold (Rule B).
    gap_threshold_ms : Max inter-frame time gap in ms (Rule D).
    min_traj_frames : Minimum frames per segment (shorter segments discarded).
    spatial_split_enabled : Enable spatial jump split (Rule F).
    max_track_speed : Max plausible inter-frame speed m/s (Rule F).
    pos_jump_threshold : Position jump threshold m (Rule F).

    Returns
    -------
    dict : {segment_id: DataFrame}, segment_id format "{ID}_seg{N}"
    """
    segments = {}

    for id_val, grp in df.groupby('ID'):
        grp = grp.sort_values('ts').reset_index(drop=True)
        ages = grp['Track_Age'].values
        ts = grp['ts'].values
        n = len(grp)

        if n == 0:
            continue

        # Detect breakpoints
        breakpoints = set()  # indices where a NEW segment starts

        for i in range(1, n):
            age_diff = int(ages[i]) - int(ages[i - 1])

            # Rule B: uint8 wraparound (age[i-1] >= wrap_high and age[i] <= wrap_low)
            if ages[i - 1] >= wrap_high and ages[i] <= wrap_low:
                continue  # Same segment, no break

            # Rule C: Non-wraparound decrease (ID reuse)
            if age_diff < 0:
                breakpoints.add(i)
                continue

            # Rule D: Time gap exceeds threshold
            dt_ms = (ts[i] - ts[i - 1]) / np.timedelta64(1, 'ms')
            if dt_ms > gap_threshold_ms:
                breakpoints.add(i)
                continue

            # Rule F: Spatial jump (optional)
            if spatial_split_enabled and 'Dx' in grp.columns and 'Dy' in grp.columns:
                dx_diff = abs(grp['Dx'].iloc[i] - grp['Dx'].iloc[i - 1])
                dy_diff = abs(grp['Dy'].iloc[i] - grp['Dy'].iloc[i - 1])
                dt_s = dt_ms / 1000.0
                if dt_s > 0:
                    speed = np.sqrt(dx_diff**2 + dy_diff**2) / dt_s
                    if speed > max_track_speed:
                        breakpoints.add(i)
                        continue
                if dx_diff > pos_jump_threshold or dy_diff > pos_jump_threshold:
                    breakpoints.add(i)
                    continue

        # Build segments from breakpoints
        sorted_bp = sorted(breakpoints)
        seg_starts = [0] + sorted_bp
        seg_ends = sorted_bp + [n]

        seg_idx = 0
        for start, end in zip(seg_starts, seg_ends):
            seg_df = grp.iloc[start:end].copy()
            if len(seg_df) >= min_traj_frames:
                seg_id = f"{id_val}_seg{seg_idx}"
                segments[seg_id] = seg_df
            seg_idx += 1

    return segments
