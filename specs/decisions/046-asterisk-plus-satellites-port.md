# Порт оставшихся asterisk_plus-сателлитов (ODU-344)

## Context

Тикет ODU-344 — «портировать остальные asterisk_plus addons». Ядро
`asterisk_plus` уже портировано в `connect_asterisk` (ADR-026). В исходном
репозитории **`oduist/pbx_addons` (ветка 19.0)** рядом с ядром лежат 11
сателлитов; из них уже есть NG-аналоги для `crm`, `helpdesk`, `phone`
(поглощён web-телефоном `connect_asterisk`). Задача этой сессии —
**план + ADR** для оставшихся; реализация — отдельными сессиями/PR.

Ключевой факт, определяющий подход: `asterisk_plus_*` сателлиты **не
портируются 1:1**. ADR-026 явно постановил (specs/decisions/026-…:135-137),
что их роль переходит к **провайдер-агностичным `connect_*`** модулям на
хуках ядра. Это подтверждается кодом: `connect_crm`/`connect_helpdesk`
зависят от `['connect', <app>]`, а не от провайдера, и линкуют бизнес-запись
к `connect.call` через выделенный M2O + `process_call_event` / `register_call`
/ `_get_ref` / `get_widget_fields`, а НЕ через общий слот `ref` +
`update_reference()` из исходников.

Скоуп, согласованный с пользователем:
- **account, project, hr, sale** → четыре новых бриджа по образцу `connect_crm`.
- **gs, yeastar** → влить в `connect_asterisk` как vendor-flavour (не отдельные модули).
- **callgroup** → полностью игнорируется (вся маршрутизация — FastAGI/`fagi_request`,
  выброшенный ADR-026; переносить нечего без ревизии ADR).
- **website** → вне скоупа (Twilio-специфичный WebRTC, отдельная история).
- **yeastar-как-вендор** — это НЕ отдельный PBX: оба ящика (Grandstream UCM,
  Yeastar) внутри — Asterisk-по-AMI; исходные модули делают `_inherit` без
  `_name` и перекрывают ровно один метод ядра.

---

## Часть 1. Четыре бизнес-бриджа (connect_account / connect_project / connect_hr / connect_sale)

Эталон — `connect_crm` (`connect_crm/models/call.py`, `__init__.py`,
`__manifest__.py`, `security/webhook.xml`, `views/*`). Каждый бридж повторяет
одну и ту же форму; ниже — общий паттерн и специфика по модулю.

### Общий паттерн (для каждого из четырёх)

Структура модуля:
```
connect_<app>/
  __init__.py            # post_init_hook как в connect_crm/__init__.py
  __manifest__.py        # version 19.0.1.0.0, depends ['connect', '<app>'], license Other proprietary
  models/__init__.py
  models/call.py         # _inherit connect.call — линк + хуки
  models/<record>.py     # _inherit target — One2many + phone_normalized + get_X_by_number
  models/settings.py     # (только где нужен auto-create) _inherit connect.settings
  security/webhook.xml    # ACL для connect.group_webhook на target-модель
  views/call_views.xml    # кнопка + notebook-страница + list-колонка
  views/<record>_views.xml# smart button + recorded-calls + phone-поля + search
  static/description/icon.png
  tests/                  # по образцу connect_crm/tests
```

`models/call.py` (`_inherit='connect.call'`) для каждого:
- выделенный M2O на target (`ondelete='set null'`, `tracking=True`) — **не** общий `ref`;
- `ref = fields.Reference(selection_add=[('<target>', '<Label>')])`;
- `_get_ref()` — маппит из M2O, иначе `super()` по записи (как `connect_crm/models/call.py:17-22`);
- `process_call_event(channel, error_data=None)` `@api.model` — `super()`, затем
  `check_license('connect_<app>', silent=True)`, затем lookup по номеру и
  проставление M2O (шаблон `connect_crm/models/call.py:24-47`);
- `register_call(channel, params)` — `super()`, license-gate, `_auto_create_*()`
  (только где есть auto-create; см. специфику);
- `create_<x>_button` / `unlink_<x>` — идемпотентная кнопка + отвязка
  (шаблон `connect_crm/models/call.py:136-161`), с контекстом `connect_call_id`;
- `get_widget_fields()` — `super()` + `fields.append('<m2o>')`;
- `@api.constrains('summary')` → `register_summary_to_rec(rec.<m2o>, rec.summary)`
  + `connect_reload_view('<target>')` (шаблон `connect_crm/models/call.py:168-181`).

