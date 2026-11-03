# ui/sidebar.py
# 🧭 Боковое меню (sidebar): сворачивание/разворачивание, авто-сворачивание,
#    hover-попав при collapsed-режиме, ripple-волны, скользящий индикатор,
#    fade+slide переходы страниц.
# Использует существующий QTabWidget как контейнер страниц: tabBar просто
# скрыт, переключение идёт через кнопки меню — логика приложения НЕ меняется.
from __future__ import annotations

import json
import os
from typing import Optional

from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QPoint, QRect, QTimer,
    pyqtSignal, pyqtProperty, QObject,
)
from PyQt6.QtGui import QColor, QPainter, QPen, QLinearGradient
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTabWidget, QGraphicsOpacityEffect, QSizePolicy, QApplication,
    QToolButton, QMenu, QGraphicsDropShadowEffect,
)
from PyQt6.QtGui import QShortcut, QKeySequence, QActionGroup, QAction

from ui.theme import COLORS as C
from ui.animations import (
    RippleOverlay, PulseDot, GlowBar, fade_in, attach_ripple,
)

SIDEBAR_EXPANDED_W = 230
SIDEBAR_COLLAPSED_W = 68
_AUTO_CLOSE_MS = 4200          # период проверки авто-сворачивания
_POPUP_DELAY_MS = 420          # задержка появления попапа в collapsed-режиме
_SETTINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "ui_settings.json")


def _f(c: str, alpha: int) -> str:
    """#RRGGBBAA из hex-цвета."""
    return f"{c}{max(0, min(255, alpha)):02X}"


def _pen(color, w):
    pen = QPen(color)
    pen.setWidthF(w)
    return pen


def _load_ui_settings() -> dict:
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_ui_settings(data: dict):
    try:
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


class NavButton(QPushButton):
    """Кнопка пункта бокового меню с полным набором анимаций."""

    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(parent)
        self._icon = icon or "•"
        self._label = text
        self.setText(f"{self._icon}  {self._label}")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(42)
        self.setProperty("cssClass", "navItem")

        self._hover_t = 0.0     # 0..1 прогресс наведения
        self._select_t = 0.0    # 0..1 прогресс выбора
        self._press_t = 0.0     # 0..1 «ripple» при клике
        self._pop_t = 0.0       # pop-эффект иконки при выборе
        self._text_w = -1.0     # доля ширины подписи (анимация collapse)

        self._ripple = RippleOverlay(self, QColor(C['accent_primary']), 420)

        self._anim_hover = QPropertyAnimation(self, b"hoverT", self)
        self._anim_hover.setDuration(170)
        self._anim_hover.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_select = QPropertyAnimation(self, b"selectT", self)
        self._anim_select.setDuration(320)
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

    def get_popT(self):
        return self._pop_t

    def set_popT(self, v):
        self._pop_t = v
        self.update()

    popT = pyqtProperty(float, fget=get_popT, fset=set_popT)

    def get_textW(self):
        return self._text_w

    def set_textW(self, v):
        self._text_w = v
        self._apply_text(v)

    textW = pyqtProperty(float, fget=get_textW, fset=set_textW)

    # --- поведение ---
    def _on_toggled(self, checked: bool):
        self._anim_select.stop()
        self._anim_select.setStartValue(self._select_t)
        self._anim_select.setEndValue(1.0 if checked else 0.0)
        self._anim_select.start()
        if checked:
            self._pop()

    def _pop(self):
        """Pop-эффект: вокруг иконки «расходится» вспышка при активации."""
        a = getattr(self, "_anim_pop", None)
        if a is None:
            a = QPropertyAnimation(self, b"popT", self)
            self._anim_pop = a
        a.setDuration(420)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.stop()
        a.start()

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

    def mouseReleaseEvent(self, e):
        try:
            inside = QRect(self.rect()).contains(e.position().toPoint())
        except Exception:
            inside = True
        if inside:
            self._ripple.fire(e.position().toPoint())
        super().mouseReleaseEvent(e)

    # --- режим значков (collapsed): подпись плавно «схлопывается» ---
    def set_labels_visible(self, visible: bool, animate: bool = True):
        target = 1.0 if visible else 0.0
        if self._text_w >= 0 and abs(self._text_w - target) < 0.001 \
                and not animate:
            self._apply_text(target)
            return
        if not animate:
            self._apply_text(target)
            return
        a = getattr(self, "_anim_text", None)
        if a is None:
            a = QPropertyAnimation(self, b"textW", self)
            self._anim_text = a
        a.setDuration(230)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.stop()
        a.setStartValue(self._text_w if self._text_w >= 0 else target)
        a.setEndValue(target)
        a.start()

    def _apply_text(self, t: float):
        if t < 0:
            t = 1.0
        if t > 0.995:
            self.setText(f"{self._icon}  {self._label}")
        elif t < 0.02:
            self.setText(self._icon)
        else:
            n = max(0, round(len(self._label) * t))
            shown = self._label[:n].rstrip()
            self.setText(f"{self._icon}  {shown}" if shown else self._icon)

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

        # анимированная левая индикаторная полоса (растёт сверху вниз)
        if self._select_t > 0.01:
            full = int(r.height() * 0.62)
            h = int(full * self._select_t)
            y = r.center().y() - h // 2
            col = QColor(C['accent_primary'])
            col.setAlpha(int(235 * self._select_t))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(QRect(r.left() + 3, y, 3, max(h, 3)), 2, 2)

        # pop-«вспышка» вокруг иконки при выборе
        if 0.0 < self._pop_t < 1.0:
            pt = self._pop_t
            rad = 6 + 20 * pt
            col = QColor(C['accent_primary'])
            col.setAlpha(int(60 * (1.0 - pt)))
            cy = r.center().y()
            cx = 22
            p.setBrush(col)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPoint(cx, cy), int(rad), int(rad * 0.6))

        p.end()
        super().paintEvent(e)


