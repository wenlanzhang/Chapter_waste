#!/usr/bin/env python3
"""Population-adjusted signed-distance logistic GAMs (panorama unit).

After accounting for local population density and panorama capture year, does
signed distance to an urban-poor settlement still explain visible-waste
probability?

Nested models (same year FE treatment as Signed_distance/1_signed_distance_gam.py):

  M0  : logit(p) = α + year
  MP  : logit(p) = α + s(log1p(pop_density)) + year
  MD  : logit(p) = α + s(signed_distance) + year          # same as primary S4
  MDP : logit(p) = α + s(signed_distance) + s(log1p(pop_density)) + year
  MDPS: MDP + thin-plate spatial field on (x, y)          # residual-spatial sensitivity

Central test: MP vs MDP. Also report MD vs MDP.
Default population covariate (the manuscript sample): static WorldPop
unconstrained Kenya 2020 (ken_ppp_2020.tif), outputs in pop_adjusted/worldpop_2020/.
Override with --pop-raster / --output-dir; worldpop_2024_constrained/ does this
for the WorldPop constrained 2024 layer (a sensitivity, not the manuscript).
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import statsmodels.api as sm
from esda.moran import Moran
from libpysal.weights import KNN
from scipy import stats
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression
from sklearn.metrics import brier_score_loss, log_loss
from statsmodels.gam.api import BSplines, GLMGam

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "chapter_paths.py").is_file())
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chapter_paths import phd_data_root  # noqa: E402
from lib.gam import (  # noqa: E402
    BOOT_SEED,
    CI_ALPHA,
    PRED_GRID_N,
    SPLINE_DEGREE,
    SPLINE_DF,
    assign_year_fe,
)
from lib.panoids import (  # noqa: E402
    PATTERN_DIR,
    enrich_sviwaste_frame,
    label_inside_settlement,
    load_slums,
    signed_distance_to_slums,
)

# Every population-raster run lives in its own folder under POP_ADJ_ROOT.
# The default is the manuscript sample: WorldPop unconstrained Kenya 2020.
# worldpop_2024_constrained/ wraps this script for the 2024 constrained layer.
POP_ADJ_ROOT = PATTERN_DIR / "Signed_distance" / "pop_adjusted"
MANUSCRIPT_SUBDIR = "worldpop_2020"
OUTPUT_DIR = POP_ADJ_ROOT / MANUSCRIPT_SUBDIR
TABLE_DIR = OUTPUT_DIR / "thesis_table"
POP_RASTER = phd_data_root() / "RS" / "Pop_density" / "UnconstraintIndividualCountries" / "ken_ppp_2020.tif"
POP_LABEL = "static WorldPop unconstrained Kenya 2020 (ken_ppp_2020, people/pixel)"
POP_SHORT = "WorldPop unconstrained KE 2020 (static)"
THESIS_NAME = "pop_adjusted_gam_worldpop_2020.csv"

SPLINE_DF_SPATIAL = 6
BLOCK_BOOT_M = 2000.0  # block side for the curve bands: residual correlation is ~0 by 2 km
BLOCK_BOOT_B = 500
N_SPATIAL_KNOTS = 25
N_CV_FOLDS = 5
MORAN_K = 8
STD_SAMPLE_N = 500  # quantiles used when standardising over the other covariate


def standardisation_points(values: pd.Series) -> np.ndarray:
    """STD_SAMPLE_N evenly spaced quantiles of a covariate, the values a curve is
    averaged over (deterministic, and equal to averaging over every panorama)."""
    v = values.to_numpy(dtype=float)
    if len(v) <= STD_SAMPLE_N:
        return v
    return np.quantile(v, (np.arange(STD_SAMPLE_N) + 0.5) / STD_SAMPLE_N)


def prepare_analysis_frame() -> pd.DataFrame:
    points = enrich_sviwaste_frame()
    slums = load_slums()
    points = label_inside_settlement(points, slums)
    points["signed_distance_m"] = signed_distance_to_slums(points, slums)
    points["x"] = points.geometry.x.astype(float)
    points["y"] = points.geometry.y.astype(float)

    pop_count, cell_area_km2 = sample_worldpop(points)
    points["pop_count"] = pop_count
    points["pop_cell_area_km2"] = cell_area_km2
    points["pop_density_km2"] = points["pop_count"] / points["pop_cell_area_km2"]
    points["log1p_pop_density"] = np.log1p(points["pop_density_km2"].to_numpy(dtype=float))

    df = points[
        [
            "panoid",
            "waste_positive",
            "inside_settlement",
            "year",
            "n_positive_views",
            "signed_distance_m",
            "x",
            "y",
            "pop_count",
            "pop_density_km2",
            "log1p_pop_density",
            "pop_cell_area_km2",
        ]
    ].copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(
        subset=[
            "year",
            "signed_distance_m",
            "waste_positive",
            "log1p_pop_density",
            "x",
            "y",
        ]
    ).copy()
    df["year"] = df["year"].astype(int)
    df["waste_positive"] = df["waste_positive"].astype(int)

    n_before_year = len(df)
    df = assign_year_fe(df)
    print(
        f"  Frame: n={len(df):,} (dropped NA pop/year/distance from "
        f"enrichment; year FE applied; n_before_fe_ops≈{n_before_year:,})"
    )
    return df.reset_index(drop=True)


def sample_worldpop(points) -> tuple[np.ndarray, np.ndarray]:
    """Sample people/pixel and approximate cell area (km²) at each panorama."""
    if not POP_RASTER.exists():
        raise FileNotFoundError(f"Missing WorldPop raster: {POP_RASTER}")

    pts_ll = points.to_crs(epsg=4326)
    coords = list(zip(pts_ll.geometry.x.to_numpy(), pts_ll.geometry.y.to_numpy()))
    lats = pts_ll.geometry.y.to_numpy(dtype=float)

    with rasterio.open(POP_RASTER) as src:
        nodata = src.nodata
        res_x, res_y = src.res
        vals = np.array([v[0] for v in src.sample(coords)], dtype=float)
        if nodata is not None:
            vals[vals == nodata] = np.nan
        vals[~np.isfinite(vals)] = np.nan
        # Constrained WorldPop: negative codes treated as missing
        vals[vals < 0] = np.nan

    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * np.cos(np.deg2rad(lats))
    area_km2 = np.abs(res_x) * m_per_deg_lon * np.abs(res_y) * m_per_deg_lat / 1e6
    area_km2 = np.maximum(area_km2, 1e-12)
    n_ok = int(np.isfinite(vals).sum())
    print(
        f"  WorldPop sample: {n_ok:,}/{len(vals):,} finite | "
        f"median count={np.nanmedian(vals):.2f} | "
        f"median dens≈{np.nanmedian(vals / area_km2):.0f} people/km² | "
        f"raster={POP_RASTER.name} ({POP_LABEL})"
    )
    return vals, area_km2


def _year_exog(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    year_dummies = pd.get_dummies(df["year_fe"], drop_first=True, prefix="year")
    year_cols = year_dummies.columns.tolist()
    exog = sm.add_constant(year_dummies.astype(float), has_constant="add")
    return exog, year_cols


def _align_exog(exog: pd.DataFrame, col_order: list[str]) -> np.ndarray:
    out = pd.DataFrame(0.0, index=np.arange(len(exog)), columns=col_order)
    for c in col_order:
        if c in exog.columns:
            out[c] = exog[c].to_numpy(dtype=float)
    return out.to_numpy(dtype=float)


def _standardize_xy(xy: np.ndarray) -> np.ndarray:
    """Centre/scale UTM metres for a stable spatial field."""
    sd = xy.std(axis=0)
    return (xy - xy.mean(axis=0)) / np.where(sd < 1e-6, 1.0, sd)


def _spatial_basis(xy: np.ndarray, knots: np.ndarray) -> np.ndarray:
    """Thin-plate radial basis on knot locations (sensitivity spatial field)."""
    d = cdist(xy, knots)
    d = np.maximum(d, 1e-6)
    phi = (d**2) * np.log(d)
    # centre columns for numerical stability
    phi = phi - phi.mean(axis=0, keepdims=True)
    scale = phi.std(axis=0, keepdims=True)
    scale[scale < 1e-12] = 1.0
    return phi / scale


DIST, POP = "signed_distance_m", "log1p_pop_density"
MODEL_SMOOTHS = {"M0": [], "MP": [POP], "MD": [DIST], "MDP": [DIST, POP]}


def smoother_for(df: pd.DataFrame, cols: list[str]) -> BSplines:
    k = len(cols)
    return BSplines(
        df[cols].astype(float), df=[SPLINE_DF] * k, degree=[SPLINE_DEGREE] * k, variable_names=cols
    )


def fit_gam(
    df: pd.DataFrame,
    smooth_cols: list[str],
    alpha: float | None = None,
    extra_exog: pd.DataFrame | None = None,
):
    """Logistic GAM: constant + year FE (+ extra_exog) + one B-spline per smooth_col.

    Returns (result, year dummy columns). No smooths means a plain GLM (M0).
    """
    y = df["waste_positive"].to_numpy(dtype=float)
    exog, year_cols = _year_exog(df)
    if extra_exog is not None:
        exog = pd.concat([exog, extra_exog], axis=1)
    if not smooth_cols:
        return sm.GLM(y, exog, family=sm.families.Binomial()).fit(), year_cols
    kwargs = {"alpha": np.full(len(smooth_cols), float(alpha))} if alpha is not None else {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = GLMGam(
            y, exog=exog, smoother=smoother_for(df, smooth_cols),
            family=sm.families.Binomial(), **kwargs,
        ).fit()
    return result, year_cols


def fit_m0(df: pd.DataFrame):
    return fit_gam(df, MODEL_SMOOTHS["M0"])


def fit_mp(df: pd.DataFrame, alpha: float | None = None):
    return fit_gam(df, MODEL_SMOOTHS["MP"], alpha)


def fit_md(df: pd.DataFrame, alpha: float | None = None):
    return fit_gam(df, MODEL_SMOOTHS["MD"], alpha)


def fit_mdp(df: pd.DataFrame, alpha: float | None = None):
    return fit_gam(df, MODEL_SMOOTHS["MDP"], alpha)


def spatial_knots(df: pd.DataFrame) -> np.ndarray:
    xy = _standardize_xy(df[["x", "y"]].to_numpy(dtype=float))
    return KMeans(n_clusters=N_SPATIAL_KNOTS, random_state=BOOT_SEED, n_init=10).fit(xy).cluster_centers_


def spatial_field(df: pd.DataFrame, knots: np.ndarray) -> pd.DataFrame:
    """Thin-plate basis columns of the spatial field, one row per panorama."""
    xy = _standardize_xy(df[["x", "y"]].to_numpy(dtype=float))
    phi = _spatial_basis(xy, knots)
    return pd.DataFrame(phi, columns=[f"spatial_rbf_{i}" for i in range(phi.shape[1])], index=df.index)


def fit_mdps(df: pd.DataFrame, knots: np.ndarray | None = None):
    """MDP + spatial field. Returns (result, year dummy columns, knots)."""
    knots = spatial_knots(df) if knots is None else knots
    result, year_cols = fit_gam(df, [DIST, POP], alpha=0.5, extra_exog=spatial_field(df, knots))
    return result, year_cols, knots


def _n_params(result) -> float:
    """Count finite estimated parameters (GLMGam df_model/aic can be unstable)."""
    params = np.asarray(result.params, dtype=float)
    return float(np.sum(np.isfinite(params)))


def _safe_aic(result) -> float:
    ll = float(result.llf)
    if not np.isfinite(ll):
        return float("nan")
    k = _n_params(result)
    if k <= 0:
        return float("nan")
    return float(-2.0 * ll + 2.0 * k)


def _model_metrics(result, name: str, n: int) -> dict:
    ll = float(result.llf)
    llnull = getattr(result, "llnull", None)
    if llnull is None or not np.isfinite(llnull) or llnull == 0:
        pseudo_r2 = np.nan
        deviance_explained = np.nan
    else:
        pseudo_r2 = float(1.0 - (ll / float(llnull)))
        null_dev = float(getattr(result, "null_deviance", np.nan))
        dev = float(result.deviance)
        deviance_explained = (
            float(1.0 - (dev / null_dev))
            if np.isfinite(null_dev) and null_dev > 0
            else np.nan
        )
    k = _n_params(result)
    return {
        "model": name,
        "n": n,
        "aic": _safe_aic(result),
        "llf": ll,
        "df_model": k,
        "deviance": float(result.deviance),
        "pseudo_r2_mcfadden": pseudo_r2,
        "deviance_explained": deviance_explained,
    }


def likelihood_ratio_test(result_full, result_nested, label: str) -> dict:
    ll_full = float(result_full.llf)
    ll_nested = float(result_nested.llf)
    df_diff = max(_n_params(result_full) - _n_params(result_nested), 1.0)
    lr_stat = max(2.0 * (ll_full - ll_nested), 0.0)
    p_value = float(stats.chi2.sf(lr_stat, df_diff))
    aic_full = _safe_aic(result_full)
    aic_nested = _safe_aic(result_nested)
    return {
        "comparison": label,
        "ll_full": ll_full,
        "ll_nested": ll_nested,
        "lr_stat": lr_stat,
        "df_diff": df_diff,
        "p_value": p_value,
        "aic_full": aic_full,
        "aic_nested": aic_nested,
        "delta_aic_nested_minus_full": float(aic_nested - aic_full),
    }


def year_standardisation_weights(df: pd.DataFrame) -> pd.Series:
    return df["year_fe"].astype(str).value_counts(normalize=True).sort_index()


def _exog_at_year(grid_n: int, year_cols: list[str], fixed_year: str) -> np.ndarray:
    exog = pd.DataFrame({"const": np.ones(grid_n, dtype=float)})
    for col in year_cols:
        level = col.replace("year_", "", 1)
        exog[col] = 1.0 if level == fixed_year else 0.0
    return exog.to_numpy(dtype=float)


def _predict_mdp(
    result, year_cols: list[str], dist: np.ndarray, logpop: np.ndarray, year_level: str
) -> np.ndarray:
    exog = _exog_at_year(len(dist), year_cols, year_level)
    xs = np.column_stack([dist, logpop])
    return np.asarray(result.predict(exog=exog, exog_smooth=xs), dtype=float)


def _mdp_year_average(
    df: pd.DataFrame,
    result,
    year_cols: list[str],
    dist_rep: np.ndarray,
    pop_rep: np.ndarray,
    n_points: int,
    grid_n: int,
) -> np.ndarray:
    """Mean MDP prediction over n_points standardisation values, weighted by year share."""
    weights = year_standardisation_weights(df)
    weights.index = weights.index.astype(str)
    out = np.zeros(grid_n, dtype=float)
    for level, wt in weights.items():
        pred = _predict_mdp(result, year_cols, dist_rep, pop_rep, str(level))
        out += float(wt) * pred.reshape(n_points, grid_n).mean(axis=0)
    return out


def mdp_distance_curve(
    df: pd.DataFrame, result, year_cols: list[str], grid: np.ndarray
) -> np.ndarray:
    """Adjusted P(waste+) over a signed-distance grid, standardised over pop + year.

    The one definition of the curve: every script and figure in pop_adjusted/
    calls this, so the central MDP curve is the same wherever it is drawn.
    Population and year shares are those of `df` itself.
    """
    pop = standardisation_points(df["log1p_pop_density"])
    g = len(grid)
    return _mdp_year_average(
        df, result, year_cols, np.tile(grid, len(pop)), np.repeat(pop, g), len(pop), g
    )


def mdp_population_curve(
    df: pd.DataFrame, result, year_cols: list[str], grid: np.ndarray
) -> np.ndarray:
    """Adjusted P(waste+) over a log1p(pop density) grid, standardised over distance + year."""
    dist = standardisation_points(df["signed_distance_m"])
    g = len(grid)
    return _mdp_year_average(
        df, result, year_cols, np.repeat(dist, g), np.tile(grid, len(dist)), len(dist), g
    )


def refit_mdp(df: pd.DataFrame):
    """MDP on a (re)sample: year FE reassigned on the rows present, ridge fallback."""
    d = assign_year_fe(df.drop(columns=["year_fe"], errors="ignore"), verbose=False)
    res, cols = fit_mdp(d)
    if not np.isfinite(float(res.llf)):
        res, cols = fit_mdp(d, alpha=1.0)
    return d, res, cols


def block_sample(xy: np.ndarray, block_m: float, rng: np.random.Generator) -> np.ndarray:
    """Row indices of one spatial block bootstrap sample (random grid offset)."""
    off = rng.uniform(0, block_m, size=2)
    cell = np.floor((xy + off) / block_m).astype(np.int64)
    key = cell[:, 0] * 1_000_003 + cell[:, 1]
    uniq, inv = np.unique(key, return_inverse=True)
    order = np.argsort(inv, kind="stable")
    starts = np.searchsorted(inv[order], np.arange(len(uniq)))
    ends = np.append(starts[1:], len(order))
    drawn = rng.integers(0, len(uniq), size=len(uniq))
    return np.concatenate([order[starts[b] : ends[b]] for b in drawn])


def block_bootstrap_seed(block_m: float) -> int:
    """Seed of the replicate stream for one block size (0 = panorama-level).

    Shared with 3_spatial_block_bootstrap.py, so the 2 km band drawn here is
    the same set of replicates as the 2 km row of its interval table.
    """
    return BOOT_SEED + int(block_m) + 7


def distance_grid(df: pd.DataFrame) -> np.ndarray:
    return np.linspace(
        float(df["signed_distance_m"].quantile(0.01)),
        float(df["signed_distance_m"].quantile(0.99)),
        PRED_GRID_N,
    )


def population_grid(df: pd.DataFrame) -> np.ndarray:
    return np.linspace(
        float(df["log1p_pop_density"].quantile(0.01)),
        float(df["log1p_pop_density"].quantile(0.99)),
        PRED_GRID_N,
    )


def block_bootstrap_curves(
    df: pd.DataFrame,
    d_grid: np.ndarray,
    p_grid: np.ndarray,
    block_m: float = BLOCK_BOOT_M,
    n_boot: int = BLOCK_BOOT_B,
) -> tuple[np.ndarray, np.ndarray]:
    """Spatial block bootstrap replicates of both adjusted curves.

    Each replicate resamples occupied blocks with replacement, refits MDP and
    re-standardises over that replicate's own population (or distance) and
    year distribution. Returns (distance draws, population draws), one row per
    replicate that fitted.
    """
    xy = df[["x", "y"]].to_numpy(dtype=float)
    rng = np.random.default_rng(block_bootstrap_seed(block_m))
    d_draws: list[np.ndarray] = []
    p_draws: list[np.ndarray] = []
    for r in range(n_boot):
        boot = df.iloc[block_sample(xy, block_m, rng)].reset_index(drop=True)
        if boot["waste_positive"].nunique() < 2:
            continue
        try:
            d, res, cols = refit_mdp(boot)
        except Exception as exc:
            print(f"    rep {r}: fit failed ({exc})")
            continue
        for draws, curve_fn, grid in (
            (d_draws, mdp_distance_curve, d_grid),
            (p_draws, mdp_population_curve, p_grid),
        ):
            try:
                draws.append(curve_fn(d, res, cols, grid))
            except Exception as exc:
                print(f"    rep {r}: {curve_fn.__name__} failed ({exc})")
        if (r + 1) % 100 == 0:
            print(f"    {r + 1}/{n_boot} replicates")
    return np.vstack(d_draws), np.vstack(p_draws)


ELASTICITY_RANGE_KM2 = (1000.0, 70000.0)


def population_elasticity(p_grid: np.ndarray, curve: np.ndarray) -> float:
    """Slope of log P(waste+) on log density over ELASTICITY_RANGE_KM2.

    1 would mean prevalence proportional to population. Same definition as
    4plot_pop_scaling_null.R.
    """
    dens = np.expm1(p_grid)
    ok = (dens >= ELASTICITY_RANGE_KM2[0]) & (dens <= ELASTICITY_RANGE_KM2[1]) & (curve > 0)
    return float(np.polyfit(np.log(dens[ok]), np.log(curve[ok]), 1)[0])


def _curve_frame(
    x: dict, mean: np.ndarray, draws: np.ndarray, block_m: float, prediction_type: str, panel: str
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            **x,
            "prob_waste_positive": mean,
            "prob_ci_low": np.nanpercentile(draws, 100.0 * (CI_ALPHA / 2.0), axis=0),
            "prob_ci_high": np.nanpercentile(draws, 100.0 * (1.0 - CI_ALPHA / 2.0), axis=0),
            "prediction_type": prediction_type,
            "ci_method": f"spatial_block_bootstrap_{block_m:.0f}m_B{len(draws)}",
            "ci_block_m": block_m,
            "ci_n_draws": len(draws),
            "ci_alpha": CI_ALPHA,
            "panel": panel,
        }
    )


def standardised_curves(
    df: pd.DataFrame, result, year_cols: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Both adjusted MDP curves with 95% spatial block bootstrap bands
    (BLOCK_BOOT_B replicates, BLOCK_BOOT_M blocks), plus the population
    elasticity with its interval from the same replicates."""
    d_grid, p_grid = distance_grid(df), population_grid(df)
    mean_d = mdp_distance_curve(df, result, year_cols, d_grid)
    mean_p = mdp_population_curve(df, result, year_cols, p_grid)
    print(
        f"  Spatial block bootstrap bands ({BLOCK_BOOT_M:,.0f} m blocks, B={BLOCK_BOOT_B})..."
    )
    d_draws, p_draws = block_bootstrap_curves(df, d_grid, p_grid)
    print(f"  Bands from {len(d_draws)} distance / {len(p_draws)} population replicates")
    curve_d = _curve_frame(
        {"signed_distance_m": d_grid},
        mean_d, d_draws, BLOCK_BOOT_M, "pop_year_standardised", "distance",
    )
    curve_p = _curve_frame(
        {"log1p_pop_density": p_grid, "pop_density_km2": np.expm1(p_grid)},
        mean_p, p_draws, BLOCK_BOOT_M, "distance_year_standardised", "population",
    )
    el_draws = np.array([population_elasticity(p_grid, c) for c in p_draws])
    elasticity = {
        "pop_elasticity": population_elasticity(p_grid, mean_p),
        "pop_elasticity_ci_low": float(np.percentile(el_draws, 100.0 * (CI_ALPHA / 2.0))),
        "pop_elasticity_ci_high": float(np.percentile(el_draws, 100.0 * (1.0 - CI_ALPHA / 2.0))),
        "pop_elasticity_share_draws_ge_1": float(np.mean(el_draws >= 1.0)),
        "pop_elasticity_ci_method": curve_p["ci_method"].iloc[0],
    }
    print(
        f"  Population elasticity {elasticity['pop_elasticity']:.2f} "
        f"({elasticity['pop_elasticity_ci_low']:.2f}–{elasticity['pop_elasticity_ci_high']:.2f})"
    )
    return curve_d, curve_p, elasticity


