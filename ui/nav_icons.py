# ui/nav_icons.py
# 🖌️ Монохромные (не цветные) векторные иконки для бокового меню.
# Иконки рисуются QPainter'ом в 24x24 с сеткой-восьмёркой, штриховые
# (outline) стили — как Material Symbols / Feather. Никаких эмодзи.
from __future__ import annotations

import math
from typing import Dict

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QIcon, QPixmap, QPainter, QPen, QColor, QPainterPath,
)


def _poly(p: QPainter, pts, close: bool = False):
    """Ломаная из точек."""
    if len(pts) < 2:
        return
    path = QPainterPath(QPointF(*pts[0]))
    for x, y in pts[1:]:
        path.lineTo(x, y)
    if close:
        path.closeSubpath()
    p.drawPath(path)


def _circ(p: QPainter, cx: float, cy: float, r: float):
    p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))


def _rrect(p: QPainter, x: float, y: float, w: float, h: float, r: float):
    p.drawRoundedRect(QRectF(x, y, w, h), r, r)


# ── Рисовалки отдельных иконок (координаты 0..24) ────────────────

def _d_gpu(p: QPainter):
    """Видеокарта: корпус + вентилятор + разъём."""
    _rrect(p, 3, 5, 18, 11, 2)                 # корпус
    _circ(p, 9.5, 10.5, 3.2)                   # вентилятор
    _circ(p, 9.5, 10.5, 0.7)                   # ось
    _poly(p, [(15, 8), (18, 8)])               # верхняя решётка
    _poly(p, [(15, 10.5), (18, 10.5)])         # средняя решётка
    _poly(p, [(15, 13), (18, 13)])             # нижняя решётка
    _poly(p, [(6, 19), (6, 16.5), (15, 16.5), (15, 19)])  # PCIe-«ножки»


def _d_kangaroo(p: QPainter):
    """Кенгуру-лапа (прыжок/поиск диапазона)."""
    _circ(p, 12, 5.6, 2.1)                     # «подушечка»-пятка
    for cx in (6.2, 9.1, 12.0, 14.9):          # пальцы
        _rrect(p, cx - 1.05, 10.5, 2.1, 8.5, 1.05)


def _d_cpu(p: QPainter):
    """Процессор: чип с ножками и ядром."""
    _rrect(p, 6, 6, 12, 12, 2)                 # корпус
    _rrect(p, 9.5, 9.5, 5, 5, 1)               # ядро
    for x in (9, 12, 15):                      # верхние/нижние ножки
        _poly(p, [(x, 6), (x, 3.5)])
        _poly(p, [(x, 18), (x, 20.5)])
    for y in (9, 12, 15):                      # боковые ножки
        _poly(p, [(6, y), (3.5, y)])
        _poly(p, [(18, y), (20.5, y)])


def _d_vanity(p: QPainter):
    """Vanity: «звёздочка блеска» + малая искра."""
    s = [(12, 3.2), (13.9, 9.1), (19.8, 11),
         (13.9, 12.9), (12, 18.8), (10.1, 12.9),
         (4.2, 11), (10.1, 9.1)]
    _poly(p, s, close=True)
    _poly(p, [(18.2, 16.2), (18.2, 19.2)])     # малая искра
    _poly(p, [(16.7, 17.7), (19.7, 17.7)])


def _d_keys(p: QPainter):
    """Связка найденных ключей: головка + стержень + насечки."""
    _circ(p, 8, 8, 3.3)                        # головка
    _poly(p, [(10.4, 10.4), (18.5, 18.5)])     # стержень
    _poly(p, [(15.2, 16.2), (17, 14.4)])       # насечка 1
    _poly(p, [(17.3, 18.3), (19.1, 16.5)])     # насечка 2


def _d_converter(p: QPainter):
    """Конвертер HEX → WIF: две стрелки обмена."""
    _poly(p, [(4, 8), (17, 8)])                # верхняя стрелка
    _poly(p, [(14, 5), (17.5, 8), (14, 11)])   # наконечник вправо
    _poly(p, [(20, 16), (7, 16)])              # нижняя стрелка
    _poly(p, [(10, 13), (6.5, 16), (10, 19)])  # наконечник влево


