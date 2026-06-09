"""Shared file-type sets and stat keys used by the API, artifacts, and dashboard chat."""

RASTER_SUFFIXES = frozenset({".tif", ".tiff", ".geotiff", ".gtiff"})
SHAPEFILE_SUFFIXES = frozenset({".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx"})
VECTOR_SUFFIXES = frozenset({".gpkg", ".shp", ".geojson"})
ALLOWED_UPLOAD_SUFFIXES = RASTER_SUFFIXES | SHAPEFILE_SUFFIXES

# Merged into API stats for the dashboard; hide from metric cards.
INTERNAL_STAT_KEYS = frozenset({"upload_dir", "primary_raster", "file_count"})
