"""Wahrheits-Prüfstand: Original-DXF als Scan simulieren und gegen das Original messen."""
import ezdxf
import pytest
from ezdxf import units

from traceify.core.model import Line, Text
from traceify.core.truth import _self_check, compare, load_cad, render_scan, scan_scale


def test_selbstprobe():
    _self_check()


def test_einheit_meter_und_bemassung(tmp_path):
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.M
    msp = doc.modelspace()
    msp.add_line((0, 0), (5, 0))
    dim = msp.add_linear_dim(base=(0, 1), p1=(0, 0), p2=(5, 0))
    dim.render()
    p = tmp_path / "plan.dxf"
    doc.saveas(p)
    ents, unit = load_cad(str(p))
    assert unit == pytest.approx(1000.0)
    assert len([e for e in ents if isinstance(e, Line)]) > 1        # Linie + Maßlinien
    assert any(isinstance(e, Text) and "5" in e.text for e in ents)  # Maßtext


def test_lage_im_bild():
    # 5 m Linie bei 1:100 und 254 dpi: 50 mm Papier = 500 px
    sc = render_scan([Line((0, 0), (5000, 0)), Line((0, 0), (0, 1000))], scale_n=100, dpi=254,
                     noise=0, blur=0)
    a = sc.truth[0]
    assert abs(a.p1[0] - a.p2[0]) == pytest.approx(500.0)
    assert sc.gray.min() < 60 and sc.gray.max() == 255


def test_versatz_wird_gemessen():
    sc = render_scan([Line((0, 0), (5000, 0)), Line((0, 0), (0, 3000))], noise=0, blur=0)
    px = 0.5 / sc.mm_per_px                                          # 0,5 mm Papier
    moved = [Line((e.p1[0] + px, e.p1[1] + px), (e.p2[0] + px, e.p2[1] + px)) for e in sc.truth]
    r = compare(sc.truth, moved, sc.gray.shape, sc.mm_per_px, tol_mm=0.3)
    assert r["lage_median_mm"] == pytest.approx(0.5, abs=0.1)
    assert r["genauigkeit"] < 0.2
    r0 = compare(sc.truth, sc.truth, sc.gray.shape, sc.mm_per_px)
    assert r0["trefferquote"] == r0["genauigkeit"] == 1.0


@pytest.mark.parametrize("n", [100, 350])
def test_plotmassstab_wird_erkannt(n):
    # Grundriss in Metern mit ungleichen Räumen; Plot ohne Maßstabsangabe → Maßstab je Plan finden
    cad = [Line((0, 0), (14, 0)), Line((14, 0), (14, 9)), Line((14, 9), (0, 9)), Line((0, 9), (0, 0)),
           Line((5, 0), (5, 9)), Line((5, 4), (14, 4)), Line((9.5, 4), (9.5, 9)), Line((0, 6.2), (5, 6.2))]
    sc = render_scan(cad, scale_n=n, dpi=300, unit_mm=1000.0, noise=0, blur=0)
    ink = ((sc.gray < 160) * 255).astype("uint8")
    found, fit = scan_scale(cad, 1000.0, ink, sc.mm_per_px)
    assert found == n and fit > 0.7