`models/<record>.py` (`_inherit='<target>'`):
- `connect_calls = One2many('connect.call', '<m2o>')` + `connect_calls_count`
  **store=True, @api.depends('connect_calls')** (не unstored search_count из исходника);
- `phone_normalized` (stored, indexed) где у записи есть телефон;
- `get_<x>_by_number(number, country=None)` → возвращает **пустой recordset**, не `None`;
  без `@tools.ormcache` (NG отказался от него);
- `create()` читает `context.get('connect_call_id')` и проставляет обратную связь
  (шаблон `connect_crm/models/crm_lead.py:44-57`).

`ODUIST_MODULES.append('connect_<app>')` — в `models/settings.py` (или в первом
импортируемом model-файле, если settings нет), как `connect_crm/models/settings.py:5`.
`security/webhook.xml` — ACL на target для `connect.group_webhook` (read + при
необходимости create/write), запись правится под sudo в webhook-контексте.

### Специфика по модулю

**connect_account** (`depends ['connect', 'account']`)
- target: `account.move`. Link-поле `invoice` (или `account_move`).
- Lookup по партнёру, а НЕ по номеру (у счёта нет своего телефона). Исходник
  (`asterisk_plus_account/models/call.py`) искал `state='posted'`,
  `move_type in ('out_invoice','in_invoice')`, `payment_state!='paid'` — **исправить
  баг**: не смешивать `in_invoice`/`out_invoice` по направлению звонка; для входящего
  → `out_invoice` клиента, ограничить одним типом.
- **Нет auto-create** (счёт из звонка не создаём) → `register_call` не нужен;
  кнопка `create_*` не нужна, только smart button + фильтр.
- Исходник не имел `security/` (band-aid `sudo()`), класс назван `AccountOrder` —
  **добавить корректный ACL, не тащить copy-paste**.
- Views: smart button на `account.view_move_form`, phone-поля, фильтр «Invoicing»
  на call search.

**connect_project** (`depends ['connect', 'project']`)
- targets: `project.task` (основной) и `project.project`. Link-поля `task` + `project`.
- Также `_inherit connect.recording` с `task`/`project` M2O, проставляемыми в `create`
  из `call.ref`/M2O (шаблон `asterisk_plus_project/models/recording.py`, переписать под
  выделенные M2O). Даёт «Recorded Calls» notebook-страницу на проекте/задаче.
- Кнопка `create_task_button` (из звонка). **Выбросить мёртвый** `project.create`-хук
  на `call_id` (никто контекст не передавал) — вместо него idempotent-кнопка NG-стиля.
- Lookup задачи фильтровать по не-folded стадии (как helpdesk), не «первая любая».

**connect_hr** (`depends ['connect', 'hr']`)
- targets: `hr.employee` (+ опц. `hr.employee.public`). Link-поле `employee`.
- Исходник **нефункционален**: нет `update_reference`, счётчик всегда 0,
  `hr.employee.public` полу-подключён, `views/hr_employee_public_views.xml` мёртв
  (домен указывает на `hr.employee`), файл назван `hr_empoloyee.py`. **Реализовать
  с нуля** по паттерну: линковать звонок к сотруднику по совпадению номера
  (`work_phone`/`mobile_phone`), smart button, фильтр. `hr.employee.public` —
  либо корректно (related M2O), либо не включать в selection вовсе.
- ACL: только read на `hr.employee` для webhook-группы (не тащить лишние create/write
  из исходника).

**connect_sale** (`depends ['connect', 'sale']` — или `sale_management`)
- target: `sale.order`. Link-поле `sale_order`.
- Lookup по партнёру, **с фильтром состояния** (не тащить `limit=1` по любому
  draft/cancel из исходника). Направление: входящий → заказы клиента.
- **Выбросить мёртвый** `sale.order.create`-хук на `call_id`.
- Опционально кнопка `create_sale_order_button` (idempotent). Views: smart button на
  `sale.view_order_form`, phone-поля, фильтр на обе search-вьюхи заказов.

### Что НЕ переносить (общий чёрный список из исходников)
`update_reference()`+`if not res`-цепочку (недетерминизм по порядку загрузки);
триплет `ref`/`model`/`res_id` как единственный линк; unstored
`asterisk_calls_count`; мёртвые `create(call_id)`-хуки; `invalidate_model(flush=True)`
вместо clear_cache; `@tools.ormcache` на lookup; version-forks
(`release.version_info`) — цель только 19.0; `self.env.cr.commit()`;
`view_mode='tree,form'`; stale ключ `"qweb"`, `price`, `images` в манифесте;
over-broad ACL create/write; copy-paste имена (класс `AccountOrder`, правило
`server_ticket_record_rule` в sale).

