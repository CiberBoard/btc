# utils/settings_manager.py
"""
🔧 Settings Manager v1.3 — Единая система настроек (ФИКС QByteArray)
==================================================
"""

from __future__ import annotations
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, TypeVar, Union

from PyQt6.QtCore import QObject, pyqtSignal, QByteArray
from PyQt6.QtWidgets import QLineEdit, QSpinBox, QComboBox, QCheckBox

logger = logging.getLogger(__name__)
T = TypeVar('T')
PathLike = Union[str, Path, None]


def _normalize_value(value: Any) -> Any:
    """
    ✅ Конвертирует Qt-типы в сериализуемые Python-типы

    - QByteArray → base64 str
    - QColor → hex str
    - и т.д.
    """
    if isinstance(value, QByteArray):
        # 🔧 Конвертируем QByteArray в base64-строку для JSON
        return value.toBase64().data().decode('ascii')

    # Можно добавить другие конвертации при необходимости:
    # from PyQt6.QtGui import QColor
    # if isinstance(value, QColor):
    #     return value.name()

    return value


class SettingsManager(QObject):
    """✅ Централизованный менеджер настроек — ФИКС QByteArray"""

    # 🔧 ИСПРАВЛЕНО: Используем 'object' вместо 'Any' для совместимости с Qt-типами
    settings_changed = pyqtSignal(str, object)
    settings_saved = pyqtSignal()
    settings_loaded = pyqtSignal()

    _instance: Optional['SettingsManager'] = None

    def __init__(self, base_dir: PathLike = None, filename: str = "settings.json"):
        super().__init__()

        if SettingsManager._instance is not None:
            return

        SettingsManager._instance = self

        if base_dir is None:
            self.base_dir = Path(__file__).parent.parent
        elif isinstance(base_dir, Path):
            self.base_dir = base_dir
        else:
            self.base_dir = Path(base_dir)

        self.filename = filename
        self.filepath = self.base_dir / filename

        self.namespaces = {
            'main': {}, 'matrix': {}, 'gpu': {}, 'cpu': {},
            'vanity': {}, 'kangaroo': {}, 'ui': {},
        }

        self._cache: Dict[str, Any] = {}
        self._loaded = False
        self._ui_parent: Optional[QObject] = None

        self.load()

    @classmethod
    def get_instance(cls, base_dir: PathLike = None, filename: str = "settings.json") -> 'SettingsManager':
        if cls._instance is None:
            cls._instance = SettingsManager(base_dir, filename)
        return cls._instance

    # ═══════════════════════════════════════════════
    # 🔑 БАЗОВЫЕ МЕТОДЫ
    # ═══════════════════════════════════════════════

    def load(self) -> bool:
        """✅ Загрузить настройки из файла"""
        if self._loaded:
            return True

        try:
            if not self.filepath.exists():
                logger.info(f"Файл настроек не найден: {self.filepath}")
                self._loaded = True
                return True

            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for ns in self.namespaces:
                self.namespaces[ns] = data.get(ns, {})

            self._cache = data
            self._loaded = True

            logger.info(f"✅ Настройки загружены: {self.filepath}")
            self.settings_loaded.emit()
            return True

        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}")
            self._create_backup_and_reset()
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки настроек: {e}")
            return False

    def save(self) -> bool:
        """✅ Сохранить настройки в файл"""
        try:
            data = {ns: dict(vals) for ns, vals in self.namespaces.items()}
            data.update(self._cache)

            self.filepath.parent.mkdir(parents=True, exist_ok=True)

            fd, temp_path = tempfile.mkstemp(
                dir=str(self.filepath.parent),
                suffix='.tmp',
                prefix='.settings_'
            )
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                Path(temp_path).replace(self.filepath)
            except:
                try:
                    os.unlink(temp_path)
                except:
                    pass
                raise

            logger.info(f"💾 Настройки сохранены: {self.filepath}")
            self.settings_saved.emit()
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения настроек: {e}")
            return False

    def _create_backup_and_reset(self):
        """Создать бэкап повреждённого файла"""
        try:
            backup_path = self.filepath.with_suffix('.json.bak')
            if self.filepath.exists():
                self.filepath.rename(backup_path)
                logger.warning(f"🔄 Создан бэкап: {backup_path}")
            self.namespaces = {ns: {} for ns in self.namespaces}
            self._cache = {}
        except Exception as e:
            logger.error(f"❌ Ошибка создания бэкапа: {e}")

    # ═══════════════════════════════════════════════
    # 🗂 МЕТОДЫ С НЕЙМСПЕЙСАМИ
    # ═══════════════════════════════════════════════

    def get(self, key: str, default: T = None, namespace: str = 'main') -> T:
        """✅ Получить значение из указанного неймспейса"""
        if namespace in self.namespaces:
            return self.namespaces[namespace].get(key, default)
        return self._cache.get(key, default)

    def set(self, key: str, value: Any, namespace: str = 'main',
            auto_save: bool = False) -> bool:
        """✅ Установить значение в указанный неймспейс"""
        if namespace not in self.namespaces:
            logger.warning(f"⚠️ Неизвестный неймспейс: {namespace}")
            return False

        old_value = self.namespaces[namespace].get(key)

        # 🔧 ИСПРАВЛЕНО: Нормализуем значение перед сохранением и эмиссией
        normalized_value = _normalize_value(value)
        self.namespaces[namespace][key] = normalized_value

        # 🔧 Эмитим уже нормализованное значение
        if old_value != normalized_value:
            self.settings_changed.emit(f"{namespace}.{key}", normalized_value)

        if auto_save:
            return self.save()
        return True

    def get_global(self, key: str, default: T = None) -> T:
        return self._cache.get(key, default)

    def set_global(self, key: str, value: Any, auto_save: bool = False) -> bool:
        # 🔧 Нормализуем глобальные значения тоже
        normalized_value = _normalize_value(value)
        self._cache[key] = normalized_value
        self.settings_changed.emit(key, normalized_value)
        if auto_save:
            return self.save()
        return True

    # ═══════════════════════════════════════════════
    # 🎛 УДОБНЫЕ МЕТОДЫ ДЛЯ UI
    # ═══════════════════════════════════════════════

    def load_ui_settings(self, widget_map: Dict[str, tuple], namespace: str = 'main'):
        """✅ Загрузить настройки в виджеты UI (поддержка кортежей из 2 или 3 элементов)"""
        for attr_name, cfg in widget_map.items():
            try:
                # 🔧 Безопасное извлечение: всегда 3 элемента, даже если в кортеже 2
                key = cfg[0]
                default = cfg[1] if len(cfg) > 1 else None
                setter = cfg[2] if len(cfg) > 2 else 'setText'

                value = self.get(key, default, namespace)
                widget = self._find_widget(attr_name)

                if not widget:
                    logger.warning(f"⚠️ Виджет '{attr_name}' не найден для настройки '{key}'")
                    continue

                method = getattr(widget, setter, None)
                if callable(method):
                    method(value)
                else:
                    setattr(widget, setter, value)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка загрузки '{attr_name}': {e}")

    def save_ui_settings(self, widget_map: Dict[str, tuple], namespace: str = 'main',
                         auto_save: bool = False):
        for attr_name, cfg in widget_map.items():
            try:
                key = cfg[0]
                getter = cfg[1] if len(cfg) > 1 else 'text'  # дефолт для QLineEdit

                widget = self._find_widget(attr_name)
                if not widget: continue

                method = getattr(widget, getter, None)
                value = method() if callable(method) else getattr(widget, getter, None)
                if value is not None:
                    self.set(key, value, namespace, auto_save=False)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка сохранения '{attr_name}': {e}")

        if auto_save:
            self.save()

    def auto_sync_all_widgets(self, parent_obj, namespace='main', save_mode=True):
        """🔄 Автоматически сохраняет/загружает ВСЕ интерактивные виджеты без ручного маппинга"""
        from PyQt6.QtWidgets import QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox

        # 1. Собираем ВСЕ виджеты в дереве родителя (включая self.ui, табы, группы и т.д.)
        widgets = parent_obj.findChildren((QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox))

        for widget in widgets:
            # 2. Определяем ключ настроек: objectName > имя_атрибута
            key = widget.objectName()

            # Пропускаем системные и безымянные
            if not key or key.startswith('qt_') or key.startswith('_'):
                # 🔧 Быстрый поиск через заранее построенный маппинг
                if not hasattr(parent_obj, '_widget_attr_map'):
                    # Строим маппинг один раз при первом вызове
                    parent_obj._widget_attr_map = {}
                    for target in [parent_obj, getattr(parent_obj, 'ui', None)]:
                        if not target: continue
                        for attr in dir(target):
                            if attr.startswith('_'): continue
                            val = getattr(target, attr, None)
                            if isinstance(val, (QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox)):
                                parent_obj._widget_attr_map[id(val)] = attr

                # Быстрый поиск по ID виджета
                key = parent_obj._widget_attr_map.get(id(widget))
                if not key: continue

            if save_mode:
                # 💾 СОХРАНЕНИЕ
                if isinstance(widget, QLineEdit):
                    value = widget.text()
                elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    value = widget.value()
                elif isinstance(widget, QComboBox):
                    value = widget.currentText()
                elif isinstance(widget, QCheckBox):
                    value = widget.isChecked()
                self.set(key, value, namespace)
            else:
                # 📥 ЗАГРУЗКА
                value = self.get(key, None, namespace)
                if value is None: continue

                if isinstance(widget, QLineEdit):
                    widget.setText(str(value))
                elif isinstance(widget, QSpinBox):
                    widget.setValue(value)
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(value))
                elif isinstance(widget, QComboBox):
                    idx = widget.findText(str(value))
                    if idx >= 0: widget.setCurrentIndex(idx)
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))


    # ═══════════════════════════════════════════════
    # 🔄 УТИЛИТЫ
    # ═══════════════════════════════════════════════

    def reset(self, namespace: Optional[str] = None):
        if namespace:
            if namespace in self.namespaces:
                self.namespaces[namespace].clear()
        else:
            self.namespaces = {ns: {} for ns in self.namespaces}
            self._cache.clear()

    def export(self) -> Dict[str, Any]:
        data = {ns: dict(vals) for ns, vals in self.namespaces.items()}
        data.update(self._cache)
        return data

    def import_settings(self, data: Dict[str, Any], merge: bool = True) -> None:
      if merge:
        for ns, values in data.items():
            if ns in self.namespaces and isinstance(values, dict):
                self.namespaces[ns].update(values)
            else:
                self._cache.update({ns: values} if not isinstance(values, dict) else values)
      else:
        self.namespaces = {ns: {} for ns in self.namespaces}
        for ns, values in data.items():
            if ns in self.namespaces and isinstance(values, dict):
                self.namespaces[ns] = values
            else:
                self._cache[ns] = values

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def __repr__(self):
        return f"SettingsManager(base_dir={self.base_dir}, loaded={self._loaded})"


