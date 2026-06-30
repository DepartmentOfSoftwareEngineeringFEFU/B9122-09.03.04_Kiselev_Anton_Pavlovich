# B9122-09.03.04_Kiselev_Anton_Pavlovich

Marine DSS — программная система поддержки принятия решений при обеспечении безопасности движения морских судов на основе ретроспективных АИС-данных.

Система позволяет загружать архивные АИС-данные, очищать их, формировать траектории судов, строить тепловую карту плотности движения, выделять зоны навигационного риска, оценивать маршрут и формировать отчёт.

---

## 1. Что нужно установить

Перед запуском проекта нужно установить:

1. **Docker Desktop**
   Нужен для запуска базы данных PostgreSQL/PostGIS и Adminer.

2. **Python 3.10+**
   Нужен для запуска backend на FastAPI.

3. **Node.js**
   Нужен для запуска frontend.

4. **Git**
   Нужен для скачивания проекта с GitHub.

---

## 2. Как скачать проект

Открыть Git Bash или терминал и выполнить:

```bash
git clone https://github.com/DepartmentOfSoftwareEngineeringFEFU/B9122-09.03.04_Kiselev_Anton.git
```

Перейти в папку проекта:

```bash
cd B9122-09.03.04_Kiselev_Anton
```

Если проект скачан ZIP-архивом, нужно просто распаковать архив и открыть папку проекта в терминале.

---

## 3. Структура проекта

```text
B9122-09.03.04_Kiselev_Anton/
│
├── backend/                 # Backend на FastAPI
├── frontend/                # Frontend на React + Vite
├── database/                # SQL-скрипт инициализации базы данных
├── ais_vladivostok_231k.csv # Тестовый CSV-файл с АИС-данными
├── docker-compose.yml       # Запуск PostgreSQL/PostGIS и Adminer
└── README.md
```

---

## 4. Запуск базы данных

В корне проекта выполнить:

```bash
docker compose up -d
```

Проверить, что контейнеры запущены:

```bash
docker compose ps
```

После запуска будут доступны:

```text
База данных PostgreSQL/PostGIS:
localhost:5433

Adminer:
http://localhost:8080/
```

Данные для входа в Adminer:

```text
Движок: PostgreSQL
Сервер: db
Пользователь: marine_user
Пароль: marine_password
База данных: marine_dss
```

Быстрая ссылка для входа в базу:

```text
http://localhost:8080/?pgsql=db&username=marine_user&db=marine_dss&ns=public
```

---

## 5. Запуск backend

Открыть новый терминал.

Перейти в папку backend:

```bash
cd backend
```

Создать виртуальное окружение:

```bash
python -m venv .venv
```

Активировать виртуальное окружение на Windows:

```bash
.\.venv\Scripts\activate
```

Если используется Git Bash, можно активировать так:

```bash
source .venv/Scripts/activate
```

Обновить pip:

```bash
python -m pip install --upgrade pip
```

Установить библиотеки:

```bash
python -m pip install -r requirements.txt
```

Создать таблицы пользователей и тестовые аккаунты:

```bash
python create_auth_tables.py
```

Запустить backend:

```bash
python -m uvicorn app.main:app --reload
```

После запуска backend будет доступен по адресу:

```text
http://localhost:8000
```

Проверка backend:

```text
http://localhost:8000/health
```

Проверка подключения к базе данных:

```text
http://localhost:8000/db-health
```

Swagger API:

```text
http://localhost:8000/docs
```

---

## 6. Тестовые пользователи

После выполнения команды:

```bash
python create_auth_tables.py
```

создаются два пользователя:

```text
Администратор:
login: admin
password: admin123
```

```text
Исследователь:
login: researcher
password: researcher123
```

Роль администратора используется для загрузки и обработки АИС-данных.

Роль исследователя используется для просмотра аналитических слоёв, оценки маршрута и формирования отчёта.

---

## 7. Запуск frontend

Открыть новый терминал.

Перейти в папку frontend:

```bash
cd frontend
```

Установить зависимости:

```bash
npm install
```

Запустить frontend:

```bash
npm run dev
```

После запуска открыть сайт в браузере:

```text
http://localhost:5173
```

---

## 8. Полный порядок запуска проекта

Для запуска проекта нужно открыть три терминала.

### Терминал 1 — база данных

В корне проекта:

```bash
docker compose up -d
```

### Терминал 2 — backend

```bash
cd backend
.\.venv\Scripts\activate
python -m uvicorn app.main:app --reload
```

Если проект запускается первый раз, перед запуском backend выполнить:

```bash
python create_auth_tables.py
```

### Терминал 3 — frontend

