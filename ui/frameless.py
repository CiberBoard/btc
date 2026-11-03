# ui/frameless.py
# Frameless-окна в едином стиле приложения:
#    - собственный тёмный titlebar (drag, maximize, close) поверх контента;
#    - на Windows нативная полоса снимается флагом Qt FramelessWindowHint
#      (без WNDPROC-сабклассинга и прямых SetWindowLong — именно они
#      приводили к крашу 0xC0000409 / стековому разрушению);
#    - перетаскивание за шапку, двойной клик = развернуть/восстановить,
#      ресайз за края — только средствами Qt (ResizeHelper).
from __future__ import annotations

import sys

from PyQt6.QtCore import Qt, QPoint, QPointF, QSize, QRectF, QObject, QEvent, QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QCursor
from PyQt6.QtWidgets import (
    QWidget, QMainWindow, QDialog, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QSizePolicy, QApplication,
)

from ui.theme import COLORS
from ui.nav_icons import make_icon, icon_names_for_label

_IS_WIN = sys.platform == "win32"


# ─────────────────────────────────────────────────────────────
# Палитра шапки — берём из общей темы приложения
# ─────────────────────────────────────────────────────────────
_BG_TITLEBAR = COLORS.get('bg_card', '#26262B')
_BG_WINDOW = COLORS.get('bg_main', '#1E1E22')
_TEXT = COLORS.get('text_primary', '#E8E8EC')
_TEXT_DIM = COLORS.get('text_secondary', '#9A9AA5')
_HOVER = COLORS.get('bg_hover', '#34343D')
_PRESSED = COLORS.get('bg_pressed', '#1A1A1F')
_CLOSE_HOVER = '#C0554F'   # приглушённый красный для кнопки закрытия
_BORDER = COLORS.get('border_soft', '#30303A')


def _clean_title(title: str) -> str:
    """Убирает эмодзи/мусорные символы из заголовка окна."""
    if not title:
        return "BGS Scanner"
    out = []
    for ch in title:
        o = ord(ch)
        if (0x1F000 <= o <= 0x1FAFF) or (0x2600 <= o <= 0x27BF) or o in (0xFE0F, 0x20E3, 0x2139):
            continue
        out.append(ch)
    t = "".join(out).strip()
    # схлопываем двойные пробелы, оставшиеся после удаления эмодзи
    while "  " in t:
        t = t.replace("  ", " ")
    return t if any(c.isalnum() for c in t) else "BGS Scanner"

_BTN_QSS = f"""
QPushButton {{
    background: transparent; border: none; border-radius: 6px;
    color: {_TEXT_DIM};
}}
QPushButton:hover {{ background: {_HOVER}; }}
QPushButton:pressed {{ background: {_PRESSED}; }}
"""

_CLOSE_QSS = f"""
QPushButton {{
    background: transparent; border: none; border-radius: 6px;
    color: {_TEXT_DIM};
}}
QPushButton:hover {{ background: {_CLOSE_HOVER}; color: #FFFFFF; }}
QPushButton:pressed {{ background: #9d4640; color: #FFFFFF; }}
"""


