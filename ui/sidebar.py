# ui/sidebar.py
# 🧭 Боковое меню (sidebar) для вкладок + анимации переходов между страницами.
# Использует существующий QTabWidget как контейнер страниц: tabBar просто
# скрыт, переключение идёт через кнопки меню — логика приложения не меняется.
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QPoint, QRect, QTimer, pyqtSignal,
    pyqtProperty, QObject
)
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPen
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTabWidget, QGraphicsOpacityEffect, QSizePolicy
)

from ui.theme import COLORS as C


def _f(c: str, alpha: int) -> str:
    """#RRGGBBAA из hex-цвета."""
    return f"{c}{max(0, min(255, alpha)):02X}"


def _pen(color, w):
    pen = QPen(color)
    pen.setWidthF(w)
    return pen


class NavButton(QPushButton):
    """Кнопка пункта бокового меню с анимациями hover/selected."""

    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(parent)
        self.setText(f"{icon}  {text}")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(42)
        self.setProperty("cssClass", "navItem")

        self._hover_t = 0.0     # 0..1 прогресс наведения
        self._select_t = 0.0    # 0..1 прогресс выбора
        self._press_t = 0.0     # 0..1 «ripple» при клике

        self._anim_hover = QPropertyAnimation(self, b"hoverT", self)
        self._anim_hover.setDuration(180)
        self._anim_hover.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_select = QPropertyAnimation(self, b"selectT", self)
        self._anim_select.setDuration(300)
        self._anim_select.setEasingCurve(QEasingCurve.Type.OutQuart)

        self._anim_press = QPropertyAnimation(self, b"pressT", self)
        self._anim_press.setDuration(380)
        self._anim_press.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.toggled.connect(self._on_toggled)

    # --- dynamic properties for QPropertyAnimation ---
    def get_hoverT(self):
        return self._hover_t

    def set_hoverT(self, v):
        self._hover_t = v
        self.update()

    hoverT = pyqtProperty(float, fget=get_hoverT, fset=set_hoverT)

    def get_selectT(self):
        return self._select_t

    def set_selectT(self, v):
        self._select_t = v
        self.update()

    selectT = pyqtProperty(float, fget=get_selectT, fset=set_selectT)

    def get_pressT(self):
        return self._press_t

    def set_pressT(self, v):
        self._press_t = v
        self.update()

    pressT = pyqtProperty(float, fget=get_pressT, fset=set_pressT)

    def _on_toggled(self, checked: bool):
        self._anim_select.stop()
        self._anim_select.setStartValue(self._select_t)
        self._anim_select.setEndValue(1.0 if checked else 0.0)
        self._anim_select.start()

    def enterEvent(self, e):
        self._anim_hover.stop()
        self._anim_hover.setStartValue(self._hover_t)
        self._anim_hover.setEndValue(1.0)
        self._anim_hover.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._anim_hover.stop()
        self._anim_hover.setStartValue(self._hover_t)
        self._anim_hover.setEndValue(0.0)
        self._anim_hover.start()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        self._anim_press.stop()
        self._press_t = 0.0
        self._anim_press.setStartValue(0.0)
        self._anim_press.setEndValue(1.0)
        self._anim_press.start()
        super().mousePressEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)

        # фон pill: прозрачный → лёгкий hover → выбранный градиент
        base = QColor(255, 255, 255, int(6 + 14 * self._hover_t))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(base)
        p.drawRoundedRect(r, 9, 9)

        if self._select_t > 0.01:
            t = self._select_t
            grad = QLinearGradient(0, r.top(), 0, r.bottom())
            g0 = QColor('#2E2E37'); g0.setAlpha(int(255 * t))
            g1 = QColor('#3A3A44'); g1.setAlpha(int(255 * t))
            grad.setColorAt(0, g1)
            grad.setColorAt(1, g0)
            p.setBrush(grad)
            p.setPen(_pen(QColor(C['border']), 1.0 * t))
            p.drawRoundedRect(r, 9, 9)
        elif self._hover_t > 0.01:
            hv = QColor(C['bg_hover'])
            hv.setAlpha(int(160 * self._hover_t))
            p.setBrush(hv)
            p.drawRoundedRect(r, 9, 9)

        # ripple — волна от левого края при клике
        if 0.0 < self._press_t < 1.0:
            rp = QColor(C['accent_primary'])
            rp.setAlpha(int(70 * (1.0 - self._press_t)))
            w = int(r.width() * self._press_t)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(rp)
            p.drawRoundedRect(QRect(r.left(), r.top(), max(w, 2), r.height()), 9, 9)

        # анимированная левая индикаторная полоса
        if self._select_t > 0.01:
            h = int(r.height() * 0.55 * self._select_t)
            y = r.center().y() - h // 2
            col = QColor(C['accent_primary'])
            col.setAlpha(int(230 * self._select_t))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(QRect(r.left() + 3, y, 3, h), 2, 2)

        p.end()
        super().paintEvent(e)


