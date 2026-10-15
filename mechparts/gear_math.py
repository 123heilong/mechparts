"""渐开线齿轮的几何计算（纯数学，不依赖 CAD 库）。

这一层把《机械原理》里的公式翻译成代码，可以单独测试和验证。
所有长度单位统一用毫米(mm)。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# 压力角的标准取值
PRESSURE_ANGLE_STANDARD = 20.0


def involute_angle(alpha: float) -> float:
    """渐开线函数 inv(a) = tan(a) - a，输入输出均为弧度。

    这是渐开线齿轮所有公式的基石：它把"压力角"换算成
    "该点对应的展开角"。
    """
    return math.tan(alpha) - alpha


@dataclass(frozen=True)
class SpurGearGeometry:
    """直齿圆柱齿轮的全部几何参数（单位 mm / 度）。

    每个字段的公式都能在《机械原理》齿轮章节找到出处，
    注释里标了公式，方便你对着教材核对。
    """

    module: float          # 模数 m
    teeth: int             # 齿数 z
    pressure_angle: float  # 分度圆压力角 alpha (度)
    face_width: float      # 齿宽 b

    def __post_init__(self) -> None:
        if self.module <= 0:
            raise ValueError(f"模数必须为正，收到 {self.module}")
        if self.teeth < 6:
            raise ValueError(
                f"齿数过少（{self.teeth}）：标准 20° 压力角下 z<6 会严重根切，"
                "且齿顶会变尖无法建模"
            )
        if not 0 < self.pressure_angle < 45:
            raise ValueError(f"压力角应在 0~45 度之间，收到 {self.pressure_angle}")
        if self.face_width <= 0:
            raise ValueError(f"齿宽必须为正，收到 {self.face_width}")

    # ---- 基本尺寸 ----
    @property
    def pitch_diameter(self) -> float:
        """分度圆直径 d = m*z"""
        return self.module * self.teeth

    @property
    def pitch_radius(self) -> float:
        return self.pitch_diameter / 2

    @property
    def base_diameter(self) -> float:
        """基圆直径 db = d*cos(alpha)"""
        return self.pitch_diameter * math.cos(math.radians(self.pressure_angle))

    @property
    def base_radius(self) -> float:
        return self.base_diameter / 2

    @property
    def addendum(self) -> float:
        """齿顶高 ha = m (标准齿，齿顶高系数 ha*=1)"""
        return self.module

    @property
    def dedendum(self) -> float:
        """齿根高 hf = 1.25*m (顶隙系数 c*=0.25)"""
        return 1.25 * self.module

    @property
    def tip_diameter(self) -> float:
        """齿顶圆直径 da = d + 2*ha"""
        return self.pitch_diameter + 2 * self.addendum

    @property
    def root_diameter(self) -> float:
        """齿根圆直径 df = d - 2*hf"""
        return self.pitch_diameter - 2 * self.dedendum

    @property
    def tip_radius(self) -> float:
        return self.tip_diameter / 2

    @property
    def root_radius(self) -> float:
        return self.root_diameter / 2

    @property
    def whole_depth(self) -> float:
        """全齿高 h = ha + hf = 2.25*m"""
        return self.addendum + self.dedendum

    @property
    def circular_pitch(self) -> float:
        """齿距 p = pi*m"""
        return math.pi * self.module

    @property
    def tooth_thickness(self) -> float:
        """分度圆齿厚 s = pi*m/2"""
        return self.circular_pitch / 2

    # ---- 渐开线参数 ----
    def profile_parameter_at_radius(self, radius: float) -> float:
        """反解：已知半径 r，求渐开线展开参数 t。

        渐开线极坐标满足 r = rb / cos(alpha_r)，
        即 alpha_r = acos(rb/r)，而展开角 t = tan(alpha_r)。
        """
        if radius < self.base_radius:
            raise ValueError(
                f"半径 {radius:.4f} 小于基圆半径 {self.base_radius:.4f}，"
                "渐开线在基圆内不存在"
            )
        ratio = min(1.0, self.base_radius / radius)
        alpha_r = math.acos(ratio)
        return math.tan(alpha_r)

    @property
    def tip_parameter(self) -> float:
        return self.profile_parameter_at_radius(self.tip_radius)

    @property
    def root_parameter(self) -> float:
        """齿根处渐开线参数；若齿根圆小于基圆，则从基圆(t=0)起算。"""
        if self.root_radius <= self.base_radius:
            return 0.0
        return self.profile_parameter_at_radius(self.root_radius)

    @property
    def flank_rotation(self) -> float:
        """齿廓的定位角：把渐开线从自然位置转到正确的周向位置。

        推导：以基圆上渐开线起点为极轴的坐标系中，渐开线上参数 t 处的
        极角为 theta(t) = t - inv(alpha_t)，半径 r = rb/cos(alpha_t)。
        在分度圆处 alpha_t = alpha，故极角 theta_p = inv(alpha)。

        齿轮的齿以极角 0 为对称中心，分度圆齿厚 s = pi*m/2，
        对应半角 theta_half = s/(2*rp) = (pi*m/2)/(m*z) = pi/(2z)。

        所以要把落在 inv(alpha) 的渐开线转到 pi/(2z)，需旋转：

            alpha_flank = pi/(2z) - inv(alpha)

        注意是"减"：对 z=20、alpha=20 度，得 4.5 - 0.854 = 3.646 度，
        齿廓恰好落在 +/-4.5 度，分度圆齿厚自然等于 pi*m/2。
        """
        inv_alpha = involute_angle(math.radians(self.pressure_angle))
        return math.pi / (2 * self.teeth) - inv_alpha

    # ---- 强度校核所需 ----
    @property
    def contact_ratio_note(self) -> str:
        """提示：端面重合度需要配对齿轮参数，单齿轮无法计算。"""
        return "重合度需配对齿轮参数，见 pairing 模块"

    def summary(self) -> dict[str, float]:
        """返回一张尺寸表，可直接用于课程设计说明书。"""
        return {
            "模数 m": self.module,
            "齿数 z": self.teeth,
            "压力角 alpha": self.pressure_angle,
            "齿宽 b": self.face_width,
            "分度圆直径 d": self.pitch_diameter,
            "基圆直径 db": self.base_diameter,
            "齿顶圆直径 da": self.tip_diameter,
            "齿根圆直径 df": self.root_diameter,
            "齿顶高 ha": self.addendum,
            "齿根高 hf": self.dedendum,
            "全齿高 h": self.whole_depth,
            "齿距 p": self.circular_pitch,
            "分度圆齿厚 s": self.tooth_thickness,
        }
