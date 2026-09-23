"""
Synthetic stylized cluster map demo (Voronoi basemap).

Produces only:
  Figure/5_spatial_pattern/demo_style/Stylized_cluster_demo_v2_voronoi.{png,pdf}

Layers:
  - Voronoi building footprints (muted earth tones, thin white street gaps)
  - Large observation points — dark inside clusters, lighter outside
  - Translucent polygonal cluster hulls

Purely synthetic demonstration data — not real geography.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath
from scipy.spatial import Voronoi
from shapely.geometry import MultiPoint, Point, Polygon, box
from shapely.ops import unary_union

# ---------------------------------------------------------------------------
# Paths / style
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "Figure" / "5_spatial_pattern" / "demo_style"
OUT_PNG = OUT_DIR / "Stylized_cluster_demo_v2_voronoi.png"
OUT_PDF = OUT_DIR / "Stylized_cluster_demo_v2_voronoi.pdf"

RNG = np.random.default_rng(42)

BUILDING_COLORS = [
    "#F4EDE3",
    "#E8DFD2",
    "#DDD2C3",
    "#D2C5B4",
    "#C9BBA8",
    "#EFE6DA",
    "#E2D8CA",
    "#D6C9B8",
]

CLUSTER_COLORS = [
    (0.92, 0.72, 0.62, 0.42),  # peach / salmon
    (0.78, 0.78, 0.55, 0.42),  # pale olive
    (0.62, 0.55, 0.48, 0.40),  # muted taupe-brown
    (0.78, 0.52, 0.52, 0.42),  # dusty rose
    (0.55, 0.72, 0.70, 0.42),  # dull teal
]
CLUSTER_EDGE = "#4A3A2E"
POINT_IN_COLOR = "#3D2B1F"  # dark — inside a cluster
POINT_OUT_COLOR = "#C4B5A5"  # lighter — outside clusters
STREET_COLOR = "#FFFFFF"
FRAME_COLOR = "#3D2B1F"
BG_COLOR = "#FAF7F2"

XMIN, XMAX = 0.0, 10.0
YMIN, YMAX = 0.0, 8.0
STREET_GAP = 0.055
HULL_PAD = 0.35


# ---------------------------------------------------------------------------
# Synthetic geometry
# ---------------------------------------------------------------------------
def make_buildings() -> list[Polygon]:
    """Fewer, larger Voronoi cells → zoomed-in urban fabric."""
    nx, ny = 6, 5
    xs = np.linspace(XMIN + 0.35, XMAX - 0.35, nx)
    ys = np.linspace(YMIN + 0.35, YMAX - 0.35, ny)
    xx, yy = np.meshgrid(xs, ys)
    seeds = np.column_stack([xx.ravel(), yy.ravel()])
    seeds += RNG.normal(0, 0.32, size=seeds.shape)

    pad = 5.0
    far = np.array(
        [
            [XMIN - pad, YMIN - pad],
            [XMIN - pad, YMAX + pad],
            [XMAX + pad, YMIN - pad],
            [XMAX + pad, YMAX + pad],
            [XMIN - pad, (YMIN + YMAX) / 2],
            [XMAX + pad, (YMIN + YMAX) / 2],
            [(XMIN + XMAX) / 2, YMIN - pad],
            [(XMIN + XMAX) / 2, YMAX + pad],
        ]
    )
    vor = Voronoi(np.vstack([seeds, far]))
    extent = box(XMIN, YMIN, XMAX, YMAX)

    buildings: list[Polygon] = []
    for region_idx in vor.point_region[: len(seeds)]:
        region = vor.regions[region_idx]
        if not region or -1 in region:
            continue
        poly = Polygon(vor.vertices[region])
        if not poly.is_valid or poly.is_empty:
            continue
        clipped = poly.intersection(extent)
        if clipped.is_empty or clipped.geom_type != "Polygon":
            continue
        eroded = clipped.buffer(-STREET_GAP)
        if eroded.is_empty or eroded.area < 0.08:
            continue
        if eroded.geom_type == "MultiPolygon":
            buildings.extend(
                g for g in eroded.geoms if g.area >= 0.08 and g.geom_type == "Polygon"
            )
        elif eroded.geom_type == "Polygon":
            buildings.append(eroded)
    return buildings


def polygonal_hull(xy: np.ndarray, pad: float = HULL_PAD) -> Polygon:
    """Convex hull expanded with mitred joins → clear polygonal outline."""
    hull = MultiPoint(xy).convex_hull
    if hull.geom_type == "Point":
        x, y = xy[0]
        return box(x - pad, y - pad, x + pad, y + pad)
    if hull.geom_type == "LineString":
        hull = hull.buffer(pad, join_style=2, mitre_limit=2.0, resolution=1)
    else:
        hull = hull.buffer(pad, join_style=2, mitre_limit=2.5, resolution=1)
    if hull.geom_type == "MultiPolygon":
        hull = max(hull.geoms, key=lambda g: g.area)
    hull = hull.simplify(0.02, preserve_topology=True)
    if hull.interiors:
        hull = Polygon(hull.exterior)
    return hull


def make_points_and_clusters() -> tuple[np.ndarray, list[Polygon]]:
    specs = [
        (2.5, 5.5, 16, 0.55, 0.65),  # top-left peach
        (5.8, 5.7, 12, 0.40, 0.38),  # top-centre olive
        (7.5, 2.5, 18, 0.65, 0.75),  # bottom-right taupe
        (2.1, 2.1, 10, 0.32, 0.28),  # bottom-left rose
        (4.6, 2.4, 9, 0.28, 0.26),  # bottom-centre teal
    ]

    clusters: list[np.ndarray] = []
    hulls: list[Polygon] = []
    for cx, cy, n, sx, sy in specs:
        xy = np.column_stack(
            [
                RNG.normal(cx, sx, n),
                RNG.normal(cy, sy, n),
            ]
        )
        xy[:, 0] = np.clip(xy[:, 0], XMIN + 0.35, XMAX - 0.35)
        xy[:, 1] = np.clip(xy[:, 1], YMIN + 0.35, YMAX - 0.35)
        clusters.append(xy)
        hulls.append(polygonal_hull(xy))

    hull_union = unary_union(hulls)
    noise_pts: list[list[float]] = []
    tries = 0
    while len(noise_pts) < 12 and tries < 2000:
        tries += 1
        cand = RNG.uniform([XMIN + 0.5, YMIN + 0.5], [XMAX - 0.5, YMAX - 0.5])
        if hull_union.contains(Point(cand[0], cand[1])):
            continue
        noise_pts.append(cand.tolist())
    all_xy = np.vstack(clusters + [np.asarray(noise_pts)])
    return all_xy, hulls


def point_membership(all_xy: np.ndarray, hulls: list[Polygon]) -> np.ndarray:
    """True if point falls inside any cluster polygon."""
    union = unary_union(hulls)
    return np.array([union.contains(Point(x, y)) for x, y in all_xy], dtype=bool)


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------
def polygon_to_patch(poly: Polygon, **kwargs) -> PathPatch:
    def ring_to_codes(coords):
        coords = list(coords)
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        n = len(coords)
        codes = [MplPath.MOVETO] + [MplPath.LINETO] * (n - 2) + [MplPath.CLOSEPOLY]
        return coords, codes

    verts, codes = ring_to_codes(poly.exterior.coords)
    for interior in poly.interiors:
        v, c = ring_to_codes(interior.coords)
        verts += v
        codes += c
    return PathPatch(MplPath(verts, codes), **kwargs)


def draw_map(
    buildings: list[Polygon],
    all_xy: np.ndarray,
    hulls: list[Polygon],
    inside: np.ndarray,
    out_paths: list[Path],
) -> None:
    fig, ax = plt.subplots(figsize=(10, 8), dpi=200)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(STREET_COLOR)

    colors = [BUILDING_COLORS[i % len(BUILDING_COLORS)] for i in range(len(buildings))]
    order = RNG.permutation(len(buildings))
    colors = [colors[i] for i in order]
    buildings_draw = [buildings[i] for i in order]

    for b, c in zip(buildings_draw, colors):
        ax.add_patch(
            polygon_to_patch(b, facecolor=c, edgecolor="none", linewidth=0, zorder=1)
        )

    for hull, rgba in zip(hulls, CLUSTER_COLORS):
        ax.add_patch(
            polygon_to_patch(
                hull,
                facecolor=rgba,
                edgecolor=CLUSTER_EDGE,
                linewidth=1.4,
                zorder=2,
                joinstyle="miter",
            )
        )

    # Outside points first (lighter), then inside (dark) so inliers sit on top
    out_xy = all_xy[~inside]
    in_xy = all_xy[inside]
    if len(out_xy):
        ax.scatter(
            out_xy[:, 0],
            out_xy[:, 1],
            s=160,
            c=POINT_OUT_COLOR,
            edgecolors="none",
            zorder=3,
            alpha=0.9,
        )
    if len(in_xy):
        ax.scatter(
            in_xy[:, 0],
            in_xy[:, 1],
            s=160,
            c=POINT_IN_COLOR,
            edgecolors="none",
            zorder=4,
            alpha=0.95,
        )

    ax.set_xlim(XMIN, XMAX)
    ax.set_ylim(YMIN, YMAX)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color(FRAME_COLOR)
        spine.set_linewidth(2.4)

    plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in out_paths:
        fig.savefig(
            path,
            dpi=300 if path.suffix.lower() == ".png" else None,
            facecolor=fig.get_facecolor(),
            bbox_inches="tight",
            pad_inches=0.08,
        )
        print(f"Wrote {path}")
    plt.close(fig)


def main() -> None:
    buildings = make_buildings()
    all_xy, hulls = make_points_and_clusters()
    inside = point_membership(all_xy, hulls)
    print(
        f"buildings={len(buildings)}  points={len(all_xy)}  "
        f"inside={inside.sum()}  outside={(~inside).sum()}  clusters={len(hulls)}"
    )
    draw_map(
        buildings,
        all_xy,
        hulls,
        inside,
        [OUT_PNG, OUT_PDF],
    )


if __name__ == "__main__":
    main()
