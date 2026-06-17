"""Shared constants for the API and pipelines."""

RASTER_SUFFIXES = frozenset({".tif", ".tiff", ".geotiff", ".gtiff"})
SHAPEFILE_SUFFIXES = frozenset({".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx"})
VECTOR_SUFFIXES = frozenset({".gpkg", ".shp", ".geojson"})
ALLOWED_UPLOAD_SUFFIXES = RASTER_SUFFIXES

TRACT_LAYER = "tracts"
