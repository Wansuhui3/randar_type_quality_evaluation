"""CLI entry point for Type quality evaluation."""
import argparse
import glob
import os
import sys
from datetime import datetime

import yaml

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.pipeline import run_pipeline
from render.curve_plot import render_all
from render.excel_export import export_report


def load_config(config_path: str) -> dict:
    """Load YAML config file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    return cfg.get('type_eval', cfg)


def main():
    parser = argparse.ArgumentParser(
        description='Type Output Quality Evaluation (Ground-Truth-Free)')
    parser.add_argument('--input', '-i', nargs='+', required=True,
                        help='Input CSV file paths (supports glob patterns)')
    parser.add_argument('--config', '-c', default=None,
                        help='Config YAML path (default: config.yaml in script dir)')
    parser.add_argument('--output', '-o', default='./output',
                        help='Output directory (default: ./output)')
    parser.add_argument('--no-embed-curves', action='store_true',
                        help='Skip embedding curve images in Excel (faster)')
    parser.add_argument('--no-curves', action='store_true',
                        help='Skip curve rendering entirely (fastest)')
    args = parser.parse_args()

    # Resolve glob patterns
    csv_paths = []
    for pattern in args.input:
        matched = glob.glob(pattern)
        if matched:
            csv_paths.extend(matched)
        elif os.path.isfile(pattern):
            csv_paths.append(pattern)
        else:
            print(f"WARNING: No files matched '{pattern}'")

    if not csv_paths:
        print("ERROR: No input CSV files found.")
        sys.exit(1)

    csv_paths = sorted(set(csv_paths))
    print(f"Input files: {len(csv_paths)}")
    for p in csv_paths:
        print(f"  {os.path.basename(p)}")

    # Load config
    if args.config:
        config_path = args.config
    else:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')

    if os.path.exists(config_path):
        config = load_config(config_path)
        print(f"Config: {config_path}")
    else:
        config = {}
        print("WARNING: No config file found, using defaults.")

    # Run pipeline
    print("\nRunning evaluation pipeline...")
    report = run_pipeline(csv_paths, config)

    print(f"  Trajectories evaluated: {report.total_trajectories}")
    print(f"  Pass: {report.pass_count}, Fail: {report.fail_count}")
    print(f"  Fail rate: {report.fail_rate * 100:.1f}%")

    # Render curves
    curve_images = {}
    if not args.no_curves:
        print("\nRendering curve plots...")
        judge_cfg = config.get('judgment', {})
        eval_range_map = judge_cfg.get('eval_range', {}) if judge_cfg.get('eval_range_enabled', True) else {}
        output_cfg = config.get('output', {})
        plot_size = tuple(output_cfg.get('plot_size', [900, 350]))
        plot_dpi = output_cfg.get('plot_dpi', 100)

        curve_images = render_all(
            report.results, eval_range_map,
            size=plot_size, dpi=plot_dpi,
        )
        print(f"  Rendered: {len(curve_images)} curves")

    # Export Excel
    print("\nGenerating Excel report...")
    os.makedirs(args.output, exist_ok=True)

    embed = not args.no_embed_curves and not args.no_curves
    excel_bytes = export_report(report, curve_images, embed=embed)

    date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_name = f"Type_quality_report_{date_str}.xlsx"
    output_path = os.path.join(args.output, output_name)

    with open(output_path, 'wb') as f:
        f.write(excel_bytes)

    file_mb = len(excel_bytes) / (1024 * 1024)
    print(f"  Output: {output_path} ({file_mb:.1f} MB)")
    print("\nDone.")


if __name__ == '__main__':
    main()
