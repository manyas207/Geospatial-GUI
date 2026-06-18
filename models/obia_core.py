"""
OBIA Proof-of-Concept
=====================
Pipeline: load -> SLIC -> features -> label -> CV -> classify -> export

Install:
    pip install numpy pandas rasterio geopandas scikit-image scikit-learn
"""

import os

import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd
from rasterio import features as rio_features
from rasterio.features import shapes
from rasterio.transform import rowcol
from shapely.geometry import shape
from joblib import Parallel, delayed
from skimage.feature import graycomatrix, graycoprops
from skimage.segmentation import slic
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GroupKFold, cross_val_predict
from datetime import datetime
from pathlib import Path

# CLI defaults — set OBIA_RASTER_PATH, OBIA_SAMPLES_PATH, OBIA_OUT_DIR in .env or pass args.
def _env_path(name: str) -> str | None:
    value = (os.environ.get(name) or "").strip()
    return value or None


RASTER = _env_path("OBIA_RASTER_PATH")
SAMPLES = _env_path("OBIA_SAMPLES_PATH")
OUT_DIR = _env_path("OBIA_OUT_DIR") or "obia_output"
CLASS_FIELD = "macroclass"
ROI_ID_FIELD = "roi_id"
CLASS_FIELD_ALIASES = (
    "macroclass",
    "macro_class",
    "class",
    "class_id",
    "Class",
    "CLASS",
    "classid",
    "landcover",
    "land_cover",
    "lc_class",
)
ROI_FIELD_ALIASES = (
    "roi_id",
    "ROI_ID",
    "roi",
    "ROI",
    "id",
    "ID",
    "polygon_id",
    "poly_id",
    "fid",
    "FID",
)

# Segmentation (set RUN_SEGMENT_SWEEP=True to find a better n_segments first)
N_SEGMENTS = 500000
COMPACTNESS = 5
SIGMA = .5
RUN_SEGMENT_SWEEP = False
SWEEP_VALUES = [50000, 100000, 200000, 300000, 500000]

# HLS L30 default band order (when band_count >= 7):
# 1=coastal, 2=blue, 3=green, 4=red, 5=nir, 6=swir1, 7=swir2
RED_BAND = 4
NIR_BAND = 5
GREEN_BAND = 3
BLUE_BAND = 2
SWIR1_BAND = 6
SWIR2_BAND = 7
MIN_OBIA_BANDS = 1

# GLCM texture (helps separate built-up from smooth snow/soil)
ENABLE_GLCM = True
GLCM_LEVELS = 32
GLCM_DISTANCES = [1]
GLCM_ANGLES = [0, np.pi / 4, np.pi / 2, 3 * np.pi / 4]
GLCM_PROPS = ["contrast", "dissimilarity", "homogeneity", "energy", "correlation", "ASM"]
GLCM_TEXTURE_BANDS = [RED_BAND, SWIR1_BAND]   # bands averaged for texture image
GLCM_SUBSAMPLE = 4       # higher = faster (2 or 4 for large scenes)
MIN_GLCM_PIXELS = 16
GLCM_N_JOBS = -1

# Keep segments where >= this fraction of ROI pixels agree on one class (0 = any touch)
MIN_CLASS_FRACTION = float(os.environ.get("OBIA_MIN_CLASS_FRACTION", "0"))

# Evaluation
CV_FOLDS = 5
HOLDOUT_FRAC = 0.2
RANDOM_STATE = 42
# ─────────────────────────────────────────────────────────────────────


def log(msg):
    print(f"[{msg}]")


def band_layout(band_count: int) -> dict[str, int | None]:
    """Map logical band roles to 1-based band indices for the raster band count."""
    if band_count < 1:
        return {k: None for k in ("blue", "green", "red", "nir", "swir1", "swir2")}

    if band_count >= 7:
        return {
            "blue": 2,
            "green": 3,
            "red": 4,
            "nir": 5,
            "swir1": 6,
            "swir2": 7,
        }

    if band_count == 6:
        return {
            "blue": 1,
            "green": 2,
            "red": 3,
            "nir": 4,
            "swir1": 5,
            "swir2": 6,
        }

    if band_count == 5:
        return {
            "blue": 1,
            "green": 2,
            "red": 3,
            "nir": 4,
            "swir1": 5,
            "swir2": None,
        }

    if band_count == 4:
        return {
            "blue": 1,
            "green": 2,
            "red": 3,
            "nir": 4,
            "swir1": None,
            "swir2": None,
        }

    if band_count == 3:
        # Common 3-band stack: red, green, NIR (e.g. Landsat B4, B3, B5).
        return {
            "blue": None,
            "green": 2,
            "red": 1,
            "nir": 3,
            "swir1": None,
            "swir2": None,
        }

    if band_count == 2:
        return {
            "blue": None,
            "green": None,
            "red": 1,
            "nir": 2,
            "swir1": None,
            "swir2": None,
        }

    # Single band — spectral stats only; no index roles assigned.
    return {role: None for role in ("blue", "green", "red", "nir", "swir1", "swir2")}