def concurvity_diagnostics(df: pd.DataFrame) -> pd.DataFrame:
    """GAM-style concurvity between distance and population smooth bases."""
    x = df[[DIST, POP]].to_numpy(dtype=float)
    basis = np.asarray(smoother_for(df, [DIST, POP]).transform(x), dtype=float)
    # Columns are the distance basis, then the population basis, equal in size.
    n_each = basis.shape[1] // 2
    b_d, b_p = basis[:, :n_each], basis[:, n_each:]

    def block_r2(target: np.ndarray, other: np.ndarray) -> tuple[float, float]:
        r2s = []
        for j in range(target.shape[1]):
            yj = target[:, j]
            if np.nanstd(yj) < 1e-12:
                continue
            reg = LinearRegression().fit(other, yj)
            r2s.append(float(reg.score(other, yj)))
        if not r2s:
            return np.nan, np.nan
        return float(np.mean(r2s)), float(np.max(r2s))

    mean_d_given_p, max_d_given_p = block_r2(b_d, b_p)
    mean_p_given_d, max_p_given_d = block_r2(b_p, b_d)
    spearman = float(
        stats.spearmanr(df["signed_distance_m"], df["log1p_pop_density"]).correlation
    )
    pearson = float(
        np.corrcoef(df["signed_distance_m"], df["log1p_pop_density"])[0, 1]
    )
    return pd.DataFrame(
        [
            {
                "spearman_signed_distance_vs_log1p_pop": spearman,
                "pearson_signed_distance_vs_log1p_pop": pearson,
                "concurvity_mean_distance_given_pop": mean_d_given_p,
                "concurvity_max_distance_given_pop": max_d_given_p,
                "concurvity_mean_pop_given_distance": mean_p_given_d,
                "concurvity_max_pop_given_distance": max_p_given_d,
                "note": (
                    "Concurvity ≈ how well each smooth's B-spline basis is linearly "
                    "predicted by the other smooth's basis (GAM analogue of collinearity). "
                    "High values imply overlapping spatial information; interpret "
                    "adjusted effects cautiously."
                ),
            }
        ]
    )


