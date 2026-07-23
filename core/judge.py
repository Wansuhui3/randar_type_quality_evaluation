"""Step 6: Transition judgment + context labeling + distance filtering."""
import numpy as np
import pandas as pd

from .models import TrajResult


def evaluate_trajectory(traj_df: pd.DataFrame, traj_id: str, radar_src: str,
                        eval_range: float = None,
                        transition_tolerance: int = 0) -> TrajResult:
    """
    Evaluate a single trajectory for Type transitions.

    Parameters
    ----------
    traj_df : DataFrame sorted by ts, with columns [Type, Measured, ExistProb, Dx, ts, Vx, Vy]
    traj_id : Global unique trajectory ID (e.g. "flr_12_seg0")
    radar_src : Radar source identifier (flr/rlr/fr/rr)
    eval_range : Effective distance threshold (m). None = no distance filtering.
    transition_tolerance : Allowed transitions before fail (default 0 = zero tolerance).

    Returns
    -------
    TrajResult
    """
    traj_sorted = traj_df.sort_values('ts').reset_index(drop=True)
    types = traj_sorted['Type'].values
    measured = traj_sorted['Measured'].values
    exist_prob = traj_sorted['ExistProb'].values
    dx = traj_sorted['Dx'].values
    n = len(traj_sorted)

    # Basic stats
    start_time = traj_sorted['ts'].iloc[0]
    end_time = traj_sorted['ts'].iloc[-1]
    duration_s = (end_time - start_time).total_seconds()
    dom_type = int(pd.Series(types).mode().iloc[0])
    speed_kmh = np.sqrt(traj_sorted['Vx'].values**2 + traj_sorted['Vy'].values**2) * 3.6
    mean_speed = float(speed_kmh.mean())

    # Detect all adjacent-frame transitions
    all_transitions = np.where(types[1:] != types[:-1])[0] + 1

    # Filter by effective distance
    if eval_range is not None and len(all_transitions) > 0:
        # For front radar: Dx <= eval_range
        # For rear radar: |Dx| <= eval_range (Dx is negative)
        if radar_src in ('rlr', 'rr'):
            in_range_mask = np.abs(dx[all_transitions]) <= eval_range
        else:
            in_range_mask = dx[all_transitions] <= eval_range
        transitions_in = all_transitions[in_range_mask]
        transitions_out = all_transitions[~in_range_mask]
    else:
        transitions_in = all_transitions
        transitions_out = np.array([], dtype=int)

    # Verdict
    count_in = len(transitions_in)
    count_all = len(all_transitions)
    verdict = 'pass' if count_in <= transition_tolerance else 'fail'

    # Context labeling (for in-range transitions)
    contexts = []
    transition_detail = []
    ep_at_jump = []

    for idx in transitions_in:
        m_prev = measured[idx - 1]
        m_curr = measured[idx]

        if m_prev == 1 and m_curr == 2:
            contexts.append('A')
        elif m_prev == 2 and m_curr == 1:
            contexts.append('B')
        elif m_prev == 1 and m_curr == 1:
            contexts.append('C')
        else:
            contexts.append('D')

        transition_detail.append(f"{types[idx - 1]}\u2192{types[idx]}")
        ep_at_jump.append(int(exist_prob[idx]))

    # Oscillation info (set by oscillation.label_all via attrs)
    has_osc = traj_sorted.attrs.get('has_msr_oscillation', False)
    osc_ratio = traj_sorted.attrs.get('msr_osc_ratio', 0.0)
    osc_segs = traj_sorted.attrs.get('msr_osc_segments', [])

    return TrajResult(
        traj_id=traj_id,
        radar_src=radar_src,
        start_time=start_time,
        end_time=end_time,
        duration_s=duration_s,
        frame_count=n,
        dominant_type=dom_type,
        mean_speed_kmh=mean_speed,
        transition_count_all=count_all,
        transition_count_in=count_in,
        verdict=verdict,
        transition_indices_in=transitions_in,
        transition_indices_out=transitions_out,
        contexts=contexts,
        transition_detail=transition_detail,
        exist_prob_at_jump=ep_at_jump,
        has_msr_oscillation=has_osc,
        msr_osc_ratio=osc_ratio,
        msr_osc_segments=osc_segs,
        traj_df=traj_sorted,
    )


def evaluate_all(segments: dict, radar_src: str,
                 eval_range: float = None,
                 transition_tolerance: int = 0) -> list:
    """
    Evaluate all trajectories in segments dict.

    Returns list[TrajResult]
    """
    results = []
    for seg_id, df in segments.items():
        result = evaluate_trajectory(
            df, traj_id=seg_id, radar_src=radar_src,
            eval_range=eval_range,
            transition_tolerance=transition_tolerance,
        )
        results.append(result)
    return results