class SidebarMenu(QWidget):
    """Левое меню: бренд + список инструментов + футер."""

    def __init__(self, tab_widget: QTabWidget, parent=None):
        super().__init__(parent)
        self.tabs = tab_widget
        self.setObjectName("sidebar")
        self.setFixedWidth(228)

        self._buttons: list[NavButton] = []
        self._indicator = _SlideIndicator(self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 14, 12, 12)
        lay.setSpacing(4)

        # ── Бренд ──
        brand = QLabel("⛏️  BGS Scanner")
        brand.setObjectName("brandLabel")
        sub = QLabel("инструменты анализа ключей")
        sub.setObjectName("brandSub")
        lay.addWidget(brand)
        lay.addWidget(sub)
        lay.addSpacing(10)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("sideDivider")
        lay.addWidget(line)
        lay.addSpacing(6)

        # ── Пункты меню из вкладок ──
        for i in range(tab_widget.count()):
            title = tab_widget.tabText(i).strip()
            icon, _, label = title.partition(' ')
            btn = NavButton(icon if icon else "•", label or title, self)
            btn.clicked.connect(lambda _c=False, idx=i: self.select_index(idx))
            lay.addWidget(btn)
            self._buttons.append(btn)

        lay.addStretch(1)

        foot = QLabel("v5.0  •  dark neutral")
        foot.setObjectName("sideFooter")
        lay.addWidget(foot)

        # индикатор поверх кнопок
        self._indicator.raise_()

        # синхронизация с текущей вкладкой
        tab_widget.currentChanged.connect(self._sync_from_tabs)
        tab_widget.tabBar().currentChanged.connect(self._sync_from_tabs)
        QTimer.singleShot(0, lambda: self._sync_from_tabs(tab_widget.currentIndex()))

    # ---------- публичное API ----------
    def select_index(self, index: int):
        """Переключить страницу с fade-анимацией."""
        if 0 <= index < self.tabs.count():
            animate_page(self.tabs, index)

    def _sync_from_tabs(self, index: int):
        for i, b in enumerate(self._buttons):
            b.blockSignals(True)
            b.setChecked(i == index)
            b.blockSignals(False)
        if 0 <= index < len(self._buttons):
            self._indicator.move_to(self._buttons[index])


class _SlideIndicator(QWidget):
    """Тонкая светящаяся линия, плавно скользящая под активным пунктом."""

    def __init__(self, parent: SidebarMenu):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._geom_anim = QPropertyAnimation(self, b"pos", self)
        self._geom_anim.setDuration(300)
        self._geom_anim.setEasingCurve(QEasingCurve.Type.InOutQuint)
        self._w_anim = QPropertyAnimation(self, b"minimumWidth", self)
        self._w_anim.setDuration(300)
        self._w_anim.setEasingCurve(QEasingCurve.Type.InOutQuint)
        self.setFixedHeight(2)

    def move_to(self, widget: QWidget):
        target_x = widget.x() + 8
        target_w = max(24, widget.width() - 16)
        target_y = widget.y() + widget.height() - 3
        self._geom_anim.stop()
        self._geom_anim.setStartValue(self.pos())
        self._geom_anim.setEndValue(QPoint(target_x, target_y))
        self._geom_anim.start()
        self._w_anim.stop()
        self._w_anim.setStartValue(self.width())
        self._w_anim.setEndValue(target_w)
        self._w_anim.start()

    def setMinimumWidth(self, w):
        super().setMinimumWidth(w)
        self.resize(w, self.height())

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = QColor(C['accent_primary'])
        g = QLinearGradient(0, 0, self.width(), 0)
        c0 = QColor(col); c0.setAlpha(0)
        c1 = QColor(col); c1.setAlpha(210)
        g.setColorAt(0.0, c0)
        g.setColorAt(0.5, c1)
        g.setColorAt(1.0, c0)
        p.fillRect(self.rect(), g)
        p.end()


