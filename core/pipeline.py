"""Pipeline orchestration: CSV -> segmentation -> preprocessing -> judgment -> report."""
import os

import numpy as np
import pandas as pd

from .segmenter import segment_trajectories
from .preprocess import gate_age, drop_short, speed_gate, duration_filter
from .oscillation import label_all
from .judge import evaluate_all
from .models import EvalReport, FilterLog


def parse_radar_source(csv_path: str) -> str:
    """Parse radar position identifier from filename."""
    fname = os.path.basename(csv_path).lower()
    if 'flr' in fname:
        return 'flr'
    elif 'rlr' in fname:
        return 'rlr'
    elif 'fr' in fname:
        return 'fr'
    elif 'rr' in fname:
        return 'rr'
    else:
        return 'unk'


def load_csv(csv_path: str) -> pd.DataFrame:
    """Load radar CSV and parse timestamp."""
    df = pd.read_csv(csv_path, skipinitialspace=True)
    df.columns = df.columns.str.strip()
    df['ts'] = pd.to_datetime(df['timestamp'].str.strip(), format='%Y_%m_%d_%H_%M_%S_%f')
    df = df.sort_values(['ID', 'ts']).reset_index(drop=True)
    return df


def run_pipeline(csv_paths: list, config: dict) -> EvalReport:
    """
    Full evaluation pipeline.

    Parameters
    ----------
    csv_paths : List of input CSV file paths (can include multiple radars).
    config : Configuration dict (loaded from YAML).

    Returns
    -------
    EvalReport containing all trajectory results and filter logs.
    """
    seg_cfg = config.get('segmenter', {})
    min_track_age = config.get('min_track_age', 10)
    speed_cfg = config.get('speed_gate', {})
    duration_cfg = config.get('duration', {1: 5.0, 2: 5.0, 3: 2.0, 4: 2.0, 7: 5.0})
    osc_cfg = config.get('oscillation', {})
    judge_cfg = config.get('judgment', {})

    eval_range_enabled = judge_cfg.get('eval_range_enabled', True)
    eval_range_map = judge_cfg.get('eval_range', {})
    transition_tolerance = judge_cfg.get('transition_tolerance', 0)

    all_results = []
    all_logs = []

    for csv_path in csv_paths:
        radar_src = parse_radar_source(csv_path)

        # Step 0: Load + segment
        df = load_csv(csv_path)
        segments = segment_trajectories(
            df,
            wrap_high=seg_cfg.get('wrap_high', 250),
            wrap_low=seg_cfg.get('wrap_low', 5),
            gap_threshold_ms=seg_cfg.get('gap_threshold_ms', 500.0),
            min_traj_frames=seg_cfg.get('min_traj_frames', 20),
            spatial_split_enabled=seg_cfg.get('spatial_split_enabled', False),
            max_track_speed=seg_cfg.get('max_track_speed', 50.0),
            pos_jump_threshold=seg_cfg.get('pos_jump_threshold', 5.0),
        )

        # Prefix traj_ids with radar source
        prefixed = {}
        for seg_id, seg_df in segments.items():
            new_id = f"{radar_src}_{seg_id}"
            prefixed[new_id] = seg_df
        segments = prefixed

        # Step 1: Track_Age gate
        segments, log1 = gate_age(segments, min_track_age)
        all_logs.append(log1)

        # Step 2: Drop short trajectories
        min_frames = seg_cfg.get('min_traj_frames', 20)
        segments, log2 = drop_short(segments, min_frames)
        all_logs.append(log2)

        # Step 3: Speed gate
        if speed_cfg.get('enabled', True):
            segments, log3 = speed_gate(
                segments,
                gate_types=speed_cfg.get('types', [1, 2]),
                threshold_kmh=speed_cfg.get('threshold_kmh', 30.0),
            )
            all_logs.append(log3)

        # Step 4: Duration filter
        # Convert string keys to int if needed (YAML may load as str)
        dur_thresholds = {int(k): float(v) for k, v in duration_cfg.items()}
        segments, log4 = duration_filter(segments, dur_thresholds)
        all_logs.append(log4)

        # Step 5: Oscillation labeling
        segments = label_all(
            segments,
            window_s=osc_cfg.get('window_s', 2.0),
            min_flips=osc_cfg.get('min_flips', 3),
        )

        # Step 6: Judgment
        eval_range = None
        if eval_range_enabled:
            eval_range = eval_range_map.get(radar_src, eval_range_map.get('unk', 100.0))

        results = evaluate_all(
            segments,
            radar_src=radar_src,
            eval_range=eval_range,
            transition_tolerance=transition_tolerance,
        )
        all_results.extend(results)

    return EvalReport(
        results=all_results,
        filter_logs=all_logs,
        config=config,
        input_files=csv_paths,
    )
