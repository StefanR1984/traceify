"""Vorlagen für typische Zeichnungsarten (GUI, API, KI)."""
from .core.vectorize import MODE_CENTERLINE, MODE_OUTLINE

PRESETS = {
    "Technische Zeichnung": dict(mode=MODE_CENTERLINE, tolerance=1.5, arcs=True, circles=True,
                                 polylines=False, despeckle=12, ocr=True, smooth=0),
    "Grundriss / Architektur": dict(mode=MODE_CENTERLINE, tolerance=2.0, arcs=True, circles=True,
                                    polylines=False, despeckle=20, ocr=True, smooth=0),
    "Handskizze": dict(mode=MODE_CENTERLINE, tolerance=3.0, arcs=True, circles=True,
                       polylines=False, despeckle=30, ocr=False, smooth=3),
    "Kontur-Polylinien (Karte)": dict(mode=MODE_CENTERLINE, tolerance=1.0, arcs=False,
                                      circles=False, polylines=True, despeckle=15, ocr=False,
                                      smooth=0),
    "Logo / CNC-Umriss": dict(mode=MODE_OUTLINE, tolerance=0.8, arcs=False, circles=True,
                              polylines=False, despeckle=20, ocr=False, smooth=0),
}
