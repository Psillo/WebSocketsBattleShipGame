Настройте переменные в файле .env
Поднимается в докере, командой:
```
docker-compose --env-file .env up --build
```
Запуск приложения:
```
. ./stop_app.sh
```
А еще можно порт прописать:
```
. ./start_app.sh -app_port 8001
```
Остановка приложения:
```
. ./stop_app.sh
```
При запуске нужно остановить локальный redis (если он есть и на стандартом порте).
"http://127.0.0.1:8000/" - главная страница.
Для начала игры нужно два человека в комнате - запустите её с разных браузеров или второе окно через режим инкогнито. После чего, выберите расположение кораблей, еще раз тыкните по полю выбора, и когда второй пользователь тоже будет готов, игра начнётся.
Задание: https://docs.google.com/document/d/1Snj9SyMENTxY3jIEErc5vflpLOPdGRw8/
Игра сделана за два дня, поэтому код ужасный и нуждается в нормальном рефакторинге.