# ValutaTrade Hub

Финальный учебный проект: консольный симулятор покупки и продажи валют. Все деньги виртуальные; команда `deposit` добавляет USD на локальный счёт и не обращается к платёжным сервисам.

## Требования и запуск

Нужны Python 3.12+ и [uv](https://docs.astral.sh/uv/). В каталоге проекта выполните:

```bash
uv sync
uv run python main.py
```

Без аргументов открывается интерактивная сессия. Так регистрация, вход и следующие сделки выполняются в одном процессе. `uv run python main.py --help` показывает команды; отдельные команды также можно запускать с аргументами, но сессия входа между такими запусками не сохраняется.

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
| `show-rates [--currency CODE] [--top N] [--base CODE]` | Показать сохранённые курсы |
| `help`, `exit` | Справка и выход |

## Источники курсов

Криптовалюты обновляются через [CoinGecko Simple Price](https://docs.coingecko.com/reference/simple-price) без ключа. Для EUR, GBP и RUB нужен ключ [ExchangeRate-API](https://www.exchangerate-api.com/docs/standard-requests):

```bash
export EXCHANGERATE_API_KEY='ваш-ключ'
uv run python main.py
```

API отдаёт количество валюты за 1 USD; приложение инвертирует это значение и хранит USD за 1 единицу валюты. Ключ не записывается в репозиторий. Если один источник недоступен, обновление другого сохраняется и выводится предупреждение. Обновление также можно запустить по расписанию через `valutatrade_hub.parser_service.scheduler.run_forever()`.

Курсы записываются в `data/rates.json`, история — в `data/exchange_rates.json`. По умолчанию срок действия курса 300 секунд, его можно изменить переменной `VALUTATRADE_RATE_TTL`. Если курс отсутствует или устарел, `buy`, `sell`, `get-rate` и оценка портфеля сообщают, что нужен `update-rates`. `show-rates` отображает сохранённый снимок даже после истечения срока.

## Данные и безопасность

При первом запуске создаются `data/users.json`, `data/portfolios.json`, `data/rates.json` и `data/exchange_rates.json`; рабочие данные исключены из Git. Пароли сохраняются как SHA-256 от случайной соли и пароля; пароль в JSON не попадает. Каждая запись JSON заменяется атомарно через временный файл. Приложение рассчитано на один локальный процесс, конкурентная запись нескольких процессов не поддерживается. Сведения о сделках и ошибках пишутся в ротируемый `data/app.log`. Для отдельных тестовых данных задайте `VALUTATRADE_DATA_DIR`.

## Проверка и демонстрация

```bash
uv run pytest -q
uv run ruff check .
```

[Локальная запись демонстрации](demo.cast) показывает регистрацию, вход, пополнение, покупку, продажу и просмотр портфеля на фикстурном курсе. Её можно воспроизвести командой `asciinema play demo.cast`. Публичный адрес записи не создан.
