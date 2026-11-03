# ui/animations.py
# ✨ Переиспользуемые анимационные примитивы Qt (без внешних зависимостей).
# Всё сделано так, чтобы НИЧЕГО не ломать: анимации только визуальные,
# никаких изменений в логике приложения.
from __future__ import annotations

import math
from typing import Optional

from PyQt6.QtCore import (
    Qt, QObject, QPropertyAnimation, QEasingCurve, QTimer,
    pyqtSignal, pyqtProperty, QPoint, QRectF,
)
from PyQt6.QtGui import QColor, QPainter, QPen, QRadialGradient, QLinearGradient
from PyQt6.QtWidgets import QWidget, QGraphicsOpacityEffect


def _ease_out_back(t: float) -> float:
    """OutBack-кривая (лёгкий «перелёт») для pop-in эффектов."""
    c1, c3 = 1.70158, 2.70158
    return 1.0 + c3 * (t - 1.0) ** 3 + c1 * (t - 1.0) ** 2


class RippleOverlay(QObject):
    """Ripple-волна от точки клика поверх любого виджета.

    Создаёт временный прозрачный child-overlay, проигрывает волну и
    удаляет себя. Безопасен для любых виджетов (в т.ч. кнопок с
    собственным paintEvent).
    """

    def __init__(self, widget: QWidget, color: Optional[QColor] = None,
                 duration: int = 430):
        super().__init__(widget)
        self._widget = widget
        self._color = color or QColor("#FFFFFF")
        self._duration = duration
        self._progress = 0.0
        self._origin = QPoint(0, 0)
        self._overlay: Optional[QWidget] = None

        self._anim = QPropertyAnimation(self, b"progress", self)
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuart)
        self._anim.finished.connect(self._cleanup)

    progress = pyqtProperty(float, lambda self: self._progress,
                            self._set_progress)

    def _set_progress(self, v: float):
        self._progress = v
        if self._overlay is not None:
            self._overlay.update()

    def fire(self, pos: Optional[QPoint] = None):
        w = self._widget
        if w is None or w.width() <= 1:
            return
        if pos is None:
            pos = QPoint(w.width() // 2, w.height() // 2)
        self._origin = QPoint(pos)

        class _Overlay(QWidget):
            pass

        ov = _Overlay(w)
        ov.setGeometry(0, 0, w.width(), w.height())
        ov.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        ov.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        ov.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        color = QColor(self._color)
        dur = self._duration

        def paint(e, _ov=ov, _color=color, _origin=self._origin, _dur=dur):
            p = QPainter(_ov)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            t = self._progress
            if t <= 0.0 or t >= 1.0:
                p.end()
                return
            rect = QRectF(_ov.rect()).adjusted(1, 1, -1, -1)
            max_r = math.hypot(rect.width(), rect.height())
            radius = max_r * 0.55 * t
            alpha = int(55 * (1.0 - t))
            c = QColor(_color)
            c.setAlpha(alpha)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawEllipse(QRectF(_origin.x() - radius, _origin.y() - radius,
                                 radius * 2, radius * 2))
            p.end()

        ov.paintEvent = paint
        ov.show()
        ov.raise_()
        self._overlay = ov

        self._anim.stop()
        self._progress = 0.0
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def _cleanup(self):
        ov, self._overlay = self._overlay, None
        if ov is not None:
            ov.deleteLater()


def attach_ripple(widget: QWidget, color: Optional[str] = None,
                  duration: int = 430) -> "RippleEventFilter":
    """Вешает ripple на mouseRelease внутри границ виджета."""
    overlay = RippleOverlay(widget, QColor(color) if color else None, duration)
    ef = RippleEventFilter(widget, overlay)
    widget.installEventFilter(ef)
    widget._ripple_filter = ef  # держим ссылку
    return ef


class RippleEventFilter(QObject):
    def __init__(self, widget: QWidget, overlay: RippleOverlay):
        super().__init__(widget)
        self._widget = widget
        self._overlay = overlay

    def eventFilter(self, obj, event):
        et = event.type()
        if et == event.Type.MouseButtonPress:
            self._widget._press_pos = event.position().toPoint()
        elif et == event.Type.MouseButtonRelease:
            try:
                inside = QRectF(self._widget.rect()).contains(event.position())
            except Exception:
                inside = True
            if inside:
                pos = getattr(self._widget, "_press_pos", None)
                self._overlay.fire(pos)
        return False


def fade_in(widget: QWidget, duration: int = 220, from_op: float = 0.0,
            curve: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
            on_done=None) -> Optional[QGraphicsOpacityEffect]:
    """Мягкое появление виджета. Возвращает эффект (или None если не удалось)."""
    try:
        eff = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", widget)
        anim.setDuration(duration)
        anim.setStartValue(from_op)
        anim.setEndValue(1.0)
        anim.setEasingCurve(curve)

        def done():
            try:
                widget.setGraphicsEffect(None)
            except RuntimeError:
                pass
            if on_done:
                try:
                    on_done()
                except Exception:
                    pass

        anim.finished.connect(done)
        anim.start()
        widget._fade_anim = anim
        return eff
    except Exception:
        return None


def slide_fade_in(widget: QWidget, dx: int = 26, dy: int = 0,
                  duration: int = 260):
    """Slide+fade появление (для панелей сайдбара/попавсов)."""
    start = widget.pos()
    eff = fade_in(widget, duration, 0.0)
    a = QPropertyAnimation(widget, b"pos", widget)
    a.setDuration(duration)
    a.setStartValue(start + QPoint(dx, dy))
    a.setEndValue(start)
    a.setEasingCurve(QEasingCurve.Type.OutQuad)
    a.start()
    widget._slide_anim = a


class PulseDot(QWidget):
    """Пульсирующая точка-индикатор (живой акцент в шапке/бренде)."""

    def __init__(self, parent=None, color: str = "#6E9C7E", size: int = 9):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(size + 6, size + 6)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._phase = 0.0
        self._anim = QPropertyAnimation(self, b"phase", self)
        self._anim.setDuration(1900)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(2.0 * math.pi)
        self._anim.setLoopCount(-1)
        self._anim.setEasingCurve(QEasingCurve.Type.Linear)

    phase = pyqtProperty(float, lambda self: self._phase, self._set_phase)

    def _set_phase(self, v):
        self._phase = v
        self.update()

    def showEvent(self, e):
        self._anim.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._anim.stop()
        super().hideEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        s = self.width() / 2.0 - 2
        pulse = 0.5 + 0.5 * math.sin(self._phase)

        halo = QColor(self._color)
        halo.setAlpha(int(45 + 55 * pulse))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo)
        p.drawEllipse(QRectF(cx - s - 2 - 2 * pulse, cy - s - 2 - 2 * pulse,
                             (s + 2 + 2 * pulse) * 2, (s + 2 + 2 * pulse) * 2))

        core = QColor(self._color)
        core.setAlpha(int(190 + 60 * pulse))
        p.setBrush(core)
        p.drawEllipse(QRectF(cx - s, cy - s, s * 2, s * 2))
        p.end()


class GlowBar(QWidget):
    """Бегущая светящаяся линия под активной областью (эффект «живого» UI)."""

    def __init__(self, parent=None, color: str = "#7D8896"):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedHeight(2)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._t = 0.0
        self._anim = QPropertyAnimation(self, b"t", self)
        self._anim.setDuration(2600)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setLoopCount(-1)
        self._anim.setEasingCurve(QEasingCurve.Type.Linear)

    t = pyqtProperty(float, lambda self: self._t, self._set_t)

    def _set_t(self, v):
        self._t = v
        self.update()

    def showEvent(self, e):
        self._anim.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._anim.stop()
        super().hideEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        w = self.width()
        if w < 8:
            p.end()
            return
        seg = max(40, w // 4)
        x = -seg + (w + seg) * self._t
        grad = QLinearGradient(x, 0, x + seg, 0)
        c0 = QColor(self._color); c0.setAlpha(0)
        c1 = QColor(self._color); c1.setAlpha(120)
        grad.setColorAt(0.0, c0)
        grad.setColorAt(0.5, c1)
        grad.setColorAt(1.0, c0)
        p.fillRect(self.rect(), grad)
        p.end()
