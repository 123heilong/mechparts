"""生成 README 里用到的示例图与图纸。

运行：python examples/make_docs.py
产物写入 docs/ 目录。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mechparts.drawings import (  # noqa: E402
    export_flange_dxf,
    export_gear_dxf,
    plot_flange,
    plot_gear,
)
from mechparts.flange import FlangeGeometry  # noqa: E402
from mechparts.gear_math import SpurGearGeometry  # noqa: E402

DOCS = ROOT / "docs"


def main() -> int:
    DOCS.mkdir(exist_ok=True)

    gear = SpurGearGeometry(module=2.0, teeth=20, pressure_angle=20.0, face_width=12.0)
    plot_gear(gear, DOCS / "gear_m2_z20.png")
    export_gear_dxf(gear, DOCS / "gear_m2_z20.dxf")
    print("已生成 docs/gear_m2_z20.png 与 .dxf")

    flange = FlangeGeometry(
        outer_diameter=160.0,
        bore_diameter=60.0,
        thickness=20.0,
        bolt_circle_diameter=125.0,
        bolt_count=4,
        bolt_hole_diameter=18.0,
    )
    plot_flange(flange, DOCS / "flange_dn50.png")
    export_flange_dxf(flange, DOCS / "flange_dn50.dxf")
    print("已生成 docs/flange_dn50.png 与 .dxf")

    # 顺便打印尺寸表，方便核对
    print()
    for k, v in gear.summary().items():
        print(f"  {k:<18s} {v:>12.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