def residual_moran(df: pd.DataFrame, result) -> dict:
    """Moran's I on MDP Pearson residuals (k-NN weights)."""
    # statsmodels resid_pearson aligned to rows
    resid = np.asarray(result.resid_pearson, dtype=float)
    mask = np.isfinite(resid)
    xy = df.loc[mask, ["x", "y"]].to_numpy(dtype=float)
    resid = resid[mask]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        w = KNN.from_array(xy, k=MORAN_K)
        w.transform = "r"
        mi = Moran(resid, w, permutations=999)
    return {
        "moran_i": float(mi.I),
        "moran_e": float(mi.EI),
        "moran_p_sim": float(mi.p_sim),
        "moran_z": float(mi.z_sim),
        "k_nn": MORAN_K,
        "n": int(mask.sum()),
        "meaningful_residual_spatial_structure": int(mi.p_sim < 0.05),
    }


def mdp_residual_frame(df: pd.DataFrame, result) -> pd.DataFrame:
    """Panorama-level MDP residuals for excess/deficit occurrence maps.

    resid_response = y − μ  (excess probability vs MDP expectation)
    resid_pearson  = (y − μ) / sqrt(μ(1−μ))  (standardised; used for Moran's I)
    """
    y = df["waste_positive"].to_numpy(dtype=float)
    mu = np.asarray(result.fittedvalues, dtype=float)
    if len(mu) != len(df):
        raise ValueError(
            f"fittedvalues length {len(mu)} != frame length {len(df)}"
        )
    resid_pearson = np.asarray(result.resid_pearson, dtype=float)
    resid_deviance = np.asarray(result.resid_deviance, dtype=float)
    cols = [
        "panoid",
        "waste_positive",
        "year",
        "year_fe",
        "signed_distance_m",
        "log1p_pop_density",
        "pop_density_km2",
        "x",
        "y",
        "inside_settlement",
    ]
    out = df[cols].copy()
    out["pred_prob"] = mu
    out["resid_response"] = y - mu
    out["resid_pearson"] = resid_pearson
    out["resid_deviance"] = resid_deviance
    out["model"] = "MDP"
    out["model_formula"] = (
        "waste ~ s(signed_distance) + s(log1p(pop_density)) + year"
    )
    return out.reset_index(drop=True)


