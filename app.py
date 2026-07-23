"""Streamlit UI - Type输出质量评估（中文界面）"""
import os
import sys
import tempfile
from datetime import datetime

import streamlit as st
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.pipeline import run_pipeline
from render.curve_plot import render_all
from render.excel_export import export_report

st.set_page_config(page_title="Type输出质量评估", layout="wide")
st.title("无真值 Type 输出质量评估")
st.caption("在无外部真值条件下，评估雷达目标 Type 分类输出的自洽性与稳定性")

# --- 侧边栏：参数配置 ---
st.sidebar.header("参数配置")

with st.sidebar.expander("距离与判定", expanded=True):
    eval_range_enabled = st.checkbox("启用有效距离筛选", value=True)
    flr_range = st.number_input("前雷达有效距离 (m)", value=100.0, step=10.0)
    rlr_range = st.number_input("后雷达有效距离 (m)", value=50.0, step=10.0)
    transition_tolerance = st.number_input("跳变容差（允许跳变次数）", value=0, min_value=0)

with st.sidebar.expander("预处理门控"):
    min_track_age = st.number_input("最小 Track_Age", value=10, min_value=1)
    speed_enabled = st.checkbox("启用速度门控", value=True)
    speed_threshold = st.number_input("速度阈值 (km/h)", value=30.0, step=5.0)
    min_frames = st.number_input("最小航迹帧数", value=20, min_value=5)

with st.sidebar.expander("输出选项"):
    embed_curves = st.checkbox("在Excel中嵌入曲线图", value=True)

# --- 主区域：文件上传 ---
st.header("1. 上传 CSV 文件")
uploaded_files = st.file_uploader(
    "选择雷达航迹 CSV 文件（支持多文件，前雷达+后雷达）",
    type="csv",
    accept_multiple_files=True,
)

if uploaded_files:
    st.write(f"已选择：{len(uploaded_files)} 个文件")
    for f in uploaded_files:
        st.text(f"  {f.name} ({f.size / 1024:.0f} KB)")

# --- 运行按钮 ---
st.header("2. 执行评估")

if st.button("开始评估", type="primary", disabled=not uploaded_files):
    if not uploaded_files:
        st.warning("请先上传 CSV 文件。")
        st.stop()

    # 根据侧边栏构建配置
    config = {
        'segmenter': {
            'wrap_high': 250, 'wrap_low': 5,
            'gap_threshold_ms': 500, 'min_traj_frames': min_frames,
            'spatial_split_enabled': False,
            'max_track_speed': 50.0, 'pos_jump_threshold': 5.0,
        },
        'min_track_age': min_track_age,
        'speed_gate': {
            'enabled': speed_enabled,
            'types': [1, 2],
            'threshold_kmh': speed_threshold,
        },
        'duration': {1: 5.0, 2: 5.0, 3: 2.0, 4: 2.0, 7: 5.0},
        'oscillation': {'window_s': 2.0, 'min_flips': 3},
        'judgment': {
            'transition_tolerance': transition_tolerance,
            'eval_range_enabled': eval_range_enabled,
            'eval_range': {
                'flr': flr_range, 'rlr': rlr_range,
                'fr': flr_range, 'rr': rlr_range, 'unk': flr_range,
            },
        },
        'output': {'plot_dpi': 100, 'plot_size': [900, 350]},
    }

    # 保存上传文件到临时目录
    with st.spinner("正在保存文件..."):
        tmp_dir = tempfile.mkdtemp()
        csv_paths = []
        for uf in uploaded_files:
            tmp_path = os.path.join(tmp_dir, uf.name)
            with open(tmp_path, 'wb') as f:
                f.write(uf.getbuffer())
            csv_paths.append(tmp_path)

    # 运行管线
    with st.spinner("正在执行评估管线..."):
        report = run_pipeline(csv_paths, config)

    st.success(
        f"共评估 {report.total_trajectories} 条航迹 | "
        f"通过: {report.pass_count} | 失败: {report.fail_count} | "
        f"跳变率: {report.fail_rate * 100:.1f}%"
    )

    # 渲染曲线
    curve_images = {}
    if embed_curves:
        with st.spinner("正在渲染曲线图..."):
            eval_range_map = config['judgment']['eval_range'] if eval_range_enabled else {}
            curve_images = render_all(report.results, eval_range_map)

    # 生成Excel
    with st.spinner("正在生成 Excel 报告..."):
        excel_bytes = export_report(report, curve_images, embed=embed_curves)

    # --- 结果预览 ---
    st.header("3. 评估结果")

    tab1, tab2, tab3 = st.tabs(["汇总统计", "失败航迹详情", "下载报告"])

    with tab1:
        summary_df = report.summary_df()
        if not summary_df.empty:
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
        else:
            st.info("暂无数据。")

    with tab2:
        fail_results = [r for r in report.results if r.verdict == 'fail']
        if fail_results:
            st.write(f"展示 {min(len(fail_results), 20)} / {len(fail_results)} 条失败航迹：")
            for result in fail_results[:20]:
                with st.expander(
                    f"{result.traj_id} | Type={result.dominant_type} | "
                    f"跳变={result.transition_count_in}/{result.transition_count_all} | "
                    f"上下文={''.join(result.contexts)}"
                ):
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        st.text(f"持续时长: {result.duration_s:.1f}s")
                        st.text(f"帧数: {result.frame_count}")
                        st.text(f"均速: {result.mean_speed_kmh:.1f} km/h")
                        st.text(f"跳变明细: {', '.join(result.transition_detail)}")
                        st.text(f"ExistProb@Jump: {result.exist_prob_at_jump}")
                        st.text(f"测量振荡: {result.has_msr_oscillation}")
                    with col2:
                        if result.traj_id in curve_images:
                            st.image(curve_images[result.traj_id], use_column_width=True)
        else:
            st.success("所有航迹均通过！")

    with tab3:
        date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        st.download_button(
            label="下载 Excel 报告",
            data=excel_bytes,
            file_name=f"Type_quality_report_{date_str}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
        st.caption(f"文件大小: {len(excel_bytes) / (1024*1024):.1f} MB")

else:
    st.info("请上传 CSV 文件后点击「开始评估」。")
