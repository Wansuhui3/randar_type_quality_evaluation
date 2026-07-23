"""Data models for Type quality evaluation."""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class TrajResult:
    """Single trajectory evaluation result."""

    traj_id: str
    radar_src: str
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    duration_s: float
    frame_count: int
    dominant_type: int
    mean_speed_kmh: float

    # Transition judgment
    transition_count_all: int
    transition_count_in: int
    verdict: str  # 'pass' / 'fail'
    transition_indices_in: np.ndarray = field(default_factory=lambda: np.array([], dtype=int))
    transition_indices_out: np.ndarray = field(default_factory=lambda: np.array([], dtype=int))

    # Context labels
    contexts: list = field(default_factory=list)  # ['C', 'A', ...]
    transition_detail: list = field(default_factory=list)  # ['1->7', '7->1']
    exist_prob_at_jump: list = field(default_factory=list)  # [100, 52]

    # Oscillation labeling
    has_msr_oscillation: bool = False
    msr_osc_ratio: float = 0.0
    msr_osc_segments: list = field(default_factory=list)

    # Raw data reference (for plotting)
    traj_df: Optional[pd.DataFrame] = field(default=None, repr=False)


@dataclass
class FilterLog:
    """Filter step log entry."""

    step_name: str
    input_count: int
    output_count: int
    removed_ids: list = field(default_factory=list)

    @property
    def removed_count(self) -> int:
        return self.input_count - self.output_count


@dataclass
class EvalReport:
    """Complete evaluation report."""

    results: list  # list[TrajResult]
    filter_logs: list  # list[FilterLog]
    config: dict
    input_files: list  # list[str]

    @property
    def radar_sources(self) -> list:
        return sorted(set(r.radar_src for r in self.results))

    @property
    def total_trajectories(self) -> int:
        return len(self.results)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if r.verdict == 'fail')

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.verdict == 'pass')

    @property
    def fail_rate(self) -> float:
        if self.total_trajectories == 0:
            return 0.0
        return self.fail_count / self.total_trajectories

    def summary_df(self) -> pd.DataFrame:
        """Aggregate statistics by radar + dominant type."""
        rows = []
        type_names = {1: 'Car', 2: 'Truck', 3: 'Cyclist', 4: 'Pedestrian', 7: 'Uncertain'}

        for radar in self.radar_sources:
            for dtype in [1, 2, 3, 4, 7]:
                group = [r for r in self.results
                         if r.radar_src == radar and r.dominant_type == dtype]
                if not group:
                    continue
                n = len(group)
                n_fail = sum(1 for r in group if r.verdict == 'fail')
                n_pass = n - n_fail

                # C-Type vs Context-ABD
                c_fail = 0
                abd_fail = 0
                for r in group:
                    if r.verdict != 'fail':
                        continue
                    if 'C' in r.contexts:
                        c_fail += 1
                    else:
                        abd_fail += 1

                fail_transitions = [r.transition_count_in for r in group if r.verdict == 'fail']
                avg_trans = np.mean(fail_transitions) if fail_transitions else 0.0
                avg_dur = np.mean([r.duration_s for r in group])

                rows.append({
                    'Radar': radar,
                    'Type': dtype,
                    'Name': type_names.get(dtype, f'Type{dtype}'),
                    'Trajectories': n,
                    'Pass': n_pass,
                    'Fail': n_fail,
                    'Fail Rate': f"{n_fail / n * 100:.1f}%" if n > 0 else "0%",
                    'C-Type Fail': c_fail,
                    'Context-ABD Fail': abd_fail,
                    'Avg Transitions': round(avg_trans, 1),
                    'Avg Duration(s)': round(avg_dur, 1),
                })

        return pd.DataFrame(rows)
