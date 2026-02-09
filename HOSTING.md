# Инструкция по хостингу бота

## Рекомендуемые платформы

### 1. Railway (рекомендуется)
- Простая настройка
- Автоматический деплой из GitHub
- Бесплатный тарифный план доступен

**Шаги:**
1. Зарегистрируйтесь на [Railway.app](https://railway.app/)
2. Создайте новый проект из GitHub репозитория
3. Добавьте переменные окружения в настройках проекта:
   - `BOT_TOKEN` - токен Telegram бота
   - `ALLOWED_CHAT_ID` - ID чата пользователя
   - `OPENROUTER_API_KEY` - API ключ OpenRouter
4. Railway автоматически определит Python и установит зависимости
5. Бот запустится автоматически

### 2. Heroku
- Классический вариант для Python ботов
- Требует файл `Procfile`

**Создайте файл `Procfile`:**
```
worker: python bot.py
```

**Шаги:**
1. Установите Heroku CLI
2. Создайте приложение: `heroku create your-bot-name`
3. Добавьте переменные окружения через панель или CLI:
   ```bash
   heroku config:set BOT_TOKEN=your_token
   heroku config:set ALLOWED_CHAT_ID=your_chat_id
   heroku config:set OPENROUTER_API_KEY=your_key
   ```
4. Деплой: `git push heroku main`

### 3. VPS (DigitalOcean, AWS, etc.)
- Полный контроль над сервером
- Требует настройки systemd или supervisor

**Создайте systemd сервис `/etc/systemd/system/telegram-bot.service`:**
```ini
[Unit]
Description=Telegram Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/bot
Environment="BOT_TOKEN=your_token"
Environment="ALLOWED_CHAT_ID=your_chat_id"
Environment="OPENROUTER_API_KEY=your_key"
ExecStart=/usr/bin/python3 /path/to/bot/bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

**Команды:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

## Важные моменты

1. **База данных**: SQLite файл `bot_database.db` создаётся автоматически. На VPS убедитесь, что у процесса есть права на запись в директорию бота.

2. **Логирование**: Все логи выводятся в stdout/stderr, что удобно для просмотра на платформах хостинга.

3. **Перезапуск**: Бот автоматически игнорирует старые обновления при перезапуске (`drop_pending_updates=True`).

4. **Мониторинг**: Следите за логами на предмет ошибок. Бот обрабатывает ошибки gracefully и продолжает работу.

5. **Безопасность**: Никогда не коммитьте файл `.env` в Git. Все секреты должны быть в переменных окружения на платформе хостинга.

## Проверка работы

После деплоя проверьте:
1. Бот отвечает на команду `/start`
2. Бот обрабатывает текстовые сообщения
3. Команды `/help`, `/now`, `/mood`, `/emergency` работают
4. В логах нет критических ошибок

## Обновление бота

При обновлении кода:
- **Railway/Heroku**: Просто сделайте `git push`, деплой произойдёт автоматически
- **VPS**: Остановите сервис, обновите код, запустите снова:
  ```bash
  sudo systemctl stop telegram-bot
  git pull
  sudo systemctl start telegram-bot
  ```
