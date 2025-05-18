# Файл: main.py
# Точка входа в приложение. Инициализирует QApplication и главное окно.

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from PySide6.QtCore import QFile, QTextStream, QDir
from app.main_window import ImageEditorWindow
import os


def main():
    app = QApplication(sys.argv)

    # Установка путей для ресурсов (иконки, стили)
    # Это важно, чтобы приложение находило ресурсы, когда запускается из разных мест
    # или когда скомпилировано.
    if getattr(sys, 'frozen', False):
        # Если приложение "заморожено" PyInstaller'ом
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(__file__)

    resources_path = os.path.join(application_path, "resources")
    styles_path = os.path.join(resources_path, "styles", "style.qss")

    # Устанавливаем QDir.setCurrent для корректной работы относительных путей в QSS (для url())
    # Хотя в нашем style.qss пока нет url(), это хорошая практика.
    QDir.setCurrent(resources_path)

    # Загрузка стилей QSS
    try:
        style_file = QFile(styles_path)  # Используем абсолютный путь
        if style_file.open(QFile.ReadOnly | QFile.Text):
            stream = QTextStream(style_file)
            app.setStyleSheet(stream.readAll())
            style_file.close()
            print(f"Стили успешно загружены из: {styles_path}")
        else:
            print(f"Не удалось открыть файл стилей: {styles_path}, ошибка: {style_file.errorString()}")
            # Попробуем относительный путь как запасной вариант, если структура другая
            style_file_rel = QFile("resources/styles/style.qss")
            if style_file_rel.open(QFile.ReadOnly | QFile.Text):
                stream_rel = QTextStream(style_file_rel)
                app.setStyleSheet(stream_rel.readAll())
                style_file_rel.close()
                print("Стили успешно загружены по относительному пути (запасной вариант).")
            else:
                print("Не удалось загрузить файл стилей и по относительному пути.")

    except Exception as e:
        print(f"Ошибка при загрузке стилей: {e}")

    window = ImageEditorWindow(resources_path)  # Передаем путь к ресурсам
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()