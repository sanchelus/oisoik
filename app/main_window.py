# Файл: app/main_window.py
# Определяет класс ImageEditorWindow, который является главным окном приложения.

import sys
import os 
from PySide6.QtWidgets import (
    QMainWindow, QLabel, QFileDialog, QScrollArea,
    QMessageBox, QSizePolicy, QInputDialog, QToolBar,
    QDockWidget, QListWidget, QListWidgetItem, QVBoxLayout,
    QWidget, QPushButton, QHBoxLayout, QSpacerItem, QLayout
)

from PySide6.QtGui import QPixmap, QImage, QAction, QGuiApplication, QIcon, QKeySequence, QColor, QCloseEvent
from PySide6.QtWidgets import QStyle 
from PySide6.QtCore import Qt, Slot, QDir, QSize
from PIL import Image, ImageQt, UnidentifiedImageError 
from PySide6.QtWidgets import QColorDialog, QSlider 


from .drawing_canvas import DrawingCanvas # Используем относительный импорт для модулей внутри пакета
from . import image_operations 
from .gradient_utils import create_linear_gradient 
from .layer_manager import LayerManager, Layer 
from .history_manager import HistoryManager 

class ImageEditorWindow(QMainWindow):
    """
    Главное окно приложения для редактирования изображений.

    Предоставляет пользовательский интерфейс для открытия, сохранения,
    редактирования изображений с использованием слоев, фильтров и инструментов рисования.
    """
    def __init__(self, resources_path): 
        """
        Инициализирует главное окно редактора.

        Args:
            resources_path (str): Путь к папке с ресурсами приложения (иконки, стили).
        """
        super().__init__()
        self.resources_path = resources_path
        self.icons_path = os.path.join(self.resources_path, "icons")

        self.setWindowTitle("ОИСОИК")
        screen = QGuiApplication.primaryScreen()
        if screen: 
            screen_geometry = screen.availableGeometry()
            self.setGeometry(screen_geometry.width() // 8, screen_geometry.height() // 8,
                             screen_geometry.width() * 3 // 4, screen_geometry.height() * 3 // 4)
        else: 
            self.setGeometry(100, 100, 1024, 768)


        self.layer_manager = LayerManager()
        self.history_manager = HistoryManager()

        self.layer_manager.active_layer_changed.connect(self.on_active_layer_changed_for_history_and_ui)

        self.current_pixmap_for_zoom = None
        self.current_zoom_factor = 1.0

        self.image_label = QLabel("Создайте или откройте изображение (Ctrl+O или Ctrl+N)")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.image_label.setStyleSheet("border: 1px solid gray;") 
        self.image_label.adjustSize() 
        self.image_label.setAutoFillBackground(False) 

        self.image_label_container = QWidget()
        self.image_label_container.setAutoFillBackground(False) 

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0,0,0,0) 
        h_layout.addStretch() 
        h_layout.addWidget(self.image_label)
        h_layout.addStretch() 

        v_layout = QVBoxLayout(self.image_label_container) 
        v_layout.setContentsMargins(0,0,0,0)
        v_layout.addStretch() 
        v_layout.addLayout(h_layout) 
        v_layout.addStretch() 

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True) 
        self.scroll_area.setWidget(self.image_label_container) 

        self.setCentralWidget(self.scroll_area)

        self.drawing_canvas = None
        self.is_drawing_active = False 

        self.init_drawing_tools()
        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_layer_panel() 

        self.statusBar().showMessage("Готово к работе!")
        self._update_actions_enabled_state()

    def _get_icon(self, name: str) -> QIcon:
        """
        Загружает иконку по имени из папки ресурсов.
        Если кастомная иконка не найдена, пытается загрузить стандартную иконку Qt.

        Args:
            name (str): Имя файла иконки (например, "open.png").

        Returns:
            QIcon: Загруженная иконка или пустая иконка, если ничего не найдено.
        """
        icon_path = os.path.join(self.icons_path, name)
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        
        if name == "open.png":
            return self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        elif name == "save.png":
            return self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        elif name == "new_file.png": 
             return self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon) 
        elif name == "undo.png":
            return self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack)
        elif name == "redo.png":
            return self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward)
        return QIcon() 

    def init_drawing_tools(self):
        """Инициализирует QAction и виджеты для инструментов рисования."""
        self.brush_action = QAction(self._get_icon("brush.png"), "Кисть", self)
        self.brush_action.setCheckable(True)
        self.brush_action.triggered.connect(self.activate_brush_mode)

        self.eraser_action = QAction(self._get_icon("eraser.png"), "Ластик", self)
        self.eraser_action.setCheckable(True)
        self.eraser_action.triggered.connect(self.activate_eraser_mode)

        self.rect_action = QAction(self._get_icon("rectangle.png"), "Прямоугольник", self) 
        self.rect_action.setCheckable(True)
        self.rect_action.triggered.connect(lambda: self.activate_shape_mode("rect"))

        self.ellipse_action = QAction(self._get_icon("ellipse.png"), "Овал", self) 
        self.ellipse_action.setCheckable(True)
        self.ellipse_action.triggered.connect(lambda: self.activate_shape_mode("ellipse"))

        self.line_action = QAction(self._get_icon("line.png"), "Линия", self) 
        self.line_action.setCheckable(True)
        self.line_action.triggered.connect(lambda: self.activate_shape_mode("line"))

        self.color_action = QAction(self._get_icon("color_picker.png"), "Цвет кисти/фигуры", self) 
        self.color_action.triggered.connect(self.select_brush_color)

        self.brush_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_size_slider.setMinimum(1)
        self.brush_size_slider.setMaximum(50)
        self.brush_size_slider.setValue(5)
        self.brush_size_slider.setFixedWidth(100)
        self.brush_size_slider.valueChanged.connect(self.change_brush_size)

        self.apply_drawing_action = QAction(self._get_icon("apply.png"), "Применить рисунок к слою", self) 
        self.apply_drawing_action.triggered.connect(self.apply_drawing_to_layer)
        
        self.clear_drawing_action = QAction(self._get_icon("clear.png"), "Очистить текущий холст рисования", self) 
        self.clear_drawing_action.triggered.connect(self.clear_drawing_canvas_content) 

        self.gradient_action = QAction(self._get_icon("gradient.png"), "Применить градиент к слою", self) 
        self.gradient_action.triggered.connect(self.apply_gradient_to_active_layer)

    def _reset_drawing_tool_actions_check_state(self):
        """Снимает выделение (checked state) со всех кнопок инструментов рисования на тулбаре."""
        self.brush_action.setChecked(False)
        self.eraser_action.setChecked(False)
        self.rect_action.setChecked(False)
        self.ellipse_action.setChecked(False)
        self.line_action.setChecked(False)

    def _create_actions(self):
        """Создает все QAction для меню и панелей инструментов."""
        self.new_action = QAction(self._get_icon("new_file.png"), "&Новый...", self)
        self.new_action.setStatusTip("Создать новое изображение")
        self.new_action.triggered.connect(self.create_new_image_dialog)
        self.new_action.setShortcut(QKeySequence.StandardKey.New)

        self.open_action = QAction(self._get_icon("open.png"), "&Открыть...", self)
        self.open_action.setStatusTip("Открыть существующее изображение")
        self.open_action.triggered.connect(self.open_image_dialog)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)

        self.save_as_action = QAction(self._get_icon("save.png"), "&Сохранить как...", self)
        self.save_as_action.setStatusTip("Сохранить текущее изображение в новый файл")
        self.save_as_action.triggered.connect(self.save_image_dialog)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)

        self.close_all_action = QAction(self._get_icon("close_all.png"), "&Закрыть все", self) 
        self.close_all_action.setStatusTip("Закрыть все открытые изображения и холсты")
        self.close_all_action.triggered.connect(self.close_all_documents)

        self.exit_action = QAction(self._get_icon("exit.png"), "&Выход", self) 
        self.exit_action.setStatusTip("Выйти из приложения")
        self.exit_action.triggered.connect(self.close) 
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)

        self.undo_action = QAction(self._get_icon("undo.png"), "&Отменить", self)
        self.undo_action.setStatusTip("Отменить последнее действие")
        self.undo_action.triggered.connect(self.trigger_undo)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)

        self.redo_action = QAction(self._get_icon("redo.png"), "&Повторить", self)
        self.redo_action.setStatusTip("Повторить отмененное действие")
        self.redo_action.triggered.connect(self.trigger_redo)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)

        self.grayscale_action = QAction(self._get_icon("filter_grayscale.png"), "&Оттенки серого", self)
        self.grayscale_action.setStatusTip("Преобразовать активный слой в оттенки серого")
        self.grayscale_action.triggered.connect(
            lambda: self._apply_filter_to_active_layer(image_operations.apply_grayscale, filter_name="Оттенки серого"))

        self.sepia_action = QAction(self._get_icon("filter_sepia.png"), "&Сепия", self)
        self.sepia_action.setStatusTip("Применить эффект сепии к активному слою")
        self.sepia_action.triggered.connect(
            lambda: self._apply_filter_to_active_layer(image_operations.apply_sepia, filter_name="Сепия"))

        self.brightness_action = QAction(self._get_icon("filter_brightness.png"), "&Яркость...", self)
        self.brightness_action.setStatusTip("Изменить яркость активного слоя")
        self.brightness_action.triggered.connect(self.adjust_brightness_on_active_layer)

        self.contrast_action = QAction(self._get_icon("filter_contrast.png"), "&Контрастность...", self)
        self.contrast_action.setStatusTip("Изменить контрастность активного слоя")
        self.contrast_action.triggered.connect(self.adjust_contrast_on_active_layer)

        self.rotate_action = QAction(self._get_icon("rotate.png"), "Повернуть на 90° &вправо", self)
        self.rotate_action.setStatusTip("Повернуть активный слой на 90 градусов по часовой стрелке")
        self.rotate_action.triggered.connect(
            lambda: self._apply_filter_to_active_layer(image_operations.rotate_90_clockwise, filter_name="Поворот на 90°"))

        self.blur_action = QAction(self._get_icon("filter_blur.png"), "&Размытие (Гаусс)...", self)
        self.blur_action.setStatusTip("Применить Гауссово размытие к активному слою")
        self.blur_action.triggered.connect(self.apply_blur_to_active_layer)

        self.sharpen_action = QAction(self._get_icon("filter_sharpen.png"), "&Резкость", self) 
        self.sharpen_action.setStatusTip("Увеличить резкость активного слоя")
        self.sharpen_action.triggered.connect(
            lambda: self._apply_filter_to_active_layer(image_operations.apply_sharpen, filter_name="Резкость"))

        self.emboss_action = QAction(self._get_icon("filter_emboss.png"), "&Тиснение", self)
        self.emboss_action.setStatusTip("Применить эффект тиснения к активному слою")
        self.emboss_action.triggered.connect(
            lambda: self._apply_filter_to_active_layer(image_operations.apply_emboss, filter_name="Тиснение"))

        self.edge_detect_action = QAction(self._get_icon("filter_edges.png"), "Обнаружение &краев", self)
        self.edge_detect_action.setStatusTip("Применить фильтр обнаружения краев к активному слою")
        self.edge_detect_action.triggered.connect(
            lambda: self._apply_filter_to_active_layer(image_operations.apply_edge_detect, filter_name="Обнаружение краев"))

        self.reset_layer_action = QAction(self._get_icon("reset.png"), "&Сбросить слой", self)
        self.reset_layer_action.setStatusTip("Сбросить изменения активного слоя к его исходному состоянию (если доступно)")
        self.reset_layer_action.triggered.connect(self.reset_active_layer_to_original)

        self.add_layer_action = QAction(self._get_icon("add_layer.png"), "&Добавить слой", self)
        self.add_layer_action.setStatusTip("Добавить новый пустой слой")
        self.add_layer_action.triggered.connect(self.add_new_layer_action)

        self.zoom_in_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp), "Увеличить (+)", self) 
        self.zoom_in_action.setStatusTip("Увеличить масштаб отображения")
        self.zoom_in_action.triggered.connect(lambda: self.zoom_image_on_display(1.25))
        self.zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn)

        self.zoom_out_action = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown), "Уменьшить (-)", self) 
        self.zoom_out_action.setStatusTip("Уменьшить масштаб отображения")
        self.zoom_out_action.triggered.connect(lambda: self.zoom_image_on_display(0.8))
        self.zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut)

        self.actual_size_action = QAction("Реальный &размер (100%)", self)
        self.actual_size_action.setStatusTip("Показать изображение в реальном размере (100%)")
        self.actual_size_action.triggered.connect(self.set_actual_image_size)
        self.actual_size_action.setShortcut(QKeySequence("Ctrl+0")) 

    def _create_menus(self):
        """Создает и наполняет главное меню приложения."""
        file_menu = self.menuBar().addMenu("&Файл")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addAction(self.close_all_action) 
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        edit_menu = self.menuBar().addMenu("&Правка")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.reset_layer_action)

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

        view_menu = self.menuBar().addMenu("&Вид")
        view_menu.addAction(self.zoom_in_action)
        view_menu.addAction(self.zoom_out_action)
        view_menu.addAction(self.actual_size_action)

    def _create_toolbar(self):
        """Создает и наполняет главную панель инструментов."""
        toolbar = QToolBar("Основная панель инструментов")
        toolbar.setMovable(True) 
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar) 

        toolbar.addAction(self.new_action)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.save_as_action)
        toolbar.addAction(self.close_all_action) 
        toolbar.addSeparator()
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)
        toolbar.addSeparator()
        toolbar.addAction(self.add_layer_action)
        toolbar.addAction(self.reset_layer_action) 
        toolbar.addSeparator()
        
        toolbar.addAction(self.brush_action)
        toolbar.addAction(self.eraser_action)
        toolbar.addAction(self.rect_action)
        toolbar.addAction(self.ellipse_action)
        toolbar.addAction(self.line_action)
        toolbar.addAction(self.color_action)
        toolbar.addWidget(QLabel(" Размер: ")) 
        toolbar.addWidget(self.brush_size_slider)
        toolbar.addAction(self.apply_drawing_action)
        toolbar.addAction(self.clear_drawing_action)
        toolbar.addSeparator()
        
        toolbar.addAction(self.gradient_action)
        toolbar.addSeparator()

        toolbar.addAction(self.grayscale_action)
        toolbar.addAction(self.blur_action)
        toolbar.addAction(self.rotate_action)

    def _create_layer_panel(self): 
        """Создает панель (DockWidget) для управления слоями."""
        self.layer_dock_widget = QDockWidget("Слои", self)
        self.layer_dock_widget.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)

        layer_panel_widget = QWidget()
        layer_layout = QVBoxLayout(layer_panel_widget) 

        self.layer_list_widget = QListWidget()
        self.layer_list_widget.setAlternatingRowColors(True)
        self.layer_list_widget.currentItemChanged.connect(self.on_layer_selection_changed_in_listwidget)
        layer_layout.addWidget(self.layer_list_widget)

        layer_buttons_layout = QHBoxLayout()
        add_btn = QPushButton(self._get_icon("add_layer.png"), "Добавить")
        add_btn.clicked.connect(self.add_new_layer_action)
        layer_buttons_layout.addWidget(add_btn)
        layer_layout.addLayout(layer_buttons_layout)

        self.layer_dock_widget.setWidget(layer_panel_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.layer_dock_widget)

    def activate_brush_mode(self):
        """Активирует инструмент 'Кисть'."""
        self.start_drawing_session(mode='brush')
        self._reset_drawing_tool_actions_check_state() 
        self.brush_action.setChecked(True) 

    def activate_eraser_mode(self):
        """Активирует инструмент 'Ластик'."""
        self.start_drawing_session(mode='eraser')
        self._reset_drawing_tool_actions_check_state()
        self.eraser_action.setChecked(True)

    def activate_shape_mode(self, shape_mode: str):
        """
        Активирует инструмент для рисования фигур.

        Args:
            shape_mode (str): Тип фигуры ('rect', 'ellipse', 'line').
        """
        self.start_drawing_session(mode=shape_mode)
        self._reset_drawing_tool_actions_check_state()
        
        actions_map = {
            "rect": self.rect_action,
            "ellipse": self.ellipse_action,
            "line": self.line_action
        }
        if shape_mode in actions_map: 
            actions_map[shape_mode].setChecked(True)

    def start_drawing_session(self, mode: str = 'brush'):
        """
        Инициализирует или настраивает сеанс рисования на DrawingCanvas.
        """
        active_layer = self.layer_manager.get_active_layer()
        if not active_layer or not active_layer.image:
            QMessageBox.warning(self, "Нет активного слоя", "Для рисования нужен активный слой с изображением.")
            self._reset_drawing_tool_actions_check_state() 
            return

        target_canvas_width = 0
        target_canvas_height = 0

        if self.current_pixmap_for_zoom and not self.current_pixmap_for_zoom.isNull():
            target_canvas_width = self.current_pixmap_for_zoom.width()
            target_canvas_height = self.current_pixmap_for_zoom.height()
        elif active_layer.image: 
            target_canvas_width = active_layer.image.width
            target_canvas_height = active_layer.image.height
        
        if target_canvas_width <= 0 or target_canvas_height <= 0:
            QMessageBox.warning(self, "Ошибка размера", f"Недопустимый размер для холста рисования: {target_canvas_width}x{target_canvas_height}.")
            self._reset_drawing_tool_actions_check_state()
            return
            
        recreate_canvas = False
        if not self.drawing_canvas: 
            recreate_canvas = True
        elif self.drawing_canvas.size() != QSize(target_canvas_width, target_canvas_height):
            recreate_canvas = True
        
        if recreate_canvas:
            if self.drawing_canvas: 
                self.drawing_canvas.hide()
                self.drawing_canvas.deleteLater()
                self.drawing_canvas = None 
            
            self.drawing_canvas = DrawingCanvas(self.image_label, target_canvas_width, target_canvas_height)
            initial_pen_color = self.drawing_canvas.pen_color 
            self.drawing_canvas.set_pen_color(initial_pen_color if initial_pen_color.isValid() else QColor(Qt.GlobalColor.black))
            self.drawing_canvas.set_pen_width(self.brush_size_slider.value())
            self.drawing_canvas.show() 
            self.drawing_canvas.move(0, 0) 
        
        if self.drawing_canvas and not self.drawing_canvas.isVisible():
            self.drawing_canvas.show()
            self.drawing_canvas.move(0,0)

        if self.drawing_canvas: 
            self.drawing_canvas.set_mode(mode) 
            self.is_drawing_active = True 
            self.statusBar().showMessage(f"Режим: {mode}. Цвет: {self.drawing_canvas.pen_color.name()}, Размер: {self.drawing_canvas.pen_width}")
        else: 
            self.is_drawing_active = False
            self._reset_drawing_tool_actions_check_state() 
            QMessageBox.critical(self, "Ошибка", "Не удалось инициализировать холст для рисования.")

        self._update_actions_enabled_state() 


    def select_brush_color(self):
        """Открывает диалог выбора цвета для кисти/фигуры."""
        initial_color = self.drawing_canvas.pen_color if self.drawing_canvas else QColor(Qt.GlobalColor.black)
        
        color = QColorDialog.getColor(initial_color, self, "Выберите цвет кисти/фигуры")
        if color.isValid():
            if self.drawing_canvas and self.is_drawing_active: 
                self.drawing_canvas.set_pen_color(color)
                self.statusBar().showMessage(f"Новый цвет кисти/фигуры: {color.name()}")
            elif self.drawing_canvas: 
                 self.drawing_canvas.set_pen_color(color) 
                 self.statusBar().showMessage(f"Цвет {color.name()} будет использован для следующего рисунка.")
            else: 
                QMessageBox.information(self, "Информация", "Сначала активируйте инструмент рисования или фигуру.")


    def change_brush_size(self, value: int):
        """
        Изменяет размер кисти/пера для DrawingCanvas.
        """
        if self.drawing_canvas: 
            self.drawing_canvas.set_pen_width(value)
            if self.is_drawing_active: 
                self.statusBar().showMessage(f"Новый размер кисти/фигуры: {value}")

    def clear_drawing_canvas_content(self): 
        """Очищает содержимое текущего DrawingCanvas (непримененный рисунок)."""
        if self.drawing_canvas and self.is_drawing_active: 
            self.drawing_canvas.clear_canvas()
            self.statusBar().showMessage("Холст для рисования очищен.")
        else:
            self.statusBar().showMessage("Нет активного холста для рисования, чтобы очищать.")


    def apply_drawing_to_layer(self):
        """Применяет текущий рисунок с DrawingCanvas к активному слою."""
        active_layer = self.layer_manager.get_active_layer()
        if not self.drawing_canvas or not self.is_drawing_active or not active_layer or not active_layer.image:
            QMessageBox.warning(self, "Ошибка", "Нет активного рисунка или слоя для применения.")
            return

        try:
            drawing_qimage = self.drawing_canvas.get_image() 
            pil_drawing = ImageQt.fromqimage(drawing_qimage.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied))
            
            if self.drawing_canvas:
                self.drawing_canvas.hide()
                self.drawing_canvas.deleteLater() 
                self.drawing_canvas = None 
            self.is_drawing_active = False 
            self._reset_drawing_tool_actions_check_state() 

            self.history_manager.add_state(active_layer.id, active_layer.image.copy())

            base_pil = active_layer.image.convert("RGBA") 
            
            if base_pil.size != pil_drawing.size:
                 pil_drawing = pil_drawing.resize(base_pil.size, Image.Resampling.LANCZOS)

            base_pil.alpha_composite(pil_drawing) 
            active_layer.image = base_pil 

            self.update_composite_image_display() 
            self.statusBar().showMessage(f"Рисунок применен к слою '{active_layer.name}'")
            self._update_actions_enabled_state() 

        except Exception as e:
            QMessageBox.critical(self, "Ошибка применения рисунка", f"Не удалось применить рисунок: {e}")
            if active_layer and self.history_manager.can_undo(active_layer.id):
                 undone_image_state_after_failed_apply = self.history_manager.undo(active_layer.id)
                 if undone_image_state_after_failed_apply: 
                     active_layer.image = undone_image_state_after_failed_apply
            self._update_actions_enabled_state() 


    def apply_gradient_to_active_layer(self):
        """Применяет линейный градиент к активному слою."""
        active_layer = self.layer_manager.get_active_layer()
        if not active_layer or not active_layer.image:
            QMessageBox.warning(self, "Нет слоя", "Нет активного слоя для применения градиента.")
            return

        from PySide6.QtWidgets import QDialog, QComboBox 
        
        start_color_q = QColorDialog.getColor(Qt.GlobalColor.white, self, "Начальный цвет градиента")
        if not start_color_q.isValid(): return
        end_color_q = QColorDialog.getColor(Qt.GlobalColor.black, self, "Конечный цвет градиента")
        if not end_color_q.isValid(): return
        
        direction_box = QComboBox()
        direction_box.addItems(["Горизонтальный", "Вертикальный"])
        direction_box.setCurrentIndex(0)
        
        direction_dialog = QDialog(self)
        direction_dialog.setWindowTitle("Направление градиента")
        layout = QVBoxLayout(direction_dialog)
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

        if direction_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        direction = 'horizontal' if direction_box.currentText() == "Горизонтальный" else 'vertical'

        width, height = active_layer.image.size
        start_rgba = (start_color_q.red(), start_color_q.green(), start_color_q.blue(), start_color_q.alpha())
        end_rgba = (end_color_q.red(), end_color_q.green(), end_color_q.blue(), end_color_q.alpha())
        
        try:
            gradient_img_pil = create_linear_gradient(width, height, start_rgba, end_rgba, direction)
            if gradient_img_pil:
                self.history_manager.add_state(active_layer.id, active_layer.image.copy())
                active_layer.image = gradient_img_pil
                self.update_composite_image_display()
                self.statusBar().showMessage("Градиент применен к активному слою.")
            else:
                QMessageBox.warning(self, "Ошибка градиента", "Не удалось создать изображение градиента.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка градиента", f"Не удалось применить градиент: {e}")

    @Slot()
    def create_new_image_dialog(self):
        """Открывает диалог для создания нового изображения."""
        if self.drawing_canvas:
            self.drawing_canvas.hide()
            self.drawing_canvas.deleteLater()
            self.drawing_canvas = None
        self.is_drawing_active = False
        self._reset_drawing_tool_actions_check_state()

        width, okW = QInputDialog.getInt(self, "Новое изображение", "Ширина (px):", 640, 1, 10000, 1)
        if not okW: return
        height, okH = QInputDialog.getInt(self, "Новое изображение", "Высота (px):", 480, 1, 10000, 1)
        if not okH: return

        new_pil_image = Image.new("RGBA", (width, height), (255, 255, 255, 255)) 

        if not self.layer_manager.has_layers():
            self.layer_manager.clear_all_layers()
            self.history_manager.clear_all_history()

        layer_name = "Фон"
        if self.layer_manager.has_layers(): 
            layer_name = f"Слой {self.layer_manager._layer_name_counter}" 

        self.layer_manager.add_layer(image=new_pil_image, name=layer_name, is_original=True) 
        
        self.refresh_layer_list() 
        if self.layer_manager.layers:
             self.layer_manager.set_active_layer_by_id(self.layer_manager.layers[-1].id)

        self.update_composite_image_display() 
        self.statusBar().showMessage(f"Создано новое изображение {width}x{height}")
        self.current_zoom_factor = 1.0 

    @Slot()
    def open_image_dialog(self):
        """Открывает диалог для выбора и загрузки изображения."""
        if self.drawing_canvas:
            self.drawing_canvas.hide()
            self.drawing_canvas.deleteLater()
            self.drawing_canvas = None
        self.is_drawing_active = False
        self._reset_drawing_tool_actions_check_state()

        start_path = QDir.homePath() 
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Открыть изображение", start_path,
            "Файлы изображений (*.png *.jpg *.jpeg *.bmp *.gif);;Все файлы (*)"
        )
        if file_path: 
            try:
                if not self.layer_manager.has_layers() or not self.layer_manager.get_active_layer():
                    self.layer_manager.clear_all_layers()
                    self.history_manager.clear_all_history()
                
                pil_img = Image.open(file_path).convert("RGBA") 
                
                layer_name = os.path.basename(file_path) 
                self.layer_manager.add_layer(image=pil_img, name=layer_name, is_original=True)
                
                self.refresh_layer_list()
                if self.layer_manager.layers: 
                    self.layer_manager.set_active_layer_by_id(self.layer_manager.layers[-1].id)

                self.update_composite_image_display()
                self.statusBar().showMessage(f"Открыто: {file_path}")
                self.current_zoom_factor = 1.0 
            except FileNotFoundError:
                QMessageBox.critical(self, "Ошибка", f"Файл не найден: {file_path}")
            except UnidentifiedImageError: 
                 QMessageBox.critical(self, "Ошибка", f"Не удалось распознать формат файла: {file_path}")
            except Exception as e: 
                QMessageBox.critical(self, "Ошибка открытия", f"Ошибка при открытии файла '{file_path}': {e}")
            finally: 
                self._update_actions_enabled_state() 

    @Slot()
    def save_image_dialog(self):
        """Открывает диалог для сохранения текущей композиции слоев."""
        if not self.layer_manager.has_layers():
            QMessageBox.warning(self, "Внимание", "Нет изображения для сохранения.")
            return

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
                image_operations.save_image(composite_image, file_path) 
                self.statusBar().showMessage(f"Композиция сохранена в: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка сохранения", f"Не удалось сохранить: {e}")

    @Slot()
    def close_all_documents(self, confirm: bool = True) -> bool: 
        """
        Закрывает все открытые изображения/холсты, сбрасывая состояние приложения.
        """
        if confirm and self.layer_manager.has_layers(): 
            reply = QMessageBox.question(self, 'Закрыть все',
                                         "Вы уверены, что хотите закрыть все открытые изображения/холсты?\n"
                                         "Несохраненные изменения будут потеряны.",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return False 

        self.layer_manager.clear_all_layers() 
        self.history_manager.clear_all_history()

        if self.drawing_canvas:
            self.drawing_canvas.hide()
            self.drawing_canvas.deleteLater() 
            self.drawing_canvas = None 
        self.is_drawing_active = False
        self._reset_drawing_tool_actions_check_state() 

        self.image_label.clear() 
        self.image_label.setText("Создайте или откройте изображение (Ctrl+O или Ctrl+N)")
        self.image_label.adjustSize() 

        self.current_pixmap_for_zoom = None
        self.current_zoom_factor = 1.0

        self.refresh_layer_list() 
        self._update_actions_enabled_state() 
        self.statusBar().showMessage("Все закрыто. Готово к новой работе!")
        return True 

    def update_composite_image_display(self):
        """
        Обновляет отображаемое изображение в QLabel (self.image_label).
        """
        composite_image_pil = self.layer_manager.get_composite_image()

        if composite_image_pil:
            try:
                q_image = ImageQt.ImageQt(composite_image_pil.convert("RGBA")) 
                self.current_pixmap_for_zoom = QPixmap.fromImage(q_image) 
                
                if abs(self.current_zoom_factor - 1.0) > 1e-5: 
                    scaled_width = int(self.current_pixmap_for_zoom.width() * self.current_zoom_factor)
                    scaled_height = int(self.current_pixmap_for_zoom.height() * self.current_zoom_factor)
                    if scaled_width > 0 and scaled_height > 0:
                         scaled_pixmap = self.current_pixmap_for_zoom.scaled(
                             scaled_width, scaled_height,
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
                         self.image_label.setPixmap(scaled_pixmap)
                    else: 
                         self.image_label.setPixmap(self.current_pixmap_for_zoom)
                else: 
                    self.image_label.setPixmap(self.current_pixmap_for_zoom)

                self.image_label.adjustSize() 
            except Exception as e:
                QMessageBox.critical(self, "Ошибка отображения", f"Не удалось отобразить композицию: {e}")
                self.image_label.setText("Ошибка отображения композиции")
                self.current_pixmap_for_zoom = None
        else: 
            self.image_label.clear()
            self.image_label.setText("Создайте или откройте изображение")
            self.current_pixmap_for_zoom = None
            self.image_label.adjustSize()

        self._update_actions_enabled_state() 


    def _apply_filter_to_active_layer(self, filter_function, *args, filter_name="фильтр"):
        """
        Применяет указанную функцию-фильтр к активному слою.
        """
        active_layer = self.layer_manager.get_active_layer()
        if not (active_layer and active_layer.image):
            QMessageBox.information(self, "Информация", "Нет активного слоя с изображением для применения фильтра.")
            return

        if self.is_drawing_active and self.drawing_canvas and not self.drawing_canvas.image.isNull():
            reply = QMessageBox.question(self, "Незавершенное рисование",
                                         "На холсте есть непримененный рисунок. Применить его перед фильтром?",
                                         QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Apply:
                self.apply_drawing_to_layer() 
            elif reply == QMessageBox.StandardButton.Cancel:
                return 
            elif reply == QMessageBox.StandardButton.Discard: 
                if self.drawing_canvas: 
                    self.drawing_canvas.clear_canvas() 
                    self.drawing_canvas.hide()
                    self.drawing_canvas.deleteLater()
                    self.drawing_canvas = None
                self.is_drawing_active = False 
                self._reset_drawing_tool_actions_check_state() 
        
        try:
            self.history_manager.add_state(active_layer.id, active_layer.image.copy()) 
            processed_image = filter_function(active_layer.image.copy(), *args) 
            
            if processed_image:
                active_layer.image = processed_image 
                self.update_composite_image_display() 
                self.statusBar().showMessage(f"Применен '{filter_name}' к слою '{active_layer.name}'")
            else:
                QMessageBox.warning(self, "Ошибка фильтра", f"Фильтр '{filter_name}' не вернул изображение.")
                if self.history_manager.can_undo(active_layer.id):
                    self.history_manager.undo(active_layer.id)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка фильтра", f"Не удалось применить '{filter_name}': {e}")
            if self.history_manager.can_undo(active_layer.id):
                self.history_manager.undo(active_layer.id)
        
        self._update_actions_enabled_state()

    @Slot()
    def adjust_brightness_on_active_layer(self):
        """Открывает диалог для настройки яркости активного слоя."""
        active_layer = self.layer_manager.get_active_layer()
        if not (active_layer and active_layer.image):
            QMessageBox.information(self, "Информация", "Сначала выберите слой с изображением.")
            return
        factor, ok = QInputDialog.getDouble(self, "Регулировка яркости", "Коэффициент:", 1.0, 0.1, 5.0, 2)
        if ok: self._apply_filter_to_active_layer(image_operations.adjust_brightness, factor, filter_name="Яркость")

    @Slot()
    def adjust_contrast_on_active_layer(self):
        """Открывает диалог для настройки контрастности активного слоя."""
        active_layer = self.layer_manager.get_active_layer()
        if not (active_layer and active_layer.image):
            QMessageBox.information(self, "Информация", "Сначала выберите слой с изображением.")
            return
        factor, ok = QInputDialog.getDouble(self, "Регулировка контрастности", "Коэффициент:", 1.0, 0.1, 5.0, 2)
        if ok: self._apply_filter_to_active_layer(image_operations.adjust_contrast, factor, filter_name="Контрастность")

    @Slot()
    def apply_blur_to_active_layer(self):
        """Открывает диалог для настройки Гауссова размытия активного слоя."""
        active_layer = self.layer_manager.get_active_layer()
        if not (active_layer and active_layer.image):
            QMessageBox.information(self, "Информация", "Сначала выберите слой с изображением.")
            return
        radius, ok = QInputDialog.getDouble(self, "Размытие по Гауссу", "Радиус размытия:", 2.0, 0.1, 20.0, 1)
        if ok: self._apply_filter_to_active_layer(image_operations.apply_gaussian_blur, radius, filter_name="Размытие")

    @Slot()
    def reset_active_layer_to_original(self):
        """Сбрасывает активный слой к его исходному состоянию."""
        active_layer = self.layer_manager.get_active_layer()
        if active_layer and active_layer.original_image:
            self.history_manager.add_state(active_layer.id, active_layer.image.copy()) 
            active_layer.image = active_layer.original_image.copy() 
            
            self.history_manager.clear_history_for_layer(active_layer.id)
            self.history_manager.add_state(active_layer.id, active_layer.image.copy(), is_initial_state=True)
            
            self.update_composite_image_display()
            self.statusBar().showMessage(f"Слой '{active_layer.name}' сброшен к оригиналу.")
        elif active_layer:
            QMessageBox.information(self, "Информация", f"Для слоя '{active_layer.name}' нет исходного состояния для сброса.")
        else:
            QMessageBox.information(self, "Информация", "Нет активного слоя для сброса.")
        self._update_actions_enabled_state()

    def refresh_layer_list(self):
        """Обновляет список слоев в QListWidget."""
        self.layer_list_widget.blockSignals(True) 
        self.layer_list_widget.clear() 
        
        active_layer_obj = self.layer_manager.get_active_layer()
        active_layer_id = active_layer_obj.id if active_layer_obj else None
        
        for i, layer in enumerate(reversed(self.layer_manager.layers)): 
            item_text = f"{layer.name} {'(V)' if layer.visible else '(H)'}" 
            list_item = QListWidgetItem(item_text) 
            list_item.setData(Qt.ItemDataRole.UserRole, layer.id) 
            self.layer_list_widget.addItem(list_item) 
            if layer.id == active_layer_id: 
                self.layer_list_widget.setCurrentItem(list_item) 
        
        self.layer_list_widget.blockSignals(False) 

    @Slot(QListWidgetItem, QListWidgetItem) 
    def on_layer_selection_changed_in_listwidget(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        """
        Слот, вызываемый при изменении выбора слоя в QListWidget.
        """
        if self.is_drawing_active and self.drawing_canvas:
            if not self.drawing_canvas.image.isNull(): 
                pass 
            
            self.drawing_canvas.hide()
            self.drawing_canvas.deleteLater()
            self.drawing_canvas = None
        self.is_drawing_active = False
        self._reset_drawing_tool_actions_check_state()

        if current_item:
            layer_id = current_item.data(Qt.ItemDataRole.UserRole)
            self.layer_manager.set_active_layer_by_id(layer_id) 
        else: 
             self.layer_manager.set_active_layer_by_id(None) 


    @Slot(object) 
    def on_active_layer_changed_for_history_and_ui(self, layer_id_obj): 
        """
        Слот, вызываемый при изменении активного слоя в LayerManager.
        """
        self._update_actions_enabled_state() 

        current_list_widget_item = self.layer_list_widget.currentItem()
        current_list_widget_selected_id = current_list_widget_item.data(Qt.ItemDataRole.UserRole) if current_list_widget_item else None

        self.layer_list_widget.blockSignals(True)
        if layer_id_obj is None: 
            if current_list_widget_item: 
                self.layer_list_widget.setCurrentItem(None) 
        elif layer_id_obj != current_list_widget_selected_id: 
            found_in_list = False
            for i in range(self.layer_list_widget.count()):
                item = self.layer_list_widget.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == layer_id_obj:
                    self.layer_list_widget.setCurrentItem(item) 
                    found_in_list = True
                    break
            if not found_in_list and current_list_widget_item : 
                 self.layer_list_widget.setCurrentItem(None) 
        self.layer_list_widget.blockSignals(False) 
        
        active_layer_from_manager = self.layer_manager.get_active_layer()
        if active_layer_from_manager:
            self.statusBar().showMessage(f"Активный слой: {active_layer_from_manager.name}")
        else:
            self.statusBar().showMessage("Нет активного слоя.")
        
        self.update_composite_image_display() 


    @Slot()
    def add_new_layer_action(self):
        """Добавляет новый пустой слой в проект."""
        width, height = 640, 480 
        if self.layer_manager.has_layers() and self.layer_manager.layers[0].image:
            ref_layer_img = self.layer_manager.layers[0].image 
            width, height = ref_layer_img.size
        elif self.current_pixmap_for_zoom and not self.current_pixmap_for_zoom.isNull(): 
            width = self.current_pixmap_for_zoom.width()
            height = self.current_pixmap_for_zoom.height()

        new_layer_image = Image.new("RGBA", (width, height), (0, 0, 0, 0)) 
        
        new_layer = self.layer_manager.add_layer(image=new_layer_image, is_original=True) 
        
        self.refresh_layer_list() 

        if new_layer:
             if not self.layer_manager.get_active_layer() or self.layer_manager.get_active_layer().id != new_layer.id:
                 self.layer_manager.set_active_layer_by_id(new_layer.id)
             self.statusBar().showMessage(f"Добавлен новый слой: {new_layer.name}")
        else:
            self.statusBar().showMessage("Ошибка при добавлении нового слоя.")
        
    @Slot()
    def trigger_undo(self):
        """Отменяет последнее действие для активного слоя."""
        active_layer = self.layer_manager.get_active_layer()
        if active_layer and self.history_manager.can_undo(active_layer.id):
            undone_image = self.history_manager.undo(active_layer.id)
            if undone_image:
                active_layer.image = undone_image
                self.update_composite_image_display()
                self.statusBar().showMessage(f"Отменено действие для слоя '{active_layer.name}'")
            else: 
                self.statusBar().showMessage(f"Не удалось отменить действие для слоя '{active_layer.name}'")
        else:
            self.statusBar().showMessage("Больше нет действий для отмены на активном слое.")
        self._update_actions_enabled_state() 

    @Slot()
    def trigger_redo(self):
        """Повторяет отмененное действие для активного слоя."""
        active_layer = self.layer_manager.get_active_layer()
        if active_layer and self.history_manager.can_redo(active_layer.id):
            redone_image = self.history_manager.redo(active_layer.id)
            if redone_image:
                active_layer.image = redone_image
                self.update_composite_image_display()
                self.statusBar().showMessage(f"Повторено действие для слоя '{active_layer.name}'")
            else: 
                self.statusBar().showMessage(f"Не удалось повторить действие для слоя '{active_layer.name}'")
        else:
            self.statusBar().showMessage("Больше нет действий для повтора на активном слое.")
        self._update_actions_enabled_state() 

    @Slot()
    def zoom_image_on_display(self, factor: float):
        """
        Изменяет масштаб отображения текущей композиции.
        """
        if not (self.current_pixmap_for_zoom and not self.current_pixmap_for_zoom.isNull()):
            self.statusBar().showMessage("Нет изображения для масштабирования.")
            return
            
        new_zoom_factor = self.current_zoom_factor * factor
        new_zoom_factor = max(0.05, min(new_zoom_factor, 20.0)) 

        if abs(new_zoom_factor - self.current_zoom_factor) < 1e-5 and factor != 1.0 : 
             self.statusBar().showMessage(f"Масштаб: {self.current_zoom_factor:.2f}x (достигнут предел)")
             return

        self.current_zoom_factor = new_zoom_factor
        original_composite_pixmap = self.current_pixmap_for_zoom 
        
        new_width = int(original_composite_pixmap.width() * self.current_zoom_factor)
        new_height = int(original_composite_pixmap.height() * self.current_zoom_factor)

        if new_width > 0 and new_height > 0:
            scaled_pixmap = original_composite_pixmap.scaled(
                new_width, new_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.adjustSize() 
            self.statusBar().showMessage(f"Масштаб: {self.current_zoom_factor:.2f}x")
        else: 
            self.image_label.setPixmap(original_composite_pixmap)
            self.image_label.adjustSize()
            self.current_zoom_factor = 1.0 
            self.statusBar().showMessage(f"Масштаб сброшен до 1.00x (ошибка масштабирования)")
        
    @Slot()
    def set_actual_image_size(self):
        """Устанавливает масштаб отображения в 100% (реальный размер)."""
        if self.current_pixmap_for_zoom and not self.current_pixmap_for_zoom.isNull(): 
            self.image_label.setPixmap(self.current_pixmap_for_zoom) 
            self.image_label.adjustSize()
            self.current_zoom_factor = 1.0
            self.statusBar().showMessage("Масштаб: 1.00x (Реальный размер)")
        else:
            self.statusBar().showMessage("Нет изображения для отображения в реальном размере.")

    def _update_actions_enabled_state(self):
        """Обновляет состояние (enabled/disabled) всех QAction."""
        has_any_layers = self.layer_manager.has_layers()
        active_layer = self.layer_manager.get_active_layer()
        has_active_layer_with_image = active_layer is not None and active_layer.image is not None

        self.save_as_action.setEnabled(has_any_layers)
        self.close_all_action.setEnabled(has_any_layers) 

        image_operations_enabled = has_active_layer_with_image
        self.grayscale_action.setEnabled(image_operations_enabled)
        self.sepia_action.setEnabled(image_operations_enabled)
        self.brightness_action.setEnabled(image_operations_enabled)
        self.contrast_action.setEnabled(image_operations_enabled)
        self.rotate_action.setEnabled(image_operations_enabled)
        self.blur_action.setEnabled(image_operations_enabled)
        self.sharpen_action.setEnabled(image_operations_enabled)
        self.emboss_action.setEnabled(image_operations_enabled)
        self.edge_detect_action.setEnabled(image_operations_enabled)
        self.gradient_action.setEnabled(image_operations_enabled) 

        self.reset_layer_action.setEnabled(image_operations_enabled and active_layer is not None and active_layer.original_image is not None)

        can_undo, can_redo = False, False
        if active_layer: 
            can_undo = self.history_manager.can_undo(active_layer.id)
            can_redo = self.history_manager.can_redo(active_layer.id)
        self.undo_action.setEnabled(can_undo)
        self.redo_action.setEnabled(can_redo)

        has_pixmap_to_zoom = self.current_pixmap_for_zoom is not None and not self.current_pixmap_for_zoom.isNull()
        self.zoom_in_action.setEnabled(has_pixmap_to_zoom)
        self.zoom_out_action.setEnabled(has_pixmap_to_zoom)
        self.actual_size_action.setEnabled(has_pixmap_to_zoom)

        drawing_tools_availability = has_active_layer_with_image
        self.brush_action.setEnabled(drawing_tools_availability)
        self.eraser_action.setEnabled(drawing_tools_availability)
        self.rect_action.setEnabled(drawing_tools_availability)
        self.ellipse_action.setEnabled(drawing_tools_availability)
        self.line_action.setEnabled(drawing_tools_availability)
        self.color_action.setEnabled(drawing_tools_availability) 
        self.brush_size_slider.setEnabled(drawing_tools_availability) 

        self.apply_drawing_action.setEnabled(self.is_drawing_active and self.drawing_canvas is not None)
        self.clear_drawing_action.setEnabled(self.is_drawing_active and self.drawing_canvas is not None)

    def closeEvent(self, event: QCloseEvent): # <-- ИЗМЕНЕНИЕ: Используем QCloseEvent напрямую
        """
        Обрабатывает событие закрытия главного окна.
        """
        if self.is_drawing_active and self.drawing_canvas and not self.drawing_canvas.image.isNull():
            reply = QMessageBox.question(self, "Незавершенное рисование",
                                         "На холсте есть непримененный рисунок. Применить его перед выходом?",
                                         QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                         QMessageBox.StandardButton.Cancel) 
            if reply == QMessageBox.StandardButton.Apply:
                self.apply_drawing_to_layer() 
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore() 
                return
        if self.layer_manager.has_layers(): 
            reply = QMessageBox.question(self, 'Подтверждение выхода',
                                     "Вы уверены, что хотите выйти?\n"
                                     "Несохраненные изменения в открытых документах могут быть потеряны.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No) 
            if reply == QMessageBox.StandardButton.Yes:
                event.accept() 
            else:
                event.ignore() 
        else: 
            event.accept()

if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    import os 

    app = QApplication(sys.argv)

    if getattr(sys, 'frozen', False): 
        application_path = os.path.dirname(sys.executable)
    else: 
        application_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    resources_path_test = os.path.join(application_path, "resources")
    styles_path_test = os.path.join(resources_path_test, "styles", "style.qss")
    
    if os.path.exists(styles_path_test):
        with open(styles_path_test, "r", encoding="utf-8") as style_file: 
            app.setStyleSheet(style_file.read())
            print(f"Стили для теста загружены из: {styles_path_test}")
    else:
        print(f"Файл стилей для теста не найден: {styles_path_test}")

    window = ImageEditorWindow(resources_path_test) 
    window.show()
    sys.exit(app.exec())