---

## Часть 2. Vendor-flavour (Grandstream UCM + Yeastar) внутри connect_asterisk

Не отдельные модули. gs/yeastar — это ~250-330 строк «flavour packs» поверх
Asterisk-по-AMI; реальной IP ~150 строк. Вливаем в `connect_asterisk`.

### Модель настроек (`connect_asterisk/models/settings.py`, `_inherit connect.settings`)
- `asterisk_vendor = fields.Selection([('generic','Generic / FreePBX'),
  ('gs_ucm','Grandstream UCM'), ('yeastar_p','Yeastar P-Series'),
  ('yeastar_s','Yeastar S-Series')], default='generic')`.
- Vendor-поля с префиксами `gs_*` / `yeastar_*` (API URL, creds, cookie/token +
  expire, verify_ssl, model/version). Секреты — `groups='connect.group_admin'` +
  `display_*` в `PROTECTED_FIELDS` (как `display_asterisk_agent_token`,
  `connect_asterisk/models/settings.py:17-18`).
- Методы vendor-API — перенести с исправлением багов:
  - GS: challenge/MD5/cookie (`asterisk_plus_gs/models/server.py:73-119`),
    `.total_seconds()` — уже корректно;
  - Yeastar S vs P-SE: auth + `recording/get_random`+`recording/download`.
    **Исправить**: несуществующий `yeastar_get_access_token()`; NameError'ы в
    `save_recording_yeastar_p_se` (undefined `server`/`recording`); `.seconds`
    → `.total_seconds()` на проверке протухания токена; missing `logger` в
    gs/recording; двойной `listAccount`.

### Импорт extensions (кнопка sync)
- `gs_sync_users` / `yeastar_*_sync_users` → одна кнопка «Import Extensions»,
  создающая `connect.asterisk.endpoint` (не legacy `asterisk_plus.user`+`user_channel`).
  Маппинг: exten → endpoint с `asterisk_channel='PJSIP/{exten}'`, транспорт,
  `asterisk_originate_context` (default `from-internal` для GS,
  `DLPN_DialPlan{exten}` для Yeastar). Create-only, как в исходнике.

### Fetch записей (vendor-specific)
- Переопределить `connect.recording.action_fetch_from_asterisk`
  (`connect_asterisk/models/recording.py:12`) стратегией по `asterisk_vendor`:
  - `gs_ucm`: тянуть байты HTTP через `recapi` (`filedir=monitor`) и загрузить в
    existing recording-pipeline (вместо агентского pull);
  - `yeastar_*`: `recording/get_random`+`download` / `download_resource_url`.
- Знание про сигнализацию файла записи (**Grandstream: `Newexten`/`StartMonitor`,
  не `VarSet`; Yeastar: AMI `Cdr.Recordfile`**) — см. блокер событий ниже.

### Блокер: allowlist AMI-событий
`connect_asterisk/controllers/webhooks.py` EVENT_HANDLERS содержит фиксированный
набор и **не** включает `Newexten` (GS) / `Cdr` (Yeastar); плюс агент форвардит
только `DEFAULT_ASTERISK_EVENTS` (`settings.py:23-25`). Нужно:
- расширить `DEFAULT_ASTERISK_EVENTS` (или сделать список, зависящий от
  `asterisk_vendor`) так, чтобы `/asterisk/api/config` отдавал агенту `Newexten`/`Cdr`;
- добавить обработчики в EVENT_HANDLERS (или точку расширения), диспатчащие на
  vendor recording-логику.
- Это **касается ADR-026** (fixed allowlist) → фиксируется в ADR-046 как правка.
- **Изменение sidecar-агента** (`oduist/asterisk-agent`) — вне Odoo-репо; отметить
  как зависимость (форвардинг `Newexten`/`Cdr`).

---

## Часть 3. ADR-046

