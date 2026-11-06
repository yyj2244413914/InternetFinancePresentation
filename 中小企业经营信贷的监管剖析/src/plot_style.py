# -*- coding: utf-8 -*-
"""
plot_style —— 图表统一样式（汇报/论文级）
========================================
用法（notebook 或脚本开头）：
    from plot_style import setup, savefig
    setup()
    savefig(fig, "fig_01_violation_ranking")
"""
import warnings
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "outputs" / "figures"
TAB_DIR = ROOT / "outputs" / "tables"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TAB_DIR.mkdir(parents=True, exist_ok=True)

# 配色：沉稳的监管蓝 + 风险红，避免花哨
C_MAIN = "#1f4e79"
C_ACCENT = "#c00000"
C_MID = "#2e75b6"
C_GREY = "#808080"
C_LIGHT = "#d9e2f3"
PALETTE = ["#1f4e79", "#2e75b6", "#8faadc", "#c00000", "#e06666",
           "#f4b183", "#7f7f7f", "#a5a5a5", "#548235", "#bf9000"]


def setup(font_size: int = 11) -> None:
    """中文字体 + 统一视觉参数。汇报前必调，否则中文全是方块。"""
    plt.rcParams.update({
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"],
        "font.family": "sans-serif",
        "axes.unicode_minus": False,
        "figure.dpi": 130,
        "savefig.dpi": 160,
        "figure.figsize": (9.5, 5.0),
        "font.size": font_size,
        "axes.titlesize": font_size + 2,
        "axes.titleweight": "bold",
        "axes.labelsize": font_size,
        "axes.edgecolor": "#666666",
        "axes.linewidth": 0.9,
        "axes.grid": True,
        "grid.color": "#dddddd",
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "legend.frameon": False,
        "legend.fontsize": font_size - 1,
        "xtick.labelsize": font_size - 1,
        "ytick.labelsize": font_size - 1,
        "figure.autolayout": True,
    })


def savefig(fig, name: str, tight: bool = True) -> Path:
    """保存到 outputs/figures/{name}.png，同时返回路径。"""
    p = FIG_DIR / f"{name}.png"
    if tight:
        fig.tight_layout()
    fig.savefig(p, bbox_inches="tight", facecolor="white")
    return p


def annotate_bars(ax, fmt: str = "{:.0f}", offset: float = 3, color: str = "#333333"):
    """在柱状图上标注数值。"""
    for rect in ax.patches:
        h = rect.get_height()
        if h and h == h:                                  # 非 nan
            ax.annotate(fmt.format(h),
                        (rect.get_x() + rect.get_width() / 2, h),
                        textcoords=f"offset points", xytext=(0, offset),
                        ha="center", va="bottom", fontsize=9, color=color)


def conclusion_box(text: str) -> None:
    """在图上加结论说明（右下角灰色小字）。"""
    plt.figtext(0.99, 0.01, text, ha="right", va="bottom",
                fontsize=9, color=C_GREY, style="italic")
