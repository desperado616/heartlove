"""
Telegram бот с интеграцией DeepSeek-R1 для психологической поддержки
Использует aiogram 3.x
"""
import os
import logging
import asyncio
import random
from datetime import datetime, time, timedelta
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

from database import (
    init_db, save_message, get_context, clear_context,
    update_user_stats, get_user_stats,
    update_last_reminder, update_boundary_reminder,
    check_recent_trigger_words
)
from deepseek_api import get_ai_response, FIRST_MESSAGE

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
ALLOWED_CHAT_ID = int(os.getenv('ALLOWED_CHAT_ID', '0'))  # [УКАЗАТЬ_ЧАТ_ID]

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден! Создайте файл .env и добавьте туда BOT_TOKEN=ваш_токен")

if ALLOWED_CHAT_ID == 0:
    raise ValueError("ALLOWED_CHAT_ID не установлен! Укажите ID чата в .env")

# Триггерные слова для напоминаний
TRIGGER_WORDS = ['одиноко', 'грустно', 'боюсь', 'не любит', 'никто', 'брошен']

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Флаг для отслеживания первого сообщения
first_message_sent = {}


def check_auth(chat_id: int) -> bool:
    """Проверка авторизации пользователя"""
    return chat_id == ALLOWED_CHAT_ID


