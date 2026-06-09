"""
LST Extraction & Validation — HLS L30 & Landsat 8/9 Collection 2
================================================================
Pipeline aligned with the QGIS LST workflow
(https://lunanotes.io/summary/a-comprehensive-guide-to-land-surface-temperature-extraction-in-qgis):

  1. Load satellite bands (B10 thermal, B04 red, B05 NIR)
  2. TOA radiance — skipped for HLS L30 (B10 ships as brightness temperature)
  3. Brightness temperature (product-specific scaling → K for LST formula)
  4. NDVI from red & NIR
  5. Proportion of vegetation (Pv)
  6. Land surface emissivity (LSE)
  7. Land surface temperature (LST)
  8. Export GeoTIFF + validation boxplot

Product auto-detection from filenames (or set scene["product"]):
  HLS L30:        B04/B05 x 0.0001  |  B10 x 0.01 °C  |  nodata -9999
  Landsat C2 L2:  SR x 0.0000275 - 0.2  |  ST_B10 x 0.00341802 + 149 K  |  nodata 0
  (LC08, LC09, and other Collection 2 L2SP stacks use the same Landsat scaling.)

Usage:
  pip install rasterio numpy matplotlib scipy
  python LST_Version1.py
  Options:
  -h, --help            show this help message and exit
  --debug               Print band metadata before processing
  --no-show             Save plot without opening a window
  --no-tif              Skip GeoTIFF export
  --output-dir OUTPUT_DIR
                        Directory for plot and GeoTIFF outputs
  --ndvi-min NDVI_MIN   Pv formula NDVI soil end
  --ndvi-max NDVI_MAX   Pv formula NDVI veg end
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from scipy import stats


# =====================================================================
# CONFIG
# =====================================================================

# NDVI limits for proportion of vegetation (Pv)
NDVI_MIN = 0.172
NDVI_MAX = 0.619

SCENES = [
    {
        "label": "Retrieval 1 (2015-06-02)",
        "b10": r"C:\Users\BCC\Desktop\Landsat_Data\Celina\2015\LC08_L2SP_027037_20150602_20200909_02_T1_ST_B10.TIF",
        "b04": r"C:\Users\BCC\Desktop\Landsat_Data\Celina\2015\LC08_L2SP_027037_20150602_20200909_02_T1_SR_B4.TIF",
        "b05": r"C:\Users\BCC\Desktop\Landsat_Data\Celina\2015\LC08_L2SP_027037_20150602_20200909_02_T1_SR_B5.TIF",
        # Historical North Texas air temperatures (June 2, 2015: 10:30 AM - 1:30 PM)
        "ref_temps_C": [31.4, 34.2, 36.8, 38.5],
    },
    {
        "label": "Retrieval 2 (2025-08-24)",
        "b10": r"C:\Users\BCC\Desktop\Landsat_Data\Celina\2025\LC09_L2SP_027037_20250824_20250825_02_T1_ST_B10.TIF",
        "b04": r"C:\Users\BCC\Desktop\Landsat_Data\Celina\2025\LC09_L2SP_027037_20250824_20250825_02_T1_SR_B4.TIF",
        "b05": r"C:\Users\BCC\Desktop\Landsat_Data\Celina\2025\LC09_L2SP_027037_20250824_20250825_02_T1_SR_B5.TIF",
        # Historical North Texas summer air temperatures (August 24, 2025: 10:30 AM - 1:30 PM)
        "ref_temps_C": [39.1, 41.8, 44.5, 46.2],
    },
]

LST_MIN_C = 15.0
LST_MAX_C = 60.0
HLS_NODATA = -9999

# Landsat 8/9 Collection 2 Level-2 (L2SP) — USGS scaling
LANDSAT_NODATA = 0
LANDSAT_ST_SCALE = 0.00341802
LANDSAT_ST_OFFSET_K = 149.0
LANDSAT_SR_SCALE = 0.0000275
LANDSAT_SR_OFFSET = -0.2

PRODUCT_HLS = "hls"
PRODUCT_LANDSAT_C2 = "landsat_c2"

LAMBDA_UM = 10.895
RHO_UM_K = 14387.7

OUTPUT_DIR = Path(__file__).resolve().parent
OUTPUT_PLOT = OUTPUT_DIR / "LST_Accuracy_Offset_Boxplot.png"
# Max pixels drawn per box (full stats still use all pixels)
BOXPLOT_SAMPLE = 10_000
RNG = np.random.default_rng(42)


@dataclass
class PipelineResult:
    label: str
    lst_2d: np.ma.MaskedArray
    lst_valid_1d: np.ndarray
    ref_mean_C: float
    ref_temps_C: list[float]
    median_lst_C: float
    mean_lst_C: float
    geotiff_path: Path | None = None


# =====================================================================
# PRODUCT DETECTION & SCALING
# =====================================================================


def detect_product(cfg: dict) -> str:
    """Detect HLS vs Landsat C2 from scene config or band filenames."""
    explicit = cfg.get("product")
    if explicit in (PRODUCT_HLS, PRODUCT_LANDSAT_C2):
        return explicit

    names = " ".join(os.path.basename(cfg[k]) for k in ("b10", "b04", "b05")).upper()
    if "HLS." in names or "HLS.L30" in names:
        return PRODUCT_HLS
    if any(
        token in names
        for token in ("LC08_", "LC09_", "LC07_", "ST_B10", "ST_B11", "_SR_B4", "_SR_B5")
    ):
        return PRODUCT_LANDSAT_C2

    raise ValueError(
        f"Cannot detect product for scene '{cfg.get('label', '?')}'. "
        f"Filenames: {names}. Set 'product': '{PRODUCT_HLS}' or '{PRODUCT_LANDSAT_C2}' in SCENES."
    )


def product_label(product: str) -> str:
    if product == PRODUCT_HLS:
        return "HLS L30"
    return "Landsat 8/9 Collection 2 L2SP"


def default_nodata(product: str) -> int:
    return HLS_NODATA if product == PRODUCT_HLS else LANDSAT_NODATA


def dn_to_brightness_temperature(
    b10_dn: np.ma.MaskedArray, product: str
) -> tuple[np.ma.MaskedArray, np.ma.MaskedArray]:
    """Return brightness temperature in °C and K (Landsat ST scaled as BT for Step 7)."""
    if product == PRODUCT_HLS:
        bt_celsius = b10_dn * 0.01
        bt_kelvin = bt_celsius + 273.15
    else:
        bt_kelvin = b10_dn * LANDSAT_ST_SCALE + LANDSAT_ST_OFFSET_K
        bt_celsius = bt_kelvin - 273.15
    return bt_celsius, bt_kelvin


def dn_to_reflectance(
    red_dn: np.ma.MaskedArray, nir_dn: np.ma.MaskedArray, product: str
) -> tuple[np.ma.MaskedArray, np.ma.MaskedArray]:
    if product == PRODUCT_HLS:
        red = red_dn * 0.0001
        nir = nir_dn * 0.0001
    else:
        red = red_dn * LANDSAT_SR_SCALE + LANDSAT_SR_OFFSET
        nir = nir_dn * LANDSAT_SR_SCALE + LANDSAT_SR_OFFSET
    return red, nir


# =====================================================================
# I/O & CHECKS
# =====================================================================


def assert_same_grid(paths: list[str]) -> dict[str, Any]:
    """Ensure B10/B04/B05 share shape, CRS, and transform."""
    with rasterio.open(paths[0]) as ref:
        meta = {
            "shape": ref.shape,
            "transform": ref.transform,
            "crs": ref.crs,
            "profile": ref.profile.copy(),
        }
    for path in paths[1:]:
        with rasterio.open(path) as src:
            if (src.shape, src.transform, src.crs) != (
                meta["shape"],
                meta["transform"],
                meta["crs"],
            ):
                raise ValueError(f"Grid mismatch — bands are not aligned:\n  {path}")
    return meta


def read_band_dn(path: str, nodata: int = HLS_NODATA, verbose: bool = True) -> np.ma.MaskedArray:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    with rasterio.open(path) as src:
        raw = src.read(1, masked=True).astype("float64")
        nd = src.nodata if src.nodata is not None else nodata
        if raw.mask is np.ma.nomask:
            raw = np.ma.MaskedArray(raw, mask=np.zeros(raw.shape, dtype=bool))
        if nd is not None:
            raw = np.ma.masked_where((raw == nd) | raw.mask, raw)
        if verbose:
            valid = raw.compressed()
            vmin = valid.min() if valid.size else float("nan")
            vmax = valid.max() if valid.size else float("nan")
            print(
                f"    [{os.path.basename(path)}]  nodata={nd}  "
                f"DN range: {vmin:.0f} – {vmax:.0f}"
            )
    return raw


def diagnose_band(path: str) -> None:
    with rasterio.open(path) as src:
        print(
            f"  {os.path.basename(path)}: dtype={src.dtypes[0]}  "
            f"nodata={src.nodata}  crs={src.crs}  shape={src.shape}"
        )


def write_lst_geotiff(lst_2d: np.ma.MaskedArray, profile: dict, out_path: Path) -> None:
    out_profile = profile.copy()
    out_profile.update(dtype="float32", count=1, nodata=-9999.0, compress="deflate")
    data = lst_2d.filled(-9999.0).astype("float32")
    with rasterio.open(out_path, "w", **out_profile) as dst:
        dst.write(data, 1)
        dst.set_band_description(1, "LST (°C)")
    print(f"  GeoTIFF -> {out_path}")


# =====================================================================
# LST PIPELINE
# =====================================================================


def run_lst_pipeline(
    cfg: dict,
    *,
    export_tif: bool = True,
    verbose: bool = True,
    output_dir: Path | None = None,
) -> PipelineResult:
    label = cfg["label"]
    paths = [cfg["b10"], cfg["b04"], cfg["b05"]]
    product = detect_product(cfg)
    nodata_default = default_nodata(product)

    print(f"\n{'=' * 62}")
    print(f"  {label}")
    print(f"  Product: {product_label(product)}")
    print(f"{'=' * 62}")

    # Step 1 — Load & verify grids
    print("  Step 1: Load satellite bands")
    grid_meta = assert_same_grid(paths)

    # Step 2 — TOA radiance (skipped for pre-scaled thermal products)
    if product == PRODUCT_HLS:
        print(
            "  Step 2: TOA spectral radiance — skipped (HLS L30 B10 = brightness temp, "
            "not raw radiance + MTL)"
        )
    else:
        print(
            "  Step 2: TOA spectral radiance — skipped (Landsat L2 ST_B10 pre-scaled; not radiance + MTL)"
        )

    # Step 3 — Brightness temperature
    print("  Step 3: Brightness temperature")
    b10_dn = read_band_dn(cfg["b10"], nodata=nodata_default, verbose=verbose)

    # Step 4 — NDVI (B04 red, B05 NIR); align masks across all bands
    print("  Step 4: NDVI (B04 red, B05 NIR)")
    red_dn = read_band_dn(cfg["b04"], nodata=nodata_default, verbose=verbose)
    nir_dn = read_band_dn(cfg["b05"], nodata=nodata_default, verbose=verbose)
    shared_mask = b10_dn.mask | red_dn.mask | nir_dn.mask
    b10_dn = np.ma.masked_where(shared_mask, b10_dn)
    red_dn = np.ma.masked_where(shared_mask, red_dn)
    nir_dn = np.ma.masked_where(shared_mask, nir_dn)

    bt_celsius, bt_kelvin = dn_to_brightness_temperature(b10_dn, product)
    valid_bt = bt_celsius.compressed()
    sane = valid_bt[(valid_bt >= 5.0) & (valid_bt <= 70.0)]
    if sane.size == 0:
        raise ValueError(
            f"No valid brightness-temperature pixels in 5–70 °C for {product_label(product)}. "
            "Run with --debug or check band paths/scaling."
        )
    print(
        f"         BT  n={len(sane):,}  "
        f"min={sane.min():.1f}C  mean={sane.mean():.1f}C  max={sane.max():.1f}C"
    )

    red, nir = dn_to_reflectance(red_dn, nir_dn, product)
    denom = nir + red
    denom = np.ma.masked_where(np.abs(denom) < 1e-9, denom)
    ndvi = np.ma.clip((nir - red) / denom, -1.0, 1.0)
    print(
        f"         NDVI  min={ndvi.min():.3f}  mean={ndvi.mean():.3f}  max={ndvi.max():.3f}"
    )

    # Step 5 — Proportion of vegetation (QGIS tutorial NDVI min/max)
    print(f"  Step 5: Proportion of vegetation (NDVI {NDVI_MIN} – {NDVI_MAX})")
    pv = np.ma.clip(((ndvi - NDVI_MIN) / (NDVI_MAX - NDVI_MIN)) ** 2, 0.0, 1.0)
    print(f"         Pv  mean={pv.mean():.3f}")

    # Step 6 — Land surface emissivity
    print("  Step 6: Land surface emissivity")
    lse = 0.004 * pv + 0.986
    print(f"         LSE  mean={lse.mean():.4f}")

    # Step 7 — LST
    print("  Step 7: Land surface temperature")
    lst_kelvin = bt_kelvin / (1.0 + (LAMBDA_UM * bt_kelvin / RHO_UM_K) * np.ma.log(lse))
    lst_celsius = lst_kelvin - 273.15

    lst_mask = (lst_celsius < LST_MIN_C) | (lst_celsius > LST_MAX_C) | lst_celsius.mask
    lst_2d = np.ma.masked_where(lst_mask, lst_celsius)

    flat = lst_2d.compressed()
    print(
        f"         LST  n={flat.size:,}  "
        f"min={flat.min():.1f}°C  mean={flat.mean():.1f}°C  max={flat.max():.1f}°C"
    )
    if flat.size == 0:
        raise ValueError(
            f"No pixels in LST range {LST_MIN_C}–{LST_MAX_C} °C. "
            "Check paths or widen LST_MIN_C / LST_MAX_C."
        )

    # Step 8 — Export
    geotiff_path = None
    if export_tif:
        print("  Step 8: Export LST raster (classify in QGIS: Singleband pseudocolor)")
        safe_label = "".join(c if c.isalnum() else "_" for c in label)[:40]
        out_dir = Path(output_dir) if output_dir is not None else OUTPUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        geotiff_path = out_dir / f"LST_{safe_label}.tif"
        write_lst_geotiff(lst_2d, grid_meta["profile"], geotiff_path)

    ref_temps = [float(t) for t in cfg["ref_temps_C"]]
    ref_mean = float(np.mean(ref_temps))

    return PipelineResult(
        label=label,
        lst_2d=lst_2d,
        lst_valid_1d=flat,
        ref_mean_C=ref_mean,
        ref_temps_C=ref_temps,
        median_lst_C=float(np.median(flat)),
        mean_lst_C=float(np.mean(flat)),
        geotiff_path=geotiff_path,
    )


# =====================================================================
# VALIDATION
# =====================================================================


def compute_offsets(lst_vals: np.ndarray, ref_mean_C: float) -> np.ndarray:
    """Pixel offsets vs the mean reference temperature (no pixel×ref cross-product)."""
    return lst_vals - ref_mean_C


def offset_summary(offsets: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(offsets.mean()),
        "std": float(offsets.std()),
        "median": float(np.median(offsets)),
        "rmse": float(np.sqrt(np.mean(offsets**2))),
        "mae": float(np.mean(np.abs(offsets))),
    }


def mean_ci_95(offsets: np.ndarray) -> tuple[float, float]:
    n = len(offsets)
    if n < 2:
        m = offsets.mean() if n else 0.0
        return m, m
    ci = stats.t.interval(0.95, df=n - 1, loc=offsets.mean(), scale=stats.sem(offsets))
    return float(ci[0]), float(ci[1])


# =====================================================================
# VISUALIZATION
# =====================================================================


def _sample_offsets(offs: np.ndarray, max_n: int = BOXPLOT_SAMPLE) -> np.ndarray:
    """Thin huge pixel arrays so box whiskers stay readable."""
    if len(offs) <= max_n:
        return offs
    return RNG.choice(offs, size=max_n, replace=False)


def plot_validation_boxplot(
    results: list[PipelineResult],
    offsets_list: list[np.ndarray],
    output_path: Path,
    *,
    show: bool = True,
) -> None:

    labels_short = [r.label.split("(")[-1].rstrip(")") for r in results]
    palette = ["#4A90D9", "#E07A5F", "#81B29A", "#F2CC8F", "#9B5DE5"]
    colors = [palette[i % len(palette)] for i in range(len(results))]

    plot_data = [_sample_offsets(offs) for offs in offsets_list]

    fig, ax = plt.subplots(figsize=(10, 7))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#fafafa")

    bp = ax.boxplot(
        plot_data,
        tick_labels=labels_short,
        patch_artist=True,
        widths=0.5,
        showfliers=True,
        flierprops=dict(marker="o", markersize=3, alpha=0.25, markerfacecolor="#888"),
        medianprops=dict(color="#1a1a1a", linewidth=2),
        boxprops=dict(linewidth=1.5),
        whiskerprops=dict(linewidth=1.2, color="#444"),
        capprops=dict(linewidth=1.2, color="#444"),
    )
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.65)
        patch.set_edgecolor("#333")

    ax.axhline(0, color="#2d6a4f", linestyle="--", linewidth=1.8, label="Zero offset (perfect match)")
    ax.set_ylabel("Offset: satellite LST - mean reference (C)", fontsize=11)
    ax.set_xlabel("Acquisition date", fontsize=11)
    ax.set_title(
        "LST validation: satellite minus reference temperature\n(HLS L30 & Landsat 8/9 C2)",
        fontsize=13,
        fontweight="bold",
        pad=12,
    )
    ax.yaxis.grid(True, linestyle="-", alpha=0.35)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right", framealpha=0.95)

    # Summary table (below the chart)
    rows = []
    for res, offs in zip(results, offsets_list):
        s = offset_summary(offs)
        rows.append(
            [
                res.label.split("(")[-1].rstrip(")"),
                f"{res.ref_mean_C:.2f}",
                f"{res.median_lst_C:.2f}",
                f"{s['mean']:+.2f}",
                f"{s['median']:+.2f}",
                f"{s['rmse']:.2f}",
                f"{len(offs):,}",
            ]
        )
    col_labels = [
        "Scene",
        "Ref mean (C)",
        "LST median (C)",
        "Bias (C)",
        "Med offset (C)",
        "RMSE (C)",
        "n pixels",
    ]
    tbl = ax.table(
        cellText=rows,
        colLabels=col_labels,
        loc="bottom",
        bbox=[0.0, -0.45, 1.0, 0.30],
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    for (row, col), cell in tbl.get_celld().items():
        if row == 0:
            cell.set_facecolor("#4A90D9")
            cell.set_text_props(fontweight="bold", color="white")
        else:
            cell.set_facecolor("#f0f4f8" if row % 2 == 1 else "white")
            cell.set_text_props(color="#222")
        cell.set_edgecolor("#ccc")

    if any(len(o) > BOXPLOT_SAMPLE for o in offsets_list):
        fig.text(
            0.5,
            0.01,
            f"Boxplot shows up to {BOXPLOT_SAMPLE:,} random pixels per scene; "
            "table stats use all pixels.",
            ha="center",
            fontsize=8,
            color="#666",
        )

    plt.subplots_adjust(bottom=0.38, top=0.90)
    fig.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"\nPlot saved -> {output_path}")
    if show:
        plt.show()
    else:
        plt.close(fig)


# =====================================================================
# MAIN
# =====================================================================


def main() -> None:
    global OUTPUT_DIR, OUTPUT_PLOT, NDVI_MIN, NDVI_MAX

    parser = argparse.ArgumentParser(
        description="LST extraction & validation (HLS L30 and Landsat 8/9 Collection 2)"
    )
    parser.add_argument("--debug", action="store_true", help="Print band metadata before processing")
    parser.add_argument("--no-show", action="store_true", help="Save plot without opening a window")
    parser.add_argument("--no-tif", action="store_true", help="Skip GeoTIFF export")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for plot and GeoTIFF outputs",
    )
    parser.add_argument("--ndvi-min", type=float, default=NDVI_MIN, help="Pv formula NDVI soil end")
    parser.add_argument("--ndvi-max", type=float, default=NDVI_MAX, help="Pv formula NDVI veg end")
    args = parser.parse_args()

    if args.output_dir is not None:
        OUTPUT_DIR = args.output_dir.resolve()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_PLOT = OUTPUT_DIR / "LST_Accuracy_Offset_Boxplot.png"

    NDVI_MIN = args.ndvi_min
    NDVI_MAX = args.ndvi_max

    if args.debug:
        print("--- Band diagnostics ---")
        for scene in SCENES:
            print(scene["label"])
            for key in ("b10", "b04", "b05"):
                diagnose_band(scene[key])

    results: list[PipelineResult] = []
    offsets_list: list[np.ndarray] = []

    for scene in SCENES:
        pr = run_lst_pipeline(scene, export_tif=not args.no_tif, verbose=True)
        results.append(pr)
        offsets_list.append(compute_offsets(pr.lst_valid_1d, pr.ref_mean_C))

    print("\n--- Offset summary (vs mean reference) ---")
    for pr, offs in zip(results, offsets_list):
        s = offset_summary(offs)
        print(f"  {pr.label}")
        print(f"    Reference mean     : {pr.ref_mean_C:.2f} °C  (n={len(pr.ref_temps_C)} readings)")
        print(f"    Scene LST median   : {pr.median_lst_C:.2f} °C")
        print(f"    Median - ref mean  : {pr.median_lst_C - pr.ref_mean_C:+.2f} C")
        for j, t in enumerate(pr.ref_temps_C, 1):
            print(f"      vs ref #{j} ({t:.1f} °C): median offset {pr.median_lst_C - t:+.2f} °C")
        print(
            f"    Pixel bias / RMSE  : {s['mean']:+.2f} / {s['rmse']:.2f} °C  "
            f"(MAE {s['mae']:.2f})"
        )
        ci_lo, ci_hi = mean_ci_95(offs)
        print(
            f"    95% CI on pixel-mean bias: [{ci_lo:.3f}, {ci_hi:.3f}] C "
            f"(optimistic; n={len(offs):,} pixels)"
        )

    plot_validation_boxplot(
        results,
        offsets_list,
        OUTPUT_PLOT,
        show=not args.no_show,
    )


if __name__ == "__main__":
    main()