def sync_widget(self, widget, key: str, namespace: str = 'main', save_mode: bool = True):
    """✅ Синхронизировать ОДИН виджет с явным ключом"""
    if save_mode:
        if isinstance(widget, QLineEdit): value = widget.text()
        elif isinstance(widget, QSpinBox): value = widget.value()
        elif isinstance(widget, QComboBox): value = widget.currentText()
        elif isinstance(widget, QCheckBox): value = widget.isChecked()
        else: return
        self.set(key, value, namespace)
    else:
        value = self.get(key, None, namespace)
        if value is None: return
        if isinstance(widget, QLineEdit): widget.setText(str(value))
        elif isinstance(widget, QSpinBox): widget.setValue(int(value))
        elif isinstance(widget, QComboBox):
            idx = widget.findText(str(value))
            if idx >= 0: widget.setCurrentIndex(idx)
        elif isinstance(widget, QCheckBox): widget.setChecked(bool(value))

# ═══════════════════════════════════════════════
# 🎯 УДОБНЫЕ ФУНКЦИИ-ХЕЛПЕРЫ
# ═══════════════════════════════════════════════

def get_settings(base_dir: PathLike = None) -> SettingsManager:
    """✅ Получить глобальный экземпляр менеджера настроек"""
    return SettingsManager.get_instance(base_dir)

