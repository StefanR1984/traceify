"""Traceify – Raster- und PDF-Zeichnungen in CAD- und CNC-Dateien umwandeln."""
__version__ = "0.6.0"

from .api import (BatchItem, ai_settings, batch_convert, convert_file, load_settings,
                  open_file, save_settings)
from .core.model import Arc, Circle, Drawing, Line, Polyline, Text
from .core.ocr import OcrSettings
from .core.pipeline import ConvertResult, ConvertSettings, convert
from .core.preprocess import PreprocessSettings
from .core.vectorize import (MODE_CENTERLINE, MODE_OUTLINE,
                             VectorizeSettings)
from .export import GcodeSettings, export

__all__ = ['Arc', 'BatchItem', 'Circle', 'ConvertResult', 'ConvertSettings', 'Drawing', 'GcodeSettings', 'Line', 'MODE_CENTERLINE', 'MODE_OUTLINE', 'OcrSettings', 'Polyline', 'PreprocessSettings', 'Text', 'VectorizeSettings', 'ai_settings', 'batch_convert', 'convert', 'convert_file', 'export', 'load_settings', 'open_file', 'save_settings']