class _FlyoutPanel(QWidget):
    """Тёмная всплывающая панель со списком пунктов (для collapsed-режима)."""

    closed = pyqtSignal()

    def __init__(self, sidebar: "SidebarMenu"):
        super().__init__(None, Qt.WindowType.Popup)
        self._sidebar = sidebar
        self.setObjectName("flyout")
        self.setStyleSheet(f"""
            #flyout {{ background: transparent; }}
            #flyoutCard {{
                background: {_f(C['bg_card'], 250)};
                border: 1px solid {_f(C['border'], 255)};
                border-radius: 12px;
            }}
            #flyoutTitle {{
                color: {C['text_secondary']};
                font-size: 8pt; padding: 10px 14px 4px 14px;
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
                background: {_f(C['bg_hover'], 255)};
                color: {C['text_primary']};
            }}
            QPushButton[cssClass="navItem"]:checked {{
                background: {_f(C['bg_elevated'], 255)};
                color: {C['text_primary']};
                font-weight: 600;
            }}
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        self._card = QWidget(self)
        self._card.setObjectName("flyoutCard")
        outer.addWidget(self._card)
        self._lay = QVBoxLayout(self._card)
        self._lay.setContentsMargins(6, 4, 6, 6)
        self._lay.setSpacing(3)

        title = QLabel("Навигация")
        title.setObjectName("flyoutTitle")
        self._lay.addWidget(title)

        self._rows: list[QPushButton] = []
        for i in range(self._sidebar.tabs.count()):
            t = self._sidebar.tabs.tabText(i).strip()
            icon, _, label = t.partition(' ')
            btn = QPushButton(f"{icon or '•'}  {label or t}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("cssClass", "navItem")
            btn.setMinimumHeight(38)
            idx = i
            btn.clicked.connect(lambda _c=False, i=idx: self._pick(i))
            self._lay.addWidget(btn)
            self._rows.append(btn)

        self._glow = GlowBar(self._card, C['accent_primary'])
        self.adjustSize()

    def _pick(self, index: int):
        self.close()
        self._sidebar.select_index(index)

    def show_near(self, anchor_global: QPoint):
        for i, b in enumerate(self._rows):
            b.setChecked(i == self._sidebar.tabs.currentIndex())
        self.adjustSize()
        screen = QApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else None
        x = anchor_global.x()
        y = anchor_global.y()
        fw, fh = self.size().width(), self.size().height()
        if geo and x + fw > geo.right():
            x = geo.right() - fw - 4
        if geo and y + fh > geo.bottom():
            y = max(geo.top(), geo.bottom() - fh - 4)
        self.move(x, y)
        # pop-in: мягкое проявление карточки
        eff = QGraphicsOpacityEffect(self._card)
        self._card.setGraphicsEffect(eff)
        a = QPropertyAnimation(eff, b"opacity", self)
        a.setDuration(160)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.start()
        self._pop_anim = a
        self.show()
        self._glow.setGeometry(8, self._card.height() - 8,
                               max(10, self._card.width() - 16), 2)
        self._glow.show()
        self._glow.raise_()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.closed.emit()


class SidebarMenu(QWidget):
    """Левое меню: бренд + список инструментов + футер.
    Поддерживает collapse/expand, авто-сворачивание и flyout-попап."""

    collapsed_changed = pyqtSignal(bool)

    def __init__(self, tab_widget: QTabWidget, parent=None):
        super().__init__(parent)
        self.tabs = tab_widget
        self._window = parent
        self.setObjectName("sidebar")
        self.setMinimumWidth(SIDEBAR_COLLAPSED_W)

        settings = _load_ui_settings()
        self._collapsed = bool(settings.get("sidebar_collapsed", False))
        self._auto_collapse = bool(settings.get("sidebar_auto_collapse", False))
        # авто-раскрытие при наведении на «ручку» в collapsed-режиме
        self._auto_expand_on_hover = bool(
            settings.get("sidebar_auto_expand", True))

        self._buttons: list[NavButton] = []
        self._indicator = _SlideIndicator(self)
        self._flyout: Optional[_FlyoutPanel] = None
        self._timer_popup = QTimer(self)
        self._timer_popup.setSingleShot(True)
        self._timer_popup.timeout.connect(self._show_flyout)
        self._idle_ticks = 0
        self._user_pinned = not self._collapsed  # развёрнут вручную?
        self._mouse_inside = False

        self.setMouseTracking(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(4)
        self._lay = lay

        # ── Шапка: бренд + кнопка toggle ──
        head = QHBoxLayout()
        head.setSpacing(4)
        brand_box = QVBoxLayout()
        brand_box.setSpacing(1)
        brand = QLabel("⛏️ BGS Scanner")
        brand.setObjectName("brandLabel")
        sub = QLabel("инструменты анализа ключей")
        sub.setObjectName("brandSub")
        self._brand = brand
        self._brand_sub = sub
        brand_box.addWidget(brand)
        brand_box.addWidget(sub)
        head.addLayout(brand_box, 1)

        self._toggle = QToolButton()
        self._toggle.setObjectName("sideToggle")
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.setFixedSize(30, 30)
        self._toggle.setToolTip("Свернуть / развернуть меню")
        self._toggle.clicked.connect(lambda: self.toggle_collapsed(user=True))
        head.addWidget(self._toggle, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(head)

        self._pulse = PulseDot(self, C['accent_success'], size=8)
        self._pulse.move(14, 16)
        self._pulse.show()
        self._pulse.raise_()

        lay.addSpacing(8)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("sideDivider")
        lay.addWidget(line)
        lay.addSpacing(4)

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
        self._foot = foot
        lay.addWidget(foot)

        self._indicator.raise_()

        tab_widget.currentChanged.connect(self._sync_from_tabs)
        tab_widget.tabBar().currentChanged.connect(self._sync_from_tabs)

        # стартовое состояние без анимации
        self._width_anim = QPropertyAnimation(self, b"minimumWidth", self)
        self._width_anim.setDuration(260)
        self._width_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._width_anim.valueChanged.connect(self._on_width_value)
        self.setMaximumWidth(SIDEBAR_COLLAPSED_W if self._collapsed
                             else SIDEBAR_EXPANDED_W)
        self.setFixedWidth(SIDEBAR_COLLAPSED_W if self._collapsed
                           else SIDEBAR_EXPANDED_W)
        for b in self._buttons:
            b._text_w = 0.0 if self._collapsed else 1.0
            b._apply_text(b._text_w)
        self._update_toggle_icon()
        if self._collapsed:
            self._foot.hide()

        QTimer.singleShot(0, lambda: self._sync_from_tabs(tab_widget.currentIndex()))

    # ---------- публичное API ----------
    @property
    def is_collapsed(self) -> bool:
        return self._collapsed

    def select_index(self, index: int):
        if 0 <= index < self.tabs.count():
            animate_page(self.tabs, index)
            self._idle_ticks = 0
            if self._collapsed:
                self._timer_popup.stop()

    def toggle_collapsed(self, user: bool = False):
        self.set_collapsed(not self._collapsed, user=user)

    def set_collapsed(self, collapsed: bool, animate: bool = True,
                      user: bool = False):
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        if user:
            self._user_pinned = not collapsed
        self._idle_ticks = 0
        self._timer_popup.stop()
        if self._flyout is not None and self._flyout.isVisible():
            self._flyout.close()

        for b in self._buttons:
            b.set_labels_visible(not collapsed, animate=animate)
        if collapsed:
            self._foot.hide()
        else:
            self._foot.show()
            fade_in(self._foot, 240, 0.0)

        self._width_anim.stop()
        self._width_anim.setStartValue(self.width())
        self._width_anim.setEndValue(SIDEBAR_COLLAPSED_W if collapsed
                                     else SIDEBAR_EXPANDED_W)
        self._width_anim.setDuration(260 if animate else 0)
        # сначала фиксируем maximumWidth под целевую ширину, чтобы
        # анимируемый minimumWidth мог её достичь
        self.setMaximumWidth(SIDEBAR_EXPANDED_W if collapsed
                             else SIDEBAR_COLLAPSED_W)
        self._width_anim.start()
        # после окончания закрепляем maximumWidth за финальным значением
        self._width_anim.finished.connect(
            lambda c=collapsed: self.setMaximumWidth(
                SIDEBAR_COLLAPSED_W if c else SIDEBAR_EXPANDED_W))

        self._update_toggle_icon()
        self._save_state()
        self.collapsed_changed.emit(collapsed)

    # ---------- internals ----------
    def _on_width_value(self, w):
        w = int(w)
        self.setFixedWidth(w)
        t = max(0.0, min(1.0, (w - SIDEBAR_COLLAPSED_W) / float(
            SIDEBAR_EXPANDED_W - SIDEBAR_COLLAPSED_W)))
        self._brand.setFixedWidth(max(1, int(t * 168)))
        self._brand_sub.setFixedWidth(max(1, int(t * 168)))
        cur = self.tabs.currentIndex()
        if 0 <= cur < len(self._buttons):
            self._indicator.reposition(self._buttons[cur])

    def _update_toggle_icon(self):
        self._toggle.setText("◀" if not self._collapsed else "▶")

    def enterEvent(self, e):
        self._mouse_inside = True
        self._idle_ticks = 0
        self._timer_popup.stop()
        if self._collapsed:
            if self._auto_expand_on_hover:
                # авто-раскрытие: плавно разворачиваемся при наведении
                self.set_collapsed(False)
            else:
                self._timer_popup.start(_POPUP_DELAY_MS)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._mouse_inside = False
        self._timer_popup.stop()
        # если развернулись сами (не пинили) — свернуться обратно
        if self._auto_expand_on_hover and not self._user_pinned \
                and not self._collapsed:
            QTimer.singleShot(450, self._collapse_if_idle)
        super().leaveEvent(e)

    def _collapse_if_idle(self):
        if not self._mouse_inside and not self._user_pinned \
                and not self._collapsed:
            self.set_collapsed(True)

    def _show_flyout(self):
        if not self._collapsed:
            return
        if self._flyout is None:
            self._flyout = _FlyoutPanel(self)
            self._flyout.closed.connect(self._on_flyout_closed)
        gp = self.mapToGlobal(QPoint(self.width() + 4, 40))
        self._flyout.show_near(gp)

    def _on_flyout_closed(self):
        self._timer_popup.stop()

    def set_auto_collapse(self, enabled: bool):
        self._auto_collapse = enabled
        self._idle_ticks = 0
        self._save_state()

    def contextMenuEvent(self, e):
        """ПКМ по меню — настройки поведения сайдбара."""
        menu = QMenu(self)
        menu.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        act_toggle = QAction("Свернуть / развернуть  (Ctrl+B)", menu)
        act_toggle.triggered.connect(lambda: self.toggle_collapsed(user=True))
        menu.addAction(act_toggle)
        menu.addSeparator()

        grp = QActionGroup(menu)
        act_pin = QAction("Закрепленное меню", menu, checkable=True)
        act_auto = QAction("Авто-сворачивать при бездействии", menu,
                           checkable=True)
        act_hover = QAction("Раскрывать при наведении", menu, checkable=True)
        for a in (act_pin, act_auto, act_hover):
            grp.addAction(a)
        if not self._collapsed and self._user_pinned:
            act_pin.setChecked(True)
        elif self._auto_collapse:
            act_auto.setChecked(True)
        else:
            act_hover.setChecked(True)

        act_pin.toggled.connect(
            lambda v: self._mode_changed('pin' if v else 'hover'))
        act_auto.toggled.connect(
            lambda v: self._mode_changed('auto' if v else 'hover'))
        act_hover.toggled.connect(
            lambda v: self._mode_changed('hover' if v else None))

        menu.addAction(act_pin)
        menu.addAction(act_auto)
        menu.addAction(act_hover)

        menu.exec(e.globalPos())
        super().contextMenuEvent(e)

    def _mode_changed(self, mode):
        if mode == 'pin':
            self._auto_collapse = False
            self._auto_expand_on_hover = False
            self._user_pinned = True
            if self._collapsed:
                self.set_collapsed(False, user=True)
        elif mode == 'auto':
            self._auto_collapse = True
            self._auto_expand_on_hover = False
            self._user_pinned = False
            self._idle_ticks = 0
        elif mode == 'hover':
            self._auto_collapse = False
            self._auto_expand_on_hover = True
            self._user_pinned = False
        self._save_state()

    def timer_tick(self):
        """Периодическая проверка: долго нет активности — авто-свернуть."""
        self._idle_ticks += 1
        if (self._auto_collapse and not self._collapsed
                and not self._mouse_inside
                and self._idle_ticks * _AUTO_CLOSE_MS >= 12000):
            self.set_collapsed(True)

    def _save_state(self):
        s = _load_ui_settings()
        s["sidebar_collapsed"] = self._collapsed
        s["sidebar_auto_collapse"] = self._auto_collapse
        s["sidebar_auto_expand"] = self._auto_expand_on_hover
        _save_ui_settings(s)

    def _sync_from_tabs(self, index: int):
        for i, b in enumerate(self._buttons):
            b.blockSignals(True)
            b.setChecked(i == index)
            b.blockSignals(False)
        if 0 <= index < len(self._buttons):
            self._indicator.move_to(self._buttons[index])

    def switch_relative(self, step: int):
        """Alt+←/→ — переход по вкладкам с анимацией."""
        cur = self.tabs.currentIndex()
        nxt = max(0, min(self.tabs.count() - 1, cur + step))
        if nxt != cur:
            self.select_index(nxt)


class _SlideIndicator(QWidget):
    """Тонкая светящаяся линия, плавно скользящая под активным пунктом."""

    def __init__(self, parent: SidebarMenu):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._geom_anim = QPropertyAnimation(self, b"pos", self)
        self._geom_anim.setDuration(320)
        self._geom_anim.setEasingCurve(QEasingCurve.Type.InOutQuint)
        self._w_anim = QPropertyAnimation(self, b"minimumWidth", self)
        self._w_anim.setDuration(320)
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

    def reposition(self, widget: QWidget):
        """Мгновенная синхронизация позиции (при анимации ширины сайдбара)."""
        self._geom_anim.stop()
        self._w_anim.stop()
        self.move(widget.x() + 8, widget.y() + widget.height() - 3)
        self.setMinimumWidth(max(24, widget.width() - 16))

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
def animate_page(tabs: QTabWidget, new_index: int, duration: int = 210):
    """Slide+fade переход страницы QTabWidget."""
    if new_index == tabs.currentIndex() or not (0 <= new_index < tabs.count()):
        return
    page = tabs.widget(new_index)
    if page is None:
        tabs.setCurrentIndex(new_index)
        return

    forward = new_index > tabs.currentIndex()

    effect = QGraphicsOpacityEffect(page)
    page.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", page)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    old_pos = page.pos()

    def cleanup():
        try:
            page.setGraphicsEffect(None)
            page.move(old_pos)
        except RuntimeError:
            pass

    anim.finished.connect(cleanup)
    anim.start()
    page._fade_anim = anim
    tabs.setCurrentIndex(new_index)

    # лёгкий slide по направлению перехода
    dx = 26 if forward else -26
    shift = QPropertyAnimation(page, b"pos", page)
    shift.setDuration(duration + 40)
    shift.setStartValue(old_pos + QPoint(dx, 0))
    shift.setEndValue(old_pos)
    shift.setEasingCurve(QEasingCurve.Type.OutQuad)
    shift.start()
    page._slide_anim = shift


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


def install_content_stagger(window, tabs: QTabWidget) -> None:
    """Каскадное появление групп/карточек внутри страницы при её открытии.
    Только визуальный эффект — в логике ничего не меняется."""
    def on_changed(index: int):
        page = tabs.widget(index)
        if page is None:
            return
        groups = [w for w in page.findChildren(QWidget)
                  if w.parent() is not None and w.isVisibleTo(page)
                  and (w.metaObject().className() == "QGroupBox"
                       or w.property("cssClass") == "card")]
        groups = groups[:8]  # не перегружаем
        for i, g in enumerate(groups):
            if g.property("_staggered") is True:
                continue
            g.setProperty("_staggered", True)
            try:
                eff = QGraphicsOpacityEffect(g)
                g.setGraphicsEffect(eff)
            except Exception:
                continue
            a = QPropertyAnimation(eff, b"opacity", g)
            a.setDuration(240)
            a.setStartValue(0.0)
            a.setEndValue(1.0)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            a.setStartDelay(60 + i * 45)

            def done(_g=g):
                try:
                    _g.setGraphicsEffect(None)
                except RuntimeError:
                    pass

            a.finished.connect(done)
            a.start()
            g._stag_anim = a

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
    #sideToggle {{
        background: {_f(C['bg_input'], 200)};
        color: {C['text_secondary']};
        border: 1px solid {_f(C['border_soft'], 255)};
        border-radius: 9px;
        font-size: 9pt;
        padding: 0px;
    }}
    #sideToggle:hover {{
        background: {_f(C['bg_hover'], 255)};
        color: {C['text_primary']};
        border: 1px solid {_f(C['border_focus'], 255)};
    }}
    #sideToggle:pressed {{
        background: {_f(C['bg_pressed'], 255)};
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


def build_sidebar_layout(window, tabs: QTabWidget) -> tuple:
    """Собирает row-layout: [меню | вкладки(tabBar скрыт)].
    Возвращает (layout, sidebar)."""
    tabs.tabBar().hide()          # сам QTabWidget остаётся контейнером страниц
    tabs.tabBar().setExpanding(False)
    tabs.setMovable(False)

    sidebar = SidebarMenu(tabs, window)

    # ── «Ручка»-вытягиватель у левого края (видна когда меню свёрнуто) ──
    handle = _EdgeHandle(sidebar, window)

    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    row.addWidget(sidebar)
    row.addWidget(tabs, 1)

    def reposition_handle():
        if sidebar.is_collapsed:
            handle.show()
            handle.raise_()
            handle.move(0, max(40, (window.height() - handle.height()) // 2))
            handle.setFixedSize(16, min(150, max(90, window.height() // 4)))
        else:
            handle.hide()

    sidebar.collapsed_changed.connect(lambda _c: QTimer.singleShot(
        280, reposition_handle))
    sidebar.collapsed_changed.connect(reposition_handle)
    QTimer.singleShot(0, reposition_handle)
    window._sidebar_handle_reposition = reposition_handle

    # ── Горячие клавиши (не конфликтуют с существующими Ctrl+S/P) ──
    sc_toggle = QShortcut(QKeySequence("Ctrl+B"), window)
    sc_toggle.setContext(Qt.ShortcutContext.WindowShortcut)
    sc_toggle.activated.connect(lambda: sidebar.toggle_collapsed(user=True))
    sc_prev = QShortcut(QKeySequence("Alt+Left"), window)
    sc_prev.setContext(Qt.ShortcutContext.WindowShortcut)
    sc_prev.activated.connect(lambda: sidebar.switch_relative(-1))
    sc_next = QShortcut(QKeySequence("Alt+Right"), window)
    sc_next.setContext(Qt.ShortcutContext.WindowShortcut)
    sc_next.activated.connect(lambda: sidebar.switch_relative(1))
    shortcuts = (sc_toggle, sc_prev, sc_next)  # держим ссылки

    # Тикер для авто-сворачивания (когда включено пользователями)
    ticker = QTimer(sidebar)
    ticker.setInterval(_AUTO_CLOSE_MS)
    ticker.timeout.connect(sidebar.timer_tick)
    ticker.start()

    return row, sidebar


class _EdgeHandle(QWidget):
    """Анимированная «ручка» у края окна: показывается когда сайдбар свёрнут,
    hover — подсветка + стрелка, клик — развернуть."""

    def __init__(self, sidebar: SidebarMenu, window):
        super().__init__(window)
        self._sidebar = sidebar
        self.setObjectName("edgeHandle")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedSize(16, 130)
        self._t = 0.0
        self._anim = QPropertyAnimation(self, b"t", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hide()

    def _set_t(self, v):
        self._t = v
        self.update()

    # pyqtProperty объявляется после сеттера (иначе NameError в теле класса)
    t = pyqtProperty(float, fget=lambda self: self._t, fset=_set_t)

    def enterEvent(self, e):
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(1.0)
        self._anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(0.0)
        self._anim.start()
        super().leaveEvent(e)

    def mouseReleaseEvent(self, e):
        try:
            inside = QRect(self.rect()).contains(e.position().toPoint())
        except Exception:
            inside = True
        if inside:
            self._sidebar.set_collapsed(False, user=True)
        super().mouseReleaseEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 6, -2, -6)
        radius = 7
        base = QColor(C['bg_elevated'])
        base.setAlpha(int(200 + 55 * self._t))
        p.setBrush(base)
        pen = QPen(QColor(C['border_focus']))
        pen.setWidthF(1.0 + self._t)
        p.setPen(pen)
        p.drawRoundedRect(r, radius, radius)

        col = QColor(C['text_secondary'])
        col.setAlpha(int(150 + 105 * self._t))
        pen2 = QPen(col)
        pen2.setWidthF(1.6)
        pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen2)
        cx = r.center().x() + 1
        cy = r.center().y()
        shift = int(2 * self._t)
        for dy in (-14, 0, 14):
            p.drawLine(cx - 3 + shift, cy + dy - 4, cx + 3 + shift, cy + dy)
            p.drawLine(cx + 3 + shift, cy + dy, cx - 3 + shift, cy + dy + 4)
        p.end()