def spatial_blocked_cv(df: pd.DataFrame) -> pd.DataFrame:
    """Out-of-sample Brier score and log-loss under spatially blocked 5-fold CV.

    Folds are five geographic clusters of panoramas (KMeans on x, y), so each
    model is scored on an area it was not fitted to. Held-out covariates are
    clipped to the training fold's range, because a B-spline basis is not
    defined outside its knots; year levels absent from the training fold fall
    on the reference year.

    A model's row with fold = -1 pools every held-out panorama, and is only
    written when all five folds predicted, so the pooled rows are comparable
    across models.
    """
    xy = df[["x", "y"]].to_numpy(dtype=float)
    labels = KMeans(
        n_clusters=N_CV_FOLDS, random_state=BOOT_SEED, n_init=10
    ).fit_predict(xy)
    rows = []
    for model_name, smooth_cols in MODEL_SMOOTHS.items():
        y_all: list[np.ndarray] = []
        p_all: list[np.ndarray] = []
        for fold in range(N_CV_FOLDS):
            test_mask = labels == fold
            train, test = df.loc[~test_mask], df.loc[test_mask]
            try:
                fit, year_cols = fit_gam(train, smooth_cols)
                test_year = test["year_fe"].astype(str).to_numpy()
                exog = np.column_stack(
                    [np.ones(len(test))]
                    + [(test_year == c.replace("year_", "", 1)).astype(float) for c in year_cols]
                )
                if smooth_cols:
                    lo = train[smooth_cols].min().to_numpy(dtype=float)
                    hi = train[smooth_cols].max().to_numpy(dtype=float)
                    xs = np.clip(test[smooth_cols].to_numpy(dtype=float), lo, hi)
                    pred = fit.predict(exog=exog, exog_smooth=xs)
                else:
                    pred = fit.predict(exog)
            except Exception as exc:
                print(f"    {model_name} fold {fold}: failed ({exc})")
                continue
            pred = np.clip(np.asarray(pred, dtype=float), 1e-6, 1 - 1e-6)
            y_true = test["waste_positive"].to_numpy(dtype=float)
            y_all.append(y_true)
            p_all.append(pred)
            rows.append(
                {
                    "model": model_name,
                    "fold": int(fold),
                    "n_train": int(len(train)),
                    "n_test": int(len(test)),
                    "n_test_positive": int(y_true.sum()),
                    "brier": float(brier_score_loss(y_true, pred)),
                    "log_loss": float(log_loss(y_true, pred, labels=[0.0, 1.0])),
                }
            )
        if len(y_all) == N_CV_FOLDS:
            y_cat, p_cat = np.concatenate(y_all), np.concatenate(p_all)
            rows.append(
                {
                    "model": model_name,
                    "fold": -1,
                    "n_train": -1,
                    "n_test": int(len(y_cat)),
                    "n_test_positive": int(y_cat.sum()),
                    "brier": float(brier_score_loss(y_cat, p_cat)),
                    "log_loss": float(log_loss(y_cat, p_cat, labels=[0.0, 1.0])),
                }
            )
    return pd.DataFrame(rows)


