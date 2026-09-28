# menus.py
"""제목 표시줄의 설정 메뉴: 테마, 언어, 종료 확인, 업데이트 확인, 정보."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu

from .. import i18n
from ..i18n import tr
from . import icons, theme

if TYPE_CHECKING:
    from .main_window import MainWindow


def build_settings_menu(window: "MainWindow") -> QMenu:
    menu = QMenu(window)
    iconed: list[tuple[QAction | QMenu, str]] = []

    theme_menu = menu.addMenu(tr("menu.theme"))
    iconed.append((theme_menu, "theme"))
    theme_group = QActionGroup(theme_menu)
    for mode, key, icon_name in (("dark", "menu.theme.dark", "moon"), ("light", "menu.theme.light", "sun"),
                                 ("system", "menu.theme.system", "theme")):
        action = theme_menu.addAction(tr(key))
        action.setCheckable(True)
        action.setChecked(window.settings.theme == mode)
        action.triggered.connect(lambda _=False, m=mode: window.set_theme(m))
        theme_group.addAction(action)
        iconed.append((action, icon_name))

    language_menu = menu.addMenu(tr("menu.language"))
    iconed.append((language_menu, "language"))
    language_group = QActionGroup(language_menu)
    choices = [("auto", tr("menu.language.auto"))] + [(code, name) for code, name in i18n.LANGUAGE_NAMES.items()]
    for code, label in choices:
        action = language_menu.addAction(label)
        action.setCheckable(True)
        action.setChecked(window.settings.language == code)
        action.triggered.connect(lambda _=False, c=code: window.set_language(c))
        language_group.addAction(action)
        if code == "auto":
            language_menu.addSeparator()

    menu.addSeparator()
    confirm_action = menu.addAction(tr("menu.confirm_exit"))
    confirm_action.setCheckable(True)
    confirm_action.setChecked(window.settings.confirm_exit)
    confirm_action.toggled.connect(window.set_confirm_exit)
    window.confirm_exit_action = confirm_action
    auto_tools_action = menu.addAction(tr("menu.auto_update_tools"))
    auto_tools_action.setCheckable(True)
    auto_tools_action.setChecked(window.settings.auto_update_tools)
    auto_tools_action.toggled.connect(window.set_auto_update_tools)
    menu.addSeparator()
    update_action = menu.addAction(tr("menu.check_update"))
    update_action.triggered.connect(lambda: window.updates.check(silent=False))
    iconed.append((update_action, "sync"))
    tools_action = menu.addAction(tr("menu.update_tools"))
    tools_action.triggered.connect(lambda: window.update_tools(manual=True))
    iconed.append((tools_action, "download"))
    about_action = menu.addAction(tr("menu.about"))
    about_action.triggered.connect(window.show_about)
    iconed.append((about_action, "info"))

    def paint_icons() -> None:
        color = theme.current().text
        for target, name in iconed:
            target.setIcon(icons.icon(name, color, 16))

    paint_icons()
    theme.manager().changed.connect(paint_icons)
    return menu
