# Анализ модулей Connect, Connect FreeSWITCH, Connect CRM и Connect Twilio

Прошёлся по моделям, контроллерам, настройкам и безопасности всех модулей. Ниже — архитектурные проблемы и узкие места, сгруппированные по степени критичности.

> **Структура**: разделы 1-5 — `connect` + `connect_freeswitch` (ядро и FreeSWITCH). Раздел 6 — `connect_crm`. Раздел 7 — `connect_twilio`.

---

## 1. КРИТИЧНЫЕ проблемы безопасности

### 1.1 Webhook-эндпоинты FreeSWITCH без аутентификации

Все вебхуки (`/freeswitch/webhook/cdr`, `/freeswitch/webhook/parking`, `/freeswitch/webhook/recording`, `/freeswitch/xml`) объявлены `auth='public', csrf=False` и **не проверяют** источник запроса:

- `connect_freeswitch/controllers/freeswitch_cdr.py:17-21`
- `connect_freeswitch/controllers/freeswitch_parking.py:24-27`
- `connect_freeswitch/controllers/freeswitch_recording.py:19-22`
- `connect_freeswitch/controllers/freeswitch_xml.py:31`

Любой, кто достанет URL Odoo, может:
- инжектить фиктивные CDR (`on_freeswitch_cdr`) — создавать фальшивые `connect.call` от имени любого пользователя, подставляя `caller_pbx_user_id`;
- загружать произвольные файлы как «записи» (PUT на `/freeswitch/webhook/recording/<filename>` — нет проверки размера, типа, UUID);
- запрашивать XML-директорию — **получать `auth_password` всех SIP-эндпоинтов и `webrtc_password` пользователей в открытом виде** (`freeswitch_xml.py:274-282`).

**Что нужно**: shared-secret/HMAC в заголовке, или как минимум IP-whitelist (контейнер FS известен и изолирован сетью).

### 1.2 XML-парсинг CDR без защиты от XXE / billion-laughs

`freeswitch_cdr.py:67-69` парсит входной XML обычным `ET.fromstring`. Входные данные не доверенные (см. 1.1). Надо `defusedxml`.

### 1.3 Пароли и секреты в открытом виде

- `connect.settings.openai_api_key` хранится plain Char с `groups="base.group_erp_manager"`, но утечка идёт через `display_openai_api_key` (маскируется «звёздочками», но до записи в БД оригинал лежит в vals и логах `write`).
- `freeswitch_xmlrpc_password`, `freeswitch_api_*` — обычные `Char`, **без `groups=`** (`connect_freeswitch/models/settings.py:83-86`). Любой `connect.group_user` через `get_param` получит пароль.
- XML-RPC URL собирается как `http://user:pass@host:port/RPC2` (`settings.py:109`) — пароль идёт plain-текстом поверх HTTP, без HTTPS и без опции ssl.

### 1.4 Инъекция в FreeSWITCH originate

`connect_freeswitch/models/call.py:149-151, 209-210`: `origination_caller_id_name` формируется через `display_name.replace("'", "")`. Экранирование наивное — запятая, `}`, `[]` ломают парсинг FS dialplan variables, и `partner.display_name` — поле, которое может задать любой пользователь. Потенциал для манипуляции дайлпланом (вставка своих переменных).

---

## 2. Узкие места производительности

### 2.1 `connect.settings` как regular Model + отсутствие кэша

`connect.settings` — обычная `models.Model`, не `TransientModel` и не `ir.config_parameter`. `get_param()` (`settings.py:206-213`) делает **`search([])` без `limit=1`** при каждом вызове. Поскольку `get_param` вызывается:

- в `_get_recording_widget` / `_get_voicemail_widget` (внутри цикла по записям),
- в `_get_instance_data` (4 вызова `ir.config_parameter.get_param`),
- в `freeswitch_xml.py` (6-7 раз за один XML-запрос FS — для каждого юзера),
- в `debug()` (проверяется `debug_mode` на каждую запись лога),

— получается **десятки SQL-запросов на один HTTP/FS-запрос**. Нет `@api.ormcache` / `@tools.ormcache`.

### 2.2 `env.registry.clear_cache()` / `clear_caches()` на каждый write

Вызывается в:
- `connect.user.create/write/unlink` (`user.py:71-87`),
- `connect.settings.create/write` (`settings.py:224-252`),
- `res.partner.create/write/unlink` (`res_partner.py:82-105`).

**Partner** — это самая часто изменяемая модель в Odoo. Каждый `write` партнёра сбрасывает **глобальный кеш реестра** всех моделей. На production с несколькими воркерами это killer performance regression — профиль простой CRM сразу проседает.

Непонятно, зачем это вообще нужно: `res.partner` fields через `connect` добавляет только Many2one/One2many — они не требуют сброса реестра.

### 2.3 `connect.channel` с `mail.thread` и 15 `tracking=True` полей

`channel.py:16-39`: практически все поля с `tracking=True`. На каждый update канала (а их несколько на звонок: create → ringing → answered → completed) пишется ~15 `mail.tracking.value`. При нагрузке 100 звонков/мин это сотни тысяч tracking-записей в день в таблице, которая и так тяжёлая.

`_rec_name = 'id'` + `mail.thread` — зачем trackать технический объект?

### 2.4 `_get_recording_data` — O(n²) фильтрация в Python

`call.py:78-92`: один `search` на список ID, потом `recordings.filtered(lambda)` в Python для **каждой** записи. Для 80-записного списка звонков — 6400 итераций. Надо через `dict` по `call.id`.

