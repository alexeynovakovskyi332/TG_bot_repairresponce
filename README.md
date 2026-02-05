# TG_bot_repairresponce
В папке с ботом нужно исправить файл .env.example (удаляем .exapmle чтобы было просто .env ) потом откравыем файл и вставляем туда ключи от бота и группы:
(оно должно быть на 2х строках, между = пробелы убираем и "" тоже не нужны ) сохраняем изменения в файле/закрываем 

Для Ubuntu:

Открываем терминал в папке с ботом и прописываем команды:
Ubuntu обычно идёт с Python 3, но лучше убедиться:
sudo apt update 
sudo apt install python3 python3-venv python3-pip -y

потом проверяем версию:
python3 --version

Создаём виртуальное окружение:
python3 -m venv venv

Активируем виртуальное окружение:
source venv/bin/activate

Устанавливаем зависимости:
pip install --upgrade pip

pip install -r requirements.txt

Запуск бота:
python3 tg_bot.py

Чтобы бот работал постоянно 
На сервере Ubuntu можно использовать screen или tmux:

sudo apt install screen

screen -S mybot

python3 tg_bot.py

Для выхода из сессии Ctrl+A D (бот будет работать в фоне)

Чтобы вернуться: screen -r mybot