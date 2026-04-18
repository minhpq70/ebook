"""
OCR Engine — Pipeline 2 tầng: PaddleOCR + VietOCR
- Tầng 1: PaddleOCR (detection + recognition) — nhanh, tốt cho đa số trường hợp
- Tầng 2: VietOCR fallback — chạy lại recognition cho dòng có confidence thấp
- PDF text-based: bỏ qua OCR hoàn toàn

Sử dụng:
    from services.ocr_engine import ocr_page_image, init_ocr
"""
from __future__ import annotations

import logging
from io import BytesIO

from PIL import Image

logger = logging.getLogger("ebook.ocr")

# ── Lazy-loaded globals ──────────────────────────────────────────────────────
_paddle_ocr = None
_vietocr_predictor = None
_CONFIDENCE_THRESHOLD = 0.85


def _get_paddle_ocr():
    """Lazy-init PaddleOCR (tải model lần đầu, cache lần sau)."""
    global _paddle_ocr
    if _paddle_ocr is None:
        try:
            from paddleocr import PaddleOCR
            _paddle_ocr = PaddleOCR(
                lang="vi",
                use_angle_cls=True,   # Tự xoay text nghiêng
                show_log=False,
                use_gpu=False,        # CPU-only (tương thích Render)
            )
            logger.info("PaddleOCR initialized (lang=vi, CPU)")
        except ImportError:
            logger.warning("PaddleOCR not installed — falling back to Tesseract")
            return None
        except Exception as e:
            logger.error("Failed to init PaddleOCR: %s", e)
            return None
    return _paddle_ocr


def _get_vietocr_predictor():
    """Lazy-init VietOCR predictor (tải model lần đầu)."""
    global _vietocr_predictor
    if _vietocr_predictor is None:
        try:
            from vietocr.tool.predictor import Predictor
            from vietocr.tool.config import Cfg

            config = Cfg.load_config_from_name("vgg_transformer")
            config["cnn"]["pretrained"] = True
            config["device"] = "cpu"  # CPU-only
            _vietocr_predictor = Predictor(config)
            logger.info("VietOCR initialized (vgg_transformer, CPU)")
        except ImportError:
            logger.warning("VietOCR not installed — PaddleOCR only mode")
            return None
        except Exception as e:
            logger.error("Failed to init VietOCR: %s", e)
            return None
    return _vietocr_predictor


def _tesseract_fallback(img: Image.Image) -> str:
    """Fallback cuối cùng: Tesseract OCR (nếu PaddleOCR không khả dụng)."""
    try:
        import pytesseract
        return pytesseract.image_to_string(img, lang="vie", timeout=30)
    except Exception as e:
        logger.warning("Tesseract fallback failed: %s", e)
        return ""


def ocr_page_image(img: Image.Image) -> str:
    """
    OCR một ảnh trang PDF → text.

    Pipeline:
    1. PaddleOCR detection + recognition
    2. Dòng nào confidence < 0.85 → chạy lại bằng VietOCR
    3. Nếu PaddleOCR không khả dụng → fallback Tesseract
    """
    paddle = _get_paddle_ocr()
    if paddle is None:
        return _tesseract_fallback(img)

    # ── Tầng 1: PaddleOCR ──
    try:
        import numpy as np
        img_array = np.array(img)
        results = paddle.ocr(img_array, cls=True)
    except Exception as e:
        logger.warning("PaddleOCR failed: %s — falling back to Tesseract", e)
        return _tesseract_fallback(img)

    if not results or not results[0]:
        return ""

    lines = results[0]  # List of [bbox, (text, confidence)]

    # ── Tầng 2: VietOCR cho dòng confidence thấp ──
    vietocr = _get_vietocr_predictor()
    output_lines: list[str] = []

    for line in lines:
        bbox = line[0]        # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        text = line[1][0]     # recognized text
        conf = line[1][1]     # confidence score

        if conf >= _CONFIDENCE_THRESHOLD or vietocr is None:
            # Confidence đủ cao HOẶC VietOCR không có → dùng PaddleOCR
            output_lines.append(text)
        else:
            # Confidence thấp → crop và chạy VietOCR
            try:
                cropped = _crop_bbox(img, bbox)
                vietocr_text = vietocr.predict(cropped)
                if vietocr_text and len(vietocr_text.strip()) > 0:
                    output_lines.append(vietocr_text)
                    logger.debug(
                        "VietOCR improved: '%s' (%.2f) → '%s'",
                        text, conf, vietocr_text
                    )
                else:
                    output_lines.append(text)  # VietOCR trả rỗng → giữ PaddleOCR
            except Exception as e:
                logger.debug("VietOCR failed for bbox, keeping PaddleOCR result: %s", e)
                output_lines.append(text)

    return "\n".join(output_lines)


def _crop_bbox(img: Image.Image, bbox: list) -> Image.Image:
    """Crop ảnh theo bounding box từ PaddleOCR."""
    import numpy as np

    pts = np.array(bbox, dtype=np.float32)
    x_min = max(0, int(pts[:, 0].min()))
    y_min = max(0, int(pts[:, 1].min()))
    x_max = min(img.width, int(pts[:, 0].max()))
    y_max = min(img.height, int(pts[:, 1].max()))

    # Thêm padding nhỏ để VietOCR dễ nhận dạng hơn
    pad = 3
    x_min = max(0, x_min - pad)
    y_min = max(0, y_min - pad)
    x_max = min(img.width, x_max + pad)
    y_max = min(img.height, y_max + pad)

    return img.crop((x_min, y_min, x_max, y_max))


def is_ocr_available() -> dict[str, bool]:
    """Kiểm tra OCR engines nào đã sẵn sàng."""
    paddle_ok = False
    vietocr_ok = False
    tesseract_ok = False

    try:
        import paddleocr  # noqa: F401
        paddle_ok = True
    except ImportError:
        pass

    try:
        import vietocr  # noqa: F401
        vietocr_ok = True
    except ImportError:
        pass

    try:
        import pytesseract  # noqa: F401
        tesseract_ok = True
    except ImportError:
        pass

    return {
        "paddleocr": paddle_ok,
        "vietocr": vietocr_ok,
        "tesseract": tesseract_ok,
    }
