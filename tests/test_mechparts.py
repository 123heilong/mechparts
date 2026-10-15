"""mechparts 测试套件。

运行：python -m pytest -q
没有 pytest 也能跑：python tests/test_mechparts.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# 允许在未安装包的情况下直接运行本文件
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mechparts.gear_math import SpurGearGeometry, involute_angle  # noqa: E402
from mechparts.gear_profile import (  # noqa: E402
    _signed_area,
    full_gear_profile,
    tooth_profile_points,
)
from mechparts.flange import FlangeGeometry  # noqa: E402

REL_TOL = 1e-3   # 离散化带来的相对误差上限
CASES = [(12, 1.0), (17, 2.0), (20, 2.0), (20, 5.0), (40, 1.5), (60, 3.0), (100, 1.0)]


def _thickness_at_pitch(geom: SpurGearGeometry, samples: int = 64) -> float:
    """数值测量分度圆齿厚：求齿廓与分度圆的交点角跨度。"""
    pts = tooth_profile_points(geom, samples=samples)
    rp = geom.pitch_radius
    angles = []
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        r0 = math.hypot(x0, y0)
        r1 = math.hypot(x1, y1)
        if (r0 - rp) * (r1 - rp) <= 0 and r0 != r1:
            t = (rp - r0) / (r1 - r0)
            angles.append(math.atan2(y0 + t * (y1 - y0), x0 + t * (x1 - x0)))
    assert len(angles) == 2, f"应与分度圆交于 2 点，实测 {len(angles)} 点"
    return (max(angles) - min(angles)) * rp


# ---------------------------------------------------------------- 渐开线函数
def test_involute_angle_known_values():
    assert math.isclose(involute_angle(0.0), 0.0, abs_tol=1e-12)
    # inv(20 deg) = tan(20deg) - 20deg(rad) = 0.0149044 (标准表值)
    expected = math.tan(math.radians(20)) - math.radians(20)
    assert math.isclose(involute_angle(math.radians(20)), expected, abs_tol=1e-15)
    assert math.isclose(involute_angle(math.radians(20)), 0.014904, abs_tol=1e-6)


# ---------------------------------------------------------------- 尺寸公式
def test_standard_dimension_formulas():
    g = SpurGearGeometry(module=2.0, teeth=20, pressure_angle=20.0, face_width=10.0)
    assert math.isclose(g.pitch_diameter, 40.0)
    assert math.isclose(g.base_diameter, 40.0 * math.cos(math.radians(20)), rel_tol=1e-12)
    assert math.isclose(g.tip_diameter, 44.0)      # d + 2m
    assert math.isclose(g.root_diameter, 35.0)     # d - 2.5m
    assert math.isclose(g.whole_depth, 4.5)        # 2.25m
    assert math.isclose(g.circular_pitch, math.pi * 2.0)
    assert math.isclose(g.tooth_thickness, math.pi)


def test_flank_rotation_formula():
    """齿廓定位角必须是 pi/(2z) - inv(alpha)。"""
    g = SpurGearGeometry(module=2.0, teeth=20, pressure_angle=20.0, face_width=10.0)
    expected = math.pi / (2 * 20) - involute_angle(math.radians(20))
    assert math.isclose(g.flank_rotation, expected, rel_tol=1e-12)


def test_base_diameter_always_smaller_than_pitch():
    for z, m in CASES:
        g = SpurGearGeometry(module=m, teeth=z, pressure_angle=20.0, face_width=10.0)
        assert g.base_diameter < g.pitch_diameter < g.tip_diameter
        assert g.root_diameter < g.pitch_diameter


# ---------------------------------------------------------------- 齿厚（核心）
def test_tooth_thickness_equals_half_pitch():
    """分度圆齿厚必须等于 pi*m/2，这是齿轮最硬的判据。"""
    for z, m in CASES:
        g = SpurGearGeometry(module=m, teeth=z, pressure_angle=20.0, face_width=10.0)
        measured = _thickness_at_pitch(g)
        assert math.isclose(measured, g.tooth_thickness, rel_tol=REL_TOL), (
            f"z={z}, m={m}: 实测齿厚 {measured:.6f} != 理论 {g.tooth_thickness:.6f}"
        )


def test_tooth_thickness_at_arbitrary_pressure_angle():
    """压力角变化时齿厚公式依然成立。"""
    for alpha in (14.5, 20.0, 25.0):
        g = SpurGearGeometry(module=2.0, teeth=24, pressure_angle=alpha, face_width=10.0)
        assert math.isclose(_thickness_at_pitch(g), g.tooth_thickness, rel_tol=REL_TOL)


def test_tip_thickness_positive():
    """齿顶不能变尖：齿顶弧长必须为正。"""
    for z, m in CASES:
        g = SpurGearGeometry(module=m, teeth=z, pressure_angle=20.0, face_width=10.0)
        pts = tooth_profile_points(g, samples=64)
        tip_angles = [
            math.atan2(y, x)
            for x, y in pts
            if math.isclose(math.hypot(x, y), g.tip_radius, rel_tol=1e-6)
        ]
        assert tip_angles, f"z={z}: 未找到齿顶点"
        assert (max(tip_angles) - min(tip_angles)) * g.tip_radius > 0


# ---------------------------------------------------------------- 轮廓几何
def test_profile_radius_bounds():
    """齿廓点必须落在齿根圆与齿顶圆之间。"""
    for z, m in CASES:
        g = SpurGearGeometry(module=m, teeth=z, pressure_angle=20.0, face_width=10.0)
        for x, y in full_gear_profile(g, samples=32):
            r = math.hypot(x, y)
            assert g.root_radius - 1e-6 <= r <= g.tip_radius + 1e-6


def test_single_tooth_tip_spans_less_than_pitch():
    """齿顶圆弧的角跨度必须小于一个齿距角。

    单齿轮廓整体可能跨越略大于一个齿距角（齿根处更宽，甚至包含
    基圆到齿根圆的径向段），但**齿顶**部分绝不能超过齿距角，
    否则相邻齿会在齿顶互相干涉。
    """
    for z, m in CASES:
        g = SpurGearGeometry(module=m, teeth=z, pressure_angle=20.0, face_width=10.0)
        pts = tooth_profile_points(g, samples=48)
        tip_angles = [
            math.atan2(y, x)
            for x, y in pts
            if math.isclose(math.hypot(x, y), g.tip_radius, rel_tol=1e-9)
        ]
        assert tip_angles, f"z={z}: 未找到齿顶点"
        tip_span = max(tip_angles) - min(tip_angles)
        assert tip_span < 2 * math.pi / z, (
            f"z={z}, m={m}: 齿顶跨度 {math.degrees(tip_span):.3f}deg "
            f"超过齿距角 {math.degrees(2*math.pi/z):.3f}deg"
        )


def test_gear_profile_is_counter_clockwise():
    """外轮廓必须逆时针，否则拉伸出的实体法向朝内。"""
    for z, m in CASES:
        g = SpurGearGeometry(module=m, teeth=z, pressure_angle=20.0, face_width=10.0)
        assert _signed_area(full_gear_profile(g, samples=16)) > 0


def test_profile_closes_around_full_circle():
    g = SpurGearGeometry(module=2.0, teeth=20, pressure_angle=20.0, face_width=10.0)
    pts = full_gear_profile(g, samples=16)
    step = 2 * math.pi / g.teeth
    per_tooth = len(pts) // g.teeth
    assert len(pts) % g.teeth == 0, "轮廓点数应能被齿数整除"
    # 相邻齿的同名点应恰好相差一个齿距角
    a0 = math.atan2(pts[0][1], pts[0][0])
    a1 = math.atan2(pts[per_tooth][1], pts[per_tooth][0])
    assert math.isclose((a1 - a0) % (2 * math.pi), step, rel_tol=1e-6)


# ---------------------------------------------------------------- 参数校验
def test_gear_rejects_invalid_parameters():
    for bad in [
        dict(module=0, teeth=20, pressure_angle=20.0, face_width=10.0),
        dict(module=2, teeth=3, pressure_angle=20.0, face_width=10.0),
        dict(module=2, teeth=20, pressure_angle=60.0, face_width=10.0),
        dict(module=2, teeth=20, pressure_angle=20.0, face_width=0),
    ]:
        try:
            SpurGearGeometry(**bad)
        except ValueError:
            continue
        raise AssertionError(f"应当拒绝非法参数 {bad}")


def test_flange_rejects_bolt_hole_overlap():
    # 螺栓孔切进中心孔
    try:
        FlangeGeometry(bolt_circle_diameter=60.0, bolt_hole_diameter=20.0, bore_diameter=60.0)
    except ValueError:
        pass
    else:
        raise AssertionError("应当拒绝切进中心孔的螺栓孔")

    # 螺栓孔超出外缘
    try:
        FlangeGeometry(bolt_circle_diameter=150.0, bolt_hole_diameter=30.0, outer_diameter=160.0)
    except ValueError:
        pass
    else:
        raise AssertionError("应当拒绝超出外缘的螺栓孔")


def test_flange_summary_contains_bolt_info():
    g = FlangeGeometry()
    s = g.summary()
    assert s["螺栓孔数量 n"] == 4
    assert math.isclose(s["螺栓孔中心圆 K"], 125.0)


# ---------------------------------------------------------------- CAD 层（可选）
def test_solid_build_and_volume():
    """需要 build123d。校验实体体积与解析解一致。"""
    try:
        from mechparts.gear_solid import build_spur_gear
        from mechparts.flange import build_flange
    except ImportError:
        print("  [跳过] 未安装 build123d")
        return

    # 法兰：解析解可精确手算
    g = FlangeGeometry()
    part = build_flange(g)
    R, r, rh = g.outer_diameter / 2, g.bore_diameter / 2, g.bolt_hole_diameter / 2
    expect = (math.pi * (R**2 - r**2) - g.bolt_count * math.pi * rh**2) * g.thickness
    assert math.isclose(part.volume, expect, rel_tol=1e-9), (
        f"法兰体积 {part.volume} != 解析解 {expect}"
    )

    # 齿轮：包围盒必须等于齿顶圆直径
    gg = SpurGearGeometry(module=2.0, teeth=20, pressure_angle=20.0, face_width=10.0)
    gear = build_spur_gear(gg, bore_diameter=10.0)
    bb = gear.bounding_box()
    assert math.isclose(bb.max.X, gg.tip_radius, rel_tol=1e-3)
    assert math.isclose(bb.max.Z, gg.face_width, rel_tol=1e-9)
    # 体积应小于同直径实心圆柱（齿槽挖掉了材料）
    solid_cyl = math.pi * gg.tip_radius**2 * gg.face_width
    assert 0.5 * solid_cyl < gear.volume < solid_cyl


def _run_all() -> int:
    funcs = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in funcs:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  FAIL  {name}\n        {type(e).__name__}: {e}")
    print(f"\n{len(funcs) - failed}/{len(funcs)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
