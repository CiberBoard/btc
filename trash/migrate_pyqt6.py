#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔧 PyQt5 → PyQt6 Auto-Migrator
Максимально автоматизирует переход на PyQt6

Использование:
    python migrate_pyqt6.py --dry-run ./src          # Тестовый прогон
    python migrate_pyqt6.py --backup ./src           # С бэкапами
    python migrate_pyqt6.py ./src                    # Применение
"""

import re
import sys
import shutil
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional, Dict

# ─────────────────────────────────────────────
# 📋 КОНФИГУРАЦИЯ ЗАМЕН
# ─────────────────────────────────────────────

# 1. Замена импортов
IMPORT_REPLACEMENTS: List[Tuple[str, str]] = [
    (r'from PyQt5\.QtWidgets import', 'from PyQt6.QtWidgets import'),
    (r'from PyQt5\.QtCore import', 'from PyQt6.QtCore import'),
    (r'from PyQt5\.QtGui import', 'from PyQt6.QtGui import'),
    (r'from PyQt5\.QtOpenGL import', 'from PyQt6.QtOpenGLWidgets import'),
    (r'from PyQt5\.QtPrintSupport import', 'from PyQt6.QtPrintSupport import'),
    (r'from PyQt5\.QtSvg import', 'from PyQt6.QtSvg import'),
    (r'from PyQt5\.QtTest import', 'from PyQt6.QtTest import'),
    (r'from PyQt5\.QtMultimedia import', 'from PyQt6.QtMultimedia import'),
    (r'from PyQt5\.QtMultimediaWidgets import', 'from PyQt6.QtMultimediaWidgets import'),
    (r'from PyQt5\.QtNetwork import', 'from PyQt6.QtNetwork import'),
    (r'from PyQt5\.QtSql import', 'from PyQt6.QtSql import'),
    (r'from PyQt5\.QtXml import', 'from PyQt6.QtXml import'),
    (r'import PyQt5', 'import PyQt6'),
]

# 2. Scoped Enums: Qt.EnumValue → Qt.EnumClass.EnumValue
# Формат: (старый_паттерн, новый_паттерн, описание)
# 2. Scoped Enums: Qt.EnumValue → Qt.EnumClass.EnumValue
SCOPED_ENUMS: List[Tuple[str, str, str]] = [
    # ───────── QAbstractItemView (QTableWidget, QTableView, QTreeView, QListView) ─────────
    (r'\bQTableWidget\.NoEditTriggers\b', 'QAbstractItemView.EditTrigger.NoEditTriggers', 'QAbstractItemView.EditTrigger'),
    (r'\bQTableWidget\.DoubleClicked\b', 'QAbstractItemView.EditTrigger.DoubleClicked', 'QAbstractItemView.EditTrigger'),
    (r'\bQTableWidget\.SelectedClicked\b', 'QAbstractItemView.EditTrigger.SelectedClicked', 'QAbstractItemView.EditTrigger'),
    (r'\bQTableWidget\.EditKeyPressed\b', 'QAbstractItemView.EditTrigger.EditKeyPressed', 'QAbstractItemView.EditTrigger'),
    (r'\bQTableWidget\.AnyKeyPressed\b', 'QAbstractItemView.EditTrigger.AnyKeyPressed', 'QAbstractItemView.EditTrigger'),
    (r'\bQTableWidget\.CurrentChanged\b', 'QAbstractItemView.EditTrigger.CurrentChanged', 'QAbstractItemView.EditTrigger'),
    (r'\bQTableWidget\.SelectItems\b', 'QAbstractItemView.SelectionBehavior.SelectItems', 'QAbstractItemView.SelectionBehavior'),
    (r'\bQTableWidget\.SelectRows\b', 'QAbstractItemView.SelectionBehavior.SelectRows', 'QAbstractItemView.SelectionBehavior'),
    (r'\bQTableWidget\.SelectColumns\b', 'QAbstractItemView.SelectionBehavior.SelectColumns', 'QAbstractItemView.SelectionBehavior'),
    (r'\bQTableWidget\.SingleSelection\b', 'QAbstractItemView.SelectionMode.SingleSelection', 'QAbstractItemView.SelectionMode'),
    (r'\bQTableWidget\.MultiSelection\b', 'QAbstractItemView.SelectionMode.MultiSelection', 'QAbstractItemView.SelectionMode'),
    (r'\bQTableWidget\.ExtendedSelection\b', 'QAbstractItemView.SelectionMode.ExtendedSelection', 'QAbstractItemView.SelectionMode'),
    (r'\bQTableWidget\.ContiguousSelection\b', 'QAbstractItemView.SelectionMode.ContiguousSelection', 'QAbstractItemView.SelectionMode'),
    (r'\bQAbstractItemView\.NoEditTriggers\b', 'QAbstractItemView.EditTrigger.NoEditTriggers', 'QAbstractItemView.EditTrigger'),
    (r'\bQAbstractItemView\.SelectRows\b', 'QAbstractItemView.SelectionBehavior.SelectRows', 'QAbstractItemView.SelectionBehavior'),
    (r'\bQAbstractItemView\.SingleSelection\b', 'QAbstractItemView.SelectionMode.SingleSelection', 'QAbstractItemView.SelectionMode'),

    # QFont Weight
    (r'\bQFont\.Thin\b', 'QFont.Weight.Thin', 'QFont.Weight'),
    (r'\bQFont\.ExtraLight\b', 'QFont.Weight.ExtraLight', 'QFont.Weight'),
    (r'\bQFont\.Light\b', 'QFont.Weight.Light', 'QFont.Weight'),
    (r'\bQFont\.Normal\b', 'QFont.Weight.Normal', 'QFont.Weight'),
    (r'\bQFont\.Medium\b', 'QFont.Weight.Medium', 'QFont.Weight'),
    (r'\bQFont\.DemiBold\b', 'QFont.Weight.DemiBold', 'QFont.Weight'),
    (r'\bQFont\.Bold\b', 'QFont.Weight.Bold', 'QFont.Weight'),
    (r'\bQFont\.ExtraBold\b', 'QFont.Weight.ExtraBold', 'QFont.Weight'),
    (r'\bQFont\.Black\b', 'QFont.Weight.Black', 'QFont.Weight'),
# Qt.ScrollBarPolicy — исправление опечатки
    (r'\bQt\.ScrollBarPolicy\.ScrollBarOff\b', 'Qt.ScrollBarPolicy.ScrollBarAlwaysOff', 'ScrollBarPolicy (fix typo)'),
# Qt.ScrollBarPolicy (полная группа)
   (r'\bQt\.ScrollBarAsNeeded\b', 'Qt.ScrollBarPolicy.ScrollBarAsNeeded', 'ScrollBarPolicy'),
   (r'\bQt\.ScrollBarAlwaysOn\b', 'Qt.ScrollBarPolicy.ScrollBarAlwaysOn', 'ScrollBarPolicy'),
   (r'\bQt\.ScrollBarAlwaysOff\b', 'Qt.ScrollBarPolicy.ScrollBarAlwaysOff', 'ScrollBarPolicy'),
    # ───────── QPalette ColorRole ─────────
    (r'\bQPalette\.Window\b', 'QPalette.ColorRole.Window', 'QPalette.ColorRole'),
    (r'\bQPalette\.WindowText\b', 'QPalette.ColorRole.WindowText', 'QPalette.ColorRole'),
    (r'\bQPalette\.Base\b', 'QPalette.ColorRole.Base', 'QPalette.ColorRole'),
    (r'\bQPalette\.AlternateBase\b', 'QPalette.ColorRole.AlternateBase', 'QPalette.ColorRole'),
    (r'\bQPalette\.Text\b', 'QPalette.ColorRole.Text', 'QPalette.ColorRole'),
    (r'\bQPalette\.Button\b', 'QPalette.ColorRole.Button', 'QPalette.ColorRole'),
    (r'\bQPalette\.ButtonText\b', 'QPalette.ColorRole.ButtonText', 'QPalette.ColorRole'),
    (r'\bQPalette\.Highlight\b', 'QPalette.ColorRole.Highlight', 'QPalette.ColorRole'),
    (r'\bQPalette\.HighlightedText\b', 'QPalette.ColorRole.HighlightedText', 'QPalette.ColorRole'),
    (r'\bQPalette\.Link\b', 'QPalette.ColorRole.Link', 'QPalette.ColorRole'),
    (r'\bQPalette\.LinkVisited\b', 'QPalette.ColorRole.LinkVisited', 'QPalette.ColorRole'),
    (r'\bQPalette\.PlaceholderText\b', 'QPalette.ColorRole.PlaceholderText', 'QPalette.ColorRole'),
    (r'\bQPalette\.ToolTipBase\b', 'QPalette.ColorRole.ToolTipBase', 'QPalette.ColorRole'),
    (r'\bQPalette\.ToolTipText\b', 'QPalette.ColorRole.ToolTipText', 'QPalette.ColorRole'),
    (r'\bQPalette\.BrightText\b', 'QPalette.ColorRole.BrightText', 'QPalette.ColorRole'),
    (r'\bQPalette\.Mid\b', 'QPalette.ColorRole.Mid', 'QPalette.ColorRole'),
    (r'\bQPalette\.Midlight\b', 'QPalette.ColorRole.Midlight', 'QPalette.ColorRole'),
    (r'\bQPalette\.Dark\b', 'QPalette.ColorRole.Dark', 'QPalette.ColorRole'),
    (r'\bQPalette\.Shadow\b', 'QPalette.ColorRole.Shadow', 'QPalette.ColorRole'),
    (r'\bQPalette\.Light\b', 'QPalette.ColorRole.Light', 'QPalette.ColorRole'),
    (r'\bQPalette\.Foreground\b', 'QPalette.ColorRole.Foreground', 'QPalette.ColorRole'),
    (r'\bQPalette\.Background\b', 'QPalette.ColorRole.Background', 'QPalette.ColorRole'),

    # ───────── QPalette ColorGroup ─────────
    (r'\bQPalette\.Disabled\b', 'QPalette.ColorGroup.Disabled', 'QPalette.ColorGroup'),
    (r'\bQPalette\.Active\b', 'QPalette.ColorGroup.Active', 'QPalette.ColorGroup'),
    (r'\bQPalette\.Inactive\b', 'QPalette.ColorGroup.Inactive', 'QPalette.ColorGroup'),

    # ───────── QSizePolicy ─────────
    (r'\bQSizePolicy\.Expanding\b', 'QSizePolicy.Policy.Expanding', 'QSizePolicy.Policy'),
    (r'\bQSizePolicy\.Fixed\b', 'QSizePolicy.Policy.Fixed', 'QSizePolicy.Policy'),
    (r'\bQSizePolicy\.Minimum\b', 'QSizePolicy.Policy.Minimum', 'QSizePolicy.Policy'),
    (r'\bQSizePolicy\.Maximum\b', 'QSizePolicy.Policy.Maximum', 'QSizePolicy.Policy'),
    (r'\bQSizePolicy\.Preferred\b', 'QSizePolicy.Policy.Preferred', 'QSizePolicy.Policy'),
    (r'\bQSizePolicy\.Ignored\b', 'QSizePolicy.Policy.Ignored', 'QSizePolicy.Policy'),

    # ───────── QHeaderView ─────────
    (r'\bQHeaderView\.Stretch\b', 'QHeaderView.ResizeMode.Stretch', 'QHeaderView.ResizeMode'),
    (r'\bQHeaderView\.ResizeToContents\b', 'QHeaderView.ResizeMode.ResizeToContents', 'QHeaderView.ResizeMode'),
    (r'\bQHeaderView\.Fixed\b', 'QHeaderView.ResizeMode.Fixed', 'QHeaderView.ResizeMode'),
    (r'\bQHeaderView\.Interactive\b', 'QHeaderView.ResizeMode.Interactive', 'QHeaderView.ResizeMode'),
    (r'\bQHeaderView\.ResizeContents\b', 'QHeaderView.ResizeMode.ResizeContents', 'QHeaderView.ResizeMode'),
    (r'\bQHeaderView\.Custom\b', 'QHeaderView.ResizeMode.Custom', 'QHeaderView.ResizeMode'),

    # ───────── Qt.ContextMenuPolicy ─────────
    (r'\bQt\.DefaultContextMenu\b', 'Qt.ContextMenuPolicy.DefaultContextMenu', 'Qt.ContextMenuPolicy'),
    (r'\bQt\.CustomContextMenu\b', 'Qt.ContextMenuPolicy.CustomContextMenu', 'Qt.ContextMenuPolicy'),
    (r'\bQt\.NoContextMenu\b', 'Qt.ContextMenuPolicy.NoContextMenu', 'Qt.ContextMenuPolicy'),
    (r'\bQt\.ActionsContextMenu\b', 'Qt.ContextMenuPolicy.ActionsContextMenu', 'Qt.ContextMenuPolicy'),
    (r'\bQt\.PreventContextMenu\b', 'Qt.ContextMenuPolicy.PreventContextMenu', 'Qt.ContextMenuPolicy'),

    # ───────── QMessageBox ─────────
    (r'\bQMessageBox\.Information\b', 'QMessageBox.Icon.Information', 'QMessageBox.Icon'),
    (r'\bQMessageBox\.Warning\b', 'QMessageBox.Icon.Warning', 'QMessageBox.Icon'),
    (r'\bQMessageBox\.Critical\b', 'QMessageBox.Icon.Critical', 'QMessageBox.Icon'),
    (r'\bQMessageBox\.Question\b', 'QMessageBox.Icon.Question', 'QMessageBox.Icon'),
    (r'\bQMessageBox\.Ok\b', 'QMessageBox.StandardButton.Ok', 'QMessageBox.StandardButton'),
    (r'\bQMessageBox\.Cancel\b', 'QMessageBox.StandardButton.Cancel', 'QMessageBox.StandardButton'),
    (r'\bQMessageBox\.Yes\b', 'QMessageBox.StandardButton.Yes', 'QMessageBox.StandardButton'),
    (r'\bQMessageBox\.No\b', 'QMessageBox.StandardButton.No', 'QMessageBox.StandardButton'),
    (r'\bQMessageBox\.Close\b', 'QMessageBox.StandardButton.Close', 'QMessageBox.StandardButton'),

    # ───────── QFileDialog ─────────
    (r'\bQFileDialog\.AcceptOpen\b', 'QFileDialog.AcceptMode.AcceptOpen', 'QFileDialog.AcceptMode'),
    (r'\bQFileDialog\.AcceptSave\b', 'QFileDialog.AcceptMode.AcceptSave', 'QFileDialog.AcceptMode'),
    (r'\bQFileDialog\.ExistingFile\b', 'QFileDialog.FileMode.ExistingFile', 'QFileDialog.FileMode'),
    (r'\bQFileDialog\.Directory\b', 'QFileDialog.FileMode.Directory', 'QFileDialog.FileMode'),
    (r'\bQFileDialog\.ShowDirsOnly\b', 'QFileDialog.Option.ShowDirsOnly', 'QFileDialog.Option'),
    (r'\bQFileDialog\.DontResolveSymlinks\b', 'QFileDialog.Option.DontResolveSymlinks', 'QFileDialog.Option'),

    # ───────── QComboBox ─────────
    (r'\bQComboBox\.NoInsert\b', 'QComboBox.InsertPolicy.NoInsert', 'QComboBox.InsertPolicy'),
    (r'\bQComboBox\.InsertAtTop\b', 'QComboBox.InsertPolicy.InsertAtTop', 'QComboBox.InsertPolicy'),
    (r'\bQComboBox\.InsertAtCurrent\b', 'QComboBox.InsertPolicy.InsertAtCurrent', 'QComboBox.InsertPolicy'),
    (r'\bQComboBox\.InsertAtBottom\b', 'QComboBox.InsertPolicy.InsertAtBottom', 'QComboBox.InsertPolicy'),

    # ───────── Alignment / Cursor / Orientation / WindowType / ItemFlag / CheckState / SortOrder / DropAction / ScrollBarPolicy / SizePolicy(Qt) / FocusPolicy / TextInteractionFlag / DockWidgetArea / ToolBarArea / Corner / ScreenOrientation / HighDpi / WindowModality / CaseSensitivity / ShortcutContext ─────────
    (r'\bQt\.AlignLeft\b', 'Qt.AlignmentFlag.AlignLeft', 'Qt.AlignmentFlag'),
    (r'\bQt\.AlignRight\b', 'Qt.AlignmentFlag.AlignRight', 'Qt.AlignmentFlag'),
    (r'\bQt\.AlignTop\b', 'Qt.AlignmentFlag.AlignTop', 'Qt.AlignmentFlag'),
    (r'\bQt\.AlignBottom\b', 'Qt.AlignmentFlag.AlignBottom', 'Qt.AlignmentFlag'),
    (r'\bQt\.AlignCenter\b', 'Qt.AlignmentFlag.AlignCenter', 'Qt.AlignmentFlag'),
    (r'\bQt\.AlignVCenter\b', 'Qt.AlignmentFlag.AlignVCenter', 'Qt.AlignmentFlag'),
    (r'\bQt\.AlignHCenter\b', 'Qt.AlignmentFlag.AlignHCenter', 'Qt.AlignmentFlag'),
    (r'\bQt\.AlignJustify\b', 'Qt.AlignmentFlag.AlignJustify', 'Qt.AlignmentFlag'),
    (r'\bQt\.WaitCursor\b', 'Qt.CursorShape.WaitCursor', 'Qt.CursorShape'),
    (r'\bQt\.ArrowCursor\b', 'Qt.CursorShape.ArrowCursor', 'Qt.CursorShape'),
    (r'\bQt\.PointingHandCursor\b', 'Qt.CursorShape.PointingHandCursor', 'Qt.CursorShape'),
    (r'\bQt\.IBeamCursor\b', 'Qt.CursorShape.IBeamCursor', 'Qt.CursorShape'),
    (r'\bQt\.SizeVerCursor\b', 'Qt.CursorShape.SizeVerCursor', 'Qt.CursorShape'),
    (r'\bQt\.SizeHorCursor\b', 'Qt.CursorShape.SizeHorCursor', 'Qt.CursorShape'),
    (r'\bQt\.SizeAllCursor\b', 'Qt.CursorShape.SizeAllCursor', 'Qt.CursorShape'),
    (r'\bQt\.ForbiddenCursor\b', 'Qt.CursorShape.ForbiddenCursor', 'Qt.CursorShape'),
    (r'\bQt\.LeftButton\b', 'Qt.MouseButton.LeftButton', 'Qt.MouseButton'),
    (r'\bQt\.RightButton\b', 'Qt.MouseButton.RightButton', 'Qt.MouseButton'),
    (r'\bQt\.MiddleButton\b', 'Qt.MouseButton.MiddleButton', 'Qt.MouseButton'),
    (r'\bQt\.ShiftModifier\b', 'Qt.KeyboardModifier.ShiftModifier', 'Qt.KeyboardModifier'),
    (r'\bQt\.ControlModifier\b', 'Qt.KeyboardModifier.ControlModifier', 'Qt.KeyboardModifier'),
    (r'\bQt\.AltModifier\b', 'Qt.KeyboardModifier.AltModifier', 'Qt.KeyboardModifier'),
    (r'\bQt\.Vertical\b', 'Qt.Orientation.Vertical', 'Qt.Orientation'),
    (r'\bQt\.Horizontal\b', 'Qt.Orientation.Horizontal', 'Qt.Orientation'),
    (r'\bQt\.Window\b', 'Qt.WindowType.Window', 'Qt.WindowType'),
    (r'\bQt\.Dialog\b', 'Qt.WindowType.Dialog', 'Qt.WindowType'),
    (r'\bQt\.Popup\b', 'Qt.WindowType.Popup', 'Qt.WindowType'),
    (r'\bQt\.ToolTip\b', 'Qt.WindowType.ToolTip', 'Qt.WindowType'),
    (r'\bQt\.SplashScreen\b', 'Qt.WindowType.SplashScreen', 'Qt.WindowType'),
    (r'\bQt\.FramelessWindowHint\b', 'Qt.WindowType.FramelessWindowHint', 'Qt.WindowType'),
    (r'\bQt\.WindowTitleHint\b', 'Qt.WindowType.WindowTitleHint', 'Qt.WindowType'),
    (r'\bQt\.ItemIsEnabled\b', 'Qt.ItemFlag.ItemIsEnabled', 'Qt.ItemFlag'),
    (r'\bQt\.ItemIsSelectable\b', 'Qt.ItemFlag.ItemIsSelectable', 'Qt.ItemFlag'),
    (r'\bQt\.ItemIsEditable\b', 'Qt.ItemFlag.ItemIsEditable', 'Qt.ItemFlag'),
    (r'\bQt\.ItemIsUserCheckable\b', 'Qt.ItemFlag.ItemIsUserCheckable', 'Qt.ItemFlag'),
    (r'\bQt\.Checked\b', 'Qt.CheckState.Checked', 'Qt.CheckState'),
    (r'\bQt\.Unchecked\b', 'Qt.CheckState.Unchecked', 'Qt.CheckState'),
    (r'\bQt\.PartiallyChecked\b', 'Qt.CheckState.PartiallyChecked', 'Qt.CheckState'),
    (r'\bQt\.AscendingOrder\b', 'Qt.SortOrder.AscendingOrder', 'Qt.SortOrder'),
    (r'\bQt\.DescendingOrder\b', 'Qt.SortOrder.DescendingOrder', 'Qt.SortOrder'),
    (r'\bQt\.CopyAction\b', 'Qt.DropAction.CopyAction', 'Qt.DropAction'),
    (r'\bQt\.MoveAction\b', 'Qt.DropAction.MoveAction', 'Qt.DropAction'),
    (r'\bQt\.LinkAction\b', 'Qt.DropAction.LinkAction', 'Qt.DropAction'),
    (r'\bQt\.IgnoreAction\b', 'Qt.DropAction.IgnoreAction', 'Qt.DropAction'),
    (r'\bQt\.ScrollBarAsNeeded\b', 'Qt.ScrollBarPolicy.ScrollBarAsNeeded', 'Qt.ScrollBarPolicy'),
    (r'\bQt\.ScrollBarAlwaysOn\b', 'Qt.ScrollBarPolicy.ScrollBarAlwaysOn', 'Qt.ScrollBarPolicy'),
    (r'\bQt\.ScrollBarAlwaysOff\b', 'Qt.ScrollBarPolicy.ScrollBarOff', 'Qt.ScrollBarPolicy'),
    (r'\bQt\.Expanding\b', 'Qt.SizePolicy.Expanding', 'Qt.SizePolicy'),
    (r'\bQt\.Minimum\b', 'Qt.SizePolicy.Minimum', 'Qt.SizePolicy'),
    (r'\bQt\.Maximum\b', 'Qt.SizePolicy.Maximum', 'Qt.SizePolicy'),
    (r'\bQt\.Preferred\b', 'Qt.SizePolicy.Preferred', 'Qt.SizePolicy'),
    (r'\bQt\.Fixed\b', 'Qt.SizePolicy.Fixed', 'Qt.SizePolicy'),
    (r'\bQt\.TabFocus\b', 'Qt.FocusPolicy.TabFocus', 'Qt.FocusPolicy'),
    (r'\bQt\.ClickFocus\b', 'Qt.FocusPolicy.ClickFocus', 'Qt.FocusPolicy'),
    (r'\bQt\.StrongFocus\b', 'Qt.FocusPolicy.StrongFocus', 'Qt.FocusPolicy'),
    (r'\bQt\.NoFocus\b', 'Qt.FocusPolicy.NoFocus', 'Qt.FocusPolicy'),
    (r'\bQt\.TextSelectableByMouse\b', 'Qt.TextInteractionFlag.TextSelectableByMouse', 'Qt.TextInteractionFlag'),
    (r'\bQt\.TextEditable\b', 'Qt.TextInteractionFlag.TextEditable', 'Qt.TextInteractionFlag'),
    (r'\bQt\.LinksAccessibleByMouse\b', 'Qt.TextInteractionFlag.LinksAccessibleByMouse', 'Qt.TextInteractionFlag'),
    (r'\bQt\.LeftDockWidgetArea\b', 'Qt.DockWidgetArea.LeftDockWidgetArea', 'Qt.DockWidgetArea'),
    (r'\bQt\.RightDockWidgetArea\b', 'Qt.DockWidgetArea.RightDockWidgetArea', 'Qt.DockWidgetArea'),
    (r'\bQt\.TopDockWidgetArea\b', 'Qt.DockWidgetArea.TopDockWidgetArea', 'Qt.DockWidgetArea'),
    (r'\bQt\.BottomDockWidgetArea\b', 'Qt.DockWidgetArea.BottomDockWidgetArea', 'Qt.DockWidgetArea'),
    (r'\bQt\.AllDockWidgetAreas\b', 'Qt.DockWidgetArea.AllDockWidgetAreas', 'Qt.DockWidgetArea'),
    (r'\bQt\.LeftToolBarArea\b', 'Qt.ToolBarArea.LeftToolBarArea', 'Qt.ToolBarArea'),
    (r'\bQt\.RightToolBarArea\b', 'Qt.ToolBarArea.RightToolBarArea', 'Qt.ToolBarArea'),
    (r'\bQt\.TopToolBarArea\b', 'Qt.ToolBarArea.TopToolBarArea', 'Qt.ToolBarArea'),
    (r'\bQt\.BottomToolBarArea\b', 'Qt.ToolBarArea.BottomToolBarArea', 'Qt.ToolBarArea'),
    (r'\bQt\.AllToolBarAreas\b', 'Qt.ToolBarArea.AllToolBarAreas', 'Qt.ToolBarArea'),
    (r'\bQt\.TopLeftCorner\b', 'Qt.Corner.TopLeftCorner', 'Qt.Corner'),
    (r'\bQt\.TopRightCorner\b', 'Qt.Corner.TopRightCorner', 'Qt.Corner'),
    (r'\bQt\.BottomLeftCorner\b', 'Qt.Corner.BottomLeftCorner', 'Qt.Corner'),
    (r'\bQt\.BottomRightCorner\b', 'Qt.Corner.BottomRightCorner', 'Qt.Corner'),
    (r'\bQt\.PortraitOrientation\b', 'Qt.ScreenOrientation.PortraitOrientation', 'Qt.ScreenOrientation'),
    (r'\bQt\.LandscapeOrientation\b', 'Qt.ScreenOrientation.LandscapeOrientation', 'Qt.ScreenOrientation'),
    (r'\bQt\.HighDpiScaleFactorRoundingPolicy\b', 'Qt.HighDpiScaleFactorRoundingPolicy', 'Qt.HighDpiScaleFactorRoundingPolicy'),
    (r'\bQt\.PassThrough\b', 'Qt.HighDpiScaleFactorRoundingPolicy.PassThrough', 'Qt.HighDpiScaleFactorRoundingPolicy'),
    (r'\bQt\.ApplicationModal\b', 'Qt.WindowModality.ApplicationModal', 'Qt.WindowModality'),
    (r'\bQt\.WindowModal\b', 'Qt.WindowModality.WindowModal', 'Qt.WindowModality'),
    (r'\bQt\.NonModal\b', 'Qt.WindowModality.NonModal', 'Qt.WindowModality'),
    (r'\bQt\.CaseSensitive\b', 'Qt.CaseSensitivity.CaseSensitive', 'Qt.CaseSensitivity'),
    (r'\bQt\.CaseInsensitive\b', 'Qt.CaseSensitivity.CaseInsensitive', 'Qt.CaseSensitivity'),
    (r'\bQt\.WindowShortcut\b', 'Qt.ShortcutContext.WindowShortcut', 'Qt.ShortcutContext'),
    (r'\bQt\.ApplicationShortcut\b', 'Qt.ShortcutContext.ApplicationShortcut', 'Qt.ShortcutContext'),
    (r'\bQt\.WidgetWithChildrenShortcut\b', 'Qt.ShortcutContext.WidgetWithChildrenShortcut', 'Qt.ShortcutContext'),
]

# 3. Устаревшие классы → новые
CLASS_REPLACEMENTS: List[Tuple[str, str, str]] = [
    (r'\bQRegExp\b', 'QRegularExpression', 'QRegExp → QRegularExpression'),
    (r'\bQRegExpValidator\b', 'QRegularExpressionValidator', 'QRegExpValidator → QRegularExpressionValidator'),
    (r'\bQDesktopWidget\b', 'QScreen + QApplication.primaryScreen()', 'QDesktopWidget удалён'),
]

# 4. Методы: .exec_() → .exec()
METHOD_REPLACEMENTS: List[Tuple[str, str, str]] = [
    (r'\.exec_\(\)', '.exec()', '.exec_() → .exec()'),
    (r'\.exec_\(', '.exec(', '.exec_( → .exec('),  # с аргументами
]

# 5. Специальные замены для конструкторов
CONSTRUCTOR_FIXES: List[Tuple[str, str, str]] = [
    # QFontMetrics.width() → horizontalAdvance()
    (r'\.width\(\)', '.horizontalAdvance()', 'QFontMetrics.width() → horizontalAdvance()'),

    # QPixmap.load() возвращает bool в PyQt6
    # (это не меняем автоматически, но логируем)
]

# 6. Импорт-фиксы для специфичных случаев
IMPORT_FIXES: List[Tuple[str, str, str]] = [
    # Если используется OpenGL
    (
        r'from PyQt6\.QtOpenGL import QOpenGLWidget',
        'from PyQt6.QtOpenGLWidgets import QOpenGLWidget',
        'QOpenGLWidget перемещён'
    ),
    # Если используется WebEngine
    (
        r'from PyQt6\.QtWebKitWidgets import',
        'from PyQt6.QtWebEngineWidgets import',
        'QtWebKit → QtWebEngine'
    ),
]


# ─────────────────────────────────────────────
# 🛠 ЯДРО МИГРАТОРА
# ─────────────────────────────────────────────

class PyQt6Migrator:
    """Основной класс для миграции кода PyQt5 → PyQt6"""

    def __init__(self, dry_run: bool = False, create_backup: bool = True):
        self.dry_run = dry_run
        self.create_backup = create_backup
        self.stats: Dict[str, int] = {
            'files_processed': 0,
            'files_changed': 0,
            'replacements_made': 0,
            'errors': 0,
        }
        self.log_messages: List[str] = []

        # Компилируем регуляры для производительности
        self._compile_patterns()

    def _compile_patterns(self):
        """Компиляция всех регулярных выражений"""
        self.import_patterns = [(re.compile(p, re.MULTILINE), r) for p, r in IMPORT_REPLACEMENTS]
        self.enum_patterns = [(re.compile(p), r, desc) for p, r, desc in SCOPED_ENUMS]
        self.class_patterns = [(re.compile(p), r, desc) for p, r, desc in CLASS_REPLACEMENTS]
        self.method_patterns = [(re.compile(p), r, desc) for p, r, desc in METHOD_REPLACEMENTS]
        self.constructor_patterns = [(re.compile(p), r, desc) for p, r, desc in CONSTRUCTOR_FIXES]
        self.import_fix_patterns = [(re.compile(p), r, desc) for p, r, desc in IMPORT_FIXES]

    def log(self, message: str, level: str = 'info'):
        """Логирование с уровнем"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        entry = f"[{timestamp}] [{level.upper()}] {message}"
        self.log_messages.append(entry)
        if level == 'error':
            print(f"❌ {message}")
        elif level == 'warning':
            print(f"⚠️  {message}")
        elif level == 'success':
            print(f"✅ {message}")
        elif not self.dry_run:
            print(f"ℹ️  {message}")

    def create_file_backup(self, filepath: Path) -> Optional[Path]:
        """Создание бэкапа файла"""
        if not self.create_backup:
            return None

        backup_dir = filepath.parent / '.pyqt5_backup'
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = backup_dir / f"{filepath.stem}_{timestamp}{filepath.suffix}"

        try:
            shutil.copy2(filepath, backup_path)
            self.log(f"Бэкап: {filepath.name} → {backup_path.name}", 'info')
            return backup_path
        except Exception as e:
            self.log(f"Не удалось создать бэкап {filepath}: {e}", 'error')
            return None

    def apply_replacements(self, content: str, filepath: Path) -> Tuple[str, int]:
        """Применение всех замен к содержимому файла"""
        original_content = content
        replacements_count = 0

        # 1. Замена импортов
        for pattern, replacement in self.import_patterns:
            matches = len(pattern.findall(content))
            if matches:
                content = pattern.sub(replacement, content)
                replacements_count += matches
                self.log(f"  📦 Импорт: {matches} замен в {filepath.name}", 'info')

        # 2. Scoped Enums (самая массовая категория)
        for pattern, replacement, desc in self.enum_patterns:
            matches = len(pattern.findall(content))
            if matches:
                content = pattern.sub(replacement, content)
                replacements_count += matches
                if matches <= 3:  # Не спамить при массовых заменах
                    self.log(f"  🔧 {desc}: {matches} замен", 'info')

        # 3. Замена классов
        for pattern, replacement, desc in self.class_patterns:
            matches = len(pattern.findall(content))
            if matches:
                content = pattern.sub(replacement, content)
                replacements_count += matches
                self.log(f"  🔄 {desc}: {matches} замен", 'warning')

        # 4. Замена методов
        for pattern, replacement, desc in self.method_patterns:
            matches = len(pattern.findall(content))
            if matches:
                content = pattern.sub(replacement, content)
                replacements_count += matches
                self.log(f"  ⚙️  {desc}: {matches} замен", 'info')

        # 5. Фиксы конструкторов
        for pattern, replacement, desc in self.constructor_patterns:
            matches = len(pattern.findall(content))
            if matches:
                # Только логируем, не меняем автоматически (требует ручной проверки)
                self.log(f"  ⚠️  {desc}: {matches} вхождений требуют ручной проверки", 'warning')

        # 6. Специальные импорт-фиксы
        for pattern, replacement, desc in self.import_fix_patterns:
            matches = len(pattern.findall(content))
            if matches:
                content = pattern.sub(replacement, content)
                replacements_count += matches
                self.log(f"  🔗 {desc}: {matches} замен", 'info')

        # 7. Специальная обработка: QRegExp → QRegularExpression
        # Добавляем импорт если нужно
        if 'QRegularExpression' in content and 'from PyQt6.QtCore import' in content:
            if 'QRegularExpressionValidator' in content:
                # Проверяем, есть ли уже этот импорт
                if 'QRegularExpressionValidator' not in content.split('from PyQt6.QtCore import')[1].split('\n')[0]:
                    # Добавляем в импорт
                    content = re.sub(
                        r'(from PyQt6\.QtCore import [^\n]+)',
                        lambda m: m.group(1).rstrip(')') + ', QRegularExpressionValidator)'
                        if ')' in m.group(1) else m.group(1) + ', QRegularExpressionValidator',
                        content
                    )
                    self.log(f"  📦 Добавлен импорт QRegularExpressionValidator", 'info')
        # ─────────────────────────────────────────────
        # 🛠 АВТО-ИМПОРТ: QAbstractItemView (если был заменён)
        # ─────────────────────────────────────────────
        if 'QAbstractItemView.EditTrigger' in content or 'QAbstractItemView.Selection' in content:
            # Проверяем, есть ли уже импорт QtWidgets
            qt_widgets_match = re.search(r'from PyQt6\.QtWidgets import ([^\n]+)', content)
            if qt_widgets_match:
                imports_line = qt_widgets_match.group(1)
                if 'QAbstractItemView' not in imports_line:
                    # Аккуратно добавляем в конец строки импорта
                    new_imports = imports_line.rstrip()
                    if new_imports.endswith(')'):
                        new_imports = new_imports[:-1] + ', QAbstractItemView)'
                    else:
                        new_imports += ', QAbstractItemView'

                    content = content.replace(
                        qt_widgets_match.group(0),
                        f'from PyQt6.QtWidgets import {new_imports}'
                    )
                    self.log("  📦 Авто-добавлен импорт QAbstractItemView", 'info')

        return content, replacements_count

    def process_file(self, filepath: Path) -> bool:
        """Обработка одного файла"""
        try:
            # Читаем файл
            with open(filepath, 'r', encoding='utf-8') as f:
                original_content = f.read()

            # Применяем замены
            new_content, replacements = self.apply_replacements(original_content, filepath)

            # Если есть изменения
            if new_content != original_content:
                self.stats['files_changed'] += 1
                self.stats['replacements_made'] += replacements

                if self.dry_run:
                    self.log(f"🔍 [DRY-RUN] {filepath}: {replacements} замен", 'success')
                else:
                    # Создаём бэкап
                    if self.create_backup:
                        self.create_file_backup(filepath)

                    # Записываем новый контент
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    self.log(f"✏️  {filepath}: {replacements} замен применено", 'success')
            else:
                self.log(f"✓ {filepath}: изменений не требуется", 'info')

            self.stats['files_processed'] += 1
            return True

        except UnicodeDecodeError:
            self.log(f"⚠️  {filepath}: не UTF-8, пропускаем", 'warning')
            return False
        except Exception as e:
            self.log(f"❌ {filepath}: ошибка обработки: {e}", 'error')
            self.stats['errors'] += 1
            return False

    def process_directory(self, root_path: Path, exclude_dirs: List[str] = None):
        """Рекурсивная обработка директории"""
        if exclude_dirs is None:
            exclude_dirs = ['.git', '__pycache__', 'venv', '.venv', 'node_modules', '.pyqt5_backup']

        self.log(f"🔍 Поиск Python-файлов в {root_path}...", 'info')

        for py_file in root_path.rglob('*.py'):
            # Пропускаем исключённые директории
            if any(excl in py_file.parts for excl in exclude_dirs):
                continue

            # Пропускаем сам скрипт миграции
            if py_file.name == 'migrate_pyqt6.py':
                continue

            self.process_file(py_file)

    def print_summary(self):
        """Печать итоговой статистики"""
        print("\n" + "=" * 60)
        print("📊 ИТОГИ МИГРАЦИИ")
        print("=" * 60)
        print(f"📁 Обработано файлов:     {self.stats['files_processed']}")
        print(f"✏️  Изменено файлов:       {self.stats['files_changed']}")
        print(f"🔄 Всего замен:           {self.stats['replacements_made']}")
        print(f"❌ Ошибок:                {self.stats['errors']}")

        if self.dry_run:
            print("\n💡 Это был тестовый прогон (--dry-run)")
            print("   Добавьте флаг --no-backup для применения изменений")

        if self.stats['errors'] > 0:
            print(f"\n⚠️  Проверьте логи выше для деталей об ошибках")

        print("=" * 60 + "\n")

    def generate_report(self, output_path: Path):
        """Генерация детального отчёта"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"PyQt5 → PyQt6 Migration Report\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Mode: {'DRY-RUN' if self.dry_run else 'APPLY'}\n")
            f.write(f"Backup: {'Enabled' if self.create_backup else 'Disabled'}\n\n")

            f.write("─" * 60 + "\n")
            f.write("STATISTICS\n")
            f.write("─" * 60 + "\n")
            for key, value in self.stats.items():
                f.write(f"{key}: {value}\n")

            f.write("\n" + "─" * 60 + "\n")
            f.write("LOG MESSAGES\n")
            f.write("─" * 60 + "\n")
            for msg in self.log_messages:
                f.write(f"{msg}\n")

        self.log(f"📄 Отчёт сохранён: {output_path}", 'success')


# ─────────────────────────────────────────────
# 🎯 CLI ИНТЕРФЕЙС
# ─────────────────────────────────────────────

def parse_args():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='🔄 Автоматическая миграция PyQt5 → PyQt6',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Примеры:
  %(prog)s ./src                      # Применить изменения
  %(prog)s --dry-run ./src           # Тестовый прогон
  %(prog)s --no-backup ./src         # Применить без бэкапов
  %(prog)s --report migration.log    # С сохранением отчёта
        '''
    )

    parser.add_argument(
        'path',
        type=str,
        help='Путь к директории или файлу для миграции'
    )

    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Тестовый режим: показать что будет изменено, но не применять'
    )

    parser.add_argument(
        '--no-backup', '-B',
        action='store_true',
        help='Не создавать бэкапы файлов'
    )

    parser.add_argument(
        '--report', '-r',
        type=str,
        default=None,
        help='Путь к файлу отчёта (по умолчанию: migration_report.txt)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод'
    )

    parser.add_argument(
        '--exclude', '-e',
        type=str,
        nargs='+',
        default=[],
        help='Дополнительные директории для исключения'
    )

    return parser.parse_args()


def main():
    """Точка входа"""
    args = parse_args()

    # Настройка логирования
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    # Проверка пути
    target_path = Path(args.path)
    if not target_path.exists():
        print(f"❌ Путь не найден: {target_path}")
        sys.exit(1)

    # Инициализация миграции
    migrator = PyQt6Migrator(
        dry_run=args.dry_run,
        create_backup=not args.no_backup
    )

    print(f"\n🚀 PyQt5 → PyQt6 Migrator")
    print(f"   Режим: {'🔍 DRY-RUN' if args.dry_run else '✏️  APPLY'}")
    print(f"   Бэкапы: {'✅ Вкл' if not args.no_backup else '❌ Выкл'}")
    print(f"   Цель: {target_path.absolute()}\n")

    if args.dry_run:
        print("⚠️  ВНИМАНИЕ: Это тестовый прогон. Изменения НЕ будут применены.\n")

    # Обработка
    if target_path.is_file():
        migrator.process_file(target_path)
    else:
        exclude_dirs = ['.git', '__pycache__', 'venv', '.venv', 'node_modules'] + args.exclude
        migrator.process_directory(target_path, exclude_dirs)

    # Итоги
    migrator.print_summary()

    # Отчёт
    if args.report:
        report_path = Path(args.report)
        migrator.generate_report(report_path)

    # Код возврата
    sys.exit(1 if migrator.stats['errors'] > 0 else 0)


if __name__ == '__main__':
    main()