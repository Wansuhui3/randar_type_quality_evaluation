# 无真值 Type 输出质量评估

在无外部真值（相机/人工标注）条件下，评估雷达目标 Type 分类输出的自洽性与稳定性。

## 核心逻辑

有效评估距离内，航迹 Type 是否发生跳变：
- 无跳变（transition_count_in == 0）→ **pass**
- 有跳变（transition_count_in > 0）→ **fail**

有效距离：前雷达 100m，后雷达 50m（可配置）。

## 项目结构

```
type_quality_eval/
├── core/               # 算法核心
│   ├── models.py       # 数据结构定义
│   ├── segmenter.py    # 七规则航迹切分
│   ├── preprocess.py   # 预处理门控（Age/帧数/速度/时长）
│   ├── oscillation.py  # Measured 振荡检测
│   ├── judge.py        # 跳变判定（A/B/C/D 上下文）
│   └── pipeline.py     # 管线编排
├── render/             # 输出渲染
│   ├── curve_plot.py   # Type 曲线图（matplotlib）
│   └── excel_export.py # Excel 报告（openpyxl）
├── docs/               # 设计文档
│   ├── 算法设计文档_v4.0.md
│   ├── 架构设计文档_v1.0.md
│   └── 需求规格与实施文档_v1.0.md
├── app.py              # Streamlit Web UI
├── main.py             # CLI 入口
├── config.yaml         # 默认配置
├── requirements.txt    # 依赖
└── 启动UI.bat          # Windows 一键启动
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### CLI 方式

```bash
python main.py --input "CD701_flr_track_*.csv" "CD701_rlr_track_*.csv" --output ./output
```

### Web UI 方式

```bash
streamlit run app.py
```

或 Windows 下双击 `启动UI.bat`。

## 技术栈

- Python 3.11+
- pandas / numpy — 数据处理
- matplotlib (Agg) — 曲线渲染
- openpyxl — Excel 生成（嵌入图片）
- PyYAML — 配置管理
- Streamlit — Web UI

## 配置说明

编辑 `config.yaml` 可调整：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| eval_range.flr | 100 | 前雷达有效距离(m) |
| eval_range.rlr | 50 | 后雷达有效距离(m) |
| min_track_age | 10 | Track_Age 门控 |
| min_traj_frames | 20 | 最小航迹帧数 |
| speed_gate.threshold_kmh | 30 | 速度门控阈值 |
| transition_tolerance | 0 | 跳变容差 |

## 输出

Excel 报告包含：
- **Summary** — 按雷达+Type 汇总统计（跳变率、C-Type/ABD-Fail 分类）
- **Type1_Car ~ Type7_Uncertain** — 逐航迹明细 + 嵌入曲线图
- **Field Guide** — 字段中英双语说明
- **Config** — 运行参数快照
