# Файл: app/main_window.py
# Определяет класс ImageEditorWindow, который является главным окном приложения.

import sys
import os  # Для работы с путями к иконкам
from PySide6.QtWidgets import (
    QMainWindow, QLabel, QFileDialog, QScrollArea,
    QMessageBox, QSizePolicy, QInputDialog, QToolBar,
    QDockWidget, QListWidget, QListWidgetItem, QVBoxLayout,
    QWidget, QPushButton, QHBoxLayout
)
from PySide6.QtGui import QPixmap, QImage, QAction, QGuiApplication, QIcon, QKeySequence
from PySide6.QtWidgets import QStyle
from PySide6.QtCore import Qt, Slot, QDir, QSize
from PIL import Image, ImageQt, UnidentifiedImageError
from PySide6.QtWidgets import QColorDialog, QSlider
from app.drawing_canvas import DrawingCanvas
from . import image_operations
from app.gradient_utils import create_linear_gradient
from PySide6.QtWidgets import QDialog, QColorDialog, QComboBox

from .layer_manager import LayerManager, Layer
from .history_manager import HistoryManager


class ImageEditorWindow(QMainWindow):
    def __init__(self, resources_path):  # Принимаем путь к ресурсам
        super().__init__()
        self.resources_path = resources_path
        self.icons_path = os.path.join(self.resources_path, "icons")

        self.setWindowTitle("Фоторедактор Pro v2")

        screen = QGuiApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        self.setGeometry(screen_geometry.width() // 8, screen_geometry.height() // 8,
                         screen_geometry.width() * 3 // 4, screen_geometry.height() * 3 // 4)

        self.layer_manager = LayerManager()
        self.history_manager = HistoryManager()

        # Связываем сигнал изменения активного слоя с обновлением истории
        self.layer_manager.active_layer_changed.connect(self.on_active_layer_changed)

        self.current_pixmap_for_zoom = None
        self.current_zoom_factor = 1.0

        self.image_label = QLabel("Создайте или откройте изображение (Ctrl+O или Ctrl+N)")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        # --- Рисование ---
        self.drawing_canvas = None
        self.is_drawing_active = False
        self.init_drawing_tools()


        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.image_label)

        self.setCentralWidget(self.scroll_area)

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_layer_panel()  # Панель слоев

        self.statusBar().showMessage("Готово к работе!")
        self._update_actions_enabled_state()


    def _get_icon(self, name):
        """Загружает иконку из папки resources/icons."""
        # Сначала пробуем стандартные иконки Qt, если не найдена кастомная
        # Это упрощение, лучше иметь четкое разделение
        standard_icon = None
        if name == "open.png":
            standard_icon = None
        elif name == "save.png":
            standard_icon = None
        elif name == "undo.png":
            standard_icon = None
        elif name == "redo.png":
            standard_icon = None
        elif name == "add_layer.png":
            standard_icon = None  # Пример
        elif name == "reset.png":
            standard_icon = None
        elif name == "rotate.png":
            standard_icon = None

        icon_path = os.path.join(self.icons_path, name)
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        elif standard_icon:
            return self.style().standardIcon(standard_icon)
        return QIcon()  # Пустая иконка, если ничего не найдено

    def init_drawing_tools(self):
        self.brush_action = QAction(QIcon(os.path.join(self.icons_path, "brush.png")), "Кисть", self)
        self.brush_action.setCheckable(True)
        self.brush_action.triggered.connect(self.activate_brush_mode)

        self.eraser_action = QAction(QIcon(os.path.join(self.icons_path, "eraser.png")), "Ластик", self)
        self.eraser_action.setCheckable(True)
        self.eraser_action.triggered.connect(self.activate_eraser_mode)

        self.color_action = QAction("Цвет", self)
        self.color_action.triggered.connect(self.select_brush_color)

        self.brush_size_slider = QSlider(Qt.Horizontal)
        self.brush_size_slider.setMinimum(1)
        self.brush_size_slider.setMaximum(50)
        self.brush_size_slider.setValue(5)
        self.brush_size_slider.setFixedWidth(100)
        self.brush_size_slider.valueChanged.connect(self.change_brush_size)

        self.apply_drawing_action = QAction("✅ Применить", self)
        self.apply_drawing_action.triggered.connect(self.apply_drawing_to_layer)

        self.clear_drawing_action = QAction("🗑 Очистить", self)
        self.clear_drawing_action.triggered.connect(self.clear_drawing_layer)

        self.gradient_action = QAction("Градиент", self)
        self.gradient_action.triggered.connect(self.apply_gradient_to_layer)

        self.rect_action = QAction("⬛ Прямоугольник", self)
        self.rect_action.setCheckable(True)
        self.rect_action.triggered.connect(lambda: self.activate_shape_mode("rect"))

        self.ellipse_action = QAction("🟠 Овал", self)
        self.ellipse_action.setCheckable(True)
        self.ellipse_action.triggered.connect(lambda: self.activate_shape_mode("ellipse"))

        self.line_action = QAction("📏 Линия", self)
        self.line_action.setCheckable(True)
        self.line_action.triggered.connect(lambda: self.activate_shape_mode("line"))

    def activate_brush_mode(self):
        self.start_drawing(eraser=False)
        self.eraser_action.setChecked(False)

    def activate_eraser_mode(self):
        self.start_drawing(eraser=True)
        self.brush_action.setChecked(False)

    def start_drawing(self, eraser=False):
        if not self.drawing_canvas:
            image_size = self.image_label.size()
            self.drawing_canvas = DrawingCanvas(self.image_label, image_size.width(), image_size.height())
            self.drawing_canvas.move(0, 0)
            self.drawing_canvas.show()
        self.drawing_canvas.set_eraser_mode(eraser)
        self.drawing_canvas.set_pen_color(self.drawing_canvas.pen_color)
        self.drawing_canvas.set_pen_width(self.brush_size_slider.value())
        self.is_drawing_active = True

    def select_brush_color(self):
        color = QColorDialog.getColor()
        if color.isValid() and self.drawing_canvas:
            self.drawing_canvas.set_pen_color(color)

    def change_brush_size(self, value):
        if self.drawing_canvas:
            self.drawing_canvas.set_pen_width(value)

    def clear_drawing_layer(self):
        if self.drawing_canvas:
            self.drawing_canvas.clear_canvas()

    def apply_drawing_to_layer(self):
        if not self.drawing_canvas or not self.layer_manager.get_active_layer():
            return
        active_layer = self.layer_manager.get_active_layer()
        drawing_qimage = self.drawing_canvas.get_image()
        drawing_pil = ImageQt.fromqimage(drawing_qimage).convert("RGBA")

        self.history_manager.add_state(active_layer.id, active_layer.image.copy())
        base_pil = active_layer.image.convert("RGBA")
        base_pil.alpha_composite(drawing_pil)
        active_layer.image = base_pil

        self.drawing_canvas.clear_canvas()
        self.update_composite_image_display()
        self.statusBar().showMessage("Рисунок применён к активному слою.")

    def _create_actions(self):
        # Файл
        self.new_action = QAction(self._get_icon("new_file.png"), "&Новый...", self)  # Нужна иконка new_file.png
        self.new_action.triggered.connect(self.create_new_image_dialog)
        self.new_action.setShortcut(QKeySequence.New)

        self.open_action = QAction(self._get_icon("open.png"), "&Открыть...", self)
        self.open_action.triggered.connect(self.open_image_dialog)
        self.open_action.setShortcut(QKeySequence.Open)

        self.save_as_action = QAction(self._get_icon("save.png"), "&Сохранить как...", self)
        self.save_as_action.triggered.connect(self.save_image_dialog)
        self.save_as_action.setShortcut(QKeySequence.SaveAs)

        self.exit_action = QAction("&Выход", self)
        self.exit_action.triggered.connect(self.close)
        self.exit_action.setShortcut(QKeySequence.Quit)

        # Правка
        self.undo_action = QAction(self._get_icon("undo.png"), "&Отменить", self)
        self.undo_action.triggered.connect(self.trigger_undo)
        self.undo_action.setShortcut(QKeySequence.Undo)

        self.redo_action = QAction(self._get_icon("redo.png"), "&Повторить", self)
        self.redo_action.triggered.connect(self.trigger_redo)
        self.redo_action.setShortcut(QKeySequence.Redo)

        # Изображение (Фильтры)
        self.grayscale_action = QAction(self._get_icon("filter_grayscale.png"), "&Оттенки серого", self)
        self.grayscale_action.triggered.connect(
            lambda: self._apply_filter_to_active_layer(image_operations.apply_grayscale, filter_name="Оттенки серого"))

        self.sepia_action = QAction(self._get_icon("filter_sepia.png"), "&Сепия", self)
        self.sepia_action.triggered.connect(
            lambda: self._apply_filter_to_active_layer(image_operations.apply_sepia, filter_name="Сепия"))

        self.brightness_action = QAction(self._get_icon("filter_brightness.png"), "&Яркость...", self)
        self.brightness_action.triggered.connect(self.adjust_brightness_on_active_layer)

        self.contrast_action = QAction(self._get_icon("filter_contrast.png"), "&Контрастность...", self)
        self.contrast_action.triggered.connect(self.adjust_contrast_on_active_layer)

        self.rotate_action = QAction(self._get_icon("rotate.png"), "Повернуть на 90° &вправо", self)
        self.rotate_action.triggered.connect(
            lambda: self._apply_filter_to_active_layer(image_operations.rotate_90_clockwise,
                                                       filter_name="Поворот на 90°"))

        self.blur_action = QAction(self._get_icon("filter_blur.png"), "&Размытие (Гаусс)...", self)
        self.blur_action.triggered.connect(self.apply_blur_to_active_layer)

        self.sharpen_action = QAction(self._get_icon("filter_sharpen.png"), "&Резкость...", self)
        self.sharpen_action.triggered.connect(
            lambda: self._apply_filter_to_active_layer(image_operations.apply_sharpen, filter_name="Резкость"))

        self.emboss_action = QAction(self._get_icon("filter_emboss.png"), "&Тиснение", self)
        self.emboss_action.triggered.connect(
            lambda: self._apply_filter_to_active_layer(image_operations.apply_emboss, filter_name="Тиснение"))

        self.edge_detect_action = QAction(self._get_icon("filter_edges.png"), "Обнаружение &краев", self)
        self.edge_detect_action.triggered.connect(
            lambda: self._apply_filter_to_active_layer(image_operations.apply_edge_detect,
                                                       filter_name="Обнаружение краев"))

        self.reset_layer_action = QAction(self._get_icon("reset.png"), "&Сбросить слой", self)  # Переименовано
        self.reset_layer_action.triggered.connect(self.reset_active_layer_to_original)
        # self.reset_layer_action.setShortcut("Ctrl+R") # Может конфликтовать с Redo на некоторых системах

        # Слои
        self.add_layer_action = QAction(self._get_icon("add_layer.png"), "&Добавить слой", self)
        self.add_layer_action.triggered.connect(self.add_new_layer_action)
        # self.delete_layer_action = QAction("Удалить слой", self) - в будущем

        # Вид
        self.zoom_in_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp), "Увеличить (+)", self)
        self.zoom_in_action.triggered.connect(lambda: self.zoom_image_on_display(1.25))
        self.zoom_in_action.setShortcut(QKeySequence.ZoomIn)

        self.zoom_out_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown), "Уменьшить (-)",
                                       self)
        self.zoom_out_action.triggered.connect(lambda: self.zoom_image_on_display(0.8))
        self.zoom_out_action.setShortcut(QKeySequence.ZoomOut)

        self.actual_size_action = QAction("Реальный &размер (100%)", self)
        self.actual_size_action.triggered.connect(self.set_actual_image_size)
        self.actual_size_action.setShortcut("Ctrl+0")

    def _create_menus(self):
        file_menu = self.menuBar().addMenu("&Файл")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        edit_menu = self.menuBar().addMenu("&Правка")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.reset_layer_action)  # Сброс слоя

        image_menu = self.menuBar().addMenu("&Изображение")
        image_menu.addAction(self.grayscale_action)
        image_menu.addAction(self.sepia_action)
        image_menu.addAction(self.blur_action)
        image_menu.addAction(self.sharpen_action)
        image_menu.addAction(self.emboss_action)
        image_menu.addAction(self.edge_detect_action)
        image_menu.addSeparator()
        image_menu.addAction(self.brightness_action)
        image_menu.addAction(self.contrast_action)
        image_menu.addSeparator()
        image_menu.addAction(self.rotate_action)

        layer_menu = self.menuBar().addMenu("&Слои")
        layer_menu.addAction(self.add_layer_action)
        # layer_menu.addAction(self.delete_layer_action)

        view_menu = self.menuBar().addMenu("&Вид")
        view_menu.addAction(self.zoom_in_action)
        view_menu.addAction(self.zoom_out_action)
        view_menu.addAction(self.actual_size_action)

    def _create_toolbar(self):
        toolbar = QToolBar("Основная панель инструментов")
        toolbar.setMovable(True)
        toolbar.setIconSize(QSize(24, 24))  # Размер иконок
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        toolbar.addAction(self.new_action)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.save_as_action)
        toolbar.addSeparator()
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)
        toolbar.addSeparator()
        toolbar.addAction(self.add_layer_action)
        toolbar.addSeparator()
        # Добавим несколько фильтров для быстрого доступа
        toolbar.addAction(self.grayscale_action)
        toolbar.addAction(self.blur_action)
        toolbar.addAction(self.rotate_action)
        toolbar.addSeparator()
        toolbar.addAction(self.brush_action)
        toolbar.addAction(self.eraser_action)
        toolbar.addAction(self.color_action)
        toolbar.addAction(self.apply_drawing_action)
        toolbar.addAction(self.clear_drawing_action)
        toolbar.addWidget(self.brush_size_slider)
        toolbar.addSeparator()
        toolbar.addAction(self.gradient_action)
        toolbar.addSeparator()
        toolbar.addAction(self.rect_action)
        toolbar.addAction(self.ellipse_action)
        toolbar.addAction(self.line_action)

    def _create_layer_panel(self):
        self.layer_dock_widget = QDockWidget("Слои", self)
        self.layer_dock_widget.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        layer_panel_widget = QWidget()
        layer_layout = QVBoxLayout()

        self.layer_list_widget = QListWidget()
        self.layer_list_widget.setAlternatingRowColors(True)
        self.layer_list_widget.currentItemChanged.connect(self.on_layer_selection_changed)
        layer_layout.addWidget(self.layer_list_widget)

        # Кнопки управления слоями
        layer_buttons_layout = QHBoxLayout()
        add_btn = QPushButton(self._get_icon("add_layer.png"), "Добавить")
        add_btn.clicked.connect(self.add_new_layer_action)
        # delete_btn = QPushButton("Удалить") # Для будущего
        # delete_btn.clicked.connect(self.delete_selected_layer_action)
        layer_buttons_layout.addWidget(add_btn)
        # layer_buttons_layout.addWidget(delete_btn)
        layer_layout.addLayout(layer_buttons_layout)

        layer_panel_widget.setLayout(layer_layout)
        self.layer_dock_widget.setWidget(layer_panel_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.layer_dock_widget)

    def activate_shape_mode(self, mode):
        self.start_drawing()
        if self.drawing_canvas:
            self.drawing_canvas.set_mode(mode)

        # Сброс чеков всех остальных
        for action in [self.brush_action, self.eraser_action,
                       self.rect_action, self.ellipse_action, self.line_action]:
            if action != self.sender():
                action.setChecked(False)

    def apply_gradient_to_layer(self):
        active_layer = self.layer_manager.get_active_layer()
        if not active_layer or not active_layer.image:
            QMessageBox.warning(self, "Нет слоя", "Нет активного слоя для применения градиента.")
            return

        # Выбор цветов
        start_color = QColorDialog.getColor(Qt.white, self, "Начальный цвет")
        if not start_color.isValid():
            return
        end_color = QColorDialog.getColor(Qt.black, self, "Конечный цвет")
        if not end_color.isValid():
            return

        # Выбор направления
        direction_box = QComboBox()
        direction_box.addItems(["Горизонтальный", "Вертикальный"])
        direction_box.setCurrentIndex(0)

        direction_dialog = QDialog(self)
        direction_dialog.setWindowTitle("Направление градиента")
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Выберите направление градиента:"))
        layout.addWidget(direction_box)

        buttons = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Отмена")
        ok_btn.clicked.connect(direction_dialog.accept)
        cancel_btn.clicked.connect(direction_dialog.reject)
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        direction_dialog.setLayout(layout)
        if direction_dialog.exec() != QDialog.Accepted:
            return

        direction = 'horizontal' if direction_box.currentText() == "Горизонтальный" else 'vertical'

        # Применяем градиент
        width, height = active_layer.image.size
        start = (start_color.red(), start_color.green(), start_color.blue(), start_color.alpha())
        end = (end_color.red(), end_color.green(), end_color.blue(), end_color.alpha())
        gradient_img = create_linear_gradient(width, height, start, end, direction)

        self.history_manager.add_state(active_layer.id, active_layer.image.copy())
        active_layer.image = gradient_img
        self.update_composite_image_display()
        self.statusBar().showMessage("Градиент применён.")

    def _update_actions_enabled_state(self):
        has_layers = self.layer_manager.has_layers()
        active_layer = self.layer_manager.get_active_layer()
        has_active_layer_with_image = active_layer is not None and active_layer.image is not None

        self.save_as_action.setEnabled(has_layers)  # Сохраняем композицию

        # Фильтры и операции доступны, если есть активный слой с изображением
        self.grayscale_action.setEnabled(has_active_layer_with_image)
        self.sepia_action.setEnabled(has_active_layer_with_image)
        self.brightness_action.setEnabled(has_active_layer_with_image)
        self.contrast_action.setEnabled(has_active_layer_with_image)
        self.rotate_action.setEnabled(has_active_layer_with_image)
        self.blur_action.setEnabled(has_active_layer_with_image)
        self.sharpen_action.setEnabled(has_active_layer_with_image)
        self.emboss_action.setEnabled(has_active_layer_with_image)
        self.edge_detect_action.setEnabled(has_active_layer_with_image)

        self.reset_layer_action.setEnabled(has_active_layer_with_image and active_layer.original_image is not None)

        # Undo/Redo зависят от состояния HistoryManager для активного слоя
        can_undo, can_redo = False, False
        if active_layer:
            can_undo = self.history_manager.can_undo(active_layer.id)
            can_redo = self.history_manager.can_redo(active_layer.id)
        self.undo_action.setEnabled(can_undo)
        self.redo_action.setEnabled(can_redo)

        # Масштабирование зависит от того, есть ли что-то на холсте
        has_pixmap = self.current_pixmap_for_zoom is not None
        self.zoom_in_action.setEnabled(has_pixmap)
        self.zoom_out_action.setEnabled(has_pixmap)
        self.actual_size_action.setEnabled(has_pixmap)

        # Добавление слоя всегда возможно, если есть проект (хотя бы один слой)
        # self.add_layer_action.setEnabled(True) # Всегда можно добавить слой

    @Slot()
    def create_new_image_dialog(self):
        width, okW = QInputDialog.getInt(self, "Новое изображение", "Ширина (px):", 640, 1, 10000)
        if not okW: return
        height, okH = QInputDialog.getInt(self, "Новое изображение", "Высота (px):", 480, 1, 10000)
        if not okH: return

        # Создаем прозрачный слой по умолчанию
        new_pil_image = Image.new("RGBA", (width, height), (255, 255, 255, 0))

        if not self.layer_manager.has_layers():  # Если слоев нет, это первый
            self.layer_manager.add_layer(image=new_pil_image, name="Фон")
        else:  # Иначе добавляем как новый слой сверху
            self.layer_manager.add_layer(image=new_pil_image)

        self.refresh_layer_list()
        self.update_composite_image_display()
        self.statusBar().showMessage(f"Создано новое изображение {width}x{height}")
        self._update_actions_enabled_state()

    @Slot()
    def open_image_dialog(self):
        start_path = QDir.homePath()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Открыть изображение", start_path,
            "Файлы изображений (*.png *.jpg *.jpeg *.bmp *.gif);;Все файлы (*)"
        )
        if file_path:
            try:
                pil_img = Image.open(file_path).convert("RGBA")

                # Если слоев нет, этот становится первым. Иначе добавляется как новый.
                if not self.layer_manager.has_layers() or not self.layer_manager.get_active_layer():
                    self.layer_manager.clear_all_layers()  # Очищаем, если вдруг что-то было
                    self.history_manager.clear_all_history()
                    layer_name = os.path.basename(file_path)
                    self.layer_manager.add_layer(image=pil_img, name=layer_name, is_original=True)
                else:
                    # Предложить добавить как новый слой или заменить активный? Пока просто новый.
                    layer_name = "Слой " + os.path.basename(file_path)
                    self.layer_manager.add_layer(image=pil_img, name=layer_name, is_original=True)

                self.refresh_layer_list()
                self.update_composite_image_display()
                self.statusBar().showMessage(f"Открыто: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка при открытии: {e}")
            finally:
                self._update_actions_enabled_state()

    @Slot()
    def save_image_dialog(self):
        if not self.layer_manager.has_layers():
            QMessageBox.warning(self, "Внимание", "Нет изображения для сохранения.")
            return

        # Сохраняем композитное изображение
        composite_image = self.layer_manager.get_composite_image()
        if not composite_image:
            QMessageBox.warning(self, "Внимание", "Не удалось создать композитное изображение для сохранения.")
            return

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Сохранить изображение как...", QDir.homePath(),
            "PNG файл (*.png);;JPEG файл (*.jpg *.jpeg);;BMP файл (*.bmp);;Все файлы (*)"
        )

        if file_path:
            try:
                image_operations.save_image(composite_image, file_path)  # Используем функцию из image_operations
                self.statusBar().showMessage(f"Композиция сохранена в: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка сохранения", f"Не удалось сохранить: {e}")

    def update_composite_image_display(self):
        """Обновляет отображаемое изображение в QLabel на основе композиции слоев."""
        active_layer = self.layer_manager.get_active_layer()
        if not self.layer_manager.has_layers() and not active_layer:
            self.image_label.clear()
            self.image_label.setText("Создайте или откройте изображение")
            self.current_pixmap_for_zoom = None
            self._update_actions_enabled_state()
            return

        # Получаем композитное изображение от LayerManager
        # Если нет активного слоя или слоев, LayerManager вернет None или пустое изображение
        # В этом случае, если есть активный слой, но он пустой, отобразим его (прозрачный)
        # Иначе, если слоев нет, отобразим композицию (которая будет пустой)

        composite_image_pil = self.layer_manager.get_composite_image()

        if composite_image_pil:
            try:
                q_image = ImageQt.ImageQt(composite_image_pil)
                pixmap = QPixmap.fromImage(q_image)

                self.image_label.setPixmap(pixmap)
                self.image_label.adjustSize()
                self.current_pixmap_for_zoom = pixmap
                self.current_zoom_factor = 1.0  # Сбрасываем зум при обновлении основного изображения
            except Exception as e:
                QMessageBox.critical(self, "Ошибка отображения", f"Не удалось отобразить композицию: {e}")
                self.image_label.setText("Ошибка отображения композиции")
                self.current_pixmap_for_zoom = None
        else:  # Если composite_image_pil is None (например, все слои невидимы или нет слоев)
            # Попытаемся отобразить активный слой, если он есть, даже если он пустой (прозрачный)
            active_layer = self.layer_manager.get_active_layer()
            if active_layer and active_layer.image:
                try:
                    q_image = ImageQt.ImageQt(active_layer.image)
                    pixmap = QPixmap.fromImage(q_image)
                    self.image_label.setPixmap(pixmap)
                    self.image_label.adjustSize()
                    self.current_pixmap_for_zoom = pixmap
                    self.current_zoom_factor = 1.0
                except Exception as e:
                    self.image_label.setText(f"Ошибка отображения активного слоя: {e}")
                    self.current_pixmap_for_zoom = None
            else:  # Совсем нечего отображать
                self.image_label.clear()
                self.image_label.setText("Нет видимых слоев или активного слоя для отображения")
                self.current_pixmap_for_zoom = None

        self._update_actions_enabled_state()

    def _apply_filter_to_active_layer(self, filter_function, *args, filter_name="фильтр"):
        active_layer = self.layer_manager.get_active_layer()
        if active_layer and active_layer.image:
            try:
                # Сохраняем состояние ДО применения фильтра для Undo
                self.history_manager.add_state(active_layer.id, active_layer.image.copy())

                processed_image = filter_function(active_layer.image.copy(), *args)  # Применяем к копии
                if processed_image:
                    active_layer.image = processed_image  # Обновляем изображение слоя
                    self.update_composite_image_display()  # Обновляем всю композицию
                    self.statusBar().showMessage(f"Применен '{filter_name}' к слою '{active_layer.name}'")
                else:
                    QMessageBox.warning(self, "Ошибка фильтра", f"Функция '{filter_name}' не вернула изображение.")
                    # Откатываем добавленное состояние, так как операция не удалась
                    self.history_manager.undo(active_layer.id)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка фильтра", f"Не удалось применить '{filter_name}': {e}")
                # Откатываем добавленное состояние
                self.history_manager.undo(active_layer.id)
        else:
            QMessageBox.information(self, "Информация", "Нет активного слоя с изображением для применения фильтра.")
        self._update_actions_enabled_state()

    # --- Слоты для конкретных фильтров ---
    @Slot()
    def adjust_brightness_on_active_layer(self):
        active_layer = self.layer_manager.get_active_layer()
        if not (active_layer and active_layer.image):
            QMessageBox.information(self, "Информация", "Сначала выберите слой с изображением.")
            return
        factor, ok = QInputDialog.getDouble(self, "Регулировка яркости", "Коэффициент:", 1.0, 0.1, 5.0, 2)
        if ok: self._apply_filter_to_active_layer(image_operations.adjust_brightness, factor, filter_name="Яркость")

    @Slot()
    def adjust_contrast_on_active_layer(self):
        active_layer = self.layer_manager.get_active_layer()
        if not (active_layer and active_layer.image):
            QMessageBox.information(self, "Информация", "Сначала выберите слой с изображением.")
            return
        factor, ok = QInputDialog.getDouble(self, "Регулировка контрастности", "Коэффициент:", 1.0, 0.1, 5.0, 2)
        if ok: self._apply_filter_to_active_layer(image_operations.adjust_contrast, factor, filter_name="Контрастность")

    @Slot()
    def apply_blur_to_active_layer(self):
        active_layer = self.layer_manager.get_active_layer()
        if not (active_layer and active_layer.image):
            QMessageBox.information(self, "Информация", "Сначала выберите слой с изображением.")
            return
        radius, ok = QInputDialog.getDouble(self, "Размытие по Гауссу", "Радиус размытия:", 2.0, 0.1, 20.0, 1)
        if ok: self._apply_filter_to_active_layer(image_operations.apply_gaussian_blur, radius, filter_name="Размытие")

    @Slot()
    def reset_active_layer_to_original(self):
        active_layer = self.layer_manager.get_active_layer()
        if active_layer and active_layer.original_image:
            # Сохраняем текущее состояние для Undo перед сбросом
            self.history_manager.add_state(active_layer.id, active_layer.image.copy())

            active_layer.image = active_layer.original_image.copy()
            self.history_manager.clear_history_for_layer(active_layer.id)  # Очищаем историю для этого слоя после сброса
            # Добавляем "original_image" как первое состояние в очищенную историю
            self.history_manager.add_state(active_layer.id, active_layer.image.copy(), is_initial_state=True)

            self.update_composite_image_display()
            self.statusBar().showMessage(f"Слой '{active_layer.name}' сброшен к оригиналу.")
        elif active_layer:
            QMessageBox.information(self, "Информация",
                                    f"Для слоя '{active_layer.name}' нет исходного состояния для сброса.")
        else:
            QMessageBox.information(self, "Информация", "Нет активного слоя для сброса.")
        self._update_actions_enabled_state()

    # --- Управление слоями ---
    def refresh_layer_list(self):
        self.layer_list_widget.clear()
        for i, layer in enumerate(reversed(self.layer_manager.layers)):  # Отображаем в порядке сверху вниз
            item_text = f"{layer.name} {'(V)' if layer.visible else '(H)'}"  # V - visible, H - hidden
            list_item = QListWidgetItem(item_text, self.layer_list_widget)
            list_item.setData(Qt.UserRole, layer.id)  # Сохраняем ID слоя в элементе списка
            if layer == self.layer_manager.get_active_layer():
                self.layer_list_widget.setCurrentItem(list_item)
        self._update_actions_enabled_state()

    @Slot()
    def on_layer_selection_changed(self, current_item, previous_item):
        if current_item:
            layer_id = current_item.data(Qt.UserRole)
            self.layer_manager.set_active_layer_by_id(layer_id)
            # self.update_composite_image_display() # Обновляем, если нужно показать только активный слой или рамку
            self.statusBar().showMessage(f"Активный слой: {self.layer_manager.get_active_layer().name}")
        self._update_actions_enabled_state()

    @Slot()
    def on_active_layer_changed(self, layer_id):
        """Слот, который вызывается при изменении активного слоя в LayerManager."""
        # Обновить состояние кнопок Undo/Redo, так как история зависит от слоя
        self._update_actions_enabled_state()
        # Обновить выделение в QListWidget, если изменение пришло не из него
        for i in range(self.layer_list_widget.count()):
            item = self.layer_list_widget.item(i)
            if item.data(Qt.UserRole) == layer_id:
                if self.layer_list_widget.currentItem() != item:  # Избегаем рекурсии
                    self.layer_list_widget.setCurrentItem(item)
                break

    @Slot()
    def add_new_layer_action(self):
        # Определяем размеры для нового слоя. Если есть другие слои, берем их размер.
        # Иначе, дефолтные или диалог.
        width, height = 640, 480  # Дефолт
        if self.layer_manager.has_layers():
            ref_layer = self.layer_manager.layers[0]  # Берем размер первого слоя как референс
            if ref_layer.image:
                width, height = ref_layer.image.size

        new_layer_image = Image.new("RGBA", (width, height), (0, 0, 0, 0))  # Прозрачный по умолчанию
        self.layer_manager.add_layer(image=new_layer_image, is_original=True)  # is_original для сброса
        self.refresh_layer_list()
        self.update_composite_image_display()  # Обновляем холст
        self.statusBar().showMessage("Добавлен новый слой.")
        self._update_actions_enabled_state()

    # --- История (Undo/Redo) ---
    @Slot()
    def trigger_undo(self):
        active_layer = self.layer_manager.get_active_layer()
        if active_layer:
            undone_image = self.history_manager.undo(active_layer.id)
            if undone_image:
                active_layer.image = undone_image
                self.update_composite_image_display()
                self.statusBar().showMessage(f"Отменено действие для слоя '{active_layer.name}'")
            else:
                self.statusBar().showMessage(f"Больше нет действий для отмены на слое '{active_layer.name}'")
        self._update_actions_enabled_state()

    @Slot()
    def trigger_redo(self):
        active_layer = self.layer_manager.get_active_layer()
        if active_layer:
            redone_image = self.history_manager.redo(active_layer.id)
            if redone_image:
                active_layer.image = redone_image
                self.update_composite_image_display()
                self.statusBar().showMessage(f"Повторено действие для слоя '{active_layer.name}'")
            else:
                self.statusBar().showMessage(f"Больше нет действий для повтора на слое '{active_layer.name}'")
        self._update_actions_enabled_state()

    # --- Масштабирование отображения ---
    @Slot()
    def zoom_image_on_display(self, factor):
        if self.current_pixmap_for_zoom:  # Масштабируем то, что сейчас на холсте (композицию)
            self.current_zoom_factor *= factor
            self.current_zoom_factor = max(0.05, min(self.current_zoom_factor, 20.0))  # Ограничения

            # Масштабируем исходный current_pixmap_for_zoom, а не уже смасштабированный
            # Это важно для сохранения качества при многократном зуме
            original_composite_pixmap = ImageQt.ImageQt(self.layer_manager.get_composite_image())
            original_composite_pixmap = QPixmap.fromImage(original_composite_pixmap)

            new_width = int(original_composite_pixmap.width() * self.current_zoom_factor)
            new_height = int(original_composite_pixmap.height() * self.current_zoom_factor)

            if new_width > 0 and new_height > 0:
                scaled_pixmap = original_composite_pixmap.scaled(
                    new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
                # self.image_label.adjustSize() # Не нужно, если scroll_area.widgetResizable = True и label.sizePolicy = Ignored
            self.statusBar().showMessage(f"Масштаб: {self.current_zoom_factor:.2f}x")

    @Slot()
    def set_actual_image_size(self):
        if self.current_pixmap_for_zoom:  # current_pixmap_for_zoom это уже композиция
            composite_pil_image = self.layer_manager.get_composite_image()
            if composite_pil_image:
                q_image = ImageQt.ImageQt(composite_pil_image)
                pixmap = QPixmap.fromImage(q_image)
                self.image_label.setPixmap(pixmap)
                # self.image_label.adjustSize()
                self.current_zoom_factor = 1.0
                self.statusBar().showMessage("Масштаб: 1.00x (Реальный размер)")

    def closeEvent(self, event):
        # TODO: Проверка на несохраненные изменения перед выходом
        reply = QMessageBox.question(self, 'Подтверждение выхода',
                                     "Вы уверены, что хотите выйти?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()