def _d_log(p: QPainter):
    """Журнал: лист с линиями текста."""
    _rrect(p, 5, 3.5, 14, 17, 2)               # лист
    _poly(p, [(8.2, 8), (15.8, 8)])
    _poly(p, [(8.2, 11.5), (15.8, 11.5)])
    _poly(p, [(8.2, 15), (13.5, 15)])


def _d_predict(p: QPainter):
    """Предсказание: хрустальный шар с бликом и подставкой."""
    _circ(p, 12, 10, 6.2)                      # шар
    _poly(p, [(8.6, 12.8), (10.6, 10.8), (9.6, 8.8)])  # блик-грань
    _poly(p, [(7.5, 17.6), (16.5, 17.6)])      # подставка
    _poly(p, [(9.6, 20.2), (14.4, 20.2)])      # основание


def _d_about(p: QPainter):
    """О программе: окружность + «i»."""
    _circ(p, 12, 12, 8.2)
    _circ(p, 12, 8.1, 0.5)                     # точка
    _poly(p, [(12, 11.2), (12, 16)])            # стержень


DRAW_FUNCS: Dict[str, object] = {
    "gpu": _d_gpu,
    "kangaroo": _d_kangaroo,
    "cpu": _d_cpu,
    "vanity": _d_vanity,
    "keys": _d_keys,
    "converter": _d_converter,
    "log": _d_log,
    "predict": _d_predict,
    "about": _d_about,
    "chevron_left": None,   # заполняется ниже
    "chevron_right": None,
    "brand": None,
}


def _d_chevron_left(p: QPainter):
    _poly(p, [(14.5, 6), (8.5, 12), (14.5, 18)])


def _d_chevron_right(p: QPainter):
    _poly(p, [(9.5, 6), (15.5, 12), (9.5, 18)])


def _d_brand(p: QPainter):
    """Бренд: блок «крипто-куб» с узлом сети."""
    _poly(p, [(12, 3.2), (19.8, 7.6), (19.8, 16.4),
              (12, 20.8), (4.2, 16.4), (4.2, 7.6)], close=True)
    _poly(p, [(4.2, 7.6), (12, 12), (19.8, 7.6)])
    _poly(p, [(12, 12), (12, 20.8)])


DRAW_FUNCS["chevron_left"] = _d_chevron_left
DRAW_FUNCS["chevron_right"] = _d_chevron_right
DRAW_FUNCS["brand"] = _d_brand


# ── Публичный API ─────────────────────────────────────────────────

def make_icon(name: str, color: str, size: int = 24,
              stroke_width: float = 1.6) -> QIcon:
    """QIcon с монохромной штриховой иконкой заданного цвета."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    scale = size / 24.0
    if abs(scale - 1.0) > 1e-6:
        p.scale(scale, scale)
    pen = QPen(QColor(color))
    pen.setWidthF(stroke_width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    fn = DRAW_FUNCS.get(name)
    if fn is not None:
        fn(p)
    p.end()
    return QIcon(pm)


def icon_names_for_label(label: str) -> str:
    """Подбор иконки по названию пункта меню (рус./англ. синонимы)."""
    t = (label or "").lower()
    table = [
        ("gpu", ("gpu", "видео", "graphics")),
        ("kangaroo", ("kangaroo", "кенгуру", "range", "диапазон")),
        ("cpu", ("cpu", "процесс")),
        ("vanity", ("vanity", "вейни", "именны")),
        ("keys", ("найден", "ключ", "found", "key")),
        ("converter", ("конверт", "wif", "hex", "convert")),
        ("log", ("лог", "журнал", "console", "output", "истори")),
        ("predict", ("predict", "предск", "прогноз", "авер")),
        ("about", ("о прог", "about", "справ", "info")),
    ]
    for name, keys in table:
        for k in keys:
            if k in t:
                return name
    return "log"
