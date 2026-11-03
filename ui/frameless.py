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
    """Собственная тёмная шапка окна: drag + double-click + controls."""

    HEIGHT = 36

    def __init__(self, host: QWidget, with_controls: bool = True):
        super().__init__(host)
        self._host = host
        self._dragging = False
        self._drag_pos = QPoint()
        self._with_controls = with_controls

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
            self.btn_close.clicked.connect(host.close)
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
            self._drag_pos = e.globalPosition().toPoint() - w.frameGeometry().topLeft()
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

class _PolishedWatcher(QObject):
    """После show() окна пересчитываем нативный frame (снимает WS_CAPTION)."""

    def __init__(self, win):
        super().__init__(win)
        self._win = win

    def eventFilter(self, obj, e):
        if e.type() == QEvent.Type.Show:
            QTimer.singleShot(0, self._repolish)
        return False

    def _repolish(self):
        try:
            self._win.windowHandle().frameStrutChanged()
        except Exception:
            pass


def apply_frameless(win, with_controls: bool = True, add_shadow: bool = True):
    """Делает окно безрамочным в стиле приложения. Идемпотентно."""
    if getattr(win, "_bgs_titlebar", None) is not None:
        return win

    # 1) Убираем нативную Windows-полосу заголовка (крестики/белая полоса).
    #    Снимаем WS_CAPTION|WS_SYSMENU, оставляем WS_THICKFRAME — тогда
    #    Qt сама обрабатывает native resize/snap, а QWindow.frameGeometry
    #    корректно учитывает толщину рамки.
    if _IS_WIN:
        try:
            hwnd = int(win.winId())
            styles = windll.user32.GetWindowLongW(hwnd, _GWL_STYLE)
            windll.user32.SetWindowLongW(
                hwnd, _GWL_STYLE,
                (styles & ~(_WS_CAPTION | _WS_SYSMENU)) | _WS_THICKFRAME)
            windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, _SWP_FLAGS)
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
            win.takeLayout()          # отвязываем старый layout от dialog
            body_lay = QVBoxLayout(body)
            body_lay.setContentsMargins(0, 0, 0, 0)
            body_lay.setSpacing(0)
            body_lay.addLayout(old_lay)
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