async def check_trigger_words(text: str) -> bool:
    """Проверяет наличие триггерных слов в тексте"""
    text_lower = text.lower()
    return any(word in text_lower for word in TRIGGER_WORDS)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    if not check_auth(message.chat.id):
        await message.answer("Извините, у вас нет доступа к этому боту.")
        return
    
    await message.answer(
        "Привет! Я здесь, чтобы поддержать тебя. "
        "Можешь написать мне о чём угодно, и я выслушаю.\n\n"
        "Используй /help для просмотра всех возможностей."
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    if not check_auth(message.chat.id):
        return
    
    help_text = (
        "📋 Доступные команды:\n\n"
        "/start — начать работу с ботом\n"
        "/help — показать эту справку\n"
        "/now — быстрые реакции на текущее состояние\n"
        "/mood — быстро оценить своё настроение\n"
        "/emergency — контакты психологических служб поддержки\n\n"
        "💬 Ты можешь просто написать мне о своих переживаниях, "
        "и я постараюсь помочь тебе разобраться в них.\n\n"
        "Помни: Паша тебя любит ❤️"
    )
    await message.answer(help_text)


@dp.message(Command("now"))
async def cmd_now(message: Message):
    """Обработчик команды /now - быстрые реакции"""
    if not check_auth(message.chat.id):
        return
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Тревожно", callback_data="now_anxious")
    builder.button(text="Одиноко", callback_data="now_lonely")
    builder.button(text="Злюсь", callback_data="now_angry")
    builder.button(text="Хочу услышать о любви", callback_data="now_love")
    builder.adjust(2)
    
    await message.answer(
        "Что ты чувствуешь прямо сейчас?",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data.startswith("now_"))
async def process_now(callback: CallbackQuery):
    """Обработка быстрых реакций"""
    if not check_auth(callback.message.chat.id):
        return
    
    chat_id = callback.message.chat.id
    
    if callback.data == "now_anxious":
        # Техника 5-4-3-2-1
        response = (
            "Давай вернёмся в тело. Это займёт всего 60 секунд, но поможет заземлиться.\n\n"
            "Назови:\n"
            "5 вещей, которые видишь вокруг\n"
            "4 вещи, которые ощущаешь кожей\n"
            "3 звука, которые слышишь\n"
            "2 запаха, которые чувствуешь\n"
            "1 вкус во рту\n\n"
            "Делай это медленно, дыши. Ты здесь, ты в безопасности."
        )
        await callback.message.edit_text(response)
        await callback.answer()
        
    elif callback.data == "now_lonely":
        # Напоминание о любви Паши + предложение написать ему
        response = (
            "Я вижу, что тебе одиноко. Помни — Паша тебя любит ❤️\n\n"
            "Может, стоит написать ему прямо сейчас? Иногда слова вслух меняют всё."
        )
        await callback.message.edit_text(response)
        await callback.answer()
        
    elif callback.data == "now_angry":
        # Помощь при злости
        response = (
            "Злость — это нормальная эмоция. Давай разберёмся, что её вызвало.\n\n"
            "Что говорит факт? Что говорит эмоция?\n\n"
            "Попробуй описать ситуацию без оценок — просто факты. "
            "Это поможет отделить реальность от эмоциональной реакции."
        )
        await callback.message.edit_text(response)
        await callback.answer()
        
    elif callback.data == "now_love":
        # Напоминание о любви Паши
        response = (
            "Помни — Паша тебя любит ❤️\n\n"
            "Когда сомневаешься, вспомни моменты, когда ты чувствовала его любовь. "
            "Они реальны, они были. Страх может затуманить память, но факты остаются.\n\n"
            "Может, стоит написать ему и сказать, что ты его любишь? "
            "Иногда слова вслух меняют всё."
        )
        await callback.message.edit_text(response)
        await callback.answer()


@dp.message(Command("mood"))
async def cmd_mood(message: Message):
    """Обработчик команды /mood - оценка настроения"""
    if not check_auth(message.chat.id):
        return
    
    builder = InlineKeyboardBuilder()
    builder.button(text="👍 Хорошо", callback_data="mood_good")
    builder.button(text="😐 Нормально", callback_data="mood_ok")
    builder.button(text="👎 Плохо", callback_data="mood_bad")
    builder.adjust(3)
    
    await message.answer(
        "Как ты себя чувствуешь сейчас?",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data.startswith("mood_"))
async def process_mood(callback: CallbackQuery):
    """Обработка выбора настроения"""
    if not check_auth(callback.message.chat.id):
        return
    
    mood_map = {
        "mood_good": "👍 Хорошо",
        "mood_ok": "😐 Нормально",
        "mood_bad": "👎 Плохо"
    }
    
    mood_text = mood_map.get(callback.data, "Неизвестно")
    
    responses = {
        "mood_good": "Отлично! Рада слышать, что у тебя хорошее настроение. Если хочешь поделиться чем-то, я всегда готова выслушать ❤️",
        "mood_ok": "Понятно. Иногда нормальное состояние — это уже хорошо. Если хочешь поговорить о чём-то, я здесь.",
        "mood_bad": "Мне жаль, что тебе плохо. Давай поговорим об этом? Расскажи, что происходит. И помни — Паша тебя любит ❤️"
    }
    
    response_text = responses.get(callback.data, "Спасибо за ответ!")
    
    await callback.message.edit_text(
        f"Ты выбрала: {mood_text}\n\n{response_text}"
    )
    await callback.answer()


@dp.message(Command("emergency"))
async def cmd_emergency(message: Message):
    """Обработчик команды /emergency - контакты психологических служб"""
    if not check_auth(message.chat.id):
        return
    
    emergency_text = (
        "🚨 КОНТАКТЫ ПСИХОЛОГИЧЕСКИХ СЛУЖБ ПОДДЕРЖКИ\n\n"
        "📞 Телефон доверия (круглосуточно):\n"
        "8-800-2000-122 (бесплатно по России)\n\n"
        "📱 Телефон экстренной психологической помощи:\n"
        "8-495-989-50-50 (Москва)\n\n"
        "💬 Онлайн-чат психологической поддержки:\n"
        "https://telefon-doveria.ru/\n\n"
        "⚠️ Если у тебя возникают суицидальные мысли, "
        "пожалуйста, немедленно обратись к специалистам. "
        "Ты не одна, и помощь доступна 24/7.\n\n"
        "Помни: Паша тебя любит, и есть люди, которые готовы помочь ❤️"
    )
    await message.answer(emergency_text)


@dp.message(F.text)
async def handle_text_message(message: Message):
    """Обработчик текстовых сообщений"""
    if not check_auth(message.chat.id):
        return
    
    chat_id = message.chat.id
    user_text = message.text
    now = datetime.now()
    
    # Обновляем статистику пользователя
    await update_user_stats(chat_id, now)
    stats = await get_user_stats(chat_id)
    
    # Проверка на зависимость (более 5 раз в день)
    # Примечание: проверка на 3 дня подряд требует более сложной логики,
    # здесь проверяем только текущий день
    if stats["message_count"] > 5:
        # Отправляем мягкое напоминание о зависимости
        dependency_warning = (
            "Я рада, что ты мне доверяешь. Но твоя главная опора — Паша и реальные люди рядом. "
            "Давай сегодня напишем ему? Иногда слова вслух меняют всё."
        )
        # Отправляем только если это не первое сообщение сегодня
        if stats["message_count"] == 6:  # Только один раз при превышении лимита
            await message.answer(dependency_warning)
    
    # Проверяем, первое ли это сообщение (не команда)
    if chat_id not in first_message_sent:
        # Проверяем, есть ли уже сообщения в базе
        context = await get_context(chat_id)
        if len(context) == 0:
            # Это первое сообщение - отправляем приветствие
            await message.answer(FIRST_MESSAGE)
            first_message_sent[chat_id] = True
            # Сохраняем дату напоминания о границах
            await update_boundary_reminder(chat_id, now)
        else:
            first_message_sent[chat_id] = True
    
    # Проверка на напоминание о границах (раз в месяц)
    stats = await get_user_stats(chat_id)
    if stats["last_boundary_reminder_date"]:
        last_reminder = datetime.fromisoformat(stats["last_boundary_reminder_date"]).date()
        days_since = (now.date() - last_reminder).days
        if days_since >= 30:
            await message.answer(
                "Напоминание: Я — цифровая поддержка, а не замена терапевту. "
                "При тяжёлых состояниях (долгая бессонница, мысли о смерти) — "
                "пожалуйста, обратись к специалисту. Ты достойна живой помощи."
            )
            await update_boundary_reminder(chat_id, now)
    
    # Проверка на тревогу/панику в тексте
    anxiety_words = ['тревожно', 'тревога', 'паника', 'паникую', 'страшно', 'боюсь', 'уход в голову']
    has_anxiety = any(word in user_text.lower() for word in anxiety_words)
    
    if has_anxiety:
        # Предлагаем технику 5-4-3-2-1
        await message.answer(
            "Давай вернёмся в тело. Это займёт всего 60 секунд, но поможет заземлиться.\n\n"
            "Назови:\n"
            "5 вещей, которые видишь вокруг\n"
            "4 вещи, которые ощущаешь кожей\n"
            "3 звука, которые слышишь\n"
            "2 запаха, которые чувствуешь\n"
            "1 вкус во рту\n\n"
            "Делай это медленно, дыши. Ты здесь, ты в безопасности."
        )
    
    # Проверка на триггерные слова
    if await check_trigger_words(user_text):
        await message.answer(
            "Я вижу, что тебе сейчас непросто. Помни, что Паша тебя любит ❤️\n\n"
            "Давай поговорим об этом подробнее?"
        )
    
    # Сохраняем сообщение пользователя
    await save_message(chat_id, "user", user_text)
    
    # Отправляем индикатор печати
    await bot.send_chat_action(chat_id, "typing")
    
    # Получаем контекст
    context = await get_context(chat_id)
    
    # Получаем ответ от AI
    try:
        ai_response = await get_ai_response(context, timeout=25)
        
        if ai_response:
            # Сохраняем ответ ассистента
            await save_message(chat_id, "assistant", ai_response)
            await message.answer(ai_response)
        else:
            # Fallback при ошибке
            fallback_message = (
                "Извини, у меня сейчас возникли технические сложности. "
                "Попробуй написать мне чуть позже.\n\n"
                "Если тебе нужна срочная поддержка, используй команду /emergency.\n\n"
                "Помни: Паша тебя любит ❤️"
            )
            await message.answer(fallback_message)
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}", exc_info=True)
        fallback_message = (
            "Извини, у меня сейчас возникли технические сложности. "
            "Попробуй написать мне чуть позже.\n\n"
            "Если тебе нужна срочная поддержка, используй команду /emergency.\n\n"
            "Помни: Паша тебя любит ❤️"
        )
        await message.answer(fallback_message)


