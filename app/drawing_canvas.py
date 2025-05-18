# Файл: app/drawing_canvas.py
# Обрабатывает рисование мышью поверх изображения.

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QMouseEvent, QPaintEvent, QImage
from PySide6.QtCore import Qt, QPoint
from PySide6.QtCore import QRect


class DrawingCanvas(QWidget):
    def __init__(self, parent=None, width=800, height=600):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

        self.image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        self.image.fill(Qt.transparent)

        self.drawing = False
        self.last_point = QPoint()
        self.pen_color = QColor(0, 0, 0)
        self.pen_width = 5
        self.eraser_mode = False

        self.mode = 'brush'  # 'brush', 'eraser', 'rect', 'ellipse', 'line'
        self.start_point = None
        self.temp_image = None

        self.setFixedSize(width, height)

    def set_pen_color(self, color: QColor):
        self.pen_color = color

    def set_pen_width(self, width: int):
        self.pen_width = width

    def set_eraser_mode(self, enabled: bool):
        self.eraser_mode = enabled

    def clear_canvas(self):
        self.image.fill(Qt.transparent)
        self.update()

    def get_image(self) -> QImage:
        return self.image

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.last_point = event.position().toPoint()
            self.start_point = self.last_point
            if self.mode in ['rect', 'ellipse', 'line']:
                self.temp_image = self.image.copy()

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.drawing:
            return

        current_point = event.position().toPoint()
        if self.mode in ['brush', 'eraser']:
            painter = QPainter(self.image)
            if self.mode == 'eraser':
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                pen = QPen(Qt.transparent, self.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            else:
                pen = QPen(self.pen_color, self.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(self.last_point, current_point)
            self.last_point = current_point
        elif self.mode in ['rect', 'ellipse', 'line']:
            self.image = self.temp_image.copy()
            painter = QPainter(self.image)
            self.draw_shape(painter, self.mode, self.start_point, current_point)

        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drawing = False
            self.temp_image = None

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.drawImage(0, 0, self.image)

    def set_mode(self, mode):
        self.mode = mode  # brush / eraser / rect / ellipse / line

    def draw_shape(self, painter, shape_type, start, end):
        pen = QPen(self.pen_color, self.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        rect = QRect(start, end)

        if shape_type == 'rect':
            painter.drawRect(rect.normalized())
        elif shape_type == 'ellipse':
            painter.drawEllipse(rect.normalized())
        elif shape_type == 'line':
            painter.drawLine(start, end)

