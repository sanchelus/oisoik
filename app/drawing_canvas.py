# Файл: app/drawing_canvas.py
# Обрабатывает рисование мышью поверх изображения и отображает курсор-кисть.

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QMouseEvent, QPaintEvent, QImage, QBrush, QResizeEvent
from PySide6.QtCore import Qt, QPoint, QRect, QSize, QEvent

class DrawingCanvas(QWidget):
    """
    Виджет для рисования на изображении.
    Поддерживает различные инструменты (кисть, ластик, фигуры)
    и отображает предварительный просмотр размера кисти/ластика.
    """
    def __init__(self, parent=None, width=800, height=600):
        """
        Инициализирует холст для рисования.

        Args:
            parent (QWidget, optional): Родительский виджет. Defaults to None.
            width (int, optional): Начальная ширина холста. Defaults to 800.
            height (int, optional): Начальная высота холста. Defaults to 600.
        """
        super().__init__(parent)

        # WA_TransparentForMouseEvents должно быть False, чтобы виджет получал события мыши
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False) 
        # WA_OpaquePaintEvent False означает, что фон может быть прозрачным
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        # Включаем отслеживание мыши для отображения курсора-кисти без нажатой кнопки
        self.setMouseTracking(True)

        # Основное изображение, на котором происходит рисование
        self.image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        self.image.fill(Qt.GlobalColor.transparent) # Изначально холст прозрачный

        self.drawing = False  # Флаг, идет ли сейчас процесс рисования (кнопка мыши нажата)
        self.last_point = QPoint() # Последняя точка для рисования линий/кривых
        
        self.pen_color = QColor(Qt.GlobalColor.black) # Текущий цвет пера/кисти
        self.pen_width = 5  # Текущая ширина пера/кисти
        
        self.mode = 'brush'  # Текущий режим рисования: 'brush', 'eraser', 'rect', 'ellipse', 'line'
        
        # Для рисования фигур
        self.start_point = QPoint() # Начальная точка для фигур
        self.temp_image = None # Временное изображение для предпросмотра фигур

        # Для курсора-кисти
        self.show_brush_cursor = False # Показывать ли курсор-кисть
        self.current_mouse_pos = QPoint() # Текущая позиция мыши для курсора-кисти

        self.setFixedSize(width, height) # Фиксируем размер виджета под размер изображения

    def set_pen_color(self, color: QColor):
        """Устанавливает цвет пера/кисти."""
        if isinstance(color, QColor):
            self.pen_color = color

    def set_pen_width(self, width: int):
        """Устанавливает ширину пера/кисти."""
        if isinstance(width, int) and width > 0:
            self.pen_width = width
            self.update() # Обновляем для перерисовки курсора-кисти, если он видим

    def set_mode(self, mode: str):
        """
        Устанавливает режим рисования.

        Args:
            mode (str): Новый режим ('brush', 'eraser', 'rect', 'ellipse', 'line').
        """
        valid_modes = ['brush', 'eraser', 'rect', 'ellipse', 'line']
        if mode in valid_modes:
            self.mode = mode
            # Курсор-кисть показываем только для кисти и ластика
            self.show_brush_cursor = mode in ['brush', 'eraser']
            self.update() # Обновляем для перерисовки курсора-кисти
        else:
            print(f"Warning: Invalid drawing mode '{mode}' requested.")


    def clear_canvas(self):
        """Очищает холст (заливает прозрачным цветом)."""
        if self.image:
            self.image.fill(Qt.GlobalColor.transparent)
            self.update() # Запрашиваем перерисовку виджета

    def get_image(self) -> QImage:
        """Возвращает текущее изображение с холста."""
        return self.image

    # --- Обработчики событий мыши ---
    def mousePressEvent(self, event: QMouseEvent):
        """Обрабатывает нажатие кнопки мыши."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.last_point = event.position().toPoint() # Сохраняем позицию в координатах виджета
            self.start_point = event.position().toPoint()

            # Если рисуем фигуру, копируем текущее изображение для предпросмотра
            if self.mode in ['rect', 'ellipse', 'line'] and self.image:
                self.temp_image = self.image.copy()
            
            self.update() # Обновляем, чтобы курсор-кисть исчез на время рисования

    def mouseMoveEvent(self, event: QMouseEvent):
        """Обрабатывает движение мыши."""
        self.current_mouse_pos = event.position().toPoint() # Обновляем позицию для курсора-кисти

        if not self.drawing: # Если кнопка не нажата, только обновляем для курсора-кисти
            if self.show_brush_cursor:
                self.update()
            return

        # Если кнопка нажата и идет рисование
        current_point = event.position().toPoint()

        if self.mode in ['brush', 'eraser'] and self.image:
            painter = QPainter(self.image)
            pen = QPen()
            pen.setWidth(self.pen_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

            if self.mode == 'eraser':
                # Ластик рисует прозрачным цветом
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                pen.setColor(Qt.GlobalColor.transparent) # Не обязательно, т.к. CompositionMode_Clear
            else: # 'brush'
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                pen.setColor(self.pen_color)
            
            painter.setPen(pen)
            painter.drawLine(self.last_point, current_point)
            self.last_point = current_point
        
        elif self.mode in ['rect', 'ellipse', 'line'] and self.temp_image:
            # Рисуем на временной копии для предпросмотра фигуры
            # Сначала восстанавливаем изображение до начала рисования фигуры
            if self.image and self.temp_image: # Проверка на None
                 self.image = self.temp_image.copy() 
            
            if self.image: # Проверка, что self.image не None
                painter = QPainter(self.image)
                self._draw_shape_on_painter(painter, self.mode, self.start_point, current_point)
        
        self.update() # Запрашиваем перерисовку

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Обрабатывает отпускание кнопки мыши."""
        if event.button() == Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            current_point = event.position().toPoint()

            if self.mode in ['rect', 'ellipse', 'line'] and self.image:
                # Финальное рисование фигуры на основном изображении
                # self.image уже содержит предпросмотр, если temp_image использовался
                # Если предпросмотр был на self.image, то ничего дополнительно делать не надо
                # Если был self.temp_image, то self.image уже обновлен в mouseMoveEvent
                pass # Фигура уже нарисована в mouseMoveEvent на self.image
            
            self.temp_image = None # Очищаем временное изображение
            self.update() # Обновляем, чтобы курсор-кисть снова появился

    def enterEvent(self, event: QEvent): # QEvent, а не QEnterEvent для PySide6 < 6.4
        """Мышь вошла в область виджета."""
        if self.mode in ['brush', 'eraser']:
            self.show_brush_cursor = True
        self.current_mouse_pos = event.position().toPoint()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent): # QEvent
        """Мышь покинула область виджета."""
        self.show_brush_cursor = False
        self.update()
        super().leaveEvent(event)

    # --- Методы отрисовки ---
    def paintEvent(self, event: QPaintEvent):
        """Перерисовывает виджет."""
        painter = QPainter(self)
        
        # Рисуем основное изображение
        if self.image:
            painter.drawImage(0, 0, self.image)

        # Рисуем курсор-кисть, если он активен и мышь не нажата (не в процессе рисования)
        if self.show_brush_cursor and not self.drawing and self.underMouse():
            self._draw_brush_cursor(painter, self.current_mouse_pos)

    def _draw_shape_on_painter(self, painter: QPainter, shape_type: str, start_pos: QPoint, end_pos: QPoint):
        """
        Вспомогательный метод для рисования фигур (прямоугольник, эллипс, линия) на QPainter.
        """
        pen = QPen(self.pen_color, self.pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        
        # Для прямоугольника и эллипса используем QRect, нормализованный для корректного рисования
        # вне зависимости от направления движения мыши.
        rect = QRect(start_pos, end_pos).normalized() 

        if shape_type == 'rect':
            painter.drawRect(rect)
        elif shape_type == 'ellipse':
            painter.drawEllipse(rect)
        elif shape_type == 'line':
            painter.drawLine(start_pos, end_pos)

    def _draw_brush_cursor(self, painter: QPainter, position: QPoint):
        """Рисует предварительный просмотр курсора-кисти (окружность)."""
        if not self.show_brush_cursor or self.pen_width <= 0:
            return

        painter.save() # Сохраняем состояние painter
        
        pen = QPen(QColor(128, 128, 128, 180)) # Полупрозрачный серый цвет для контура
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush) # Без заливки

        radius = self.pen_width / 2.0
        # Рисуем окружность с центром в текущей позиции мыши
        painter.drawEllipse(position, radius, radius)
        
        painter.restore() # Восстанавливаем состояние painter

    def resizeEvent(self, event: QResizeEvent):
        """Обрабатывает изменение размера виджета (если он не фиксированный)."""
        # Если бы изображение должно было масштабироваться с виджетом,
        # здесь нужно было бы пересоздавать или масштабировать self.image.
        # Но т.к. setFixedSize используется, этот метод может не быть критичным,
        # если только размер не меняется программно извне после __init__.
        # print(f"DrawingCanvas resized to: {event.size()}")
        super().resizeEvent(event)