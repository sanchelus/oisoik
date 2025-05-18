# Файл: app/layer_manager.py
# Управляет слоями изображения.

import uuid
from PIL import Image
from PySide6.QtCore import QObject, Signal


class Layer:
    """Представляет один слой изображения."""

    def __init__(self, name="Новый слой", image=None, visible=True, opacity=1.0, is_original=False):
        self.id = uuid.uuid4()  # Уникальный идентификатор слоя
        self.name = name
        self.image = image  # PIL Image object
        self.original_image = image.copy() if image and is_original else None  # Для сброса
        self.visible = visible
        self.opacity = opacity  # От 0.0 до 1.0 (пока не используется в композиции)

    def __repr__(self):
        return f"Layer(id={self.id}, name='{self.name}', image_exists={self.image is not None})"


class LayerManager(QObject):
    """Управляет списком слоев и их композицией."""
    active_layer_changed = Signal(uuid.UUID)  # Сигнал об изменении активного слоя (передает ID)
    layer_added = Signal(uuid.UUID)
    layer_removed = Signal(uuid.UUID)  # Для будущего
    layers_reordered = Signal()  # Для будущего

    def __init__(self):
        super().__init__()
        self.layers = []  # Список объектов Layer, нижний слой - первый в списке
        self._active_layer_id = None
        self._layer_name_counter = 1

    def has_layers(self):
        return bool(self.layers)

    def add_layer(self, name=None, image=None, position=None, visible=True, opacity=1.0, is_original=False):
        if name is None:
            name = f"Слой {self._layer_name_counter}"
            self._layer_name_counter += 1

        new_layer = Layer(name=name, image=image, visible=visible, opacity=opacity, is_original=is_original)

        if position is None or position >= len(self.layers):
            self.layers.append(new_layer)  # Добавляем наверх (в конец списка)
        else:
            self.layers.insert(position, new_layer)

        if not self._active_layer_id or len(self.layers) == 1:  # Если это первый слой или не было активного
            self.set_active_layer_by_id(new_layer.id)

        self.layer_added.emit(new_layer.id)
        return new_layer

    def get_active_layer(self):
        if self._active_layer_id:
            for layer in self.layers:
                if layer.id == self._active_layer_id:
                    return layer
        return None

    def set_active_layer_by_id(self, layer_id):
        old_active_id = self._active_layer_id
        found = False
        for layer in self.layers:
            if layer.id == layer_id:
                self._active_layer_id = layer_id
                found = True
                break
        if not found:  # Если ID не найден, сбрасываем активный слой
            self._active_layer_id = None

        if old_active_id != self._active_layer_id:
            self.active_layer_changed.emit(self._active_layer_id if self._active_layer_id else uuid.UUID(int=0))

    def get_composite_image(self):
        """Создает композитное изображение из всех видимых слоев."""
        if not self.layers:
            return None

        # Определяем размер композиции по первому слою с изображением
        base_width, base_height = None, None
        for layer in self.layers:  # Ищем первый слой с размерами
            if layer.image and layer.visible:
                base_width, base_height = layer.image.size
                break

        if base_width is None or base_height is None:  # Если нет видимых слоев с изображениями
            # Попробуем взять размеры у первого невидимого, если есть
            if self.layers and self.layers[0].image:
                base_width, base_height = self.layers[0].image.size
            else:  # Совсем нет изображений ни в одном слое
                return Image.new("RGBA", (1, 1), (0, 0, 0, 0))  # Возвращаем минимальное пустое изображение

        # Создаем базовое изображение (холст) - полностью прозрачное
        composite = Image.new("RGBA", (base_width, base_height), (0, 0, 0, 0))

        for layer in self.layers:  # Слои рисуются снизу вверх
            if layer.visible and layer.image:
                # Убедимся, что слой имеет тот же размер, что и холст
                # (В будущем здесь может быть логика смещения слоя или масштабирования)
                if layer.image.size != (base_width, base_height):
                    # Простое решение: если размер не совпадает, пропускаем слой или центрируем/обрезаем
                    # Пока пропустим, чтобы избежать ошибок. В реальном приложении нужна обработка.
                    print(
                        f"Предупреждение: Слой '{layer.name}' имеет размер {layer.image.size}, а холст {base_width}x{base_height}. Слой пропущен в композиции.")
                    # continue # Раскомментировать, если нужно строгое совпадение размеров
                    # Вместо пропуска, создадим временное изображение нужного размера и вставим туда слой
                    temp_layer_canvas = Image.new("RGBA", (base_width, base_height), (0, 0, 0, 0))
                    # Простое размещение в левом верхнем углу, если слой меньше
                    paste_x = 0
                    paste_y = 0
                    # Можно добавить логику центрирования или обрезки здесь
                    temp_layer_canvas.paste(layer.image, (paste_x, paste_y),
                                            layer.image if layer.image.mode == 'RGBA' else None)
                    image_to_composite = temp_layer_canvas
                else:
                    image_to_composite = layer.image

                # Простое наложение с учетом альфа-канала слоя
                # Для opacity слоя (будущее): можно создать альфа-маску с учетом layer.opacity
                if image_to_composite.mode == 'RGBA':
                    composite.alpha_composite(image_to_composite)
                else:  # Если слой не RGBA, конвертируем его для безопасного alpha_composite
                    composite.alpha_composite(image_to_composite.convert("RGBA"))
        return composite

    def clear_all_layers(self):
        self.layers = []
        self._active_layer_id = None
        self._layer_name_counter = 1
        # Нужно будет также очистить историю, связанную с этими слоями
        # self.layers_reordered.emit() # Или какой-то сигнал об очистке