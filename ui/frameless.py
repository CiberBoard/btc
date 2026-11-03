# ui/frameless.py
# 🪟 Frameless-окна в едином стиле приложения:
#    - собственный тёмный titlebar (drag, maximize, close) поверх контента;
#    - на Windows дополнительно срезаем нативные WS_CAPTION/WS_THICKFRAME
#      через WM_WINDOWPOSCHANGING (без DWM-щелей и белой полосы);
#    - корректный maximize без перекрытия taskbar (WM_GETMINMAXINFO);
#    - перетаскивание за окно, двойной клик = свернуть/развернуть.
from __future__ import annotations

import ctypes
import sys

from PyQt6.QtCore import Qt, QPoint, QSize, QRectF, QObject, QEvent, QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QCursor
from PyQt6.QtWidgets import (
    QWidget, QMainWindow, QDialog, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QGraphicsDropShadowEffect,
)

from ui.theme import COLORS
from ui.nav_icons import make_icon, icon_names_for_label

_IS_WIN = sys.platform == "win32"

if _IS_WIN:
    try:
        from ctypes import windll, wintypes, byref, sizeof, cast, POINTER

        _GWL_STYLE = -16
        _WS_CAPTION = 0x00C00000
        _WS_THICKFRAME = 0x00040000
        _WS_SYSMENU = 0x00080000
        _SWP_FLAGS = 0x0002 | 0x0001 | 0x0020 | 0x0004  # NOSIZE|NOMOVE|NOZORDER|FRAMECHANGED

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class MINMAXINFO(ctypes.Structure):
            _fields_ = [("ptReserved", POINT), ("ptMaxSize", POINT),
                        ("ptMaxPosition", POINT), ("ptMinTrackSize", POINT),
                        ("ptMaxTrackSize", POINT)]

        class WINDOWPOS(ctypes.Structure):
            _fields_ = [("hwnd", wintypes.HWND), ("hwndInsertAfter", wintypes.HWND),
                        ("x", ctypes.c_int), ("y", ctypes.c_int),
                        ("cx", ctypes.c_int), ("cy", ctypes.c_int),
                        ("flags", wintypes.UINT)]

        _WM_GETMINMAXINFO = 0x0024
        _WM_WINDOWPOSCHANGING = 0x0046
        _MONITOR_DEFAULTTONEAREST = 0x00000002

        _user32 = windll.user32
        _GetWindowLongW = _user32.GetWindowLongW
        _SetWindowLongW = _user32.SetWindowLongW
        _DefWindowProcW = _user32.DefWindowProcW
        _SetWindowPos = _user32.SetWindowPos
        _MonitorFromWindow = _user32.MonitorFromWindow

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                        ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]

        _GetMonitorInfoW = _user32.GetMonitorInfoW
        _WIN_SUBCLASS_AVAILABLE = True
    except Exception:
        _WIN_SUBCLASS_AVAILABLE = False
else:
    _WIN_SUBCLASS_AVAILABLE = False


# ─────────────────────────────────────────────────────────────
# Win32: subclass WNDPROC — только для WM_GETMINMAXINFO,
# чтобы maximize не перекрывал taskbar (work area монитора).
# ─────────────────────────────────────────────────────────────

_SUBCLASSES = {}  # hwnd -> (callback, holder) — не даём GC собрать callback