class _WinBtn(QPushButton):
    """Кнопка window controls, рисует символ через QPainter.

    Размер НЕ задаётся через setFixedSize(): глобальный QSS приложения
    (`QPushButton { padding: 8px 20px; min-height: 34px; }`) при каждом
    StyleChange перезаписывал minimumSize кнопок, они раздувались до
    50×50 внутри 36-пиксельной шапки, выходили за её границы и «съедали»
    всю ширину layout'а — из-за чего шапка визуально «ломалась».
    Теперь размеры контролируются только sizeHint + Fixed sizePolicy
    (QSS не может их переопределить), а геометрия кнопок выставляется
    вручную в TitleBar.resizeEvent.
    """

    BTN_W = 40   # ширина кнопки в логических px (как нативные Windows controls)

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self._kind = kind  # 'min' | 'max' | 'restore' | 'close'
        self._btn_h = 32
        if kind == 'close':
            self.setObjectName("appTitleBarClose")
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # никаких margin/padding из чужого QSS не останется:
        self.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_bar_height(self, h: int):
        self._btn_h = h
        self.updateGeometry()

    def changeEvent(self, e):
        # QSS с `min-height` может при StyleChange раздуть our widget за
        # пределы шапки (Qt применяет minimum из стиля). Возвращаем размер.
        from PyQt6.QtCore import QEvent as _QE
        if e.type() == _QE.Type.StyleChange:
            g = self.geometry()
            if g.height() != self._btn_h or g.width() != self.BTN_W:
                self.setGeometry(g.x(), g.y(), self.BTN_W, self._btn_h)
        super().changeEvent(e)

    def sizeHint(self):
        return QSize(self.BTN_W, self._btn_h)

    def minimumSizeHint(self):
        return QSize(self.BTN_W, self._btn_h)

    def paintEvent(self, e):
        super().paintEvent(e)  # фон hover/pressed из QSS
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        hovered = self.underMouse()
        col = "#FFFFFF" if (self._kind == 'close' and hovered) else _TEXT_DIM
        pen = QPen(QColor(col))
        pen.setWidthF(1.2)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        # Глифы рисуем в координатах с точкой .5 — так штриховые линии
        # ложатся ровно на пикетную сетку и не «мылятся»/не кажутся кривыми.
        # s — масштаб глифа (учитывает DPI-масштаб экрана).
        s = getattr(self, '_glyph_scale', 1.0)
        if self._kind == 'min':
            # тире как у Windows: 10 px, по центру
            y = int(cy) + 0.5
            half = 5.0 * s
            p.drawLine(QPointF(cx - half, y), QPointF(cx + half, y))
        elif self._kind == 'max':
            # квадрат ~10×10 со стороной на полу-пикселе → чёткие грани
            side = round(10.0 * s)
            x0 = int(cx - side / 2) + 0.5
            y0 = int(cy - side / 2) + 0.5
            p.drawRect(QRectF(x0, y0, side - 1, side - 1))
        elif self._kind == 'restore':
            # два overlapping окна (стиль Windows restore)
            side = round(9.0 * s)
            off = max(2, round(3 * s))
            x0 = int(cx - side / 2) + 0.5
            y0 = int(cy - side / 2 + off / 2) + 0.5
            p.drawRect(QRectF(x0, y0, side - 1, side - 1))
            path = QPainterPath(QPointF(x0 + off, y0))
            path.lineTo(QPointF(x0 + off, y0 - off))
            path.lineTo(QPointF(x0 + side + off - 1, y0 - off))
            path.lineTo(QPointF(x0 + side + off - 1, y0 + side - off))
            path.lineTo(QPointF(x0 + side - 1, y0 + side - off))
            p.drawPath(path)
        elif self._kind == 'close':
            # крестик ~10×10, концы на полу-пикселях — симметричный, без «лесенки»
            half = round(4.5 * s) + 0.5
            x0 = int(cx) + 0.5
            y0 = int(cy) + 0.5
            p.drawLine(QPointF(x0 - half, y0 - half), QPointF(x0 + half, y0 + half))
            p.drawLine(QPointF(x0 + half, y0 - half), QPointF(x0 - half, y0 + half))
        p.end()


