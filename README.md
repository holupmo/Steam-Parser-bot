# 🎮 Steam Parser Bot

**Асинхронный Telegram бот для поиска скидок в Steam**

Бот парсит актуальные скидки Steam, фильтрует по параметрам и присылает топ предложений прямо в Telegram. Работает без API ключа, использует асинхронные запросы для максимальной скорости.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## ✨ Возможности

- ⚡ **Асинхронный парсинг** — до 15 одновременных запросов
- 🎯 **Фильтрация** — по скидке, цене, жанрам, рейтингу Metacritic
- 💾 **Кэширование** — повторные поиски мгновенны
- 🔘 **Удобные кнопки** — постоянная клавиатура внизу экрана
- 📊 **Красивый вывод** — форматированные сообщения с эмодзи
- 🚫 **Без API ключа** — работает сразу после установки

---

**Пример вывода:**

🎮 Найдено 5 игр
💰 Экономия: 1247₽

    Hades
    🏷️ Скидка: -75%
    💵 Цена: 229₽
    ⭐ Рейтинг: 93%
    🔗 Купить

    Hollow Knight
    🏷️ Скидка: -80%
    💵 Цена: 105₽
    ⭐ Рейтинг: 96%
    🔗 Купить


---

## 🚀 Быстрый старт

### Установка

```bash
# Клонируем репозиторий
git clone https://github.com/holumpo/steam-hunter-bot.git
cd steam-hunter-bot

# Создаём виртуальное окружение
python -m venv venv

# Активируем
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt
