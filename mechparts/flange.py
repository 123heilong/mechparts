"""法兰参数化建模，含螺栓孔阵列与可选凸台。

螺栓孔按标准（GB/T 9119 等）通常沿螺栓孔中心圆均匀分布，
这里直接用极坐标阵列生成。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FlangeGeometry:
    """法兰几何参数（单位 mm）。

    默认值是一个常见的 DN50 级别法兰量级，实际使用请按标准查表。
    """

    outer_diameter: float = 160.0   # 法兰外径 D
    bore_diameter: float = 60.0     # 中心通孔直径 d
    thickness: float = 20.0         # 法兰厚度 t
    bolt_circle_diameter: float = 125.0  # 螺栓孔中心圆直径 K
    bolt_count: int = 4             # 螺栓孔数量 n
    bolt_hole_diameter: float = 18.0     # 螺栓孔直径
    raised_face_diameter: float = 0.0    # 凸台(密封面)直径，0 表示无凸台
    raised_face_height: float = 0.0      # 凸台高度

    def __post_init__(self) -> None:
        if self.outer_diameter <= 0:
            raise ValueError("法兰外径必须为正")
        if not 0 <= self.bore_diameter < self.outer_diameter:
            raise ValueError(
                f"中心孔直径 {self.bore_diameter} 必须非负且小于外径 {self.outer_diameter}"
            )
        if self.thickness <= 0:
            raise ValueError("法兰厚度必须为正")
        if self.bolt_count < 0:
            raise ValueError("螺栓孔数量不能为负")
        if self.bolt_count > 0:
            if self.bolt_hole_diameter <= 0:
                raise ValueError("螺栓孔数量大于 0 时，孔径必须为正")
            if self.bolt_circle_diameter <= 0:
                raise ValueError("螺栓孔数量大于 0 时，中心圆直径必须为正")

            hole_r = self.bolt_hole_diameter / 2
            bc_r = self.bolt_circle_radius
            # 孔必须完全落在法兰实体上：不碰中心孔、不超出外缘
            if bc_r - hole_r <= self.bore_diameter / 2:
                raise ValueError(
                    f"螺栓孔会切进中心孔：中心圆半径 {bc_r:.2f} - 孔半径 {hole_r:.2f} "
                    f"= {bc_r - hole_r:.2f} <= 中心孔半径 {self.bore_diameter/2:.2f}"
                )
            if bc_r + hole_r >= self.outer_diameter / 2:
                raise ValueError(
                    f"螺栓孔超出法兰外缘：中心圆半径 {bc_r:.2f} + 孔半径 {hole_r:.2f} "
                    f"= {bc_r + hole_r:.2f} >= 外半径 {self.outer_diameter/2:.2f}"
                )
        if self.raised_face_diameter > 0 and self.raised_face_height <= 0:
            raise ValueError("指定了凸台直径，则凸台高度必须为正")
        if self.raised_face_diameter > self.outer_diameter:
            raise ValueError("凸台直径不能大于法兰外径")

    @property
    def bolt_circle_radius(self) -> float:
        return self.bolt_circle_diameter / 2

    def summary(self) -> dict[str, float]:
        d = {
            "法兰外径 D": self.outer_diameter,
            "中心孔直径 d": self.bore_diameter,
            "法兰厚度 t": self.thickness,
            "螺栓孔中心圆 K": self.bolt_circle_diameter,
            "螺栓孔数量 n": self.bolt_count,
            "螺栓孔直径": self.bolt_hole_diameter,
        }
        if self.raised_face_diameter > 0:
            d["凸台直径"] = self.raised_face_diameter
            d["凸台高度"] = self.raised_face_height
        return d


def build_flange(geom: FlangeGeometry):
    """生成法兰实体。"""
    from build123d import (
        Axis,
        BuildPart,
        BuildSketch,
        Circle,
        Mode,
        PolarLocations,
        extrude,
    )

    with BuildPart() as part:
        with BuildSketch():
            Circle(geom.outer_diameter / 2)
            if geom.bore_diameter > 0:
                Circle(geom.bore_diameter / 2, mode=Mode.SUBTRACT)
            if geom.bolt_count > 0:
                with PolarLocations(geom.bolt_circle_radius, geom.bolt_count):
                    Circle(geom.bolt_hole_diameter / 2, mode=Mode.SUBTRACT)
        extrude(amount=geom.thickness)

        # 凸台（密封面）叠加在端面上
        if geom.raised_face_diameter > 0:
            top_face = part.faces().sort_by(Axis.Z)[-1]
            with BuildSketch(top_face):
                Circle(geom.raised_face_diameter / 2)
            extrude(amount=geom.raised_face_height)

    return part.part
