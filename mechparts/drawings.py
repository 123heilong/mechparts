"""二维图纸：预览图（PNG）与 DXF 导出。

机械专业交付物最终大多是二维图，所以这里把齿廓导出成 DXF，
可以直接导入 AutoCAD / SolidWorks / 用于线切割和激光切割。
"""

from __future__ import annotations

from pathlib import Path

from .flange import FlangeGeometry
from .gear_math import SpurGearGeometry
from .gear_profile import full_gear_profile


def gear_reference_radii(geom: SpurGearGeometry) -> dict[str, float]:
    """齿轮的四个特征圆半径，供画图和标注使用。"""
    return {
        "齿顶圆": geom.tip_radius,
        "分度圆": geom.pitch_radius,
        "基圆": geom.base_radius,
        "齿根圆": geom.root_radius,
    }


def export_gear_dxf(
    geom: SpurGearGeometry,
    path: str | Path,
    include_reference_circles: bool = True,
    samples: int = 32,
) -> Path:
    """把齿轮轮廓导出为 DXF。

    图层划分：
      GEAR_OUTLINE  实际齿廓（下料用）
      GEAR_REF      分度圆 / 基圆等辅助线（不参与加工）
    """
    import ezdxf

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.new("R2010", setup=True)
    doc.layers.add("GEAR_OUTLINE", color=7)
    doc.layers.add("GEAR_REF", color=8, linetype="DASHED")
    msp = doc.modelspace()

    outline = full_gear_profile(geom, samples=samples)
    msp.add_lwpolyline(
        outline + [outline[0]], close=True, dxfattribs={"layer": "GEAR_OUTLINE"}
    )

    if include_reference_circles:
        for name, r in gear_reference_radii(geom).items():
            msp.add_circle((0, 0), r, dxfattribs={"layer": "GEAR_REF"})

    doc.saveas(str(path))
    return path


def export_flange_dxf(
    geom: FlangeGeometry,
    path: str | Path,
    include_reference_circles: bool = True,
) -> Path:
    """把法兰轮廓导出为 DXF。"""
    import ezdxf

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.new("R2010", setup=True)
    doc.layers.add("FLANGE_OUTLINE", color=7)
    doc.layers.add("FLANGE_REF", color=8, linetype="DASHED")
    msp = doc.modelspace()

    msp.add_circle((0, 0), geom.outer_diameter / 2,
                   dxfattribs={"layer": "FLANGE_OUTLINE"})
    if geom.bore_diameter > 0:
        msp.add_circle((0, 0), geom.bore_diameter / 2,
                       dxfattribs={"layer": "FLANGE_OUTLINE"})

    if geom.bolt_count > 0:
        import math

        for i in range(geom.bolt_count):
            a = 2 * math.pi * i / geom.bolt_count
            cx = geom.bolt_circle_radius * math.cos(a)
            cy = geom.bolt_circle_radius * math.sin(a)
            msp.add_circle((cx, cy), geom.bolt_hole_diameter / 2,
                           dxfattribs={"layer": "FLANGE_OUTLINE"})

    if include_reference_circles and geom.bolt_count > 0:
        msp.add_circle((0, 0), geom.bolt_circle_radius,
                       dxfattribs={"layer": "FLANGE_REF"})

    doc.saveas(str(path))
    return path


def _matplotlib():
    import matplotlib

    matplotlib.use("Agg")  # 无界面后端，便于脚本批量出图
    import matplotlib.pyplot as plt

    # 让图表能正确显示中文：优先使用系统的 CJK 字体，找不到就退回默认
    # （退回时中文会显示成方框，但图形本身不受影响）
    from matplotlib import font_manager

    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC",
                 "Source Han Sans SC", "DengXian", "SimSun"):
        if name in installed:
            plt.rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
            break
    plt.rcParams["axes.unicode_minus"] = False  # 负号显示为普通减号

    return plt


