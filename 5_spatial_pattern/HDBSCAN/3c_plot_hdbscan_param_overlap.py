"""
HDBSCAN parameter sensitivity: the cluster count changes, the hotspot areas do not.

Three seaborn heatmaps over min_cluster_size x min_samples, primary (25, 6) outlined:
  (a) number of clusters
  (b) share of panoramas in a primary hotspot that are still in a hotspot
  (c) Jaccard overlap of the clustered panoramas with the primary run

Input:  5_spatial_pattern/HDBSCAN/Nairobi_hdbscan_param_overlap.csv (3c_hdbscan_param_overlap.py)
Output: Figure/5_spatial_pattern/HDBSCAN/Hdbscan_param_overlap.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle

_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import figure_dir, pattern_dir  # noqa: E402

IN_CSV = pattern_dir() / "HDBSCAN" / "Nairobi_hdbscan_param_overlap.csv"
OUT_PNG = figure_dir() / "5_spatial_pattern" / "HDBSCAN" / "Hdbscan_param_overlap.png"

# Chapter palette, kept light: each scale tops out at a mid tone, not the darkest brown.
PAPER = "#F7F3EE"
TAN = "#C4A484"
MID_BROWN = "#8B6F4E"
DARK_BROWN = "#6B4428"
SAGE = "#64705E"
TEXT = "#4D2D18"
CAPTION = "#7A6A5C"

BROWNS = LinearSegmentedColormap.from_list("browns", [PAPER, TAN, MID_BROWN])
GREENS = LinearSegmentedColormap.from_list("greens", [PAPER, "#B9C0B2", SAGE])

PRIMARY = (25, 6)


def panel(ax, d: pd.DataFrame, col: str, fmt, cmap, vmin: float, vmax: float, title: str, subtitle: str) -> None:
    grid = d.pivot(index="min_cluster_size", columns="min_samples", values=col).sort_index(ascending=False)
    labels = grid.apply(lambda s: s.map(fmt))
    sns.heatmap(
        grid, ax=ax, cmap=cmap, vmin=vmin, vmax=vmax, cbar=False,
        annot=labels, fmt="", linewidths=1.5, linecolor="white", square=False,
        annot_kws={"fontsize": 10},
    )
    # Dark text only where the tile is pale enough to need it.
    for text, value in zip(ax.texts, grid.to_numpy().ravel()):
        text.set_color("white" if (value - vmin) / (vmax - vmin) > 0.72 else TEXT)
    r = list(grid.index).index(PRIMARY[0])
    c = list(grid.columns).index(PRIMARY[1])
    ax.add_patch(Rectangle((c, r), 1, 1, fill=False, edgecolor=DARK_BROWN, linewidth=2.4, clip_on=False))
    ax.set_xlabel("min_samples", color=TEXT)
    ax.set_ylabel("min_cluster_size", color=TEXT)
    ax.tick_params(colors=TEXT, length=0)
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
    ax.text(0, 1.10, title, transform=ax.transAxes, fontsize=11, fontweight="bold", color=TEXT)
    ax.text(0, 1.03, subtitle, transform=ax.transAxes, fontsize=9, color=CAPTION)


def main() -> None:
    if not IN_CSV.exists():
        sys.exit(f"Missing {IN_CSV}\nRun 5_spatial_pattern/HDBSCAN/3c_hdbscan_param_overlap.py first")
    d = pd.read_csv(IN_CSV)
    d["primary"] = d["primary"].astype(str).str.lower().eq("true")
    alt = d[~d["primary"]]
    n_primary = int(d.loc[d["primary"], "n_clusters"].iloc[0])

    sns.set_theme(style="white", rc={"font.family": ["Arial", "Helvetica", "DejaVu Sans"]})
    # Axes placed by hand, in inches, so every tile is square (6 rows x 5 columns)
    # and the gap between panels only has to hold the next panel's y-axis labels.
    n_rows, n_cols = d["min_cluster_size"].nunique(), d["min_samples"].nunique()
    tile = 0.56
    ax_w, ax_h = n_cols * tile, n_rows * tile
    left, gap, right = 0.85, 1.0, 0.25
    bottom, top = 1.2, 0.7
    fig_w = left + 3 * ax_w + 2 * gap + right
    fig_h = bottom + ax_h + top
    fig = plt.figure(figsize=(fig_w, fig_h))
    axes = [
        fig.add_axes(((left + i * (ax_w + gap)) / fig_w, bottom / fig_h, ax_w / fig_w, ax_h / fig_h))
        for i in range(3)
    ]
    panel(
        axes[0], d, "n_clusters", lambda v: f"{int(v)}", BROWNS,
        d["n_clusters"].min(), d["n_clusters"].max(),
        "(a) Number of clusters",
        f"{d['n_clusters'].min()}–{d['n_clusters'].max()} across the grid; primary {n_primary}",
    )
    panel(
        axes[1], d, "primary_retained", lambda v: f"{100 * v:.0f}%", GREENS, 0.80, 1.0,
        "(b) Primary hotspot panoramas retained",
        f"Median {100 * alt['primary_retained'].median():.0f}% "
        f"(range {100 * alt['primary_retained'].min():.0f}–{100 * alt['primary_retained'].max():.0f}%)",
    )
    panel(
        axes[2], d, "jaccard_clustered", lambda v: f"{v:.2f}", GREENS, 0.70, 1.0,
        "(c) Overlap with primary (Jaccard)",
        f"Median {alt['jaccard_clustered'].median():.2f} "
        f"(range {alt['jaccard_clustered'].min():.2f}–{alt['jaccard_clustered'].max():.2f})",
    )

    caption = (
        f"Each tile compares one HDBSCAN run with the primary run (min_cluster_size {PRIMARY[0]}, "
        f"min_samples {PRIMARY[1]}; outlined) on the same 2,696 waste-positive panoramas.\n"
        f"Across the {len(alt)} alternatives, at most {int(alt['primary_dissolved'].max())} of the "
        f"{n_primary} primary clusters dissolve into noise. The count changes because the same areas are "
        "split (low min_cluster_size) or merged (high min_cluster_size):\n"
        f"a median {100 * alt['split_nesting'].median():.0f}% of clustered panoramas sit in an alternative "
        "cluster lying mainly within one primary cluster, and "
        f"{100 * alt['merge_nesting'].median():.0f}% in a primary cluster lying mainly within one alternative cluster."
    )
    fig.text(0.15 / fig_w, 0.12 / fig_h, caption, fontsize=8, color=CAPTION, ha="left", va="bottom", linespacing=1.5)

    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=400, facecolor="white")
    print(f"Wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
