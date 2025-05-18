# Файл: app/image_operations.py
# Содержит функции для выполнения различных операций над изображениями с использованием Pillow.

from PIL import Image, ImageEnhance, ImageOps, ImageFilter


def apply_grayscale(image_pil):
    if image_pil: return image_pil.convert("L").convert("RGBA")
    return None


def apply_sepia(image_pil):
    if image_pil:
        if image_pil.mode != 'RGB' and image_pil.mode != 'RGBA':
            image_pil = image_pil.convert('RGBA')

        r, g, b, *a = image_pil.split()

        r_new = r.point(
            lambda i: i * 0.393 + g.getdata()[r.getdata().index(i)] * 0.769 + b.getdata()[r.getdata().index(i)] * 0.189)
        g_new = r.point(
            lambda i: i * 0.349 + g.getdata()[r.getdata().index(i)] * 0.686 + b.getdata()[r.getdata().index(i)] * 0.168)
        b_new = r.point(
            lambda i: i * 0.272 + g.getdata()[r.getdata().index(i)] * 0.534 + b.getdata()[r.getdata().index(i)] * 0.131)

        # Ограничение значений в диапазоне 0-255 (Pillow делает это автоматически при .point, но для ясности)
        # r_new = r_new.point(lambda i: min(255, int(i)))
        # g_new = g_new.point(lambda i: min(255, int(i)))
        # b_new = b_new.point(lambda i: min(255, int(i)))

        if a:  # Если был альфа-канал
            return Image.merge('RGBA', (r_new, g_new, b_new, a[0]))
        else:
            return Image.merge('RGB', (r_new, g_new, b_new)).convert('RGBA')
    return None


def adjust_brightness(image_pil, factor):
    if image_pil:
        enhancer = ImageEnhance.Brightness(image_pil)
        return enhancer.enhance(factor)
    return None


def adjust_contrast(image_pil, factor):
    if image_pil:
        enhancer = ImageEnhance.Contrast(image_pil)
        return enhancer.enhance(factor)
    return None


def rotate_90_clockwise(image_pil):
    if image_pil: return image_pil.transpose(Image.ROTATE_270)
    return None


# --- Новые фильтры ---
def apply_gaussian_blur(image_pil, radius=2):
    """Применяет Гауссово размытие."""
    if image_pil:
        return image_pil.filter(ImageFilter.GaussianBlur(radius))
    return None


def apply_sharpen(image_pil):
    """Применяет фильтр увеличения резкости."""
    if image_pil:
        return image_pil.filter(ImageFilter.SHARPEN)
    return None


def apply_emboss(image_pil):
    """Применяет фильтр тиснения."""
    if image_pil:
        return image_pil.filter(ImageFilter.EMBOSS)
    return None


def apply_edge_detect(image_pil):
    """Применяет фильтр обнаружения краев."""
    if image_pil:
        # FIND_EDGES может сделать изображение довольно темным, EDGE_ENHANCE_MORE мягче
        return image_pil.filter(ImageFilter.FIND_EDGES)
    return None


def save_image(image_pil, file_path):
    img_to_save = image_pil
    if file_path.lower().endswith((".jpg", ".jpeg")):
        if img_to_save.mode == 'RGBA':
            background = Image.new("RGB", img_to_save.size, (255, 255, 255))
            background.paste(img_to_save, mask=img_to_save.split()[3])
            img_to_save = background
        elif img_to_save.mode == 'P' and 'transparency' in img_to_save.info:
            img_to_save = img_to_save.convert('RGB')
    img_to_save.save(file_path)