Файл `specs/decisions/046-asterisk-plus-satellites-port.md`, заголовок
`# ADR-046: Port of remaining asterisk_plus satellites`. Нумерация: highest — 045
(с коллизиями; дизамбигуация по slug). Содержание:
- **Проблема**: 8 оставшихся сателлитов, direction решён ADR-026 (агностичные `connect_*`).
- **Решение по группам**:
  1. account/project/hr/sale → 4 агностичных `connect_*` бриджа на хуках ядра
     (`process_call_event`/`register_call`/`_get_ref`/`get_widget_fields`), НЕ порт
     `update_reference`-цепочки; выделенный M2O на бридж (устраняет
     недетерминизм слота `ref`).
  2. gs/yeastar → vendor-flavour в `connect_asterisk` (`asterisk_vendor` Selection),
     а не отдельные модули; обоснование — это Asterisk-по-AMI, не вендор-драйверы.
     Правка ADR-026: расширяемый AMI-allowlist (`Newexten`/`Cdr`) + агент их форвардит.
  3. callgroup → **не портируется**: маршрутизация = FastAGI (`fagi_request`),
     выброшенный ADR-026 §1; MiniVM-voicemail тоже отложен ADR-026 §4. Оставить
     запись «rejected/deferred» с тремя рассмотренными опциями (CURL-assist,
     dialplan-сниппет, AGI-в-sidecar) на будущее.
  4. website → вне скоупа (Twilio WebRTC).
- **Boundary/consequences**: co-installation, license-регистрация, ADR-034
  (colocated tests), ADR-039 (18.0-backport только XML/migrations), ADR-011
  (тегированные тесты).

## Обновление документации/спеков (в тех же PR)
- `specs/` — добавить `specs/connect_account.md` и аналоги (по образцу
  `specs/connect_crm.md`), обновить AGENTS.md список модулей.
- `docs/user` + `docs/admin` — где меняется UI/установка.
- `mkdocs.yml` — навигация под новые модули.

---

## Критические файлы

**Читать как эталон (NG):**
- `connect_crm/models/call.py` — паттерн бриджа (линк/хуки/кнопки/summary).
- `connect_crm/models/crm_lead.py` — One2many/phone_normalized/get_X_by_number/create-context.
- `connect_crm/{__init__,__manifest__}.py`, `connect_crm/security/webhook.xml`,
  `connect_crm/views/*`, `connect_crm/tests/*` — структура/ACL/вьюхи/тесты.
- `connect_helpdesk/*` — второй эталон (auto-create-настройки, get_ticket_by_number).
- `connect_asterisk/models/settings.py` — паттерн vendor-полей на singleton + PROTECTED_FIELDS.
- `connect_asterisk/models/recording.py`, `controllers/agent_api.py`,
  `controllers/webhooks.py` — точки для vendor-fetch и AMI-allowlist.
- `connect_asterisk/models/endpoint.py` — target для sync_users.

**Читать как источник (pbx_addons 19.0, /srv/projects/pbx_addons):**
- `asterisk_plus_account/`, `_project/`, `_hr/`, `_sale/` — логика бриджей (с багами).
- `asterisk_plus_gs/models/{server,recording}.py`, `data/events.xml` — GS API/recording.
- `asterisk_plus_yeastar/models/{server,recording,user_channel}.py`, `data/events.xml`.
- `asterisk_plus_crm/`, `_helpdesk/` — сверить, как исходники выглядели до NG-переписи.

**Создавать:**
- `connect_account/`, `connect_project/`, `connect_hr/`, `connect_sale/` (полные модули).
- `connect_asterisk/` — правки settings/recording/controllers + views + миграция (vendor-поля).
- `specs/decisions/046-asterisk-plus-satellites-port.md`.

---

## Верификация

1. **Установка/апгрейд**: `oduflow install_odoo_modules` для четырёх новых
   бриджей + `upgrade_odoo_modules connect_asterisk`; читать install-логи из ответа MCP.
2. **Тесты**: `oduflow run_odoo_tests connect_account` (и project/hr/sale),
   `run_odoo_tests connect_asterisk`. Тесты — colocated (ADR-034), тегированы именем
   модуля (ADR-011).
3. **UI-проверка** (agent-browser, `admin`/`test` после reset_admin_password):
   для каждого бриджа — smart button на форме записи, notebook/фильтр на call,
   кнопка create/unlink идемпотентна; для vendor — форма настроек Asterisk
   показывает vendor-поля по выбору `asterisk_vendor`, кнопка Import Extensions.
4. **Хуки линковки** (`run_odoo_shell`): эмулировать `process_call_event` — убедиться,
   что звонок линкуется к нужной записи по номеру/партнёру и что несколько бриджей
   в одной БД не конфликтуют (каждый пишет свой M2O).
5. **Vendor recording** (по возможности) — `action_fetch_from_asterisk` под каждый
   `asterisk_vendor`; иначе покрыть юнит-тестом с моком vendor-API.
6. Backport 18.0 (ADR-039) — только XML/migrations, `.py` байт-в-байт; отдельным
   шагом после мержа 19.0-PR.