### 2.5 `_route_internal` — полный скан `connect.exten`

`freeswitch_xml.py:378-385`: если точное совпадение `number == destination` не найдено, делается `Exten.search([])` (все экстеншены) и циклом `re.match` в Python. При 500+ экстеншенах каждый внутренний звонок — full table scan + N python-regex. Решение: хранить скомпилированный regex-флаг или использовать PostgreSQL `~` оператор.

### 2.6 `get_widget_calls` N+1

`call.py:352-363`: цикл `for call in calls: call.read([...])[0]` — это N запросов вместо одного `search_read`. При широком окне виджета (50 звонков) — 50 SELECTов.

### 2.7 `_get_connect_calls_count` / `_messages_count` не batch

`res_partner.py:163-184`: `search_count` на каждом партнёре в цикле. Kanban/list view партнёров сразу даёт по 2 SELECT на каждую отрисованную карточку.

### 2.8 `_reference_models` при каждой загрузке формы

`message.py:75-76`: возвращает **все** `ir.model` — это сотни моделей; используется в `fields.Reference(selection='_reference_models')`. Надо ограничить моделями-моделью.

### 2.9 Синхронный HTTP к лицензионному серверу внутри write()

`license.py:100-111`: `write` лицензии триггерит `update_license_status()` — 30-секундный таймаут на `requests.post`. Если клиент в форме переключил галочку «Subscribe to updates», сохранение формы блокируется на сетевой вызов. Должно идти через cron или `with_delay`.

### 2.10 `connect.debug` — пишет в БД при каждом событии

`settings.py:36-42`: когда включён `debug_mode`, каждый `debug()` делает `create()`. При обработке одного CDR — 10-20 таких вызовов. На живом трафике DB быстро пухнет, даже если есть daily cleanup.

---

## 3. Архитектурные проблемы

### 3.1 Транзакционный кошмар в `on_freeswitch_cdr`

`connect_freeswitch/models/call.py:275-321`: обработчик вебхука HTTP делает **три `env.cr.commit()` вручную**, оборачивает всё в `pg_advisory_lock` сессионного уровня. Комментарии честно объясняют почему так сделано — но это знак, что архитектура обмена между A-leg и B-leg через вебхуки **неустойчива**.

Проблемы:
- Если исключение до `commit` в try — advisory_lock отпустится в finally, но частичные записи уже закоммичены первым явным `commit()`.
- Невозможно корректно обернуть в Odoo retry-логику (`@api.model` с retry на serialization failure).
- Ломает принцип «одна HTTP-транзакция — один commit» Odoo.

**Решение**: вынести обработку CDR в очередь (`queue_job`) — вебхук только ставит задачу, воркер обрабатывает последовательно без race condition A/B-leg.

### 3.2 Двойная реализация `get_webrtc_config`

`connect_freeswitch/models/settings.py:208-249` и `connect_freeswitch/controllers/webrtc.py:13-44` — **две почти идентичные копии** логики. Версия в контроллере проще (нет ICE servers, нет displayMode). Легко разойдутся.

### 3.3 `connect.settings` vs `ir.config_parameter` — две системы настроек одновременно

`_get_instance_data` читает `connect.api_url`, `connect.instance_uid`, `web.base.url`, `connect.call_duration_limit` из `ir.config_parameter`, а всё остальное — из `connect.settings`. Граница произвольна, поддерживать сложно. `instance_uid` дублируется ещё и в `oduist.license`.

### 3.4 Permissions/sudo-культура

Почти везде `.sudo()` по умолчанию — в вычисляемых полях (`_get_connect_calls_count`), при чтении настроек в виджетах, при поиске партнёров (`get_partner_by_number`). Это обходит `record_rules` и лишает команду возможности использовать multi-company safe-by-default.

`process_call_event` делает `self = self.sudo()` в самом начале — то есть вся логика построения звонка идёт superuser-ом независимо от того, кто инициировал.

### 3.5 `register_call_post_message` с `SUPERUSER_ID`

`call.py:286-290`: используется `with_user(SUPERUSER_ID).message_post` — сообщение ставится как будто от админа. Правильнее — от `user_connect_webhook` (уже есть в data).

### 3.6 Жёсткая связь `connect.message` с `_reference_models`

`_compute_ref` ссылается на произвольную модель. Если модель удалена (миграции), ORM bails с generic Exception, которое глотается (`message.py:83-85`). Invariant `res_model` должен валидироваться на save.

### 3.7 `Exten.create` «переиспользует» существующий номер

`connect/models/exten.py:57-66`: если `number` совпадает и `dst` пуст — `write` поверх и `return exten`. Это **меняет семантику `create`** — клиентский код ожидает новый ID, получает existing. Нарушает ODM-контракт. Классический источник багов.

### 3.8 Версионные ветвления разлиты по коду

`release.version_info[0] >= 17 / 15 / 19` встречается в 15+ местах в обоих модулях (call.py, channel.py, recording.py, user.py, settings.py, res_partner.py, res_users.py, message.py, fs_parking_slot.py, gateway.py). Нет единой утилиты/миксина. Читать/поддерживать тяжело. Минимум — выделить в `utils.py` константы типа `ODOO_V17_PLUS`.

### 3.9 `_reload_sofia_profile()` после каждого write gateway

`gateway.py:71-76`: **любой** write (даже чекбокса `active`) перезагружает sofia-профиль → **рвёт все активные звонки через этот профиль**. Нужен debounce или явная кнопка «Apply».

