"""mechparts —— 机械标准件参数化生成器。

用代码描述零件，一键导出 STEP / STL，可直接用于课程设计与毕设。

快速开始
--------
    from mechparts import SpurGearGeometry, build_spur_gear, export

    g = SpurGearGeometry(module=2.0, teeth=20, pressure_angle=20.0, face_width=10.0)
    part = build_spur_gear(g, bore_diameter=10.0)
    export(part, "gear.step")
"""

from __future__ import annotations

__version__ = "0.1.0"

from .gear_math import SpurGearGeometry, involute_angle
from .gear_profile import full_gear_profile, tooth_profile_points

__all__ = [
    "__version__",
    "SpurGearGeometry",
    "involute_angle",
    "full_gear_profile",
    "tooth_profile_points",
    "build_spur_gear",
    "export",
]


def __getattr__(name: str):
    """惰性导入 CAD 层，让没装 build123d 的环境也能用纯数学功能。"""
    if name in ("build_spur_gear", "export"):
        from . import gear_solid

        return getattr(gear_solid, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
