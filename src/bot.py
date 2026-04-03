import asyncio
import json
from pathlib import Path
from typing import Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler
from telegram.request import HTTPXRequest
from dotenv import load_dotenv
import os

from src.async_steam_parser import AsyncSteamParser
from src.filters import GameFilter

import warnings
from telegram.warnings import PTBUserWarning

warnings.filterwarnings("ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

USER_FILTERS: Dict[int, Dict[str, Any]] = {}

ASK_DISCOUNT, ASK_RATING, ASK_PRICE, ASK_GENRES = range(4)

class SteamHunterBot:
    def __init__(self):
        self.parser = None
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await update.message.reply_text(
            f"🎮 Привет, {user.first_name}!\n\n"
            f"Я охотник за скидками в Steam.\n\n"
            f"📋 Команды:\n"
            f"/quick — быстрый поиск (скидка 70%+)\n"
            f"/best — лучшие предложения (скидка 80%+)\n"
            f"/hunt — поиск со своими параметрами\n"
            f"/filters — настроить фильтры\n"
            f"/help — помощь\n\n"
            f"Просто запускай и получай топ игр со скидками! 🚀"
        )
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📖 Помощь:\n\n"
            "/quick — скидка от 70%, 2 страницы, без деталей (быстро)\n"
            "/best — скидка от 80%, 3 страницы, с деталями\n"
            "/hunt — задай свои параметры (скидка, цена, жанры)\n"
            "/filters — сохрани настройки для следующих поисков\n"
            "/top — показать последние найденные игры\n\n"
            "Пример: /hunt 75 500 Action,RPG\n"
            "Ищет игры со скидкой 75%+, ценой до 500₽, жанры Action или RPG"
        )
    
    async def quick(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🔍 Быстрый поиск... Подожди пару секунд ⏳")
        
        async with AsyncSteamParser(max_concurrent=15) as parser:
            games = await parser.get_sale_games(max_pages=2)
            
            if not games:
                await update.message.reply_text("❌ Игры не найдены")
                return
            
            filter_engine = GameFilter(min_discount=70)
            filtered = filter_engine.filter_batch(games)
            
            await self._send_results(update, context, filtered[:10])
    
    async def best(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🔍 Ищу лучшие предложения... Это может занять 10-15 секунд ⏳")
        
        async with AsyncSteamParser(max_concurrent=15) as parser:
            games = await parser.get_sale_games(max_pages=3)
            
            if not games:
                await update.message.reply_text("❌ Игры не найдены")
                return
            
            games = await parser.enrich_games_with_details(games)
            
            filter_engine = GameFilter(min_discount=80, min_rating=80)
            filtered = filter_engine.filter_batch(games)
            
            await self._send_results(update, context, filtered[:10])
    
    async def hunt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        args = context.args
        
        if len(args) >= 1:
            discount = int(args[0]) if args[0].isdigit() else 70
            max_price = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
            genres = args[2] if len(args) > 2 else None
            
            await self._run_hunt(update, context, discount, max_price, genres)
        else:
            keyboard = [
                [InlineKeyboardButton("🎯 Быстрый поиск (70%)", callback_data="hunt_quick")],
                [InlineKeyboardButton("💎 Лучшие предложения (80%)", callback_data="hunt_best")],
                [InlineKeyboardButton("⚙️ Свои параметры", callback_data="hunt_custom")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("🎮 Выбери режим поиска:", reply_markup=reply_markup)
    
    async def _run_hunt(self, update: Update, context: ContextTypes.DEFAULT_TYPE, discount=70, max_price=None, genres=None, min_rating=0):
        await update.message.reply_text(f"🔍 Поиск: скидка {discount}%+, цена до {max_price or '∞'}₽, жанры: {genres or 'все'}... ⏳")
        
        async with AsyncSteamParser(max_concurrent=15) as parser:
            games = await parser.get_sale_games(max_pages=3)
            
            if not games:
                await update.message.reply_text("❌ Игры не найдены")
                return
            
            games = await parser.enrich_games_with_details(games)
            
            genre_list = [g.strip() for g in genres.split(',')] if genres else []
            
            filter_engine = GameFilter(
                min_discount=discount,
                min_rating=min_rating,
                max_price=max_price,
                genres=genre_list
            )
            
            filtered = filter_engine.filter_batch(games)
            
            if not filtered:
                await update.message.reply_text("⚠️ Нет игр подходящих под критерии. Попробуй снизить требования.")
                return
            
            await self._send_results(update, context, filtered[:10])
    
    async def _send_results(self, update: Update, context: ContextTypes.DEFAULT_TYPE, games):
        if not games:
            await update.message.reply_text("❌ Ничего не найдено")
            return
        
        total_savings = sum(g.get('original_price', 0) - g.get('price', 0) for g in games if g.get('original_price'))
        
        message = f"🎮 *Найдено {len(games)} игр*\n"
        message += f"💰 *Экономия:* {total_savings}₽\n\n"
        
        for idx, game in enumerate(games, 1):
            message += f"{idx}. *{game.get('name', 'Unknown')}*\n"
            message += f"   🏷️ Скидка: *-{game.get('discount', 0)}%*\n"
            message += f"   💵 Цена: *{game.get('price', 0)}₽*\n"
            if game.get('rating_percent', 0) > 0:
                message += f"   ⭐ Рейтинг: *{game.get('rating_percent')}%*\n"
            message += f"   🔗 [Купить]({game.get('url')})\n\n"
            
            if idx >= 10:
                break
        
        message += f"\n📁 Полный список в /top"
        
        await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True)
        
        context.user_data['last_results'] = games
    
    async def top(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if 'last_results' not in context.user_data:
            await update.message.reply_text("📭 Сначала выполни поиск командой /quick, /best или /hunt")
            return
        
        games = context.user_data['last_results']
        await self._send_results(update, context, games)
    
    async def filters(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🎯 Скидка", callback_data="filter_discount")],
            [InlineKeyboardButton("⭐ Рейтинг", callback_data="filter_rating")],
            [InlineKeyboardButton("💰 Макс. цена", callback_data="filter_price")],
            [InlineKeyboardButton("🎮 Жанры", callback_data="filter_genres")],
            [InlineKeyboardButton("✅ Показать текущие", callback_data="filter_show")],
            [InlineKeyboardButton("🗑️ Сбросить всё", callback_data="filter_reset")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("⚙️ Настройки фильтров:", reply_markup=reply_markup)
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        if data == "filter_discount":
            await query.edit_message_text("Введи минимальную скидку (число от 0 до 100):")
            return ASK_DISCOUNT
        
        elif data == "filter_rating":
            await query.edit_message_text("Введи минимальный рейтинг (число от 0 до 100):")
            return ASK_RATING
        
        elif data == "filter_price":
            await query.edit_message_text("Введи максимальную цену в рублях:")
            return ASK_PRICE
        
        elif data == "filter_genres":
            await query.edit_message_text("Введи жанры через запятую (например: Action,RPG,Strategy):")
            return ASK_GENRES
        
        elif data == "filter_show":
            filters = USER_FILTERS.get(user_id, {})
            if not filters:
                await query.edit_message_text("📭 Фильтры не настроены. Используются значения по умолчанию.")
            else:
                msg = "📊 *Твои фильтры:*\n"
                msg += f"🎯 Скидка: {filters.get('discount', 70)}%\n"
                msg += f"⭐ Рейтинг: {filters.get('rating', 0)}%\n"
                msg += f"💰 Макс. цена: {filters.get('max_price', '∞')}₽\n"
                msg += f"🎮 Жанры: {filters.get('genres', 'все')}\n"
                await query.edit_message_text(msg, parse_mode='Markdown')
        
        elif data == "filter_reset":
            USER_FILTERS[user_id] = {}
            await query.edit_message_text("✅ Все фильтры сброшены!")
        
        elif data.startswith("hunt_"):
            if data == "hunt_quick":
                await self.quick(update, context)
            elif data == "hunt_best":
                await self.best(update, context)
            elif data == "hunt_custom":
                await query.edit_message_text(
                    "Введи параметры поиска в формате:\n"
                    "/hunt <скидка> <макс_цена> <жанры>\n\n"
                    "Пример: /hunt 75 500 Action,RPG"
                )
        
        return ConversationHandler.END

def main():
    if not BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не найден в .env файле")
        print("Создай .env файл и добавь: BOT_TOKEN=твой_токен")
        return
    
    print("🤖 Бот запускается...")
    
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .build()
    )
    
    bot = SteamHunterBot()
    
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help))
    application.add_handler(CommandHandler("quick", bot.quick))
    application.add_handler(CommandHandler("best", bot.best))
    application.add_handler(CommandHandler("hunt", bot.hunt))
    application.add_handler(CommandHandler("top", bot.top))
    application.add_handler(CommandHandler("filters", bot.filters))
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(bot.button_callback, pattern="^filter_")],
        states={
            ASK_DISCOUNT: [CallbackQueryHandler(bot.button_callback, pattern="^filter_discount$")],
            ASK_RATING: [CallbackQueryHandler(bot.button_callback, pattern="^filter_rating$")],
            ASK_PRICE: [CallbackQueryHandler(bot.button_callback, pattern="^filter_price$")],
            ASK_GENRES: [CallbackQueryHandler(bot.button_callback, pattern="^filter_genres$")],
        },
        fallbacks=[CommandHandler("cancel", bot.start)],
        per_message=True,
    )
    application.add_handler(conv_handler)
    
    application.add_handler(CallbackQueryHandler(bot.button_callback))
    
    print("🤖 Бот запущен и готов к работе!")
    application.run_polling()

if __name__ == "__main__":
    main()