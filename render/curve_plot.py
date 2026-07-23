"""Type curve plot rendering (matplotlib Agg backend)."""
import io

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

from core.models import TrajResult

TYPE_LABELS = {1: '1-Car', 2: '2-Truck', 3: '3-Cyclist', 4: '4-Ped', 7: '7-Uncertain'}


def render_curve(result: TrajResult, eval_range: float = None,
                 size: tuple = (900, 350), dpi: int = 100) -> bytes:
    """
    Render a single trajectory Type curve plot.

    Returns PNG bytes.
    """
    df = result.traj_df
    if df is None or len(df) == 0:
        return b''

    # Time axis (seconds from start)
    t0 = df['ts'].iloc[0]
    t = (df['ts'] - t0).dt.total_seconds().values
    types = df['Type'].values
    dx = df['Dx'].values
    measured = df['Measured'].values

    fig_w = size[0] / dpi
    fig_h = size[1] / dpi
    fig, ax1 = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)

    # Effective distance zone (light blue background)
    if eval_range is not None:
        if result.radar_src in ('rlr', 'rr'):
            in_range_mask = np.abs(dx) <= eval_range
        else:
            in_range_mask = dx <= eval_range
        _shade_in_range(ax1, t, in_range_mask)

    # MSR oscillation zones (grey background)
    if result.has_msr_oscillation and result.msr_osc_segments:
        for seg_start, seg_end in result.msr_osc_segments:
            s_sec = (seg_start - t0).total_seconds()
            e_sec = (seg_end - t0).total_seconds()
            ax1.axvspan(s_sec, e_sec, alpha=0.12, color='gray', zorder=0)

    # Type step plot (left Y axis)
    ax1.step(t, types, where='post', color='#1a1a1a', linewidth=1.3, zorder=3)
    ax1.set_yticks([1, 2, 3, 4, 7])
    ax1.set_yticklabels([TYPE_LABELS.get(i, str(i)) for i in [1, 2, 3, 4, 7]], fontsize=7)
    ax1.set_ylim(0.5, 7.5)
    ax1.set_ylabel('Type', fontsize=8)
    ax1.set_xlabel('Time (s)', fontsize=8)

    # Transition markers
    traj_sorted = df.reset_index(drop=True)
    types_arr = traj_sorted['Type'].values
    all_trans = np.where(types_arr[1:] != types_arr[:-1])[0] + 1

    for idx in all_trans:
        is_in_range = idx in set(result.transition_indices_in)
        if is_in_range:
            ax1.plot(t[idx], types[idx], 'o', color='red', markersize=6, zorder=5)
            ax1.annotate(f'{types[idx-1]}->{types[idx]}',
                        xy=(t[idx], types[idx]),
                        xytext=(t[idx] + 0.2, types[idx] + 0.35),
                        fontsize=6, color='red', fontweight='bold')
        else:
            ax1.plot(t[idx], types[idx], 'o', color='orange', markersize=6,
                    markerfacecolor='none', markeredgewidth=1.5, zorder=5)
            ax1.annotate(f'({types[idx-1]}->{types[idx]})',
                        xy=(t[idx], types[idx]),
                        xytext=(t[idx] + 0.2, types[idx] + 0.35),
                        fontsize=6, color='orange', fontstyle='italic')

    # Dx distance line (right Y axis)
    ax2 = ax1.twinx()
    ax2.plot(t, dx, color='#2196F3', linewidth=0.9, alpha=0.75, zorder=2)
    if eval_range is not None:
        if result.radar_src in ('rlr', 'rr'):
            ax2.axhline(y=-eval_range, color='#2196F3', linestyle='--',
                       linewidth=1.0, alpha=0.6)
            ax2.set_ylim(-max(abs(dx.min()), eval_range * 1.5), 0)
        else:
            ax2.axhline(y=eval_range, color='#2196F3', linestyle='--',
                       linewidth=1.0, alpha=0.6)
            ax2.set_ylim(0, max(dx.max(), eval_range * 1.3))
    ax2.set_ylabel('Dx (m)', fontsize=8, color='#2196F3')
    ax2.tick_params(axis='y', labelcolor='#2196F3', labelsize=7)

    # Title
    title = (f"{result.traj_id} | dom={result.dominant_type} | "
             f"dur={result.duration_s:.1f}s | "
             f"trans={result.transition_count_in}/{result.transition_count_all} | "
             f"{result.verdict}")
    ax1.set_title(title, fontsize=8, fontweight='bold', pad=6)

    # Legend
    handles = [
        plt.Line2D([0], [0], color='#1a1a1a', linewidth=1.3, label='Type'),
        plt.Line2D([0], [0], color='#2196F3', linewidth=0.9, label='Dx (m)'),
    ]
    if eval_range is not None:
        handles.append(plt.Line2D([0], [0], color='#2196F3', linestyle='--',
                                  linewidth=1.0, label=f'Eval Range ({eval_range:.0f}m)'))
    handles.extend([
        plt.Line2D([0], [0], marker='o', color='red', linestyle='None',
                  markersize=5, label='Jump (in-range)'),
        plt.Line2D([0], [0], marker='o', color='orange', linestyle='None',
                  markersize=5, markerfacecolor='none', markeredgewidth=1.5,
                  label='Jump (out-range)'),
    ])
    if result.has_msr_oscillation:
        handles.append(mpatches.Patch(color='gray', alpha=0.12, label='MSR Oscillation'))

    ax1.legend(handles=handles, loc='upper right', fontsize=5.5, ncol=2, framealpha=0.85)

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _shade_in_range(ax, t: np.ndarray, mask: np.ndarray):
    """Shade contiguous in-range intervals with light blue."""
    if not mask.any():
        return
    starts = np.where(mask[1:] & ~mask[:-1])[0] + 1
    ends = np.where(~mask[1:] & mask[:-1])[0] + 1
    if mask[0]:
        starts = np.insert(starts, 0, 0)
    if mask[-1]:
        ends = np.append(ends, len(t) - 1)
    for s, e in zip(starts, ends):
        ax.axvspan(t[s], t[e], alpha=0.06, color='#2196F3', zorder=0)


def render_all(results: list, eval_range_map: dict,
               size: tuple = (900, 350), dpi: int = 100) -> dict:
    """
    Render all trajectory curves.

    Returns {traj_id: png_bytes}
    """
    images = {}
    for result in results:
        eval_range = eval_range_map.get(result.radar_src)
        png_bytes = render_curve(result, eval_range=eval_range, size=size, dpi=dpi)
        if png_bytes:
            images[result.traj_id] = png_bytes
    return images