### 3.10 Отсутствие кэша FreeSWITCH XML-ответов

Каждая SIP-регистрация эндпоинта (а они происходят каждые `expire_seconds` = по умолчанию 3600с, а часто 60-300с) → FS дергает `/freeswitch/xml` → Odoo собирает полный ответ из БД с 5-10 `search`/`get_param`. Диалпланы тоже не кешируются. При 100 эндпоинтах это постоянный фоновый трафик в Odoo.

---

## 4. Мелкие проблемы / качество кода

- `call.py:130`: пустой override `write(vals)` — просто `return super().write(vals)`, наследие от удалённой логики. Удалить.
- `call.py:283-284`: `logger.exception('...', e)` — exception message попадёт ещё раз (logger.exception уже логирует traceback). Так же в нескольких других местах.
- `recording.py:170-182`: **`self.env.cr.commit()` внутри `create()` ORM-метода** — опасная практика, может привести к частичной commitnuтой транзакции.
- `res_users.py:31-38`: `while True: search(...)` для генерации PIN — не потокобезопасно, и `uuid.uuid4().hex` выше строки — dead code (перезаписывается).
- `main.py:42`: `_serve_media` полностью грузит файл в память (`response.content`), не стримит. Большие записи → OOM.
- `freeswitch_xml.py:360-369`: `valet parking` слоты матчатся до exact `exten` матча — не указан приоритет, порядок условий хрупкий.
- `settings.py:232-252`: `write()` не возвращает `res` в ветках после `clear_cache` — возвращает `None` вместо `True`. Ломает ORM-контракт.
- `channel.py:57-58`: `get_user_by_uri` ищет пользователя по URI — вызывается внутри `_get_channel_numbers`, compute-функции. Compute работает в sudo, но результат хранится → при миграции пользователя число устаревает.
- `message.py:14`: глобальный мутирующий side-effect `mail.safe_attrs = mail.safe_attrs | frozenset(['controls'])` при импорте модуля — меняет глобальное состояние Odoo.
- `fs_parking_slot.py:380`: `re.escape` не применяется к `number` в некоторых генерациях dialplan — зависит от пути.

---

## 5. Сводная таблица «что чинить в первую очередь»

| Приоритет | Проблема | Почему |
|---|---|---|
| P0 | HMAC/shared-secret на FS-вебхуках | Утечка SIP/WebRTC паролей через `/freeswitch/xml` |
| P0 | `defusedxml` для CDR | XXE из публичного эндпоинта |
| P0 | `env.registry.clear_cache()` в `res.partner` write | Глобальная регрессия perf |
| P0 | Ручные `cr.commit()` в `on_freeswitch_cdr` / `recording.create` | Риск частично закомиченных транзакций |
| P1 | `ormcache` для `connect.settings.get_param` | Линейная деградация под нагрузкой |
| P1 | Убрать `tracking=True` с технических полей `connect.channel` | Рост `mail.tracking.value` |
| P1 | `groups=` на пароли FS XML-RPC | Эскалация прав |
| P1 | CDR через queue_job, не синхронно | Надёжность обработки race A/B-leg |
| P2 | Кэш XML-ответов для FS (директория, диалплан) | Базовый throughput |
| P2 | Дедупликация `get_webrtc_config` между settings.py и webrtc.py | Drift-багов станет меньше |
| P2 | Вынести version-switch в utils/mixin | Читаемость |
| P3 | `_get_recording_data` O(n²) → dict | Широкие списки звонков |
| P3 | `_reload_sofia_profile` — debounce или ручной apply | Срыв активных звонков при edit gateway |

---

# Анализ модуля Connect CRM

Прошёлся по `connect_crm/models/*`, `security/webhook.xml`, `__manifest__.py` и `__init__.py`. Модуль небольшой (≈380 строк Python), но именно поэтому каждый его дефект сразу ложится на горячий путь обработки звонков и на CRM-нагруженную БД.

---

## 6.1 КРИТИЧНЫЕ проблемы безопасности

### 6.1.1 Webhook-группа получает полный CRUD на `crm.lead`

`connect_crm/security/webhook.xml:3-52`: роль `connect.group_webhook` получает `perm_read/create/write=1` на `crm.lead`, а `ir.rule` `crm_lead_webhook_rule` ставит `domain_force=[(1,'=',1)]` — то есть **обходит все record rules мульти-компании**.

Это важно в связке с разборами выше:
- FreeSWITCH webhooks в core — public без HMAC (см. §1.1);
- Twilio webhooks отключают сигнатуру параметром `twilio_verify_requests` (см. §7.1.9).

Если любой вебхук-эндпоинт удастся отправить без проверки подписи (или Twilio-токен скомпрометирован), владелец входа сможет через webhook user'a читать/писать **все** leads — включая чужие компании.