def plot_gear(
    geom: SpurGearGeometry,
    path: str | Path,
    samples: int = 32,
    annotate: bool = True,
) -> Path:
    """画齿轮二维预览图，标注四个特征圆。"""
    plt = _matplotlib()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    outline = full_gear_profile(geom, samples=samples)
    xs = [p[0] for p in outline] + [outline[0][0]]
    ys = [p[1] for p in outline] + [outline[0][1]]

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.fill(xs, ys, color="#c8d8e8", zorder=1)
    ax.plot(xs, ys, color="#1f4e79", lw=1.2, zorder=2, label="齿廓")

    import math

    theta = [2 * math.pi * i / 360 for i in range(361)]
    styles = {
        "齿顶圆": ("#d62728", "--"),
        "分度圆": ("#2ca02c", "-."),
        "基圆": ("#ff7f0e", ":"),
        "齿根圆": ("#7f7f7f", "--"),
    }
    for name, r in gear_reference_radii(geom).items():
        color, ls = styles[name]
        ax.plot([r * math.cos(t) for t in theta],
                [r * math.sin(t) for t in theta],
                color=color, ls=ls, lw=0.9,
                label=f"{name} d={2*r:.2f}")

    if annotate:
        # 标注半径尺寸线
        ax.annotate("", xy=(geom.tip_radius, 0), xytext=(0, 0),
                    arrowprops=dict(arrowstyle="->", color="#333", lw=0.8))
        ax.text(geom.tip_radius * 0.55, 1.5, f"ra={geom.tip_radius:.2f}",
                fontsize=9, color="#333")

    ax.set_aspect("equal")
    ax.grid(alpha=0.25, ls=":")
    ax.legend(fontsize=7, loc="upper right", framealpha=0.9)
    ax.set_title(
        f"直齿圆柱齿轮  m={geom.module:g}  z={geom.teeth}  "
        f"$\\alpha$={geom.pressure_angle:g}°  b={geom.face_width:g}",
        fontsize=11,
    )
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")

    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def plot_flange(geom: FlangeGeometry, path: str | Path) -> Path:
    """画法兰二维预览图。"""
    plt = _matplotlib()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    import math

    fig, ax = plt.subplots(figsize=(7, 7))

    theta = [2 * math.pi * i / 360 for i in range(361)]
    R = geom.outer_diameter / 2
    ax.fill([R * math.cos(t) for t in theta], [R * math.sin(t) for t in theta],
            color="#dfe7ef", zorder=1)
    ax.plot([R * math.cos(t) for t in theta], [R * math.sin(t) for t in theta],
            color="#1f4e79", lw=1.4, label=f"外径 D={geom.outer_diameter:g}")

    if geom.bore_diameter > 0:
        r = geom.bore_diameter / 2
        ax.fill([r * math.cos(t) for t in theta], [r * math.sin(t) for t in theta],
                color="white", zorder=2)
        ax.plot([r * math.cos(t) for t in theta], [r * math.sin(t) for t in theta],
                color="#1f4e79", lw=1.4, label=f"中心孔 d={geom.bore_diameter:g}")

    if geom.bolt_count > 0:
        rh = geom.bolt_hole_diameter / 2
        for i in range(geom.bolt_count):
            a = 2 * math.pi * i / geom.bolt_count
            cx, cy = geom.bolt_circle_radius * math.cos(a), geom.bolt_circle_radius * math.sin(a)
            ax.fill([cx + rh * math.cos(t) for t in theta],
                    [cy + rh * math.sin(t) for t in theta], color="white", zorder=2)
            ax.plot([cx + rh * math.cos(t) for t in theta],
                    [cy + rh * math.sin(t) for t in theta], color="#1f4e79", lw=1.0)
        ax.plot([geom.bolt_circle_radius * math.cos(t) for t in theta],
                [geom.bolt_circle_radius * math.sin(t) for t in theta],
                color="#2ca02c", ls="-.", lw=0.9,
                label=f"中心圆 K={geom.bolt_circle_diameter:g}")

    ax.set_aspect("equal")
    ax.grid(alpha=0.25, ls=":")
    ax.legend(fontsize=8, loc="upper right", framealpha=0.9)
    ax.set_title(
        f"法兰  D={geom.outer_diameter:g}  d={geom.bore_diameter:g}  "
        f"t={geom.thickness:g}  n={geom.bolt_count}-$\\phi${geom.bolt_hole_diameter:g}",
        fontsize=11,
    )
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")

    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path