def configure_paths(
    pop_raster: Path | None = None,
    output_dir: Path | None = None,
    pop_label: str | None = None,
    pop_short: str | None = None,
    thesis_name: str | None = None,
) -> None:
    """Set module-level I/O paths (used by CLI / variant wrappers)."""
    global OUTPUT_DIR, TABLE_DIR, POP_RASTER, POP_LABEL, POP_SHORT, THESIS_NAME
    if output_dir is not None:
        OUTPUT_DIR = Path(output_dir)
        TABLE_DIR = OUTPUT_DIR / "thesis_table"
    if pop_raster is not None:
        POP_RASTER = Path(pop_raster)
    if pop_label is not None:
        POP_LABEL = pop_label
    if pop_short is not None:
        POP_SHORT = pop_short
    if thesis_name is not None:
        THESIS_NAME = thesis_name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Population-adjusted signed-distance GAMs (panorama unit)"
    )
    p.add_argument(
        "--pop-raster",
        type=Path,
        default=None,
        help="WorldPop GeoTIFF (default: unconstrained ken_ppp_2020)",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for CSVs / thesis_table (default: pop_adjusted/worldpop_2020/)",
    )
    p.add_argument(
        "--pop-label",
        type=str,
        default=None,
        help="Long label for logs / summary population_note",
    )
    p.add_argument(
        "--pop-short",
        type=str,
        default=None,
        help="Short label for thesis table 'Population data' row",
    )
    p.add_argument(
        "--thesis-name",
        type=str,
        default=None,
        help="Thesis CSV filename (default: pop_adjusted_gam_worldpop_2020.csv)",
    )
    p.add_argument(
        "--residuals-only",
        action="store_true",
        help=(
            "Fit MDP on existing analysis frame (or rebuild frame) and write "
            "panorama residual CSV only; skip bootstrap / CV / thesis table."
        ),
    )
    return p.parse_args(argv)