# ════════════════════════════════════════════════════════════
#  Анимации контента
# ════════════════════════════════════════════════════════════
def animate_page(tabs: QTabWidget, new_index: int, duration: int = 200):
    """Мягкий fade при переключении страницы QTabWidget."""
    if new_index == tabs.currentIndex() or not (0 <= new_index < tabs.count()):
        return
    page = tabs.widget(new_index)
    if page is None:
        tabs.setCurrentIndex(new_index)
        return

    effect = QGraphicsOpacityEffect(page)
    page.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", page)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def cleanup():
        try:
            page.setGraphicsEffect(None)
        except RuntimeError:
            pass

    anim.finished.connect(cleanup)
    anim.start()
    page._fade_anim = anim  # держим ссылку до окончания
    tabs.setCurrentIndex(new_index)


def install_tab_animations(tabs: QTabWidget) -> None:
    """Fade-анимация при любом программном setCurrentIndex (сигналы, hotkeys)."""
    def on_changed(index: int):
        if index < 0:
            return
        page = tabs.widget(index)
        if page is None or getattr(page, '_fade_running', False):
            return
        page._fade_running = True
        eff = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(eff)
        a = QPropertyAnimation(eff, b"opacity", page)
        a.setDuration(180)
        a.setStartValue(0.25)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)

        def done():
            page._fade_running = False
            try:
                page.setGraphicsEffect(None)
            except RuntimeError:
                pass

        a.finished.connect(done)
        a.start()
        page._fade_anim = a

    tabs.currentChanged.connect(on_changed)


SIDEBAR_QSS = f"""
    #sidebar {{
        background: {_f(C['bg_card'], 255)};
        border-right: 1px solid {_f(C['border_soft'], 255)};
    }}
    #sidebar #brandLabel {{
        color: {C['text_primary']};
        font-size: 12.5pt;
        font-weight: 700;
        letter-spacing: 0.3px;
        padding: 2px 4px 0px 4px;
        background: transparent;
    }}
    #sidebar #brandSub {{
        color: {C['text_secondary']};
        font-size: 8pt;
        padding: 0px 4px;
        background: transparent;
    }}
    #sidebar #sideDivider {{
        background: {_f(C['border'], 140)};
        max-height: 1px;
        border: none;
    }}
    #sidebar #sideFooter {{
        color: {C['text_disabled']};
        font-size: 7.5pt;
        padding: 4px;
        background: transparent;
    }}
    QPushButton[cssClass="navItem"] {{
        background: transparent;
        color: {C['text_secondary']};
        border: 1px solid transparent;
        border-radius: 9px;
        text-align: left;
        padding-left: 14px;
        padding-right: 10px;
        font-size: 9.5pt;
    }}
    QPushButton[cssClass="navItem"]:hover {{
        color: {C['text_primary']};
    }}
    QPushButton[cssClass="navItem"]:checked {{
        color: {C['text_primary']};
        font-weight: 600;
    }}
"""


def build_sidebar_layout(window, tabs: QTabWidget) -> QHBoxLayout:
    """Собирает row-layout: [меню | вкладки(tabBar скрыт)]. Возвращает (layout, sidebar)."""
    tabs.tabBar().hide()          # сам QTabWidget остаётся контейнером страниц
    tabs.tabBar().setExpanding(False)
    tabs.setMovable(False)

    sidebar = SidebarMenu(tabs, window)
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    row.addWidget(sidebar)
    row.addWidget(tabs, 1)
    return row, sidebar
