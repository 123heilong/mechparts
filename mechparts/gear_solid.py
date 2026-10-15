"""把数学层的齿廓变成真正的三维实体（STEP / STL）。

依赖 build123d。齿形的所有计算都在 gear_math / gear_profile 里完成，
这里只做"把点连成面、再拉伸、再挖孔"的工作。
"""

from __future__ import annotations

from pathlib import Path

from .gear_math import SpurGearGeometry
from .gear_profile import full_gear_profile


def build_spur_gear(
    geom: SpurGearGeometry,
    bore_diameter: float = 0.0,
    samples: int = 24,
):
    """按几何参数生成直齿圆柱齿轮实体。

    参数
    ----
    geom : SpurGearGeometry
    bore_diameter : float
        中心孔直径(mm)，0 表示实心齿轮。
    samples : int
        每条渐开线齿廓的离散点数，越大越精确（也越慢）。

    返回
    ----
    build123d 的 Part 对象
    """
    from build123d import (
        BuildLine,
        BuildPart,
        BuildSketch,
        Circle,
        Mode,
        Polyline,
        extrude,
        make_face,
    )

    if bore_diameter < 0:
        raise ValueError(f"中心孔直径不能为负，收到 {bore_diameter}")

    root_radius = geom.root_radius
    if bore_diameter > 0:
        bore_radius = bore_diameter / 2
        if bore_radius >= root_radius:
            raise ValueError(
                f"中心孔半径 {bore_radius:.3f} 不小于齿根圆半径 {root_radius:.3f}，"
                "会切穿轮齿。请减小孔径，或增大模数 / 齿数"
            )

    outline = full_gear_profile(geom, samples=samples)

    with BuildPart() as part:
        with BuildSketch():
            with BuildLine():
                Polyline(*(outline + [outline[0]]))
            make_face()
            if bore_diameter > 0:
                Circle(bore_diameter / 2, mode=Mode.SUBTRACT)
        extrude(amount=geom.face_width)

    return part.part


def export(part, path: str | Path, fmt: str | None = None) -> Path:
    """导出实体为 STEP 或 STL，格式可由扩展名推断。"""
    from build123d import export_step, export_stl

    path = Path(path)
    fmt = (fmt or path.suffix.lstrip(".")).lower()
    path.parent.mkdir(parents=True, exist_ok=True)

    if fmt in ("step", "stp"):
        export_step(part, str(path))
    elif fmt == "stl":
        export_stl(part, str(path))
    else:
        raise ValueError(f"不支持的格式 {fmt!r}，请用 step 或 stl")
    return path