def run_residuals_only() -> Path:
    """Fit MDP and write panorama residual CSV (for excess-occurrence map)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frame_path = OUTPUT_DIR / "Nairobi_pop_adjusted_gam_frame.csv"
    if frame_path.exists():
        print(f"Loading existing analysis frame: {frame_path}")
        df = pd.read_csv(frame_path)
        for col in ("waste_positive", "year", "year_fe"):
            if col not in df.columns:
                raise ValueError(f"Frame missing required column: {col}")
        df["year_fe"] = df["year_fe"].astype(str)
        df["waste_positive"] = df["waste_positive"].astype(int)
    else:
        print("No saved frame; rebuilding analysis frame...")
        df = prepare_analysis_frame()
        df.to_csv(frame_path, index=False)
        print(f"Wrote {frame_path}")

    print(
        f"  n={len(df):,} | waste+={int(df['waste_positive'].sum()):,} | "
        f"year_fe={sorted(df['year_fe'].unique().tolist())}"
    )
    print("  Fitting MDP (s(distance) + s(log1p pop) + year)...")
    res_mdp, _ = fit_mdp(df)
    resid = mdp_residual_frame(df, res_mdp)
    resid_path = OUTPUT_DIR / "Nairobi_pop_adjusted_mdp_residuals.csv"
    resid.to_csv(resid_path, index=False)
    print(
        f"  Residuals: mean response={resid['resid_response'].mean():.4f} | "
        f"mean |Pearson|={resid['resid_pearson'].abs().mean():.3f} | "
        f"P(waste+) mean pred={resid['pred_prob'].mean():.4f}"
    )
    print(f"Wrote {resid_path}")
    return resid_path


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    configure_paths(
        pop_raster=args.pop_raster,
        output_dir=args.output_dir,
        pop_label=args.pop_label,
        pop_short=args.pop_short,
        thesis_name=args.thesis_name,
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Population raster: {POP_RASTER}")

    if args.residuals_only:
        print("Residuals-only mode (MDP panorama residuals for mapping)...")
        run_residuals_only()
        return

    print("Population-adjusted signed-distance GAMs (panorama unit)...")

    df = prepare_analysis_frame()
    print(
        f"  n={len(df):,} | waste+={int(df['waste_positive'].sum()):,} | "
        f"year_fe={sorted(df['year_fe'].unique().tolist())}"
    )

    frame_path = OUTPUT_DIR / "Nairobi_pop_adjusted_gam_frame.csv"
    df.to_csv(frame_path, index=False)

    print("\n  Fitting M0 (year only)...")
    res_m0, _ = fit_m0(df)
    print("  Fitting MP (s(log1p pop) + year)...")
    res_mp, _ = fit_mp(df)
    print("  Fitting MD (s(distance) + year) [S4 specification]...")
    res_md, _ = fit_md(df)
    print("  Fitting MDP (s(distance) + s(log1p pop) + year)...")
    res_mdp, year_cols_mdp = fit_mdp(df)

    print("  Writing MDP panorama residuals for excess-occurrence map...")
    resid = mdp_residual_frame(df, res_mdp)
    resid_path = OUTPUT_DIR / "Nairobi_pop_adjusted_mdp_residuals.csv"
    resid.to_csv(resid_path, index=False)
    print(f"  Wrote {resid_path}")

    metrics = pd.DataFrame(
        [
            _model_metrics(res_m0, "M0", len(df)),
            _model_metrics(res_mp, "MP", len(df)),
            _model_metrics(res_md, "MD", len(df)),
            _model_metrics(res_mdp, "MDP", len(df)),
        ]
    )

    lrt_rows = [
        likelihood_ratio_test(res_mdp, res_mp, "MP_vs_MDP"),
        likelihood_ratio_test(res_mdp, res_md, "MD_vs_MDP"),
        likelihood_ratio_test(res_md, res_m0, "M0_vs_MD"),
        likelihood_ratio_test(res_mp, res_m0, "M0_vs_MP"),
    ]
    lrt_df = pd.DataFrame(lrt_rows)

    central = lrt_df.loc[lrt_df["comparison"] == "MP_vs_MDP"].iloc[0]
    distance_remains = bool(
        central["p_value"] < 0.05 or central["delta_aic_nested_minus_full"] > 2
    )
    conclusion = (
        "After accounting for local population density and panorama capture year, "
        "signed distance to urban-poor settlement still explained variation in "
        "waste-positive probability (MP vs MDP)."
        if distance_remains
        else "After population and year adjustment, evidence that signed distance "
        "adds information beyond population was weaker; interpret cautiously."
    )
    print(
        f"\n  Central test MP vs MDP: LR={central['lr_stat']:.2f}, "
        f"df={central['df_diff']:.1f}, p={central['p_value']:.3e}, "
        f"ΔAIC={central['delta_aic_nested_minus_full']:.1f}"
    )
    print(f"  Conclusion: {conclusion}")

    print("\n  Concurvity diagnostics...")
    conc = concurvity_diagnostics(df)
    print(
        f"  Spearman(dist, log1p pop)={conc.iloc[0]['spearman_signed_distance_vs_log1p_pop']:.3f} | "
        f"concurvity max(dist|pop)={conc.iloc[0]['concurvity_max_distance_given_pop']:.3f}"
    )

    print("\n  Residual Moran's I (MDP)...")
    moran = residual_moran(df, res_mdp)
    print(
        f"  Moran's I={moran['moran_i']:.4f}, p_sim={moran['moran_p_sim']:.4f} "
        f"(k={MORAN_K})"
    )

    # The distance curve under MDPS is compared in 7_spatial_field_sensitivity.py.
    if moran["meaningful_residual_spatial_structure"]:
        print("\n  Fitting MDPS (MDP + spatial thin-plate field)...")
        res_mdps, _, _ = fit_mdps(df)
        metrics = pd.concat(
            [metrics, pd.DataFrame([_model_metrics(res_mdps, "MDPS", len(df))])],
            ignore_index=True,
        )
        lrt_df = pd.concat(
            [lrt_df, pd.DataFrame([likelihood_ratio_test(res_mdps, res_mdp, "MDP_vs_MDPS")])],
            ignore_index=True,
        )
    else:
        print("  Residual spatial structure weak; skipping MDPS.")

    print("\n  Adjusted prediction curves from MDP...")
    curve_d, curve_p, elasticity = standardised_curves(df, res_mdp, year_cols_mdp)

    print("\n  Spatially blocked 5-fold CV (Brier / log-loss)...")
    cv = spatial_blocked_cv(df)

    # Summary + thesis table
    mdp_met = metrics.loc[metrics["model"] == "MDP"].iloc[0]
    mp_met = metrics.loc[metrics["model"] == "MP"].iloc[0]
    md_met = metrics.loc[metrics["model"] == "MD"].iloc[0]
    pop_vs_mdp = lrt_df.loc[lrt_df["comparison"] == "MD_vs_MDP"].iloc[0]

    summary = {
        "role": "population_adjusted_signed_distance_robustness",
        "population_raster": POP_RASTER.name,
        "population_note": (
            f"{POP_LABEL}; not matched to panorama capture year"
        ),
        "n_panoids": int(len(df)),
        "n_waste_positive": int(df["waste_positive"].sum()),
        "n_year_levels": int(df["year_fe"].nunique()),
        "year_levels": "|".join(sorted(df["year_fe"].unique().astype(str))),
        "aic_M0": float(metrics.loc[metrics["model"] == "M0", "aic"].iloc[0]),
        "aic_MP": float(mp_met["aic"]),
        "aic_MD": float(md_met["aic"]),
        "aic_MDP": float(mdp_met["aic"]),
        "delta_aic_MP_minus_MDP": float(central["delta_aic_nested_minus_full"]),
        "lrt_MP_vs_MDP_stat": float(central["lr_stat"]),
        "lrt_MP_vs_MDP_df": float(central["df_diff"]),
        "lrt_MP_vs_MDP_p": float(central["p_value"]),
        "delta_aic_MD_minus_MDP": float(pop_vs_mdp["delta_aic_nested_minus_full"]),
        "lrt_MD_vs_MDP_stat": float(pop_vs_mdp["lr_stat"]),
        "lrt_MD_vs_MDP_p": float(pop_vs_mdp["p_value"]),
        "pseudo_r2_MDP": float(mdp_met["pseudo_r2_mcfadden"]),
        "deviance_explained_MDP": float(mdp_met["deviance_explained"]),
        "distance_remains_after_pop_year": int(distance_remains),
        "spearman_dist_logpop": float(
            conc.iloc[0]["spearman_signed_distance_vs_log1p_pop"]
        ),
        "concurvity_max_dist_given_pop": float(
            conc.iloc[0]["concurvity_max_distance_given_pop"]
        ),
        **elasticity,
        "moran_i_mdp_resid": moran["moran_i"],
        "moran_p_mdp_resid": moran["moran_p_sim"],
        "unit": "panorama",
        "central_test": "MP vs MDP",
        "conclusion": conclusion,
    }
    if "MDPS" in metrics["model"].values:
        summary["aic_MDPS"] = float(
            metrics.loc[metrics["model"] == "MDPS", "aic"].iloc[0]
        )

    outputs = {
        "model_metrics": metrics,
        "lrt": lrt_df,
        "concurvity": conc,
        "moran": pd.DataFrame([moran]),
        "curve_distance": curve_d,
        "curve_population": curve_p,
        "spatial_cv": cv,
        "summary": pd.DataFrame([summary]),
    }
    print(f"\nWrote {frame_path}\nWrote {resid_path}")
    for name, table in outputs.items():
        path = OUTPUT_DIR / f"Nairobi_pop_adjusted_{name}.csv"
        table.to_csv(path, index=False)
        print(f"Wrote {path}")

    thesis = pd.DataFrame(
        [
            ("Role", "Population-adjusted signed-distance robustness", ""),
            ("Population data", POP_SHORT, ""),
            ("Panoramas in GAM", f"{summary['n_panoids']:,}", ""),
            ("Waste-positive panoramas", f"{summary['n_waste_positive']:,}", ""),
            ("Year FE levels", summary["year_levels"], ""),
            ("M0", "logit(p)=α+year", ""),
            ("MP", "logit(p)=α+s(log1p(pop_density))+year", ""),
            ("MD", "logit(p)=α+s(signed_distance)+year", "same as primary S4"),
            (
                "MDP",
                "logit(p)=α+s(signed_distance)+s(log1p(pop_density))+year",
                "",
            ),
            ("Central test", "MP vs MDP", ""),
            ("LRT (MP vs MDP)", f"{central['lr_stat']:.2f}", f"df={central['df_diff']:.1f}"),
            ("LRT p-value (MP vs MDP)", f"{central['p_value']:.3e}", ""),
            ("ΔAIC (MP − MDP)", f"{central['delta_aic_nested_minus_full']:.1f}", ""),
            (
                "McFadden pseudo-R² (MDP)",
                f"{mdp_met['pseudo_r2_mcfadden']:.4f}"
                if np.isfinite(mdp_met["pseudo_r2_mcfadden"])
                else "",
                "",
            ),
            (
                "ΔAIC (MD − MDP) [pop adds?]",
                f"{pop_vs_mdp['delta_aic_nested_minus_full']:.1f}",
                "",
            ),
            (
                "Spearman(distance, log1p pop)",
                f"{summary['spearman_dist_logpop']:.3f}",
                "",
            ),
            (
                "Concurvity max (distance | pop)",
                f"{summary['concurvity_max_dist_given_pop']:.3f}",
                "",
            ),
            (
                "Moran's I (MDP Pearson resid.)",
                f"{moran['moran_i']:.4f}",
                f"p={moran['moran_p_sim']:.4f}",
            ),
            (
                "Population elasticity (1,000–70,000 /km²)",
                f"{elasticity['pop_elasticity']:.2f}",
                f"{BLOCK_BOOT_M / 1000:g} km block 95% CI "
                f"{elasticity['pop_elasticity_ci_low']:.2f}–{elasticity['pop_elasticity_ci_high']:.2f}",
            ),
            (
                "Distance remains after pop+year?",
                "Yes" if distance_remains else "Weaker / check",
                "",
            ),
            ("Interpretation", conclusion, ""),
        ],
        columns=["Variable", "Value", "Unit"],
    )
    thesis_path = TABLE_DIR / THESIS_NAME
    thesis.to_csv(thesis_path, index=False)
    print(f"Wrote {thesis_path}")


if __name__ == "__main__":
    main()
