# Файл: app/ui_utils.py
# (Без изменений в этой версии, но оставлен для будущих утилит)
from PySide6.QtGui import QAction, QIcon

def create_action(parent, text, slot=None, shortcut=None, icon_path=None, tip=None):
    action = QAction(text, parent)
    if icon_path: action.setIcon(QIcon(icon_path))
    if slot: action.triggered.connect(slot)
    if shortcut: action.setShortcut(shortcut)
    if tip:
        action.setToolTip(tip)
        action.setStatusTip(tip)
    return action