def _band_mean_series(gdf: pd.DataFrame, band: int | None, *, raw: bool = False) -> pd.Series | None:
    if band is None:
        return None
    prefix = "raw_b" if raw else "b"
    col = f"{prefix}{band}_mean"
    if col not in gdf.columns:
        return None
    return gdf[col]


def _read_samples(samples_path: str, raster_crs) -> gpd.GeoDataFrame:
    samples = gpd.read_file(samples_path)
    if samples.crs is None:
        if raster_crs is None:
            raise ValueError(
                "Training shapefile has no CRS (.prj missing). "
                "Re-export with a projection or include the .prj file in your upload."
            )
        samples = samples.set_crs(raster_crs)
    elif raster_crs is not None:
        samples = samples.to_crs(raster_crs)
    return _prepare_training_samples(samples)


def _resolve_column(
    frame: pd.DataFrame,
    preferred: str,
    aliases: tuple[str, ...],
) -> str | None:
    if preferred in frame.columns:
        return preferred
    lower_map = {str(col).lower(): col for col in frame.columns}
    for alias in aliases:
        hit = lower_map.get(alias.lower())
        if hit is not None:
            return str(hit)
    return None


def _prepare_training_samples(samples: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Normalize class / ROI columns expected by the OBIA labeling step."""
    samples = samples.copy()
    columns = ", ".join(str(col) for col in samples.columns)

    class_col = _resolve_column(samples, CLASS_FIELD, CLASS_FIELD_ALIASES)
    if class_col is None:
        raise ValueError(
            "Training shapefile needs a class column (e.g. macroclass). "
            f"Found columns: {columns}"
        )
    if class_col != CLASS_FIELD:
        samples[CLASS_FIELD] = samples[class_col]

    roi_col = _resolve_column(samples, ROI_ID_FIELD, ROI_FIELD_ALIASES)
    if roi_col is None:
        log(
            "   Training shapefile has no roi_id column — assigning one id per polygon"
        )
        samples[ROI_ID_FIELD] = np.arange(1, len(samples) + 1, dtype=np.int64)
    elif roi_col != ROI_ID_FIELD:
        samples[ROI_ID_FIELD] = samples[roi_col]

    if not pd.api.types.is_numeric_dtype(samples[CLASS_FIELD]):
        codes, _ = pd.factorize(samples[CLASS_FIELD])
        samples[CLASS_FIELD] = codes + 1

    return samples


def load_raster(path):
    with rasterio.open(path) as src:
        data = src.read().astype(np.float32)
        return data, src.meta.copy(), src.transform, src.crs, src.nodata


def normalize_bands(data, nodata):
    out = data.copy()
    for i in range(out.shape[0]):
        band = out[i]
        valid = band[band != nodata] if nodata is not None else band.ravel()
        lo, hi = np.percentile(valid, [2, 98])
        out[i] = np.clip((band - lo) / (hi - lo + 1e-9), 0, 1)
    return out


def run_slic(img, n_segments):
    labels = slic(
        img,
        n_segments=n_segments,
        compactness=COMPACTNESS,
        sigma=SIGMA,
        start_label=1,
        channel_axis=-1,
        enforce_connectivity=True,
    )
    return labels.astype(np.int32)


def polygonize_labels(labels, transform, crs):
    polys = [
        {"segment_id": int(v), "geometry": shape(g)}
        for g, v in shapes(labels, mask=labels > 0, transform=transform)
    ]
    return gpd.GeoDataFrame(polys, crs=crs)


def spectral_features(gdf, labels, data, nodata):
    band_count = data.shape[0]
    flat_labels = labels.ravel()

    for b in range(band_count):
        flat_band = data[b].ravel()
        valid = flat_labels > 0
        if nodata is not None:
            valid &= flat_band != nodata

        df = pd.DataFrame({
            "segment_id": flat_labels[valid],
            "val": flat_band[valid],
        })
        agg = df.groupby("segment_id").agg(
            mean=("val", "mean"),
            std=("val", "std"),
            median=("val", "median"),
        )
        agg["std"] = agg["std"].fillna(0)
        gdf = gdf.merge(
            agg.rename(columns={
                "mean": f"b{b + 1}_mean",
                "std": f"b{b + 1}_std",
                "median": f"b{b + 1}_median",
            }),
            on="segment_id",
            how="left",
        )

    feature_cols = [
        f"b{b}_{s}"
        for b in range(1, band_count + 1)
        for s in ("mean", "std", "median")
    ]
    return gdf, feature_cols


def shape_features(gdf):
    gdf = gdf.copy()
    gdf["area"] = gdf.geometry.area
    gdf["perimeter"] = gdf.geometry.length
    gdf["compactness"] = 4 * np.pi * gdf["area"] / (gdf["perimeter"] ** 2 + 1e-9)
    bounds = gdf.geometry.bounds
    width = bounds["maxx"] - bounds["minx"]
    height = bounds["maxy"] - bounds["miny"]
    gdf["elongation"] = np.maximum(width, height) / (np.minimum(width, height) + 1e-9)
    return gdf, ["area", "perimeter", "compactness", "elongation"]


def raw_spectral_features(gdf, labels, raw_data, nodata):
    """Per-segment means on raw reflectance (better for snow/soil indices)."""
    band_count = raw_data.shape[0]
    flat_labels = labels.ravel()
    cols = []

    for b in range(band_count):
        flat_band = raw_data[b].ravel()
        valid = flat_labels > 0
        if nodata is not None:
            valid &= flat_band != nodata

        df = pd.DataFrame({
            "segment_id": flat_labels[valid],
            "val": flat_band[valid],
        })
        agg = df.groupby("segment_id")["val"].mean().rename(f"raw_b{b + 1}_mean")
        gdf = gdf.merge(agg, on="segment_id", how="left")
        cols.append(f"raw_b{b + 1}_mean")

    return gdf, cols


def index_features(gdf, band_count: int):
    """Spectral indices — only computed when the required bands exist."""
    gdf = gdf.copy()
    layout = band_layout(band_count)
    index_cols: list[str] = []

    red = _band_mean_series(gdf, layout["red"])
    nir = _band_mean_series(gdf, layout["nir"])
    green = _band_mean_series(gdf, layout["green"])
    blue = _band_mean_series(gdf, layout["blue"])
    swir1 = _band_mean_series(gdf, layout["swir1"])
    swir2 = _band_mean_series(gdf, layout["swir2"])

    raw_red = _band_mean_series(gdf, layout["red"], raw=True)
    raw_nir = _band_mean_series(gdf, layout["nir"], raw=True)
    raw_green = _band_mean_series(gdf, layout["green"], raw=True)
    raw_blue = _band_mean_series(gdf, layout["blue"], raw=True)
    raw_swir1 = _band_mean_series(gdf, layout["swir1"], raw=True)
    raw_swir2 = _band_mean_series(gdf, layout["swir2"], raw=True)

    if red is not None and nir is not None:
        gdf["ndvi"] = (nir - red) / (nir + red + 1e-9)
        index_cols.append("ndvi")
    if green is not None and nir is not None:
        gdf["ndwi"] = (green - nir) / (green + nir + 1e-9)
        index_cols.append("ndwi")
    if red is not None and nir is not None:
        gdf["nir_red_ratio"] = nir / (red + 1e-9)
        index_cols.append("nir_red_ratio")

    if raw_green is not None and raw_swir1 is not None:
        gdf["ndsi"] = (raw_green - raw_swir1) / (raw_green + raw_swir1 + 1e-9)
        index_cols.append("ndsi")

    if all(s is not None for s in (raw_swir1, raw_red, raw_nir, raw_blue)):
        gdf["bsi"] = (
            (raw_swir1 + raw_red) - (raw_nir + raw_blue)
        ) / (raw_swir1 + raw_red + raw_nir + raw_blue + 1e-9)
        index_cols.append("bsi")

    if all(s is not None for s in (raw_blue, raw_green, raw_red)):
        gdf["brightness"] = (raw_blue + raw_green + raw_red) / 3.0
        index_cols.append("brightness")

    if raw_swir1 is not None and raw_swir2 is not None:
        gdf["swir1_swir2_ratio"] = raw_swir1 / (raw_swir2 + 1e-9)
        index_cols.append("swir1_swir2_ratio")
    if raw_nir is not None and raw_swir1 is not None:
        gdf["nir_swir1_ratio"] = raw_nir / (raw_swir1 + 1e-9)
        index_cols.append("nir_swir1_ratio")
    if raw_green is not None and raw_swir1 is not None:
        gdf["green_swir1_ratio"] = raw_green / (raw_swir1 + 1e-9)
        index_cols.append("green_swir1_ratio")

    return gdf, index_cols


def texture_band_indices(band_count: int) -> list[int]:
    """0-based band indices to average for GLCM texture (falls back for small stacks)."""
    layout = band_layout(band_count)
    preferred = [layout["red"], layout["swir1"], layout["nir"], layout["green"]]
    indices: list[int] = []
    for band in preferred:
        if band is not None and band <= band_count:
            zero_idx = band - 1
            if zero_idx not in indices:
                indices.append(zero_idx)
        if len(indices) >= 2:
            break
    if not indices:
        indices = list(range(min(2, band_count)))
    return indices


def _segment_glcm(seg_id, labels_work, gray_q):
    mask = labels_work == seg_id
    if mask.sum() < MIN_GLCM_PIXELS:
        return seg_id, {p: np.nan for p in GLCM_PROPS}

    rows, cols = np.where(mask)
    patch = gray_q[rows.min():rows.max() + 1, cols.min():cols.max() + 1]
    try:
        glcm = graycomatrix(
            patch,
            distances=GLCM_DISTANCES,
            angles=GLCM_ANGLES,
            levels=GLCM_LEVELS,
            symmetric=True,
            normed=True,
        )
        return seg_id, {
            p: float(graycoprops(glcm, p).mean()) for p in GLCM_PROPS
        }
    except ValueError:
        return seg_id, {p: np.nan for p in GLCM_PROPS}


def glcm_features(gdf, labels, gray):
    gray_q = np.clip(
        (gray * (GLCM_LEVELS - 1)).round(), 0, GLCM_LEVELS - 1
    ).astype(np.uint8)

    if GLCM_SUBSAMPLE > 1:
        gray_q = gray_q[::GLCM_SUBSAMPLE, ::GLCM_SUBSAMPLE]
        labels_work = labels[::GLCM_SUBSAMPLE, ::GLCM_SUBSAMPLE]
    else:
        labels_work = labels

    seg_ids = gdf["segment_id"].tolist()
    log(f"   Computing GLCM for {len(seg_ids)} segments (subsample={GLCM_SUBSAMPLE})")
    results = Parallel(n_jobs=GLCM_N_JOBS)(
        delayed(_segment_glcm)(seg_id, labels_work, gray_q) for seg_id in seg_ids
    )

    rows = [{"segment_id": seg_id, **props} for seg_id, props in results]
    glcm_df = pd.DataFrame(rows).rename(
        columns={p: f"glcm_{p}" for p in GLCM_PROPS}
    )
    gdf = gdf.merge(glcm_df, on="segment_id", how="left")
    glcm_cols = [f"glcm_{p}" for p in GLCM_PROPS]
    for col in glcm_cols:
        gdf[col] = gdf[col].fillna(gdf[col].median())
    return gdf, glcm_cols


def print_feature_importance(clf, feature_cols, top_n=15):
    importances = pd.Series(clf.feature_importances_, index=feature_cols)
    top = importances.sort_values(ascending=False).head(top_n)
    log("Top feature importances:")
    for name, score in top.items():
        print(f"   {name}: {score:.4f}")


def _pixel_buffer_distance(transform) -> float:
    """~half a raster pixel in map units — helps tiny ROIs and points rasterize."""
    return max(abs(transform.a), abs(transform.e), 1e-12) * 0.51


def _expand_training_geometries(samples: gpd.GeoDataFrame, transform) -> gpd.GeoDataFrame:
    """Buffer points and pixel-sized polygons so they survive rasterization."""
    buffer_dist = _pixel_buffer_distance(transform)
    tiny_area = (buffer_dist * 2) ** 2

    def expand(geom):
        if geom is None or geom.is_empty:
            return geom
        if geom.geom_type == "Point":
            return geom.buffer(buffer_dist)
        if geom.geom_type in ("Polygon", "MultiPolygon") and geom.area <= tiny_area:
            return geom.buffer(buffer_dist)
        return geom

    out = samples.copy()
    out["geometry"] = out.geometry.apply(expand)
    return out


def _representative_point(geom):
    if geom is None or geom.is_empty:
        return None
    if geom.geom_type == "Point":
        return geom
    return geom.representative_point()


def _vote_from_sample_points(
    samples: gpd.GeoDataFrame,
    labels: np.ndarray,
    transform,
    class_field: str,
    roi_field: str,
) -> pd.DataFrame:
    """Label the segment under each training point/centroid (pixel-sample friendly)."""
    rows: list[dict] = []
    height, width = labels.shape

    for _, sample in samples.iterrows():
        pt = _representative_point(sample.geometry)
        if pt is None:
            continue
        try:
            row_idx, col_idx = rowcol(transform, pt.x, pt.y)
        except Exception:
            continue
        if not (0 <= row_idx < height and 0 <= col_idx < width):
            continue
        seg_id = int(labels[row_idx, col_idx])
        if seg_id <= 0:
            continue
        rows.append(
            {
                "segment_id": seg_id,
                class_field: int(sample[class_field]),
                "_roi_code": int(sample["_roi_code"]),
            }
        )

    return pd.DataFrame(rows)


def label_segments(gdf, labels, samples, transform, class_field, roi_field):
    samples = samples.copy()
    roi_codes, roi_labels = pd.factorize(samples[roi_field])
    samples["_roi_code"] = roi_codes + 1
    samples_for_raster = _expand_training_geometries(samples, transform)

    raster_kwargs = dict(
        out_shape=labels.shape,
        transform=transform,
        fill=0,
        dtype="int32",
        all_touched=True,
    )
    class_raster = rio_features.rasterize(
        (
            (geom, int(val))
            for geom, val in zip(samples_for_raster.geometry, samples_for_raster[class_field])
        ),
        **raster_kwargs,
    )
    roi_raster = rio_features.rasterize(
        (
            (geom, int(val))
            for geom, val in zip(samples_for_raster.geometry, samples_for_raster["_roi_code"])
        ),
        **raster_kwargs,
    )
    code_to_roi = {i + 1: label for i, label in enumerate(roi_labels)}

    flat_seg = labels.ravel()
    flat_class = class_raster.ravel()
    flat_roi = roi_raster.ravel()
    mask = (flat_seg > 0) & (flat_class > 0)

    vote = pd.DataFrame({
        "segment_id": flat_seg[mask],
        class_field: flat_class[mask],
        "_roi_code": flat_roi[mask],
    })
    point_vote = _vote_from_sample_points(
        samples, labels, transform, class_field, roi_field
    )
    if not point_vote.empty:
        vote = pd.concat([vote, point_vote], ignore_index=True)

    if vote.empty:
        gdf[class_field] = np.nan
        gdf[roi_field] = np.nan
        gdf["class_fraction"] = np.nan
        return gdf, gdf.iloc[0:0], 0

    class_counts = (
        vote.groupby(["segment_id", class_field])
        .size()
        .reset_index(name="n")
    )
    totals = vote.groupby("segment_id").size().rename("total")
    best_class = (
        class_counts.sort_values("n", ascending=False)
        .groupby("segment_id")
        .first()
        .reset_index()
    )
    best_class = best_class.merge(totals, on="segment_id")
    best_class["class_fraction"] = best_class["n"] / best_class["total"]

    roi_counts = (
        vote.groupby(["segment_id", "_roi_code"])
        .size()
        .reset_index(name="n")
    )
    best_roi = (
        roi_counts.sort_values("n", ascending=False)
        .groupby("segment_id")
        .first()
        .reset_index()[["segment_id", "_roi_code"]]
    )
    best_roi[roi_field] = best_roi["_roi_code"].map(code_to_roi)
    best_roi = best_roi.drop(columns=["_roi_code"])

    gdf = gdf.merge(
        best_class[["segment_id", class_field, "class_fraction"]],
        on="segment_id",
        how="left",
    )
    gdf = gdf.merge(best_roi, on="segment_id", how="left")

    labeled = gdf.dropna(subset=[class_field, roi_field]).copy()
    labeled = labeled[labeled["class_fraction"] >= MIN_CLASS_FRACTION]
    candidates = gdf.dropna(subset=[class_field, roi_field])
    return gdf, labeled, len(candidates)


def _bounds_overlap_raster_samples(raster_bounds, sample_bounds) -> bool:
    """raster_bounds: west,south,east,north; sample_bounds: minx,miny,maxx,maxy."""
    rw, rs, re, rn = raster_bounds
    sminx, sminy, smaxx, smaxy = sample_bounds
    return not (smaxx < rw or sminx > re or smaxy < rs or sminy > rn)


def _explain_no_labeled_segments(
    samples: gpd.GeoDataFrame,
    labels: np.ndarray,
    transform,
    class_field: str,
    *,
    candidates: int,
) -> str:
    from rasterio.transform import array_bounds

    height, width = labels.shape
    raster_bounds = array_bounds(height, width, transform)
    sample_bounds = samples.total_bounds
    class_raster = rio_features.rasterize(
        ((geom, int(val)) for geom, val in zip(samples.geometry, samples[class_field])),
        out_shape=labels.shape,
        transform=transform,
        fill=0,
        dtype="int32",
        all_touched=True,
    )
    roi_pixels = int((class_raster > 0).sum())
    overlap_pixels = int(((labels > 0) & (class_raster > 0)).sum())

    if not _bounds_overlap_raster_samples(raster_bounds, sample_bounds):
        return (
            "No labeled segments: training polygons and raster do not cover the same area. "
            f"Raster bounds (W,S,E,N): ({raster_bounds[0]:.4f}, {raster_bounds[1]:.4f}, "
            f"{raster_bounds[2]:.4f}, {raster_bounds[3]:.4f}). "
            f"Training bounds: ({sample_bounds[0]:.4f}, {sample_bounds[1]:.4f}, "
            f"{sample_bounds[2]:.4f}, {sample_bounds[3]:.4f}). "
            "Register a city that matches your data extent, or use rasters/ROIs from that city."
        )
    if roi_pixels == 0:
        return (
            "No labeled segments: training polygons rasterize to zero pixels. "
            "Check that ROIs are polygons (not points), include a .prj file, and use the correct CRS."
        )
    if overlap_pixels == 0:
        return (
            "No labeled segments: raster and training polygons overlap in extent but share no pixels. "
            "This usually means a CRS mismatch — re-export the shapefile with the same projection as the GeoTIFF."
        )
    if candidates > 0:
        return (
            f"No labeled segments: {candidates} segment(s) touched training areas but none met "
            f"MIN_CLASS_FRACTION={MIN_CLASS_FRACTION} (segments were too mixed). "
            "Try lowering OBIA_MIN_CLASS_FRACTION (e.g. 0.3) or OBIA_N_SEGMENTS in .env."
        )
    return (
        "No labeled segments: training areas did not match any image segments. "
        "Try more training polygons, larger ROIs, or OBIA_N_SEGMENTS in .env."
    )


def sweep_n_segments(img, samples, transform, crs, values):
    log("Segment sweep (SLIC + labeling only)")
    rows = []
    for n in values:
        labels = run_slic(img, n)
        gdf = polygonize_labels(labels, transform, crs)
        _, labeled, _ = label_segments(
            gdf, labels, samples, transform, CLASS_FIELD, ROI_ID_FIELD
        )
        per_class = labeled[CLASS_FIELD].value_counts().to_dict() if len(labeled) else {}
        rows.append({
            "n_segments": n,
            "segments": len(gdf),
            "labeled": len(labeled),
            "per_class": per_class,
        })
        log(f"   n={n}: {len(labeled)} labeled / {len(gdf)} segments  {per_class}")

    best = max(rows, key=lambda r: r["labeled"])
    log(f"Suggested N_SEGMENTS = {best['n_segments']} ({best['labeled']} labeled)")
    return rows


def split_holdout(labeled, frac, seed):
    rng = np.random.default_rng(seed)
    roi_ids = labeled[ROI_ID_FIELD].unique()
    n_holdout = max(1, int(len(roi_ids) * frac))
    holdout_rois = set(rng.choice(roi_ids, size=n_holdout, replace=False))
    train = labeled[~labeled[ROI_ID_FIELD].isin(holdout_rois)].copy()
    val = labeled[labeled[ROI_ID_FIELD].isin(holdout_rois)].copy()
    return train, val, holdout_rois


def prepare_xy(frame, feature_cols):
    X = frame[feature_cols].fillna(0).values
    y = frame[CLASS_FIELD].values
    return X, y


def write_classified_raster(path, array, meta):
    """Write raster; if the target file is locked, use a timestamped name."""
    path = Path(path)
    meta = meta.copy()
    meta.update(count=1, dtype="int32", nodata=0)

    candidates = [path, path.with_name(f"{path.stem}_{datetime.now():%Y%m%d_%H%M%S}{path.suffix}")]
    last_error = None

    for candidate in candidates:
        try:
            with rasterio.open(str(candidate), "w", **meta) as dst:
                dst.write(array, 1)
            if candidate != path:
                log(f"   {path.name} is locked (close QGIS/Explorer); wrote {candidate.name}")
            return str(candidate)
        except Exception as exc:
            last_error = exc
            if "Permission denied" not in str(exc) and "locked" not in str(exc).lower():
                raise

    raise last_error


def run_obia_pipeline(
    raster_path: str,
    samples_path: str | None = None,
    out_dir: str | None = None,
    *,
    n_segments: int | None = None,
    run_segment_sweep: bool = False,
) -> dict:
    """Run full OBIA pipeline; returns stats dict and captured log text via caller."""
    raster_path = str(raster_path)
    out_dir = str(out_dir or OUT_DIR)
    samples_path = samples_path or SAMPLES or _env_path("OBIA_SAMPLES_PATH")
    n_segments = n_segments if n_segments is not None else N_SEGMENTS

    if not samples_path:
        raise ValueError(
            "Training shapefile path is required. Upload .shp/.shx/.dbf with the raster "
            "or set OBIA_SAMPLES_PATH in .env."
        )

    Path(out_dir).mkdir(parents=True, exist_ok=True)

    log("1. Loading raster")
    raw_data, meta, transform, crs, nodata = load_raster(raster_path)
    band_count = int(raw_data.shape[0])
    if band_count < MIN_OBIA_BANDS:
        raise ValueError(f"Raster must have at least {MIN_OBIA_BANDS} band(s); found {band_count}.")

    data = normalize_bands(raw_data, nodata)
    img = np.transpose(data, (1, 2, 0))

    samples = _read_samples(samples_path, crs)
    log(f"   Raster bands: {band_count} (HLS layout used when >= 7 bands)")

    if run_segment_sweep:
        sweep_n_segments(img, samples, transform, crs, SWEEP_VALUES)
        log("Sweep done. Set N_SEGMENTS and RUN_SEGMENT_SWEEP=False, then rerun.")
        return {"stats": {"mode": "segment_sweep"}}

    log(f"2. SLIC segmentation (n_segments={n_segments})")
    labels = run_slic(img, n_segments)
    log(f"   {len(np.unique(labels))} segments created")

    log("3. Polygonizing")
    gdf = polygonize_labels(labels, transform, crs)
    log(f"   {len(gdf)} polygons")

    log("4. Spectral + shape + index + texture features")
    gdf, spectral_cols = spectral_features(gdf, labels, data, nodata)
    gdf, raw_cols = raw_spectral_features(gdf, labels, raw_data, nodata)
    gdf, shape_cols = shape_features(gdf)
    gdf, index_cols = index_features(gdf, band_count)
    feature_cols = spectral_cols + raw_cols + shape_cols + index_cols

    if ENABLE_GLCM and band_count >= 1:
        tex_bands = texture_band_indices(band_count)
        gray = np.mean(data[tex_bands], axis=0)
        gdf, glcm_cols = glcm_features(gdf, labels, gray)
        feature_cols += glcm_cols
    else:
        log("   GLCM disabled (set ENABLE_GLCM=True to enable)")

    log("5. Labeling segments from training ROIs")
    log(
        f"   Labeling mode: pixel/point-friendly "
        f"(MIN_CLASS_FRACTION={MIN_CLASS_FRACTION})"
    )
    gdf, labeled, candidate_count = label_segments(
        gdf, labels, samples, transform, CLASS_FIELD, ROI_ID_FIELD
    )
    log(
        f"   {len(labeled)} labeled segments "
        f"(of {len(gdf)} total, min class fraction {MIN_CLASS_FRACTION})"
    )
    if len(labeled) == 0:
        raise ValueError(
            _explain_no_labeled_segments(
                samples,
                labels,
                transform,
                CLASS_FIELD,
                candidates=candidate_count,
            )
        )

    log("6. ROI-grouped cross-validation")
    X, y = prepare_xy(labeled, feature_cols)
    groups = labeled[ROI_ID_FIELD].values
    n_splits = min(CV_FOLDS, len(np.unique(groups)))
    if n_splits < 2:
        log("   Skipped (need at least 2 ROIs for grouped CV)")
    else:
        clf_cv = RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
        cv_preds = cross_val_predict(
            clf_cv, X, y, cv=GroupKFold(n_splits=n_splits), groups=groups
        )
        print("Grouped CV report (by ROI):")
        print(classification_report(y, cv_preds, zero_division=0))

    log("7. Hold-out validation by ROI")
    train_df, val_df, holdout_rois = split_holdout(labeled, HOLDOUT_FRAC, RANDOM_STATE)
    log(f"   Train: {len(train_df)} segments, Hold-out: {len(val_df)} segments "
        f"({len(holdout_rois)} ROIs)")

    X_train, y_train = prepare_xy(train_df, feature_cols)
    X_val, y_val = prepare_xy(val_df, feature_cols)

    clf = RandomForestClassifier(
        n_estimators=200,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    if len(val_df) > 0:
        val_preds = clf.predict(X_val)
        print("Hold-out validation report:")
        print(classification_report(y_val, val_preds, zero_division=0))
        print("Confusion matrix (rows=actual, cols=predicted):")
        print(confusion_matrix(y_val, val_preds))

        val_export = val_df.copy()
        val_export["predicted"] = val_preds
        val_export["correct"] = val_export[CLASS_FIELD] == val_export["predicted"]
        val_path = str(Path(out_dir) / "validation.gpkg")
        val_export.to_file(val_path, driver="GPKG")
        log(f"   Validation -> {val_path} (open in QGIS, style by correct)")

    log("8. Retrain on all labeled segments and classify scene")
    X_all_labeled, y_all = prepare_xy(labeled, feature_cols)
    clf.fit(X_all_labeled, y_all)
    print_feature_importance(clf, feature_cols)

    X_scene = gdf[feature_cols].fillna(0).values
    gdf["predicted"] = clf.predict(X_scene)

    log("9. Exporting")
    out_vec = str(Path(out_dir) / "classified.gpkg")
    gdf.to_file(out_vec, driver="GPKG")
    log(f"   Vector -> {out_vec}")

    classified_arr = rio_features.rasterize(
        ((g, int(v)) for g, v in zip(gdf.geometry, gdf["predicted"])),
        out_shape=(meta["height"], meta["width"]),
        transform=transform,
        fill=0,
        dtype="int32",
    )
    out_ras = write_classified_raster(Path(out_dir) / "classified.tif", classified_arr, meta)
    log(f"   Raster -> {out_ras}")

    log("Done. Check validation.gpkg in QGIS for honest accuracy.")

    class_counts = labeled[CLASS_FIELD].value_counts().to_dict()
    return {
        "stats": {
            "band_count": band_count,
            "total_segments": int(len(gdf)),
            "labeled_segments": int(len(labeled)),
            "class_counts": {str(k): int(v) for k, v in class_counts.items()},
            "holdout_segments": int(len(val_df)),
            "classified_gpkg": out_vec,
            "classified_tif": out_ras,
        },
    }


def run_obia_segmentation_only(
    raster_path: str,
    out_dir: str | None = None,
    *,
    n_segments: int = 50_000,
) -> dict:
    """SLIC segmentation without training shapefile (no classification)."""
    out_dir = str(out_dir or OUT_DIR)
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    log("1. Loading raster")
    raw_data, meta, transform, crs, nodata = load_raster(raster_path)
    data = normalize_bands(raw_data, nodata)
    img = np.transpose(data, (1, 2, 0))

    log(f"2. SLIC segmentation (n_segments={n_segments})")
    labels = run_slic(img, n_segments)
    unique = np.unique(labels)
    segment_count = int(len(unique[unique > 0]))

    log("3. Polygonizing")
    gdf = polygonize_labels(labels, transform, crs)
    out_vec = str(Path(out_dir) / "segments.gpkg")
    gdf.to_file(out_vec, driver="GPKG")
    log(f"   Vector -> {out_vec}")
    log("No training shapefile found — classification skipped.")

    return {
        "stats": {
            "total_segments": segment_count,
            "polygons": int(len(gdf)),
            "segments_gpkg": out_vec,
            "mode": "segmentation_only",
        },
    }


def main():
    raster = RASTER or _env_path("OBIA_RASTER_PATH")
    samples = SAMPLES or _env_path("OBIA_SAMPLES_PATH")
    out_dir = OUT_DIR or _env_path("OBIA_OUT_DIR") or "obia_output"
    if not raster or not samples:
        raise SystemExit(
            "Set OBIA_RASTER_PATH and OBIA_SAMPLES_PATH in .env (or pass paths to run_obia_pipeline)."
        )
    run_obia_pipeline(raster, samples, out_dir)


if __name__ == "__main__":
    main()
