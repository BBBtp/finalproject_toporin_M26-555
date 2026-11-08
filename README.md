# ValutaTrade Hub

Финальный учебный проект: консольный симулятор покупки и продажи валют. Все деньги виртуальные; команда `deposit` добавляет USD на локальный счёт и не обращается к платёжным сервисам.

## Требования и запуск

Нужны Python 3.12+ и [uv](https://docs.astral.sh/uv/). В каталоге проекта выполните:

```bash
python3 -m uv sync
python3 -m uv run valutatrade
```

Без аргументов открывается интерактивная сессия. Так регистрация, вход и следующие сделки выполняются в одном процессе. `python3 -m uv run valutatrade --help` показывает команды; отдельные команды также можно запускать с аргументами, но сессия входа между такими запусками не сохраняется.

## Первый сценарий

```text
valutatrade> register --username toporin --password secret123
valutatrade> login --username toporin --password secret123
valutatrade> deposit --amount 1000
valutatrade> update-rates --source coingecko
valutatrade> get-rate --from BTC --to USD
valutatrade> buy --currency BTC --amount 0.001
valutatrade> show-portfolio --base USD
valutatrade> sell --currency BTC --amount 0.0005
valutatrade> show-rates --top 3
valutatrade> exit
```

Цена `BTC/USD` — USD за один BTC. При покупке из USD списывается `количество × цена`, при продаже такая же сумма зачисляется в USD. Сумма должна быть от `0.00000001` до `999999999999.99999999` с точностью до восьми знаков после запятой. При нехватке средств ни один кошелёк не изменяется. Можно покупать и продавать EUR, GBP, RUB, BTC, ETH, SOL; USD служит расчётной валютой.

## Команды

| Команда | Назначение |
| --- | --- |
| `register --username NAME --password PASSWORD` | Создать пользователя и портфель |
| `login --username NAME --password PASSWORD` | Войти в текущем процессе |
| `logout` | Завершить сеанс |
| `deposit --amount N` | Пополнить виртуальный USD-кошелёк |
| `show-portfolio [--base CODE]` | Показать кошельки и общую стоимость |
| `buy --currency CODE --amount N` | Купить валюту за USD |
| `sell --currency CODE --amount N` | Продать валюту за USD |
| `get-rate --from CODE --to CODE` | Показать свежий курс; кросс-курс через USD |
| `update-rates [--source coingecko\|exchangerate]` | Получить курсы от одного или обоих API |
| `show-rates [--currency CODE] [--top N] [--base CODE]` | Показать сохранённые курсы; `--top` отбирает криптовалюты |
| `help`, `exit` | Справка и выход |

## Источники курсов

Криптовалюты обновляются через [CoinGecko Simple Price](https://docs.coingecko.com/reference/simple-price) без ключа. По заданию для EUR, GBP и RUB нужно зарегистрироваться и получить ключ [ExchangeRate-API](https://www.exchangerate-api.com/docs/standard-requests). Ключ задаётся в окружении и не сохраняется в Git:

```bash
export EXCHANGERATE_API_KEY='ваш-ключ'
python3 -m uv run valutatrade
```

API отдаёт количество валюты за 1 USD; приложение инвертирует это значение и хранит USD за 1 единицу валюты. Ключ не записывается в репозиторий. Если один источник недоступен, обновление другого сохраняется и выводится предупреждение. Обновление также можно запустить по расписанию через `valutatrade_hub.parser_service.scheduler.run_forever()`.

Курсы записываются в `data/rates.json`, история — в `data/exchange_rates.json`. По умолчанию срок действия курса 300 секунд, его можно изменить переменной `VALUTATRADE_RATE_TTL`. Если курс отсутствует или устарел, `buy`, `sell` и оценка портфеля предлагают выполнить `update-rates`; `get-rate` сначала пытается обновить курс через нужный источник. `show-rates` отображает сохранённый снимок даже после истечения срока. Ответ ExchangeRate-API содержит количество EUR/GBP/RUB за 1 USD, поэтому для хранения курса «валюта → USD» оно инвертируется.

## Структура

- `valutatrade_hub/core/` — валюты, модели, исключения, операции с портфелем и курсами.
- `valutatrade_hub/infra/` — настройки из `pyproject.toml` и атомарное JSON-хранилище.
- `valutatrade_hub/parser_service/` — конфигурация, клиенты двух API, обновление, история и планировщик.
- `valutatrade_hub/cli/` — разбор команд и таблицы для пользователя.
- `data/` — четыре JSON-файла из задания; `scripts/record_demo.py` создаёт демонстрацию.

## Данные и безопасность

В репозитории лежат пустые шаблоны `data/users.json`, `data/portfolios.json`, `data/rates.json` и `data/exchange_rates.json`, как требует структура задания. **Не добавляйте в Git свои рабочие версии этих файлов.** Для личных данных задайте `VALUTATRADE_DATA_DIR` вне репозитория; приложение создаст в этом каталоге собственные JSON-файлы. Пароли сохраняются как SHA-256 от случайной соли и пароля; пароль в JSON не попадает. Каждая запись JSON заменяется атомарно через временный файл. Регистрация двух связанных записей защищена локальным журналом: после прерывания приложение восстановит прежнее согласованное состояние при следующем обращении к данным. Приложение рассчитано на один локальный процесс, конкурентная запись нескольких процессов не поддерживается. Сведения о сделках и ошибках пишутся в ротируемый `data/app.log`.

## Проверка и демонстрация

```bash
python3 -m uv run pytest -q
python3 -m uv run ruff check .
python3 -m uv build
```

[Локальная запись демонстрации](demo.cast) показывает регистрацию, вход, `update-rates`, `show-rates`, `get-rate`, покупку, продажу, портфель и ошибки. Запись использует тестовые клиенты вместо сетевых запросов и воспроизводится командой `asciinema play demo.cast`. Публичный адрес записи не создан.
