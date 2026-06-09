"""
OBIA Proof-of-Concept
=====================
Pipeline: load -> SLIC -> features -> label -> CV -> classify -> export

Install:
    pip install numpy pandas rasterio geopandas scikit-image scikit-learn
"""

import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd
from rasterio import features as rio_features
from rasterio.features import shapes
from shapely.geometry import shape
from joblib import Parallel, delayed
from skimage.feature import graycomatrix, graycoprops
from skimage.segmentation import slic
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GroupKFold, cross_val_predict
from datetime import datetime
from pathlib import Path

# ── EDIT THESE ───────────────────────────────────────────────────────
RASTER   = r"C:\Users\BCC\Desktop\SA_TD_GTD\Teresina\Teresina_2015\HLS.L30.T23MQQ.2015218T125847.v2.0.B_stack_raster.tif"
SAMPLES  = r"C:\Users\BCC\Desktop\SA_TD_GTD\Teresina\Teresina_2015\TD\TD_Teresina_2015.shp"
OUT_DIR  = r"C:\Users\BCC\Desktop\OBIA_poc_Output"
CLASS_FIELD = "macroclass"
ROI_ID_FIELD = "roi_id"

# Segmentation (set RUN_SEGMENT_SWEEP=True to find a better n_segments first)
N_SEGMENTS = 500000
COMPACTNESS = 5
SIGMA = .5
RUN_SEGMENT_SWEEP = False
SWEEP_VALUES = [50000, 100000, 200000, 300000, 500000]

# HLS L30 default band order: 1=coastal, 2=blue, 3=green, 4=red, 5=nir, 6=swir1, 7=swir2
RED_BAND = 4
NIR_BAND = 5
GREEN_BAND = 3
BLUE_BAND = 2
SWIR1_BAND = 6
SWIR2_BAND = 7

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

# Keep segments where >= this fraction of ROI pixels agree on one class
MIN_CLASS_FRACTION = 0.5

# Evaluation
CV_FOLDS = 5
HOLDOUT_FRAC = 0.2
RANDOM_STATE = 42
# ─────────────────────────────────────────────────────────────────────


def log(msg):
    print(f"[{msg}]")


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


def index_features(gdf):
    gdf = gdf.copy()
    red = gdf[f"b{RED_BAND}_mean"]
    nir = gdf[f"b{NIR_BAND}_mean"]
    green = gdf[f"b{GREEN_BAND}_mean"]
    blue = gdf[f"b{BLUE_BAND}_mean"]
    swir1 = gdf[f"b{SWIR1_BAND}_mean"]
    swir2 = gdf[f"b{SWIR2_BAND}_mean"]

    raw_red = gdf[f"raw_b{RED_BAND}_mean"]
    raw_nir = gdf[f"raw_b{NIR_BAND}_mean"]
    raw_green = gdf[f"raw_b{GREEN_BAND}_mean"]
    raw_blue = gdf[f"raw_b{BLUE_BAND}_mean"]
    raw_swir1 = gdf[f"raw_b{SWIR1_BAND}_mean"]
    raw_swir2 = gdf[f"raw_b{SWIR2_BAND}_mean"]

    gdf["ndvi"] = (nir - red) / (nir + red + 1e-9)
    gdf["ndwi"] = (green - nir) / (green + nir + 1e-9)
    gdf["nir_red_ratio"] = nir / (red + 1e-9)

    # Snow / soil / built-up discriminators (raw reflectance)
    gdf["ndsi"] = (raw_green - raw_swir1) / (raw_green + raw_swir1 + 1e-9)
    gdf["bsi"] = (
        (raw_swir1 + raw_red) - (raw_nir + raw_blue)
    ) / (raw_swir1 + raw_red + raw_nir + raw_blue + 1e-9)
    gdf["brightness"] = (raw_blue + raw_green + raw_red) / 3.0
    gdf["swir1_swir2_ratio"] = raw_swir1 / (raw_swir2 + 1e-9)
    gdf["nir_swir1_ratio"] = raw_nir / (raw_swir1 + 1e-9)
    gdf["green_swir1_ratio"] = raw_green / (raw_swir1 + 1e-9)

    return gdf, [
        "ndvi", "ndwi", "nir_red_ratio",
        "ndsi", "bsi", "brightness",
        "swir1_swir2_ratio", "nir_swir1_ratio", "green_swir1_ratio",
    ]


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


def label_segments(gdf, labels, samples, transform, class_field, roi_field):
    samples = samples.copy()
    roi_codes, roi_labels = pd.factorize(samples[roi_field])
    samples["_roi_code"] = roi_codes + 1

    class_raster = rio_features.rasterize(
        ((geom, int(val)) for geom, val in zip(samples.geometry, samples[class_field])),
        out_shape=labels.shape,
        transform=transform,
        fill=0,
        dtype="int32",
    )
    roi_raster = rio_features.rasterize(
        ((geom, int(val)) for geom, val in zip(samples.geometry, samples["_roi_code"])),
        out_shape=labels.shape,
        transform=transform,
        fill=0,
        dtype="int32",
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
    if vote.empty:
        gdf[class_field] = np.nan
        gdf[roi_field] = np.nan
        gdf["class_fraction"] = np.nan
        return gdf, gdf.iloc[0:0]

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
    return gdf, labeled


def sweep_n_segments(img, samples, transform, crs, values):
    log("Segment sweep (SLIC + labeling only)")
    rows = []
    for n in values:
        labels = run_slic(img, n)
        gdf = polygonize_labels(labels, transform, crs)
        _, labeled = label_segments(
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
    samples_path = samples_path or SAMPLES
    n_segments = n_segments if n_segments is not None else N_SEGMENTS

    Path(out_dir).mkdir(parents=True, exist_ok=True)

    log("1. Loading raster")
    raw_data, meta, transform, crs, nodata = load_raster(raster_path)
    data = normalize_bands(raw_data, nodata)
    img = np.transpose(data, (1, 2, 0))

    samples = gpd.read_file(samples_path).to_crs(crs)

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
    gdf, index_cols = index_features(gdf)
    feature_cols = spectral_cols + raw_cols + shape_cols + index_cols

    if ENABLE_GLCM:
        tex_bands = [b - 1 for b in GLCM_TEXTURE_BANDS]
        gray = np.mean(data[tex_bands], axis=0)
        gdf, glcm_cols = glcm_features(gdf, labels, gray)
        feature_cols += glcm_cols
    else:
        log("   GLCM disabled (set ENABLE_GLCM=True to enable)")

    log("5. Labeling segments from training ROIs")
    gdf, labeled = label_segments(
        gdf, labels, samples, transform, CLASS_FIELD, ROI_ID_FIELD
    )
    log(
        f"   {len(labeled)} labeled segments "
        f"(of {len(gdf)} total, min class fraction {MIN_CLASS_FRACTION})"
    )
    if len(labeled) == 0:
        raise ValueError(
            "No labeled segments. Try RUN_SEGMENT_SWEEP=True or lower MIN_CLASS_FRACTION."
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
    run_obia_pipeline(RASTER, SAMPLES, OUT_DIR)


if __name__ == "__main__":
    main()
