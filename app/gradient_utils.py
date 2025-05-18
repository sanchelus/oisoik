# Файл: app/gradient_utils.py
from PIL import Image

def create_linear_gradient(width, height, start_color, end_color, direction='horizontal'):
    """Создаёт PIL-изображение с линейным градиентом."""
    base = Image.new('RGBA', (width, height), start_color)
    top = Image.new('RGBA', (width, height), end_color)

    if direction == 'horizontal':
        mask = Image.linear_gradient('L').resize((width, 1)).resize((width, height))
    else:
        mask = Image.linear_gradient('L').resize((1, height)).resize((width, height))

    base.paste(top, (0, 0), mask)
    return base