```bash
cd frontend
npm install
npm run dev
```

После этого открыть:

```text
http://localhost:5173
```

---

## 9. Как работать с системой

### Шаг 1. Войти как администратор

```text
login: admin
password: admin123
```

### Шаг 2. Загрузить CSV-файл

В интерфейсе выбрать файл:

```text
ais_vladivostok_231k.csv
```

Нажать кнопку загрузки CSV-файла.

### Шаг 3. Подготовить аналитические данные

После загрузки данных нажать кнопки:

```text
Сформировать траектории судов
Построить тепловую карту
Сформировать зоны риска
```

### Шаг 4. Выйти из администратора

Нажать кнопку выхода из системы.

### Шаг 5. Войти как исследователь

```text
login: researcher
password: researcher123
```

### Шаг 6. Открыть аналитические слои

Нажать кнопки:

```text
Показать траектории
Показать тепловую карту
Показать зоны риска
```

### Шаг 7. Оценить маршрут

В блоке задания маршрута оставить тестовый маршрут или изменить точки маршрута.

Нажать:

```text
Оценить риск маршрута
```

### Шаг 8. Сформировать отчёт

После оценки маршрута нажать:

```text
Сформировать отчёт
```

При необходимости отчёт можно экспортировать в TXT.

---

## 10. Полезные адреса

```text
Frontend:
http://localhost:5173

Backend:
http://localhost:8000

Swagger API:
http://localhost:8000/docs

Проверка backend:
http://localhost:8000/health

Проверка базы данных:
http://localhost:8000/db-health

Adminer:
http://localhost:8080/

Быстрый вход в Adminer:
http://localhost:8080/?pgsql=db&username=marine_user&db=marine_dss&ns=public
```

---

## 11. Остановка проекта

Остановить backend и frontend:

```text
Ctrl + C
```

Остановить базу данных и Adminer:

```bash
docker compose down
```

Если нужно полностью удалить базу данных и начать заново:

```bash
docker compose down -v
```

После удаления базы нужно снова запустить Docker и создать пользователей:

```bash
docker compose up -d
cd backend
.\.venv\Scripts\activate
python create_auth_tables.py
```

---

## 12. Возможные ошибки

### Backend не подключается к базе данных

Проверить, что Docker запущен:

```bash
docker compose ps
```

Проверить backend:

```text
http://localhost:8000/db-health
```

Если база не запущена, выполнить:

```bash
docker compose up -d
```

---

### Не работает вход в систему

Нужно создать таблицы пользователей:

```bash
cd backend
.\.venv\Scripts\activate
python create_auth_tables.py
```

После этого войти:

```text
admin / admin123
researcher / researcher123
```

---

### Не запускается frontend

Нужно перейти в папку frontend и установить зависимости:

```bash
cd frontend
npm install
npm run dev
```

---

### Порт уже занят

В проекте используются порты:

```text
5433 — PostgreSQL/PostGIS
8080 — Adminer
8000 — backend
5173 — frontend
```

Если один из портов занят, нужно закрыть программу, которая его использует, или изменить порт в настройках проекта.

---

## 13. Команды для обновления проекта на GitHub

После изменения файлов выполнить:

```bash
git add .
git commit -m "Update project"
git push
```

## Скриншоты

### Swagger API

<img width="1904" height="991" alt="image" src="https://github.com/user-attachments/assets/7db9aa22-881a-482c-b2e3-01c127876a13" />

### База данных Adminer

<img width="1919" height="994" alt="image" src="https://github.com/user-attachments/assets/12d82e0e-166c-4046-993e-dfd44f5d51cb" />

### Интерфейс системы

1. Авторизация

<img width="1919" height="992" alt="image" src="https://github.com/user-attachments/assets/63f7d916-0d1f-4209-add5-d84e9b043639" />

2. Экран Администратора

<img width="1904" height="990" alt="image" src="https://github.com/user-attachments/assets/3efd069a-4435-4813-a221-2fdff68e3dc8" />

3. Экран Исследователя

<img width="1902" height="993" alt="image" src="https://github.com/user-attachments/assets/e5756668-8a0b-432a-b97d-ffd9716d244d" />

<img width="1919" height="992" alt="image" src="https://github.com/user-attachments/assets/06249674-4f16-47e0-8cda-2644b5439124" />

<img width="1919" height="994" alt="image" src="https://github.com/user-attachments/assets/68c2d976-974b-4c7e-ad81-7b1c44804e67" />

4. Отчётность 

<img width="1919" height="575" alt="image" src="https://github.com/user-attachments/assets/acf1a1cf-7386-44ff-aebd-2d5412e03c4e" />