if _WIN_SUBCLASS_AVAILABLE:
    from ctypes import WINFUNCTYPE

    _SUBCLASS_PROC_TYPE = WINFUNCTYPE(
        wintypes.LPARAM,           # LRESULT (64-bit safe)
        wintypes.HWND, wintypes.UINT,
        wintypes.WPARAM, wintypes.LPARAM)

    _SetWindowLongPtrW = _user32.SetWindowLongPtrW
    _SetWindowLongPtrW.restype = wintypes.LPARAM
    _SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    _CallWindowProcW = _user32.CallWindowProcW
    _CallWindowProcW.restype = wintypes.LPARAM
    _CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND,
                                 wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    _GetWindowLongW.restype = wintypes.LONG
    _SetWindowLongW.restype = wintypes.LONG

    def _install_win_hooks(win):
        """Subclass WNDPROC: чиним maximize под taskbar через WM_GETMINMAXINFO."""
        try:
            hwnd = int(win.winId())
            if hwnd in _SUBCLASSES:
                return

            holder = {}

            def wnd_proc(h, msg, wparam, lparam):
                try:
                    if msg == _WM_GETMINMAXINFO:
                        mmi = cast(lparam, POINTER(MINMAXINFO)).contents
                        mon = _MonitorFromWindow(h, _MONITOR_DEFAULTTONEAREST)
                        mi = MONITORINFO()
                        mi.cbSize = sizeof(MONITORINFO)
                        if _GetMonitorInfoW(mon, byref(mi)):
                            mmi.ptMaxPosition.x = mi.rcWork.left - mi.rcMonitor.left
                            mmi.ptMaxPosition.y = mi.rcWork.top - mi.rcMonitor.top
                            mmi.ptMaxSize.x = mi.rcWork.right - mi.rcWork.left
                            mmi.ptMaxSize.y = mi.rcWork.bottom - mi.rcWork.top
                        return 0
                except Exception:
                    pass
                return _CallWindowProcW(holder['old'], h, msg, wparam, lparam)

            cb = _SUBCLASS_PROC_TYPE(wnd_proc)
            old = _SetWindowLongPtrW(hwnd, -8, ctypes.cast(cb, ctypes.c_void_p))
            holder['old'] = old
            _SUBCLASSES[hwnd] = (cb, holder)
        except Exception:
            pass


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
    """Миниатюрная кнопка window controls (28×20), рисует символ через QPainter."""

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self._kind = kind  # 'min' | 'max' | 'restore' | 'close'
        self.setFixedSize(30, 22)
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.setStyleSheet(_CLOSE_QSS if kind == 'close' else _BTN_QSS)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, e):
        super().paintEvent(e)  # фон hover/pressed из QSS
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        hovered = self.underMouse()
        col = "#FFFFFF" if (self._kind == 'close' and hovered) else _TEXT_DIM
        pen = QPen(QColor(col))
        pen.setWidthF(1.3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        cx, cy = self.width() / 2, self.height() / 2
        if self._kind == 'min':
            p.drawLine(QPoint(int(cx - 5), int(cy)), QPoint(int(cx + 5), int(cy)))
        elif self._kind == 'max':
            p.drawRect(QRectF(cx - 5, cy - 4.5, 10, 9))
        elif self._kind == 'restore':
            p.drawRect(QRectF(cx - 5, cy - 2.5, 8, 7))
            path = QPainterPath()
            path.moveTo(cx - 2, cy - 3.5)
            path.lineTo(cx - 2, cy - 5.5)
            path.lineTo(cx + 5, cy - 5.5)
            path.lineTo(cx + 5, cy + 1.5)
            path.lineTo(cx + 3, cy + 1.5)
            p.drawPath(path)
        elif self._kind == 'close':
            p.drawLine(QPoint(int(cx - 5), int(cy - 4)), QPoint(int(cx + 5), int(cy + 4)))
            p.drawLine(QPoint(int(cx + 5), int(cy - 4)), QPoint(int(cx - 5), int(cy + 4)))
        p.end()


class TitleBar(QWidget):
    """Собственная тёмная шапка окна: drag + double-click + controls.

    Управление окном доступно всегда (перемещение мышью, двойной клик),
    кнопки min/max/close скрываются только если явно передан
    with_controls=False — по умолчанию они есть на КАЖДОМ окне приложения,
    включая диалоги, в едином стиле темы.
    """

    HEIGHT = 36

    def __init__(self, host: QWidget, with_controls=None):
        # None → controls включены по умолчанию для всех окон (в т.ч. диалогов)
        if with_controls is None:
            with_controls = True
        super().__init__(host)
        self._host = host
        self._dragging = False
        self._drag_pos = QPoint()
        self._with_controls = bool(with_controls)

        self.setObjectName("appTitleBar")
        self.setFixedHeight(self.HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            #appTitleBar {{ background: {_BG_TITLEBAR}; }}
            #appTitleLabel {{ color: {_TEXT}; font-size: 12px; font-weight: 600;
                             background: transparent; }}
            #appTitleSub {{ color: {_TEXT_DIM}; font-size: 11px; background: transparent; }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 6, 0)
        lay.setSpacing(8)

        self._icon = QLabel()
        self._icon.setFixedSize(18, 18)
        self._icon.setScaledContents(True)
        self._icon.setStyleSheet("background: transparent;")
        self._set_icon_for_title(host.windowTitle())
        lay.addWidget(self._icon)

        self._title = QLabel(_clean_title(host.windowTitle()))
        self._title.setObjectName("appTitleLabel")
        lay.addWidget(self._title)
        lay.addStretch(1)

        if with_controls:
            self.btn_min = _WinBtn('min', self)
            self.btn_max = _WinBtn('max', self)
            self.btn_close = _WinBtn('close', self)
            self.btn_min.clicked.connect(host.showMinimized)
            self.btn_max.clicked.connect(self._toggle_max)
            self.btn_close.clicked.connect(self._close_host)
            lay.addWidget(self.btn_min)
            lay.addWidget(self.btn_max)
            lay.addWidget(self.btn_close)
        else:
            self.btn_min = None
            self.btn_max = None
            self.btn_close = None

        def _on_title_changed(t: str):
            self._title.setText(_clean_title(t))
            self._set_icon_for_title(t)

        host.windowTitleChanged.connect(_on_title_changed)

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
                       int(e.globalPosition().y() - self.HEIGHT // 2))
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

if _WIN_SUBCLASS_AVAILABLE:
    _DWMWA_EXTENDED_FRAME_BOUNDS = 9
    _DwmGetWindowAttribute = windll.dwmapi.DwmGetWindowAttribute
    _DwmGetWindowAttribute.restype = ctypes.HRESULT if hasattr(ctypes, "HRESULT") else ctypes.c_long

    def _strip_native_caption(win):
        """Гарантированно снимает нативную полосу заголовка Windows.

        ДВА взаимодополняющих способа (применяются оба):
          1) Флаг Qt FramelessWindowHint — самый надёжный: Qt сама
             пересоздаёт окно без WS_CAPTION/WS_TITLEBAR на любой стадии.
          2) Прямой SetWindowLongW(GWL_STYLE, ...) со снятием
             WS_CAPTION|WS_SYSMENU и сохранением WS_THICKFRAME
             (нативный resize/snap остаётся работает).
        Применяется ДО show(), поэтому белая полоса не мелькает при старте.
        """
        try:
            win.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        except Exception:
            pass
        try:
            hwnd = int(win.winId())
            styles = _GetWindowLongW(hwnd, _GWL_STYLE)
            new = (styles & ~(_WS_CAPTION | _WS_SYSMENU)) | _WS_THICKFRAME
            if new != styles:
                _SetWindowLongW(hwnd, _GWL_STYLE, new)
                _SetWindowPos(hwnd, 0, 0, 0, 0, 0, _SWP_FLAGS)
        except Exception:
            pass

    def _ensure_no_caption(win):
        """Повторная страховка после show()/showEvent(): если Windows или Qt
        вернули WS_CAPTION (например, после showMaximized), снова срезаем его."""
        try:
            if not win.isVisible():
                return
            hwnd = int(win.winId())
            styles = _GetWindowLongW(hwnd, _GWL_STYLE)
            if styles & _WS_CAPTION:
                _SetWindowLongW(hwnd, _GWL_STYLE,
                                (styles & ~(_WS_CAPTION | _WS_SYSMENU)) | _WS_THICKFRAME)
                _SetWindowPos(hwnd, 0, 0, 0, 0, 0, _SWP_FLAGS)
        except Exception:
            pass


class _CaptionGuard(QObject):
    """Следит, чтобы нативный caption не возвращался при show/resize/state."""

    def __init__(self, win):
        super().__init__(win)
        self._win = win

    def eventFilter(self, obj, e):
        t = e.type()
        if t in (QEvent.Type.Show, QEvent.Type.WindowStateChange, QEvent.Type.Resize):
            QTimer.singleShot(0, lambda: _ensure_no_caption(self._win))
        return False


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

    Вызывать ДО первого show() окна — тогда белая нативная полоса
    не появляется даже на кадр.
    """
    if getattr(win, "_bgs_titlebar", None) is not None:
        return win

    # 1) Убираем нативную Windows-полосу заголовка (крестики/белая полоса):
    #    FramelessWindowHint + снятие WS_CAPTION|WS_SYSMENU (оставляем
    #    WS_THICKFRAME — Qt/native обрабатывают resize/snap, а drag по краю
    #    работает штатно).
    if _WIN_SUBCLASS_AVAILABLE:
        _strip_native_caption(win)
        win.installEventFilter(_CaptionGuard(win))
    elif _IS_WIN:
        try:
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
        old = win.centralWidget()
        wrap = QWidget()
        wrap.setObjectName("framelessRoot")
        v = QHBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(bar)
        if old is not None:
            v.addWidget(old, 1)
        win.setCentralWidget(wrap)
    elif isinstance(win, QDialog):
        old_lay = win.layout()
        # оборачиваем исходный layout dialog'а во внутренний widget
        body = QWidget(win)
        body.setObjectName("framelessBody")
        if old_lay is not None:
            moved = False
            try:
                win.takeLayout()          # Qt >= 6.4
                moved = True
            except AttributeError:
                pass                      # нет takeLayout — старый layout
                                          # переедет на body ниже сам
            if moved:
                body_lay = QVBoxLayout(body)
                body_lay.setContentsMargins(0, 0, 0, 0)
                body_lay.setSpacing(0)
                body_lay.addLayout(old_lay)
            else:
                # takeLayout недоступен: НЕ отвязываем старый layout от dialog
                # (в этой версии PyQt его нельзя удалить корректно). Вместо это
                # переносим все item'ы в новый layout поверх body, а у dialog
                # переиспользуем ОСТАВШИЙСЯ пустой layout под [bar, body].
                new_host_lay = type(old_lay)(body)
                try:
                    m_ = old_lay.contentsMargins()
                    new_host_lay.setContentsMargins(m_.left(), m_.top(), m_.right(), m_.bottom())
                except Exception:
                    pass
                try:
                    new_host_lay.setSpacing(old_lay.spacing())
                except Exception:
                    pass
                while old_lay.count():
                    new_host_lay.addItem(old_lay.takeAt(0))
                # old_lay теперь пустой, но всё ещё layout dialog'а —
                # наполним им структуру окна вместо создания нового layout
                v = old_lay
                v.addWidget(bar)
                v.addWidget(body, 1)
        else:
            v = QHBoxLayout(win)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(0)
            v.addWidget(bar)
            v.addWidget(body, 1)
    else:
        raise TypeError("apply_frameless поддерживает QMainWindow/QDialog")

    # 3) Тень под шапкой + тонкая рамка всего окна
    sh = QGraphicsDropShadowEffect(bar)
    sh.setBlurRadius(14)
    sh.setOffset(0, 2)
    sh.setColor(QColor(0, 0, 0, 90))
    bar.setGraphicsEffect(sh)

    overlay = _FrameOverlay(win)
    overlay.setGeometry(win.rect())
    win._bgs_overlay = overlay
    win.installEventFilter(_GeoSync(win, overlay))

    # 4) Resizer по краям — только если Windows-хуки недоступны
    #    (иначе нативный hit-test сам даёт resize/snap по краям)
    if not _WIN_SUBCLASS_AVAILABLE:
        helper = ResizeHelper(win)
        win.installEventFilter(helper)
        for c in win.findChildren(QWidget):
            if c is not bar and not isinstance(c, _WinBtn):
                c.installEventFilter(helper)
        win._bgs_resizer = helper

    # 5) Синхронизация кнопки max/restore
    win.installEventFilter(_MaxSync(win))

    # 6) Win32: снимаем WS_CAPTION/WS_THICKFRAME через subclass WNDPROC,
    #    чиним maximize под taskbar через WM_GETMINMAXINFO.
    if _WIN_SUBCLASS_AVAILABLE:
        if win.isVisible():
            _install_win_hooks(win)
        else:
            win.showEvent = _wrap_show_install_hooks(win)  # type: ignore
    return win


def _wrap_show_install_hooks(win):
    original = win.showEvent

    def show_event(e):
        original(e)
        _install_win_hooks(win)

    return show_event


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
