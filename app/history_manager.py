# Файл: app/history_manager.py
# Управляет историей действий (Undo/Redo) для каждого слоя.

from collections import defaultdict


class HistoryManager:
    """Управляет стеками undo/redo для состояний изображений каждого слоя."""

    def __init__(self, max_history_depth=20):
        self.max_depth = max_history_depth
        # Словарь, где ключ - ID слоя, значение - словарь {'undo': [], 'redo': []}
        self.history_stacks = defaultdict(lambda: {'undo': [], 'redo': []})

    def add_state(self, layer_id, image_state_pil, is_initial_state=False):
        """Добавляет новое состояние изображения для указанного слоя."""
        if not layer_id: return

        layer_history = self.history_stacks[layer_id]

        # Если это не первое состояние после сброса/создания, добавляем текущее в undo
        if not is_initial_state and layer_history['undo']:
            # Проверка, чтобы не добавлять дубликаты подряд (если изображение не изменилось)
            # Это требует сравнения изображений, что может быть дорого.
            # Пока упростим и будем добавлять.
            pass

        layer_history['undo'].append(image_state_pil)

        # Ограничиваем глубину истории undo
        while len(layer_history['undo']) > self.max_depth:
            layer_history['undo'].pop(0)  # Удаляем самое старое состояние

        # При добавлении нового состояния, очищаем стек redo
        if not is_initial_state:  # Не очищаем redo, если это самое первое состояние (например, при сбросе)
            layer_history['redo'].clear()

    def undo(self, layer_id):
        """Отменяет последнее действие для слоя, возвращает предыдущее состояние изображения."""
        if not layer_id or not self.can_undo(layer_id):
            return None

        layer_history = self.history_stacks[layer_id]
        # Последний элемент в 'undo' - это текущее состояние.
        # Нам нужно состояние *перед* ним.
        # Но наша логика add_state добавляет *текущее* состояние в undo перед изменением.
        # Значит, при undo, мы берем последнее из undo, кладем его в redo,
        # и возвращаем ПРЕДПОСЛЕДНЕЕ из undo (если оно есть).

        current_state = layer_history['undo'].pop()  # Извлекаем текущее состояние
        layer_history['redo'].append(current_state)  # Перемещаем его в redo

        if layer_history['undo']:
            return layer_history['undo'][-1].copy()  # Возвращаем предыдущее состояние (теперь оно последнее в undo)
        else:
            # Если стек undo пуст после извлечения, значит, мы откатились к самому началу.
            # В этом случае, возможно, нужно вернуть "оригинальное" изображение слоя, если оно хранится.
            # Или просто сигнализировать, что дальше отменять нечего.
            # Для текущей логики, если undo пуст, значит, некуда откатываться.
            # Вернем current_state обратно в undo, т.к. отмена невозможна дальше.
            layer_history['undo'].append(layer_history['redo'].pop())  # Возвращаем состояние
            return None

    def redo(self, layer_id):
        """Повторяет отмененное действие для слоя, возвращает восстановленное состояние изображения."""
        if not layer_id or not self.can_redo(layer_id):
            return None

        layer_history = self.history_stacks[layer_id]
        redone_state = layer_history['redo'].pop()  # Извлекаем состояние из redo
        layer_history['undo'].append(redone_state)  # Перемещаем его обратно в undo (как текущее)
        return redone_state.copy()

    def can_undo(self, layer_id):
        # Можно отменить, если в стеке undo БОЛЕЕ ОДНОГО элемента
        # (первый элемент - это самое начальное состояние, к которому мы откатываемся)
        return layer_id in self.history_stacks and len(self.history_stacks[layer_id]['undo']) > 1

    def can_redo(self, layer_id):
        return layer_id in self.history_stacks and bool(self.history_stacks[layer_id]['redo'])

    def clear_history_for_layer(self, layer_id):
        """Очищает историю для конкретного слоя."""
        if layer_id in self.history_stacks:
            self.history_stacks[layer_id]['undo'].clear()
            self.history_stacks[layer_id]['redo'].clear()

    def clear_all_history(self):
        self.history_stacks.clear()