**Нужно**: сузить domain (например, по `company_id` текущего webhook user'a), или выдать только `perm_read`, а `perm_create/write` оставить только через контролируемый API `get_lead_by_number` / `create_record_from_message`.

### 6.1.2 Webhook group читает `mail.alias_domain`, `crm.stage`, `crm.team`

`webhook.xml:13-41` — на первый взгляд безобидно (read-only), но вебхук-пользователь при компрометации Twilio-токена превращается в источник утечки структуры CRM (списка стадий, команд, доменных алиасов).

### 6.1.3 `crm.lead.sudo()` везде + отсутствие фильтра по компании

`crm_lead.py:109` и `models/call.py:34, 51`: поиск лида/utm.source делается `.sudo().search(...)` без фильтра по компании. На multi-company-инстансе звонок, попавший на номер одной компании, может быть привязан к лиду другой компании (если там есть такой номер в контактах/source). Это утечка связки «телефон — чужая сделка».

---

## 6.2 Корректность / бизнес-логика

### 6.2.1 `_search_lead_by_number` цепляется за закрытые стадии при ошибке

`crm_lead.py:94-99`:
```python
try:
    open_stages_ids = ...search([('is_won', '=', False)]).ids
except Exception:
    open_stages_ids = ...search([]).ids
```
Если `is_won` отсутствует (модификация модели/миграция), fallback берёт **все** стадии, включая won и lost. Результат: новый входящий звонок цепляется к давно закрытому лиду. Логика «найти открытый лид» ломается тихо.

### 6.2.2 `register_crm_lead_call_summary` на `@api.constrains('summary')`

`call.py:168-181`: метод регистрируется как `constrains` по `summary`. Constrains срабатывает на **каждый** write с изменением поля, даже если summary формировался OpenAI и тут же переписывается (draft → final). В результате на каждое уточнение summary — перезапись chatter-а связанного лида и `connect_reload_view('crm.lead')`.

**Нужно**: это не инвариант (нечего валидировать), а сайд-эффект — перенести на event hook (after_save) или на явный вызов из пайплайна транскрипции.

### 6.2.3 `default_sales_person.id` из `ir.config_parameter`

`call.py:75` и далее `call.py:95`: `default_sales_person = Settings.get_param('auto_create_leads_sales_person')`. `connect.settings.get_param` в ядре возвращает значение поля — для `Many2one` это запись или False. Дальше `default_sales_person.id` — работает, если параметр возвращает recordset; но если в коде `get_param` где-то заменят на чистый `ir.config_parameter.get_param` (как уже частично сделано для `api_url`/`instance_uid` в ядре, см. §3.3), вернётся **строка с id** — и `.id` упадёт `AttributeError`. Текущая реализация хрупкая из-за смешения двух систем настроек.

### 6.2.4 Дубли условий «какую sales person выбрать»

`call.py:91-93` и `call.py:119`: логика «кого назначить» разбросана между incoming и outgoing ветками; если появится ветка transfer / conference — забудут в одной из двух веток.

### 6.2.5 `phone_normalized` не реагирует на `partner_id.phone`

`crm_lead.py:74-84`: декоратор `@api.depends(..., 'partner_id.phone', 'partner_id.mobile')` объявлен, но в теле compute значения берутся только из `rec.phone` / `rec.mobile`. При изменении телефона партнёра `phone_normalized` не обновится до следующего `write` на самом лиде.

### 6.2.6 `UNIQUE(phone)` на `utm.source`

`utm.py:10`: `Constraint('UNIQUE(phone)', ...)`. Мы не нормализуем `phone` в `utm.source` (в отличие от `crm.lead.phone_normalized`). Значит `+37312345678` и `37312345678` проходят оба — уникальность ничего не гарантирует, а поиск в `call.py:34` по `('phone', '=', call.called)` пропускает матч, если форматы разошлись.

### 6.2.7 `create_record_from_message` плодит лиды без дедупа и rate-limit

`crm_lead.py:27-38`: на каждое входящее SMS/WhatsApp от нового номера создаётся лид с `name=from_number` и `phone=from_number`. Спам-бот, шлющий SMS с разных номеров → неограниченный рост записей `crm.lead`.

---

## 6.3 Производительность

### 6.3.1 `env.registry.clear_cache()` на каждый CRUD `crm.lead`

`crm_lead.py:59, 65, 71` — `clear_cache()` в `create`, `write`, `unlink`. Та же проблема, что с `res.partner.write` в ядре (см. §2.2). Лид — массовая запись. На каждом salesperson'е, переводящем стадию или меняющем ожидаемую выручку, тратится **глобальный cache flush**. На прод-инстансе с активной командой продаж — постоянный дребезг кешей ORM.

### 6.3.2 `_get_connect_calls_count` — `search_count` на запись

`crm_lead.py:86-91`:
```python
@api.depends('connect_calls')
def _get_connect_calls_count(self):
    for rec in self:
        rec.connect_calls_count = self.env['connect.call'].search_count([('lead', '=', rec.id)])
```
Поле `store=True` + зависит от `connect_calls` (O2M). На список из 80 leads → 80 `SELECT COUNT(*)`. При открытии kanban CRM с 200 leads — 200 отдельных COUNT-запросов.

**Нужно**: `rec.connect_calls_count = len(rec.connect_calls)` — одна ORM-загрузка O2M-реляций.

### 6.3.3 `_auto_create_lead` читает 8-9 параметров через `get_param`

`call.py:67-76`: 8 подряд `Settings.get_param(...)`. По текущей реализации `get_param` в ядре (см. §2.1) — это 8 × `search([])` на `connect.settings` на каждый звонок.

### 6.3.4 `get_lead_by_number` — 3 последовательных поиска

`crm_lead.py:117-137`: до 3 независимых `_search_lead_by_number` вызова + `format_number` на каждый incoming звонок. Каждый поиск сам включает `search` по `crm.stage` и `search` по `crm.lead` с OR-ветками. Итого до 6 SQL против `crm.lead`/`crm.stage` на один звонок.

### 6.3.5 `process_call_event` всегда дергает license check

`call.py:29, 51, 170`: три `check_license` в горячем пути одного звонка. Лицензия проверяется в ядре уже в `process_call_event` базового класса — здесь добавлена ещё одна.

---

## 6.4 Архитектурные проблемы

### 6.4.1 Пересечение нормализации номеров

Модуль импортирует `strip_number`/`format_number` из `connect.models.res_partner` (ядро) и одновременно использует `res.partner._normalize_phone`. Получаются 2 разные функции нормализации. Для `crm.lead.phone_normalized` — одна; для поиска в `_search_lead_by_number` — другая форма (`+` + strip). Нужен единый `connect.utils.normalize_phone(number, country=None) -> str`.

### 6.4.2 Мутация глобального `ODUIST_MODULES`

`settings.py:3-5`: `ODUIST_MODULES.append('connect_crm')` — side-effect при импорте. Тот же паттерн в `connect_twilio/models/settings.py:13`. При double-import (reload, тесты) список растёт дубликатами.

### 6.4.3 `post_init_hook` — синхронный HTTP до окончания установки

`__init__.py:9-16`: `env['oduist.license'].update_license_status(raise_exc=False)` внутри post_init. Установка модуля блокируется на 30s таймауте license server'а (см. §2.9).

### 6.4.4 `module.write({'create_date': fields.Datetime.now()})` в post_init

`__init__.py:12-13` — правка технических полей `ir.module.module`. `create_date` — audit-поле Odoo; лучше отдельное поле в `oduist.license` для «first_installed_at».

### 6.4.5 Лид авто-создаётся `@api.constrains('summary')` во время транскрипции

`call.py:168-181` — как отмечено в §6.2.2, это не инвариант. Связывает CRM-модуль с жизненным циклом OpenAI-транскрипции.

---

## 6.5 Мелкие / качество кода

- `call.py:165`: локальная переменная `fields` затеняет `odoo.fields`.
- `call.py:46, 56`: `logger.exception('CRM process_call_event error:')` без контекста call/partner — тяжело грепать.
- `crm_lead.py:45`: контекст `connect_call_id` в `create` обрабатывается **только** если лицензия валидна, иначе call игнорируется — непредсказуемо.
- `crm_lead.py:148`: `self.sudo().lead = lead` — sudo-write в click-handler, без audit-поля.
- `crm_lead.py:19-24`: `phone_normalized`, `mobile_normalized` сохраняются (`store=True`, `index=True`), но на миграции старых данных compute не будет запущен автоматически — нужен data-migration (которого нет).
- `utm.py:3`: `from odoo.models import Constraint` — без fallback на старые Odoo. В то время как `connect_twilio/models/user.py:11-13` имеет `if release.version_info[0] >= 19:`. Несогласованность.

---

## 6.6 Сводная таблица «что чинить в первую очередь» (connect_crm)

| Приоритет | Проблема | Почему |
|---|---|---|
| P0 | ACL webhook-группы на `crm.lead` с доменом `(1,'=',1)` | Обход мульти-компании через webhook user |
| P0 | `env.registry.clear_cache()` в `crm.lead` CRUD | Массовая регрессия perf (как `res.partner` в ядре) |
| P1 | `_search_lead_by_number` fallback на все стадии | Привязка звонка к закрытым сделкам |
| P1 | `_get_connect_calls_count` `search_count` на запись | N SELECTов в kanban/list |
| P1 | `register_crm_lead_call_summary` на `@constrains` | Дублирующие chatter-посты при апдейте summary |
| P1 | 8 `get_param` в `_auto_create_lead` горячем пути | Линейная перегрузка `connect.settings` |
| P2 | Две системы нормализации телефона | Провалы матчинга номер→лид/partner |
| P2 | `UNIQUE(phone)` в `utm.source` без нормализации | Полуломаные дубликаты |
| P2 | `get_lead_by_number` 3 последовательных SQL | Лишняя нагрузка на входящий |
| P2 | `post_init_hook` с sync HTTP до license сервера | Блокировка установки |
| P3 | `create_record_from_message` без rate-limit | Спам лидов с входящих SMS |
| P3 | Side-effect `ODUIST_MODULES.append` при импорте | Дубли при reload/тестах |
| P3 | `phone_normalized` depends на `partner_id.phone`, а compute не использует | Staleness при апдейте партнёра |

---

# Анализ модуля Connect Twilio

Прошёлся по всем `connect_twilio/models/*`, `controllers/twilio_webhooks.py`, `wizard/whatsapp_composer.py`, `security/access_rules.xml`, `data/ir_cron.xml`. Модуль большой (~5k строк), с тремя видами I/O (Twilio REST, Twilio webhooks, sync HTTP прямо из write), и это само по себе источник большинства проблем ниже.

---

## 7.1 КРИТИЧНЫЕ проблемы безопасности

### 7.1.1 RCE by design: `connect.twiml.render_python` исполняет `exec()`

`connect_twilio/models/twiml.py:216-237`:
```python
def render_python(self, request={}, params={}):
    import twilio
    exec(self.twipy, {}, {
        'env': self.env, 'self': self, ...
    })
```
Любой пользователь из `connect.group_admin` (право `write` на `connect.twiml`) может записать произвольный Python в поле `twipy` и вызвать его через `/twilio/webhook/twiml/<id>`. Даже если signature-verify включён, достаточно скомпрометированного Twilio auth_token — и сразу `os.system(...)` / exfiltration `env['res.users'].search([]).mapped('login')`.

**Нужно**: либо убрать `code_type='twipy'` целиком, либо перевести на `safe_eval`.

### 7.1.2 Незащищённый Jinja2 в `render_twiml`

`twiml.py:209-214`:
```python
environment = jinja2.Environment()
template = environment.from_string(self.twiml)
request.update(params)
res = template.render(**request)
```
Чистый `jinja2.Environment` без sandbox. В Jinja можно дотянуться до builtins через `{{ ().__class__.__mro__[1].__subclasses__() }}`. А `request` заливается данными из входящего вебхука — атакующий управляет значениями, подставляемыми в шаблон. SSTI/RCE.

**Нужно**: `jinja2.sandbox.SandboxedEnvironment` + whitelist, либо `mail.render_mixin`.

### 7.1.3 Generic `call_action` webhook с динамической моделью

`controllers/twilio_webhooks.py:74-80`:
```python
@route('/twilio/webhook/<string:model_name>/call_action/<int:record_id>', ...)
def call_action_edit_webhook(self, model_name, record_id, **kw):
    model = request.env[model_name].with_user(request.env.ref("connect.user_connect_webhook"))
    res = model.on_call_action(record_id, kw)
```
`model_name` — параметр из URL. Любая модель с методом `on_call_action` доступна через вебхук. Избыточная поверхность атаки.

**Нужно**: allowlist — `model_name in {'connect.user', 'connect.callflow'}`.

### 7.1.4 Stored XSS через `message.receive` → chatter `Markup`

`models/message.py:219-238`:
```python
body = Markup(
    "<div class='d-flex flex-row px-1'>"
    "<span class='px-1'>{}</span></div>".format(values.get('body'))
)
```
`values.get('body')` приходит напрямую из входящего Twilio SMS/WhatsApp. `Markup(...)` **явно помечает строку как безопасную** — Odoo не будет эскейпить её при рендере chatter-а. Любой атакующий, отправивший SMS на корпоративный номер Twilio, инжектит `<script>` в чаттер связанного lead/partner/employee.

**Нужно**: `Markup.escape(values.get('body'))` перед format.

### 7.1.5 `render_python` + `jinja2` + webhook = трёхэтажный сюрприз

Связка §7.1.1 + §7.1.2 + §7.1.3: даже если каждый по отдельности «закрыт», одного скомпрометированного auth_token достаточно, чтобы поднять exec() на Odoo-сервере.

### 7.1.6 `parseString` из stdlib на пользовательский XML

`twiml.py:18`: `pretty_xml = dom.parseString(str(content))`. `xml.dom.minidom` уязвим к billion-laughs / XXE при наличии DOCTYPE. Та же нота, что для FreeSWITCH CDR в ядре (§1.2): использовать `defusedxml`.

### 7.1.7 Hardcoded dev host в `connect.call.transfer`

`models/call.py:296-298`:
```python
def transfer_user():
    ...
    sip = Sip('sip:user@devmax17.sip.twilio.com')
    ...
    client.calls(user_channel.sid).update(twiml=response)
```
Production-модуль в мастер-ветке, внутри кнопки «Transfer», содержит жёстко прошитый dev-домен. Любой, кто кликнет transfer, перенаправит активный разговор на личный поддомен разработчика.

### 7.1.8 `http → https` наивная замена при сверке Twilio signature

`controllers/twilio_webhooks.py:17`:
```python
url = request.httprequest.url.replace('http:', 'https:')
```
`str.replace` заменит также `http:` в query/fragment/PATH. Корректно: `werkzeug.urls.url_parse(url)._replace(scheme='https')`.

### 7.1.9 `twilio_verify_requests` выключается чекбоксом

`settings.py:78-80`: флаг `twilio_verify_requests=Boolean(default=True)`. Снятие галочки в UI делает все 12 вебхук-эндпоинтов публичными: можно создавать `connect.call`/`connect.channel`, писать chatter на любую запись, рендерить `TwiML` (включая `exec`).

**Нужно**: UI-warning при снятии; лучше — IP-allowlist Twilio параллельно с подписью.

### 7.1.10 `message_status_webhook` → chatter-post на произвольный res_id

`models/whatsapp_sender.py:348-387`: `update_message_status` ищет `connect.message` по `MessageSid`, читает из неё `res_model`/`res_id` и постит chatter. Зная `MessageSid`, можно инжектить `error_message` в записи `connect.message.error_message`, который потом читается в UI.

### 7.1.11 `account_sid` + `auth_token` читаются путями, обходящими `groups=`

`settings.py:61-63`: `auth_token` с `groups=` защитой, но `get_client()` делает `.sudo().get_param("auth_token")`. Любой метод модели потенциально отдаёт токен. `twilio_webhooks.py:16` делает `sudo().get_param('auth_token')` напрямую в публичном контроллере.

---

## 7.2 Узкие места производительности

### 7.2.1 `_compute_direction` — два full-scan search на каждое сообщение

`models/message.py:22-40`: два `search([])` внутри цикла `for rec in self`. На list/kanban из 80 сообщений — 160 full-scan SELECT'ов. Depends не включает `connect.number.phone_number` / `connect.whatsapp_sender.number` — поле останется stale.

### 7.2.2 Синхронный HTTP к Twilio внутри каждого ORM `write/create/unlink`

Модели и точки вызова:
- `connect.domain` — `create/write/unlink` (`domain.py:361-443`)
- `connect.number` — `write` (`number.py:106-120`)
- `connect.twiml` — `create/write/unlink` (`twiml.py:85-161`)
- `connect.user` — `create/write/unlink` (`user.py:281-341`)
- `connect.outgoing_callerid` — `unlink` (`outgoing_callerid.py:139-155`)
- `connect.message_content_template` — `create/unlink/write`

Галочка `active=True` на 50 users → 50 × HTTP к Twilio. Массовое удаление домена — блокировка транзакции на минуты. В проде регулярно ловятся `RequestTimeout` посреди транзакции → частичные коммиты.

**Нужно**: `queue_job`/отложенная задача.

### 7.2.3 `connect.domain.route_call` — full scan экстеншенов на каждый входящий

`domain.py:530-539`: при отсутствии точного совпадения — `search([])` по `connect.exten` + N `re.match` в Python. Та же проблема, что в FreeSWITCH `_route_internal` (§2.5). Twilio ждёт TwiML не дольше ~15 сек.

### 7.2.4 `compute` методы читают настройки 3-4 раза за одну перерисовку

- `number._get_twilio_urls` (`number.py:43-78`) — 4 `get_param`.
- `twiml._get_twilio_urls` (`twiml.py:169-179`) — 3 `get_param`.
- `whatsapp_sender._get_twilio_urls` — 2 `get_param`.
- `callflow._get_gather_action_url` — 2 `get_param`.

Каждый `get_param` из ядра = `search([])` на `connect.settings` (§2.1). Открыть view с 50 записями → сотни лишних SELECT'ов.

### 7.2.5 `fetch_call_prices_batch` — последовательные HTTP без параллелизма

`call.py:202-249`: cron раз в 5 минут, на базе в 1000 звонков/сутки — 1000 HTTP на cron-тик, сериализовано. Таймаута нет.

### 7.2.6 `sync` методы — каскад синхронных HTTP

- `whatsapp_sender.sync()`: GET senders + POST per sender. 10 senders = 11 HTTP.
- `message_content_template.sync()`: GET контента + **для каждого** GET `approval_fetch` (timeout=15). 100 шаблонов × 15 = до 25 минут sync'а.
- `outgoing_callerid.sync_outgoing_callerid`: O(N) API + 2 search на номер.
- `domain.sync`: пересоздание домена → HTTP per user.

### 7.2.7 `settings.write` — `clear_cache()` поверх ядерного clear_cache

`settings.py:325-328`. Ядро в `connect.settings.write` уже делает то же (§2.2). На каждом апдейте настроек — **двойной** глобальный flush.

### 7.2.8 `Message._compute_direction` зависит от `status` — избыточный пересчёт

Депенденс срабатывает на каждый апдейт статуса вебхука (delivered → read → …). Каждый раз — 2 full-scan.

### 7.2.9 `domain.create` + `_create_user_credentials_for_domain` в транзакции

`domain.py:346-366, 116-156`. Если 50-й пользователь упадёт — Twilio-side уже создано 49, а в Odoo откатится. Полная рассинхронизация.

### 7.2.10 `user.generate_twilio_password` использует `random.*`

`user.py:266-279`: `random.choice`, `random.choices`, `random.shuffle` — не криптографически стойкие. Используй `secrets`. Ядро (§4) имеет ту же проблему в PIN-генерации.

---

## 7.3 Архитектурные проблемы

### 7.3.1 Проверка сигнатуры — в каждом route, вручную

`twilio_webhooks.py`: 12 роутов, каждый начинается с `if not self.check_signature(kw): return ...`. Забыли в новом роуте — открыли лазейку. Нужен декоратор `@twilio_signed_route`.

### 7.3.2 `message.receive` — 200-строчный god-method

`message.py:42-285`: в одном методе — проверка AccountSid, парсинг media, поиск parent, создание message, fallback-создание записи в целевой модели, запись в chatter, и ветка «статус обновить». Разбить на `_parse_inbound`, `_resolve_target`, `_create_or_update_record`, `_post_to_chatter`.

### 7.3.3 Две сущности для пароля SIP: `password` + `sid`

`user.py:61-62`: `password` хранится как `'***'` (маска) после первой записи. При миграции домена код **создаёт новый пароль** и перезаписывает sid без уведомления пользователя. IP-телефон со старым паролем перестанет работать.

### 7.3.4 `Number.write` триггерит full-sync даже при `active`-toggle

`number.py:106-120`: без фильтра по полям. Любой write запустит `update_twilio_number`. Как с `gateway` в FreeSWITCH (§3.9).

### 7.3.5 `TwiML.create` — сначала ORM, потом Twilio, без rollback

`twiml.py:85-93`: если `create_twilio_app` падает — запись в Odoo уже сохранена, а Twilio-сущности нет. Тот же паттерн в `domain.create`, `user.create`.

### 7.3.6 `Settings.get_client` — новый Twilio Client на каждый вызов

`settings.py:87-110`: каждый `get_client()` создаёт новый `twilio.rest.Client`, читая 4-5 `get_param`. В sync-цикле клиент создаётся повторно. Нужен cache по транзакции.

### 7.3.7 `number.write` сбрасывает destination через `None`

`number.py:107-110`: `vals.update({field: None})` — `None` не валидное значение для `Many2one` в Odoo (принимает `False`). Undefined behaviour.

### 7.3.8 `_sql_constrains` (typo) в `connect.domain`

`domain.py:38-40`:
```python
_sql_constrains = [
    ("uniq_subdomain", "UNIQUE(subdomain)", "This subdomain is already used!")
]
```
Должно быть `_sql_constraints`. Odoo игнорирует атрибут — constraint не создан в БД. Дубликаты subdomain возможны.

### 7.3.9 `recording.prepare_data` — `data[field].utcnow()` вместо значения

`recording.py:30-31`:
```python
if field in ['start_time', 'date_created', 'date_updated']:
    data[field] = data[field].utcnow()
```
`datetime.utcnow()` возвращает **текущее** UTC-время, независимо от `data[field]`. Вместо оригинального `start_time` сохраняется момент обработки вебхука. «start_time» ≈ «end_time».

### 7.3.10 `message.receive` — chatter автор = `SUPERUSER_ID`

`message.py:214-216`: тот же анти-паттерн, что в ядре (§3.5). Надо `user_connect_webhook`.

### 7.3.11 `whatsapp_composer.default_get` — silent try/except

`wizard/whatsapp_composer.py:35-42`: если `_phone_format` упал — пустое поле `phone` без объяснения.

### 7.3.12 24-часовое окно WhatsApp захардкожено

`whatsapp_sender.py:253-268`: `raise ValidationError` при >24ч. Не настраивается; composer проверяет window до выбора `content_template`.

### 7.3.13 `transfer()` в `connect.call` — dev stub

`call.py:251-303`: кроме hardcoded dev URL (§7.1.7), нет сохранения conf_id в БД, нет audit. Если `transfer_other` успешен, а `transfer_user` провалился — звонок «завис» в конференции без участников.

### 7.3.14 `_get_dialplan` делает render в compute поле

`exten.py:17-24`: при каждой перерисовке формы исполняется Jinja/TwiML/`exec` шаблона. Открыть list extensions → все `twipy` коды исполняются на сервере.

### 7.3.15 Кросс-импорт `settings.strip_number` / `format_connect_response`

`settings.py:49-55`, используется в `user.py`, `domain.py`, `number.py`, `outgoing_callerid.py`. Дублируется с ядром (`connect/models/res_partner.strip_number`). Две разные функции с одним именем.

---

## 7.4 Мелкие проблемы / качество кода

- `call.py:252`: import внутри метода, хотя `VoiceResponse` уже импортирован на top level.
- `twilio_webhooks.py`: все роуты возвращают `f'{res}'` — TwiML-XML как `text/html`. Правильный Content-Type — `text/xml`.
- `domain.py:201-211`: warning при inconsistent mappings, но код идёт дальше и использует `register_mappings[0]`.
- `message.py:274`: `message.update({'status': ...})` — работает, потому что `.update` на recordset = `write`, но читается как ошибка.
- `user.py:32-37`, `whatsapp_sender.py:56-63`: `if release.version_info[0] >= 19:` разветвление Constraint vs `_sql_constraints` рассеяно по моделям. Нужна утилита.
- `whatsapp_sender.py:88`: `json.dumps(data.get('offline_reasons'))` — сохранение JSON-as-string в `Text` вместо отдельной структуры.
- `twilio_webhooks.py:27`: `return '<Response><Say>Invalid Twilio request!</Say></Response>'` — говорит attacker'у, что сигнатура не прошла. Лучше 401 с нейтральным телом.
- `message_content_template.py:412-414`: повторный HTTP GET внутри `sync` для каждой записи.

---

## 7.5 Сводная таблица «что чинить в первую очередь» (connect_twilio)

| Приоритет | Проблема | Почему |
|---|---|---|
| P0 | `render_python` с `exec()` | RCE при компрометации auth_token или admin-аккаунта |
| P0 | Нессандбоксный `jinja2.Environment` в `render_twiml` | SSTI/инфoleak через webhook params |
| P0 | Stored XSS в `message.receive` через `Markup.format` | Скрипт в chatter любой связанной записи из inbound SMS |
| P0 | Generic webhook `call_action/<model>/<id>` | Неограниченный RPC-surface |
| P0 | Hardcoded dev URL `devmax17.sip.twilio.com` в `call.transfer` | Перехват трансферов |
| P0 | Защита webhook'ов тогглится чекбоксом `twilio_verify_requests` | Всё выше умножается на риск отключённой подписи |
| P1 | `recording.prepare_data` ставит `utcnow()` вместо оригинального времени | `start_time` = время обработки, аналитика сломана |
| P1 | `_compute_direction` делает 2 full-scan per record | Регрессия на list/kanban сообщений |
| P1 | Sync HTTP в `write`/`create`/`unlink` 7+ моделей | Блокировки транзакций, timeouts, частичные коммиты |
| P1 | Full-scan `connect.exten` в `domain.route_call` | Лаг входящего звонка при многих extensions |
| P1 | `_sql_constrains` typo в `domain` — UNIQUE не создан | Дубликаты subdomain возможны |
| P1 | RNG для SIP-паролей через `random.*` | Не криптографически стойкий |
| P2 | Signature-check в каждом роуте вручную | Риск забыть при добавлении нового |
| P2 | `render_python` в `_get_dialplan` compute | Код `twipy` исполняется при открытии form/list |
| P2 | `fetch_call_prices_batch` — N синхронных HTTP | Долгие cron-тики |
| P2 | `message_content_template.sync` — N × 15s | Sync-окно до 25 минут |
| P2 | `http→https` наивный replace в signature validator | Failed validation за reverse-proxy |
| P2 | `settings.write` двойной `clear_cache` | Усиленный cache-thrash из ядра |
| P3 | `update_message_status` позволяет манипулировать `error_message` | Косвенная инъекция в UI |
| P3 | `message.receive` 200-строчный god-method | Хрупкость, сложность тестирования |
| P3 | Новый Twilio `Client` на каждый вызов | Лишние инициализации в sync-циклах |
| P3 | Duplicate `strip_number` / `format_connect_response` с ядром | Drift в нормализации |
