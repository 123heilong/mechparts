"""由几何参数生成齿廓点列，并建成三维实体。

分两步：
1. `tooth_profile_points()` 纯数学，输出单个齿的闭合轮廓点（二维）
2. `build_spur_gear()` 调用 build123d 把齿廓阵列成整圈并拉伸成实体
"""

from __future__ import annotations

import math

from .gear_math import SpurGearGeometry


def _involute_points(
    geom: SpurGearGeometry, samples: int
) -> list[tuple[float, float]]:
    """生成一条渐开线齿廓（从齿根到齿顶），返回二维点列。

    渐开线的自然参数方程为：
        x(t) = rb * (cos t + t*sin t)
        y(t) = rb * (sin t - t*cos t)
    该曲线在 t 处与基圆相切，t 越大半径越大。
    """
    rb = geom.base_radius
    t0 = geom.root_parameter
    t1 = geom.tip_parameter
    if t1 <= t0:
        raise ValueError("齿顶参数不大于齿根参数，几何参数不合理")

    pts: list[tuple[float, float]] = []
    for i in range(samples + 1):
        t = t0 + (t1 - t0) * i / samples
        pts.append((rb * (math.cos(t) + t * math.sin(t)),
                    rb * (math.sin(t) - t * math.cos(t))))
    return pts


def _rotate(pt: tuple[float, float], angle: float) -> tuple[float, float]:
    c, s = math.cos(angle), math.sin(angle)
    x, y = pt
    return (x * c - y * s, x * s + y * c)


def _arc_points(radius: float, a0: float, a1: float, samples: int) -> list[tuple[float, float]]:
    """在给定半径上，从角度 a0 到 a1 采样圆弧点。"""
    if samples < 1:
        return []
    return [
        (radius * math.cos(a0 + (a1 - a0) * i / samples),
         radius * math.sin(a0 + (a1 - a0) * i / samples))
        for i in range(samples + 1)
    ]


def tooth_profile_points(geom: SpurGearGeometry, samples: int = 24) -> list[tuple[float, float]]:
    """生成单个齿的闭合轮廓（逆时针），已定位到正确的周向位置。

    构造顺序：
      齿根圆(该齿一侧) -> 左齿廓渐开线 -> 齿顶圆弧 -> 右齿廓渐开线(镜像) -> 回到起点
    """
    pts: list[tuple[float, float]] = []

    # --- 左齿廓：从齿根到齿顶，再整体旋转到正确位置 ---
    left = _involute_points(geom, samples)
    rot = geom.flank_rotation
    left = [_rotate(p, rot) for p in left]

    # --- 右齿廓：镜像后要反向，才能保持外轮廓逆时针 ---
    right = [(x, -y) for (x, y) in left]

    tip_angles = [math.atan2(y, x) for (x, y) in left]
    a_tip_left = tip_angles[-1]
    a_tip_right = -a_tip_left

    # 齿顶圆弧：从左齿廓顶点走到右齿廓顶点（跨过齿顶中线，即极角 0）
    tip_arc = _arc_points(geom.tip_radius, a_tip_left, a_tip_right, max(3, samples // 4))

    pts.extend(left)

    # 齿顶圆弧去掉首尾（与齿廓端点重复）
    pts.extend(tip_arc[1:-1] if len(tip_arc) > 2 else [])

    # 右齿廓：镜像并反向（从齿顶回到齿根）
    pts.extend(reversed(right))

    # --- 齿根：若齿根圆小于基圆，需从基圆径向补到齿根圆 ---
    if geom.root_radius < geom.base_radius:
        root_angles = [math.atan2(y, x) for (x, y) in pts[-1:]] + [
            math.atan2(y, x) for (x, y) in right[-1:]
        ]
        a_back_root = -tip_angles[0]
        # 右侧径向下落
        pts.append((geom.root_radius * math.cos(a_back_root),
                    geom.root_radius * math.sin(a_back_root)))
        # 齿根圆弧：从右齿根绕到左齿根（注意要逆时针绕大圈？不——这里只补本齿根部）
        root_arc = _arc_points(
            geom.root_radius, a_back_root, tip_angles[0], max(3, samples // 4)
        )
        pts.extend(root_arc[1:])

    return _ensure_counter_clockwise(pts)


def _signed_area(pts: list[tuple[float, float]]) -> float:
    """鞋带公式求多边形有向面积，用于判断绕向。"""
    area = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        area += x0 * y1 - x1 * y0
    return area / 2


def _ensure_counter_clockwise(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return pts if _signed_area(pts) > 0 else list(reversed(pts))


def full_gear_profile(geom: SpurGearGeometry, samples: int = 24) -> list[tuple[float, float]]:
    """把单个齿绕圆心阵列一整圈，得到齿轮外轮廓。"""
    tooth = tooth_profile_points(geom, samples)
    step = 2 * math.pi / geom.teeth
    out: list[tuple[float, float]] = []
    for i in range(geom.teeth):
        out.extend(_rotate(p, i * step) for p in tooth)
    return out
