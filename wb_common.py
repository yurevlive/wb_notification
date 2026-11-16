"""Общая логика WB: адреса CDN, загрузка товара, разбор команд.

Используется воркером (GitHub Actions) и сервером.
"""

import requests

BASIS = 395  # базовая цена WB, к которой привязаны коэффициенты
COEF_WALLET = 426 / BASIS
COEF_SBP = 454 / BASIS

VOL_LIMITS = (
    143, 287, 431, 719, 1007, 1061, 1115, 1169, 1313, 1601, 1655, 1919,
    2045, 2189, 2405, 2621, 2837, 3053, 3269, 3485, 3701, 3917, 4133, 4349,
    4565, 4877, 5189, 5501, 5813, 6125, 6437, 6749, 7061, 7373, 7685,
)

HEADERS = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"}


def basket_host(volume):
    for i, limit in enumerate(VOL_LIMITS, 1):
        if volume <= limit:
            return "%02d" % i
    return "36"


def product_base(sku):
    volume, part = sku // 100000, sku // 1000
    return "https://basket-%s.wbbasket.ru/vol%d/part%d/%d" % (
        basket_host(volume), volume, part, sku,
    )


def product_image(sku):
    return product_base(sku) + "/images/c246x328/1.webp"


def product_url(sku):
    return "https://www.wildberries.ru/catalog/%d/detail.aspx" % sku


def prices_from_base(base_rub):
    """Базовая цена в рублях -> (кошелёк, СБП)."""
    if not base_rub:
        return None, None
    return round(base_rub * COEF_WALLET), round(base_rub * COEF_SBP)


def fetch_product(sku, timeout=15):
    """Возвращает (название, цена_кошелёк, цена_СБП, картинка). Цены могут быть None."""
    base = product_base(sku)
    name, wallet, sbp = "Товар %d" % sku, None, None
    try:
        r = requests.get(base + "/info/ru/card.json", headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            name = r.json().get("imt_name") or name
    except (requests.RequestException, ValueError):
        pass
    try:
        r = requests.get(base + "/info/price-history.json", headers=HEADERS, timeout=timeout)
        if r.status_code == 200 and r.json():
            kop = r.json()[-1].get("price", {}).get("RUB", 0)
            wallet, sbp = prices_from_base(kop // 100)
    except (requests.RequestException, ValueError):
        pass
    return name, wallet, sbp, product_image(sku)


def parse_add_command(text):
    """'АРТИКУЛ ЦЕНА [ЛИМИТ]' -> (sku, target, limit) или None."""
    parts = text.replace(",", " ").split()
    if len(parts) < 2:
        return None
    try:
        sku = int(parts[0])
        target = int(parts[1])
        limit = int(parts[2]) if len(parts) >= 3 else 1
    except ValueError:
        return None
    if sku <= 0 or target <= 0 or limit <= 0:
        return None
    return sku, target, min(limit, 99)