class TitleBar(QWidget):
    """Собственная тёмная шапка окна: drag + double-click + controls.

    Архитектура (исправляет «съезжающую» шапку):
      • Шапка — overlay поверх верхней части окна, ширина = width(host),
        высота = _bar_h. Синхронизируется в refresh_geometry() по Resize/Show.
      • Кнопки min/max/close НЕ участвуют в layout'е вообще — их геометрия
        выставляется вручную в resizeEvent (right-to-left, вплотную к правому
        краю). Layout содержит только иконку + заголовок слева, поэтому ни
        один внешний QSS (padding/min-height у QPushButton из темы) не может
        раздуть кнопки и сломать ряд.
      • Собственный QSS шапки понижает специфичность правил окна до нуля для
        её дочерних виджетов (фон/рамка/отступы заданы явно).
    """

    HEIGHT = 36          # базовая высота шапки (лог. px при DPR 1.0)
    BTN_W = 40           # ширина window-control кнопки (как в Windows)
    LEFT_PAD = 10        # отступ слева под иконку/заголовок

    def __init__(self, host: QWidget, with_controls=None):
        # None → controls включены по умолчанию для всех окон (в т.ч. диалогов)
        if with_controls is None:
            with_controls = True
        super().__init__(host)
        self._host = host
        self._dragging = False
        self._drag_pos = QPoint()
        self._with_controls = bool(with_controls)
        self._buttons: tuple = ()   # заполняется ниже, до создания layout'а

        self.setObjectName("appTitleBar")
        # Высота шапки — константа приложения (Qt уже работает в
        # логических DIP-координатах на Windows; умножать ещё раз на DPR
        # означало бы «гигантскую» шапку при 125/150% масштабировании).
        self._bar_h = self.HEIGHT
        self._btn_h = self._bar_h
        try:
            scr = self.screen() or QApplication.primaryScreen()
            dpr = float(scr.devicePixelRatio()) if scr is not None else 1.0
        except Exception:
            dpr = 1.0
        self._dpr = max(1.0, dpr)
        # глифы чуть крупнее на HiDPI, но без искажений пропорций
        self._glyph_scale = max(1.0, min(1.25, self._dpr))
        self.setFixedHeight(self._bar_h)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            #appTitleBar {{ background: {_BG_TITLEBAR}; border: none; }}
            #appTitleBar QLabel {{ background: transparent; border: none;
                                  color: {_TEXT}; font-size: 12px; }}
            #appTitleLabel {{ color: {_TEXT}; font-size: 12px; font-weight: 600;
                             background: transparent; border: none; }}
            #appTitleSub {{ color: {_TEXT_DIM}; font-size: 11px; background: transparent; }}
            #appTitleBar QPushButton {{
                background: transparent; border: none; border-radius: 0;
                color: {_TEXT_DIM}; padding: 0; margin: 0;
            }}
            #appTitleBar QPushButton:hover {{ background: {_HOVER}; }}
            #appTitleBar QPushButton:pressed {{ background: {_PRESSED}; }}
            #appTitleBarClose {{
                background: transparent; border: none; border-radius: 0;
                color: {_TEXT_DIM}; padding: 0; margin: 0;
            }}
            #appTitleBarClose:hover {{ background: {_CLOSE_HOVER}; color: #FFFFFF; }}
            #appTitleBarClose:pressed {{ background: #9d4640; color: #FFFFFF; }}
        """)

        # ── layout ТОЛЬКО для левой части (иконка + заголовок) ──
        lay = QHBoxLayout(self)
        lay.setContentsMargins(self.LEFT_PAD, 0,
                               self._controls_block_width() + 6, 0)
        lay.setSpacing(8)

        self._icon = QLabel()
        self._icon.setObjectName("appTitleIcon")
        self._icon.setFixedSize(18, 18)
        self._icon.setStyleSheet("background: transparent; border: none;")
        self._set_icon_for_title(host.windowTitle())
        lay.addWidget(self._icon)

        self._title = QLabel(_clean_title(host.windowTitle()))
        self._title.setObjectName("appTitleLabel")
        self._title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        lay.addWidget(self._title)
        lay.addStretch(1)

        # ── window controls: вне layout, прибиты к правому краю ──
        if with_controls:
            self.btn_min = _WinBtn('min', self)
            self.btn_max = _WinBtn('max', self)
            self.btn_close = _WinBtn('close', self)
            self.btn_min.clicked.connect(host.showMinimized)
            self.btn_max.clicked.connect(self._toggle_max)
            self.btn_close.clicked.connect(self._close_host)
            self._buttons = (self.btn_min, self.btn_max, self.btn_close)
            for b in self._buttons:
                b._glyph_scale = self._glyph_scale
                b.set_bar_height(self._btn_h)
        else:
            self.btn_min = None
            self.btn_max = None
            self.btn_close = None
            self._buttons = ()

        self._layout_controls()

        def _on_title_changed(t: str):
            self._title.setText(_clean_title(t))
            self._set_icon_for_title(t)

        host.windowTitleChanged.connect(_on_title_changed)

    # ── geometry ──────────────────────────────────────────────
    def _controls_block_width(self) -> int:
        return len(self._buttons) * self.BTN_W if self._buttons else 0

    def _layout_controls(self):
        """Кнопки управления — строго у правого края, справа налево:
        close, max, min. Высотой во всю шапку, как нативные Windows."""
        w = self.width()
        x = w
        for b in reversed(self._buttons):
            bw = self.BTN_W
            x -= bw
            b.setGeometry(x, 0, bw, self._btn_h)
            b.raise_()

    def refresh_geometry(self):
        """Шапка = вся ширина окна, поверх его верхней части."""
        try:
            self.setGeometry(0, 0, max(self._host.width(), 0), self._bar_h)
            self._layout_controls()
            self.raise_()
        except Exception:
            pass

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # пересчитываем правый margin layout'а и позиции кнопок
        self.layout().setContentsMargins(
            self.LEFT_PAD, 0, self._controls_block_width() + 6, 0)
        self._layout_controls()

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh_geometry()

    def _close_host(self):
        """Закрытие окна: exec-диалог закрываем через reject(), остальное — close()."""
        w = self._host
        try:
            from PyQt6.QtWidgets import QDialog
            if isinstance(w, QDialog) and w.isModal():
                w.reject()
                return
        except Exception:
            pass
        w.close()

    # ── brand/title icon ──
    def _set_icon_for_title(self, title: str):
        name = icon_names_for_label(title or "")
        pm = make_icon(name or "brand", _TEXT_DIM, 18).pixmap(QSize(18, 18))
        if not pm.isNull():
            self._icon.setPixmap(pm)

    # ── maximize / restore ──
    def _toggle_max(self):
        w = self._host
        if w.isMaximized():
            w.showNormal()
        else:
            w.showMaximized()
        # сразу пересобираем геометрию шапки под новый размер окна
        QTimer.singleShot(0, self.refresh_geometry)

    def sync_max_button(self):
        if self.btn_max is not None:
            self.btn_max._kind = 'restore' if self._host.isMaximized() else 'max'
            self.btn_max.update()

    # ── drag & double click ──
    def _grab_offset(self, e) -> QPoint:
        """Смещение курсора от левого верхнего угла CLIENT-видимой области окна.

        geometry() — это client area (без нативной рамки/тени), поэтому
        корректно и для окон с WS_THICKFRAME, и для полностью frameless.
        """
        return e.globalPosition().toPoint() - self._host.geometry().topLeft()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            w = self._host
            if w.isMaximized():
                # при перетаскивании развёрнутого окна — вернуть в normal
                ratio = e.position().x() / max(1, self.width())
                w.showNormal()
                geo = w.geometry()
                w.move(int(e.globalPosition().x() - geo.width() * ratio),
                       int(e.globalPosition().y() - self._bar_h // 2))
            self._dragging = True
            self._drag_pos = self._grab_offset(e)
            e.accept()

    def mouseMoveEvent(self, e):
        if self._dragging and e.buttons() & Qt.MouseButton.LeftButton:
            self._host.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._dragging = False

    def mouseDoubleClickEvent(self, e):
        if self._with_controls:
            self._toggle_max()

    # ── painting ──
    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setPen(QPen(QColor(_BORDER)))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        p.end()


class ResizeHelper(QObject):
    """Ресайз frameless-окна за края (работает и в normal, и в maximized)."""

    MARGIN = 6

    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self._press_global = QPoint()
        self._start_geo = None
        self._edges = 0  # bitmask: 1 left, 2 right, 4 top, 8 bottom
        win.setMouseTracking(True)
        for child in win.findChildren(QWidget):
            try:
                child.setMouseTracking(True)
            except Exception:
                pass

    # edge detection ─────────────────────────────────────────
    def _edge_at(self, pos: QPoint) -> int:
        m = self.MARGIN
        r = self._win.rect()
        edges = 0
        if pos.x() <= m:
            edges |= 1
        if pos.x() >= r.width() - m:
            edges |= 2
        if pos.y() <= m:
            edges |= 4
        if pos.y() >= r.height() - m:
            edges |= 8
        return edges

    def eventFilter(self, obj, e):
        et = e.type()
        if et == QEvent.Type.MouseMove:
            if self._edges and (e.buttons() & Qt.MouseButton.LeftButton):
                self._resize_to(e.globalPosition().toPoint())
                return False
            pos = e.position().toPoint()
            cur = self._cursor_for(self._edge_at(pos))
            if cur is not None:
                self._win.setCursor(cur)
            else:
                self._win.unsetCursor()
            return False
        if et == QEvent.Type.MouseButtonPress and e.button() == Qt.MouseButton.LeftButton:
            pos = e.position().toPoint()
            self._edges = self._edge_at(pos)
            if self._edges:
                self._press_global = e.globalPosition().toPoint()
                self._start_geo = self._win.geometry()
                return True
        if et == QEvent.Type.MouseButtonRelease:
            self._edges = 0
        return False

    def _cursor_for(self, edges: int):
        if edges == 1 or edges == 2:
            return QCursor(Qt.CursorShape.SizeHorCursor)
        if edges == 4 or edges == 8:
            return QCursor(Qt.CursorShape.SizeVerCursor)
        if edges in (5, 10):
            return QCursor(Qt.CursorShape.SizeFDiagCursor)
        if edges in (6, 9):
            return QCursor(Qt.CursorShape.SizeBDiagCursor)
        return None

    def _resize_to(self, gp: QPoint):
        w = self._win
        g = self._start_geo
        dx = gp.x() - self._press_global.x()
        dy = gp.y() - self._press_global.y()
        min_w = w.minimumWidth() if w.minimumWidth() > 0 else 400
        min_h = w.minimumHeight() if w.minimumHeight() > 0 else 300
        x, y = g.x(), g.y()
        ww, hh = g.width(), g.height()
        if self._edges & 1:
            nw = max(min_w, ww - dx)
            x = g.x() + (ww - nw)
            ww = nw
        if self._edges & 2:
            ww = max(min_w, ww + dx)
        if self._edges & 4:
            nh = max(min_h, hh - dy)
            y = g.y() + (hh - nh)
            hh = nh
        if self._edges & 8:
            hh = max(min_h, hh + dy)
        w.setGeometry(x, y, ww, hh)


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

# Примечание: нативная полоса Windows снимается ИСКЛЮЧИТЕЛЬНО флагом Qt
# FramelessWindowHint. Прямые вызовы SetWindowLong/SetWindowPos и
# subclass'инг WNDPROC были удалены — именно они вызывали разрушение
# стека и краш процесса (exit code 0xC0000409) на Windows x64.


# ─────────────────────────────────────────────────────────────
# Единый стиль для нативных попапов: QMessageBox / QFileDialog / QMenu
# (ставим Fusion + стили через app stylesheet — диалоги наследуют его).
# ─────────────────────────────────────────────────────────────

_POPUP_QSS = f"""
    QMessageBox, QDialog {{ background: {_BG_WINDOW}; color: {_TEXT}; }}
    QMessageBox QLabel {{ background: transparent; color: {_TEXT}; font-size: 10pt; }}
    QMessageBox QPushButton, QDialog QPushButton {{
        background: {_BG_TITLEBAR}; color: {_TEXT};
        border: 1px solid {_BORDER}; border-radius: 6px;
        padding: 6px 18px; min-width: 72px; font-weight: 600;
    }}
    QMessageBox QPushButton:hover, QDialog QPushButton:hover {{
        background: {_HOVER}; border-color: #4A4A55;
    }}
    QMessageBox QPushButton:pressed, QDialog QPushButton:pressed {{
        background: {_PRESSED};
    }}
    QMessageBox QPushButton:default {{
        background: #3A6D8F; border-color: #4E86AC; color: #FFFFFF;
    }}
    QMessageBox QPushButton:default:hover {{ background: #44799C; }}
    QFileDialog {{ background: {_BG_WINDOW}; }}
    QFileDialog QLabel {{ background: transparent; color: {_TEXT_DIM}; }}
    QFileDialog QLineEdit#nameFilterLineEdit,
    QFileDialog QLineEdit {{
        background: #1A1A1F; color: {_TEXT};
        border: 1px solid {_BORDER}; border-radius: 6px; padding: 5px 8px;
    }}
    QFileDialog QListView, QFileDialog QTreeView {{
        background: #1A1A1F; alternate-background-color: #212127;
        color: {_TEXT}; border: 1px solid {_BORDER}; border-radius: 6px;
        outline: none; selection-background-color: #3A6D8F;
        selection-color: #FFFFFF;
    }}
    QFileDialog QComboBox {{
        background: {_BG_TITLEBAR}; color: {_TEXT};
        border: 1px solid {_BORDER}; border-radius: 6px; padding: 4px 8px;
    }}
    QMenu {{
        background: {_BG_TITLEBAR}; color: {_TEXT};
        border: 1px solid {_BORDER}; border-radius: 8px; padding: 4px;
    }}
    QMenu::item {{ padding: 6px 22px; border-radius: 5px; background: transparent; }}
    QMenu::item:selected {{ background: {_HOVER}; }}
    QMenu::separator {{ height: 1px; background: {_BORDER}; margin: 4px 8px; }}
    QToolTip {{
        background: {_BG_TITLEBAR}; color: {_TEXT};
        border: 1px solid {_BORDER}; border-radius: 5px; padding: 4px 8px;
    }}
"""


def style_app_popups(app) -> None:
    """Единый тёмный стиль для всех всплывающих окон приложения
    (QMessageBox, QFileDialog, QMenu, тултипы). Наследуется дочерними окнами."""
    try:
        from PyQt6.QtWidgets import QApplication, QStyleFactory
        app.setStyle(QStyleFactory.create("Fusion"))
    except Exception:
        pass
    try:
        base = app.styleSheet()
        if "#appPopupStyleRoot" not in base:
            app.setStyleSheet(base + "\n/* appPopupStyleRoot */\n" + _POPUP_QSS)
    except Exception:
        pass


def force_non_native_dialogs() -> None:
    """Глобально отключает нативные Windows-диалоги файлов/папок.

    QFileDialog больше не создаёт нативное окно Windows (со своей белой
    полосой и крестиками) — всегда рисуется Qt в теме приложения.
    Реализация: переопределяем статический getSaveFileName / getOpenFileName
    / getExistingDirectory с предустановленным DontUseNativeDialog.
    """
    try:
        from PyQt6.QtWidgets import QFileDialog

        _DontNative = QFileDialog.Option.DontUseNativeDialog
        orig_save = QFileDialog.getSaveFileName
        orig_open = QFileDialog.getOpenFileName
        orig_openf = QFileDialog.getOpenFileNames
        orig_dir = QFileDialog.getExistingDirectory

        def getSaveFileName(*a, **kw):
            kw['options'] = kw.get('options', QFileDialog.Option()) | _DontNative
            return orig_save(*a, **kw)

        def getOpenFileName(*a, **kw):
            kw['options'] = kw.get('options', QFileDialog.Option()) | _DontNative
            return orig_open(*a, **kw)

        def getOpenFileNames(*a, **kw):
            kw['options'] = kw.get('options', QFileDialog.Option()) | _DontNative
            return orig_openf(*a, **kw)

        def getExistingDirectory(*a, **kw):
            kw['options'] = kw.get('options', QFileDialog.Option()) | _DontNative
            return orig_dir(*a, **kw)

        QFileDialog.getSaveFileName = staticmethod(getSaveFileName)
        QFileDialog.getOpenFileName = staticmethod(getOpenFileName)
        QFileDialog.getOpenFileNames = staticmethod(getOpenFileNames)
        QFileDialog.getExistingDirectory = staticmethod(getExistingDirectory)
    except Exception:
        pass


def apply_frameless(win, with_controls: bool = True, add_shadow: bool = True):
    """Делает окно безрамочным в стиле приложения. Идемпотентно.

    Реализация — только средствами Qt (FramelessWindowHint + собственный
    titlebar + ResizeHelper). Никаких ctypes/WNDPROC-хуков: они вызывали
    краш 0xC0000409 на Windows.

    Вызывать ДО первого show() окна — тогда белая нативная полоса
    не появляется даже на кадр.
    """
    if getattr(win, "_bgs_titlebar", None) is not None:
        return win

    # 1) Убираем нативную полосу заголовка Windows (белая полоса с
    #    крестиками) — штатным флагом Qt. Делаем это ДО создания любых
    #    дочерних виджетов и ДО show(), чтобы окно один раз пересоздалось
    #    без WS_CAPTION и не мелькала нативная шапка.
    # СТАЛО: только если флаг ещё не стоит (иначе Qt пересоздаст окно и
    # invalidates любые QGraphicsOpacityEffect-кэши на дочерних виджетах).
    try:
        if not (win.windowFlags() & Qt.WindowType.FramelessWindowHint):
            win.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    except Exception:
        pass

    # Единый фон окна (в т.ч. под собственной шапкой) — из палитры темы
    win.setStyleSheet(
        win.styleSheet() + f"""
        #framelessRoot, #framelessBody {{ background: {_BG_WINDOW}; }}
        QMainWindow, QDialog {{ background: {_BG_WINDOW}; }}
        """)

    # 2) Собственный titlebar
    bar = TitleBar(win, with_controls=with_controls)
    win._bgs_titlebar = bar

    if isinstance(win, QMainWindow):
        old = win.takeCentralWidget()
        wrap = QWidget()
        wrap.setObjectName("framelessRoot")
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, bar.height(), 0, 0)
        v.setSpacing(0)
        if old is not None:
            v.addWidget(old, 1)
        win.setCentralWidget(wrap)
    elif isinstance(win, QDialog):
        old_lay = win.layout()
        if old_lay is not None:
            # Простой и надёжный вариант: НЕ трогаем layout содержимого
            # dialog'а, а добавляем сверху отступ под overlay-шапку.
            m_ = old_lay.contentsMargins()
            old_lay.setContentsMargins(m_.left(), m_.top() + bar.height(),
                                       m_.right(), m_.bottom())
        else:
            body = QWidget(win)
            body.setObjectName("framelessBody")
            v = QVBoxLayout(win)
            v.setContentsMargins(0, bar.height(), 0, 0)
            v.setSpacing(0)
            v.addWidget(body, 1)
    else:
        raise TypeError("apply_frameless поддерживает QMainWindow/QDialog")

    # 2c) Шапка — поверх верхней части окна, всегда на всю ширину;
    #     кнопки гарантированно справа, layout содержимого их не сдвигает.
    bar.setParent(None)
    bar.setParent(win)
    _BarOverlaySync(win, bar)
    bar.refresh_geometry()
    bar.show()
    bar.raise_()

    # 3) Разделитель под шапкой рисует сама TitleBar (paintEvent);
    #    QGraphicsDropShadowEffect на неё НЕ вешаем: у overlay-шапки,
    #    перекрывающей край окна, эффект обрезает тень и при каждом
    #    resize заставляет Qt пересоздавать offscreen-буфер — это один
    #    из источников нестабильности на Windows.
    overlay = _FrameOverlay(win)
    overlay.setGeometry(win.rect())
    win._bgs_overlay = overlay
    win.installEventFilter(_GeoSync(win, overlay))

    # 4) Resizer по краям — реализован только средствами Qt и работает
    #    одинаково на всех платформах (frameless-окна без нативного
    #    hit-test'а рамок).
    helper = ResizeHelper(win)
    win.installEventFilter(helper)
    for c in win.findChildren(QWidget):
        if c is not bar and not isinstance(c, _WinBtn):
            c.installEventFilter(helper)
    win._bgs_resizer = helper

    # 5) Синхронизация кнопки max/restore
    win.installEventFilter(_MaxSync(win))

    return win


class _BarOverlaySync(QObject):
    """Держит overlay-шапку во всю ширину окна и поверх содержимого."""

    def __init__(self, win, bar):
        super().__init__(win)
        self._bar = bar
        win.installEventFilter(self)

    def eventFilter(self, obj, e):
        t = e.type()
        if t in (QEvent.Type.Resize, QEvent.Type.Show):
            self._bar.refresh_geometry()
        return False


class _FrameOverlay(QWidget):
    """Тонкая рамка цвета темы поверх всего содержимого окна."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.lower()

    def paintEvent(self, e):
        p = QPainter(self)
        pen = QPen(QColor(_BORDER))
        pen.setWidth(1)
        p.setPen(pen)
        r = self.rect().adjusted(0, 0, -1, -1)
        p.drawRect(r)
        p.end()


class _GeoSync(QObject):
    """Держит overlay-рамку в размере окна."""

    def __init__(self, win, overlay):
        super().__init__(win)
        self._overlay = overlay

    def eventFilter(self, obj, e):
        if e.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self._overlay.setGeometry(obj.rect())
        return False


class _MaxSync(QObject):
    """Переключает иконку maximize/restore при смене состояния окна."""

    def __init__(self, win):
        super().__init__(win)
        self._bar = win._bgs_titlebar

    def eventFilter(self, obj, e):
        if e.type() == QEvent.Type.WindowStateChange:
            # состояние обновится после обработки события окном
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self._bar.sync_max_button)
        return False