async def send_weekly_reminders():
    """Отправляет напоминания 2 раза в неделю (случайные дни, время 11:00-19:00)"""
    while True:
        now = datetime.now()
        stats = await get_user_stats(ALLOWED_CHAT_ID)
        
        # Проверяем, прошло ли минимум 48 часов с последнего напоминания
        can_send = True
        if stats["last_reminder_date"]:
            try:
                last_reminder = datetime.fromisoformat(stats["last_reminder_date"])
                hours_since = (now - last_reminder).total_seconds() / 3600
                if hours_since < 48:
                    can_send = False
            except (ValueError, TypeError):
                # Если дата некорректна, разрешаем отправку
                can_send = True
        
        if can_send:
            # Вычисляем случайное время между 11:00 и 19:00
            target_hour = random.randint(11, 19)
            target_minute = random.randint(0, 59)
            target_datetime = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
            
            # Если текущее время уже прошло целевое время, планируем на завтра
            if now > target_datetime:
                target_datetime += timedelta(days=1)
            
            # Вычисляем задержку до следующего напоминания
            delay = (target_datetime - now).total_seconds()
            
            logger.info(f"Следующее напоминание запланировано на {target_datetime.strftime('%Y-%m-%d %H:%M')}")
            
            await asyncio.sleep(delay)
            
            # Проверяем триггерные слова за последние 24 часа
            has_triggers = await check_recent_trigger_words(ALLOWED_CHAT_ID, hours=24)
            
            if has_triggers:
                # Усиленное напоминание при триггерах
                reminder_text = "Вижу, сегодня было непросто. Но помни — Паша тебя любит ❤️"
            else:
                # Обычное напоминание
                reminder_text = "Помни, что Паша тебя любит ❤️"
            
            try:
                await bot.send_message(ALLOWED_CHAT_ID, reminder_text)
                await update_last_reminder(ALLOWED_CHAT_ID, datetime.now())
                logger.info("Напоминание отправлено")
            except Exception as e:
                logger.error(f"Ошибка при отправке напоминания: {e}")
        else:
            # Ждём до следующей проверки (через час)
            await asyncio.sleep(3600)


async def main():
    """Основная функция запуска бота"""
    try:
        # Инициализируем базу данных
        await init_db()
        logger.info("База данных инициализирована")
        
        # Запускаем задачу для еженедельных напоминаний
        asyncio.create_task(send_weekly_reminders())
        logger.info("Задача еженедельных напоминаний запущена")
        
        # Запускаем бота
        logger.info("Бот запущен и готов к работе!")
        await dp.start_polling(
            bot, 
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True  # Игнорируем старые обновления при перезапуске
        )
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        raise
