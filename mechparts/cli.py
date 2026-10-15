"""命令行入口。

示例
----
    # 生成 M2 z20 齿轮，带 10mm 中心孔，导出 STEP
    python -m mechparts gear --module 2 --teeth 20 --bore 10 -o out/gear.step

    # 只看尺寸表（写课程设计说明书时很有用）
    python -m mechparts gear --module 2 --teeth 20 --table

    # 生成法兰
    python -m mechparts flange --od 160 --bore 60 --thickness 20 --bolts 4 -o out/flange.step
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _print_table(title: str, data: dict) -> None:
    print(f"\n{title}")
    print("-" * 42)
    for k, v in data.items():
        if isinstance(v, float):
            print(f"  {k:<18s} {v:>12.4f}")
        else:
            print(f"  {k:<18s} {v:>12}")


def _emit(kind: str, geom, out: str) -> None:
    """按扩展名分派导出：step/stl 出三维，dxf 出下料图，png 出预览图。"""
    ext = Path(out).suffix.lower()
    if ext in (".step", ".stp", ".stl"):
        from .gear_solid import build_spur_gear, export
        from .flange import build_flange

        part = build_spur_gear(geom, bore_diameter=0.0) if kind == "gear" else build_flange(geom)
        export(part, out)
    elif ext == ".dxf":
        from .drawings import export_flange_dxf, export_gear_dxf

        if kind == "gear":
            export_gear_dxf(geom, out)
        else:
            export_flange_dxf(geom, out)
    elif ext in (".png", ".jpg", ".jpeg", ".pdf", ".svg"):
        from .drawings import plot_flange, plot_gear

        if kind == "gear":
            plot_gear(geom, out)
        else:
            plot_flange(geom, out)
    else:
        raise ValueError(f"无法识别的输出扩展名 {ext!r}（支持 step/stl/dxf/png）")
    print(f"已导出 {out}")


def _cmd_gear(args: argparse.Namespace) -> int:
    from .gear_math import SpurGearGeometry

    geom = SpurGearGeometry(
        module=args.module,
        teeth=args.teeth,
        pressure_angle=args.pressure_angle,
        face_width=args.width,
    )

    # 无论是否导出，都先把尺寸表打出来——这是课程设计最需要的东西
    _print_table(f"直齿圆柱齿轮  尺寸表 (m={args.module}, z={args.teeth})", geom.summary())

    if args.table and not args.outputs:
        return 0

    if not args.outputs:
        print("\n未指定输出文件，仅打印尺寸表。加 -o 可导出模型。")
        return 0

    # 三维导出需要处理中心孔，单独走一条路径
    solid_outputs = [o for o in args.outputs if Path(o).suffix.lower() in (".step", ".stp", ".stl")]
    if solid_outputs:
        from .gear_solid import build_spur_gear, export

        part = build_spur_gear(geom, bore_diameter=args.bore, samples=args.samples)
        print(f"\n实体体积 {part.volume:.2f} mm^3，包围盒 {part.bounding_box()}")
        for out in solid_outputs:
            export(part, out)
            print(f"已导出 {out}")

    for out in args.outputs:
        if out not in solid_outputs:
            _emit("gear", geom, out)
    return 0


def _cmd_flange(args: argparse.Namespace) -> int:
    from .flange import FlangeGeometry

    geom = FlangeGeometry(
        outer_diameter=args.od,
        bore_diameter=args.bore,
        thickness=args.thickness,
        bolt_circle_diameter=args.bolt_circle,
        bolt_count=args.bolts,
        bolt_hole_diameter=args.bolt_hole,
        raised_face_diameter=args.raised_face or 0.0,
        raised_face_height=args.raised_height or 0.0,
    )

    _print_table("法兰  尺寸表", geom.summary())

    if args.table and not args.outputs:
        return 0
    if not args.outputs:
        print("\n未指定输出文件，仅打印尺寸表。加 -o 可导出模型。")
        return 0

    from .flange import build_flange
    from .gear_solid import export

    solid_outputs = [o for o in args.outputs if Path(o).suffix.lower() in (".step", ".stp", ".stl")]
    if solid_outputs:
        part = build_flange(geom)
        print(f"\n实体体积 {part.volume:.2f} mm^3，包围盒 {part.bounding_box()}")
        for out in solid_outputs:
            export(part, out)
            print(f"已导出 {out}")

    for out in args.outputs:
        if out not in solid_outputs:
            _emit("flange", geom, out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mechparts",
        description="机械标准件参数化生成器：用代码生成零件并导出 STEP / STL",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # ---- gear ----
    g = sub.add_parser("gear", help="直齿圆柱齿轮")
    g.add_argument("--module", "-m", type=float, required=True, help="模数 m (mm)")
    g.add_argument("--teeth", "-z", type=int, required=True, help="齿数 z")
    g.add_argument("--pressure-angle", type=float, default=20.0, help="压力角(度)，默认 20")
    g.add_argument("--width", "-b", type=float, default=10.0, help="齿宽 (mm)，默认 10")
    g.add_argument("--bore", type=float, default=0.0, help="中心孔直径 (mm)，默认 0 实心")
    g.add_argument("--samples", type=int, default=24, help="齿廓离散点数，默认 24（越大越精确）")
    g.add_argument("--table", action="store_true", help="只打印尺寸表，不建模")
    g.add_argument("-o", "--outputs", nargs="+", default=[], help="输出文件，如 out/gear.step")
    g.set_defaults(func=_cmd_gear)

    # ---- flange ----
    f = sub.add_parser("flange", help="法兰")
    f.add_argument("--od", type=float, required=True, help="法兰外径 (mm)")
    f.add_argument("--bore", type=float, default=0.0, help="中心孔直径 (mm)")
    f.add_argument("--thickness", "-t", type=float, required=True, help="法兰厚度 (mm)")
    f.add_argument("--bolt-circle", type=float, default=0.0, help="螺栓孔中心圆直径 (mm)")
    f.add_argument("--bolts", type=int, default=0, help="螺栓孔数量")
    f.add_argument("--bolt-hole", type=float, default=0.0, help="螺栓孔直径 (mm)")
    f.add_argument("--raised-face", type=float, default=0.0, help="凸台直径 (mm)")
    f.add_argument("--raised-height", type=float, default=0.0, help="凸台高度 (mm)")
    f.add_argument("--table", action="store_true", help="只打印尺寸表，不建模")
    f.add_argument("-o", "--outputs", nargs="+", default=[], help="输出文件")
    f.set_defaults(func=_cmd_flange)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ValueError as e:
        print(f"参数错误：{e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
