"""Step 5: Measured state oscillation labeling."""
import numpy as np
import pandas as pd


def detect_oscillation(traj_df: pd.DataFrame, window_s: float = 2.0,
                       min_flips: int = 3) -> tuple:
    """
    Detect Measured state oscillation in a single trajectory.

    In a sliding window of window_s seconds, if Measured flips (1<->2)
    >= min_flips times, mark that interval as oscillation.

    NOTE: This is a factual measurement-state label, NOT a causal
    "occlusion" diagnosis.

    Returns (has_oscillation, osc_segments, osc_ratio)
      - has_oscillation: bool
      - osc_segments: [(t_start, t_end), ...] as pd.Timestamp tuples
      - osc_ratio: fraction of frames in oscillation-marked intervals
    """
    measured = traj_df['Measured'].values
    ts = traj_df['ts'].values
    n = len(traj_df)

    if n < 2:
        return False, [], 0.0

    # Find flip indices
    flips = np.where(measured[1:] != measured[:-1])[0] + 1

    if len(flips) < min_flips:
        return False, [], 0.0

    # Mark oscillation zones
    osc_mask = np.zeros(n, dtype=bool)
    window_ns = int(window_s * 1e9)

    for flip_idx in flips:
        t_center = ts[flip_idx]
        window_start = t_center - np.timedelta64(window_ns, 'ns')
        window_end = t_center + np.timedelta64(window_ns, 'ns')

        # Count flips within this window
        in_window = (ts[flips] >= window_start) & (ts[flips] <= window_end)
        flips_in_window = np.sum(in_window)

        if flips_in_window >= min_flips:
            # Mark all frames in this window
            frame_in_window = (ts >= window_start) & (ts <= window_end)
            osc_mask[frame_in_window] = True

    if not osc_mask.any():
        return False, [], 0.0

    # Convert mask to segments
    segments = _mask_to_segments(osc_mask, ts)
    ratio = float(osc_mask.sum()) / n

    return True, segments, ratio


def _mask_to_segments(mask: np.ndarray, ts: np.ndarray) -> list:
    """Convert boolean mask to list of (t_start, t_end) tuples."""
    segments = []
    in_seg = False
    start_idx = 0

    for i in range(len(mask)):
        if mask[i] and not in_seg:
            start_idx = i
            in_seg = True
        elif not mask[i] and in_seg:
            segments.append((pd.Timestamp(ts[start_idx]), pd.Timestamp(ts[i - 1])))
            in_seg = False

    if in_seg:
        segments.append((pd.Timestamp(ts[start_idx]), pd.Timestamp(ts[-1])))

    return segments


def label_all(segments: dict, window_s: float = 2.0,
              min_flips: int = 3) -> dict:
    """
    Apply oscillation labeling to all trajectories.
    Adds columns: has_msr_osc, msr_osc_ratio to each DataFrame.
    Stores osc_segments as metadata attribute.

    Returns the same segments dict (modified in place).
    """
    for seg_id, df in segments.items():
        has_osc, osc_segs, ratio = detect_oscillation(df, window_s, min_flips)
        df = df.copy()
        df.attrs['has_msr_oscillation'] = has_osc
        df.attrs['msr_osc_segments'] = osc_segs
        df.attrs['msr_osc_ratio'] = ratio
        segments[seg_id] = df

    return segments
