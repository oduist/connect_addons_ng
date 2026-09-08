# Контент-план Oduist Connect: полный список статей

Составлен по фактическому содержанию документации (28 модулей, ~70 страниц
`*/docs/**`, `specs/`, `docs/changelog.md`). Каждая статья опирается на реально
описанную возможность — ничего не выдумано. Источник указан, чтобы автор мог
открыть страницу и писать по ней.

**Язык статей — английский** (аудитория Odoo международная), комментарии здесь
русские. Каждая статья затем сжимается в пост по конвейеру из `README.md`.

## Как читать приоритеты

| Метка | Что значит | Когда писать |
|---|---|---|
| **P1** | Ловит готовый спрос (человек уже ищет решение) или наш главный крючок — AI-агенты | Первые 3 месяца |
| **P2** | Раскрывает продукт, поддерживает P1 внутренними ссылками | Месяцы 3–6 |
| **P3** | Длинный хвост, инженерная аудитория, репутация | По остаточному принципу |

**Типы интента:** `COMM` — коммерческий (человек выбирает и готов купить),
`INFO` — информационный (учится, попадёт в воронку позже), `PROBLEM` —
проблемный (что-то сломалось, ищет решение — самый дешёвый трафик и самая
лояльная аудитория), `BRAND` — репутация/инженерный бренд.

---

## A. Опорные статьи (pillar) — большие, на них ссылается всё остальное

| # | Заголовок | Мысль / интент | Источник |
|---|---|---|---|
| A1 | **Telephony for Odoo in 2026: the complete guide** | Главная опорная страница: типы решений, что вообще бывает, к чему ведёт каждый путь. `INFO` | все docs |
| A2 | **Which telephony provider should you use with Odoo?** | Дерево решений: облачный CPaaS vs self-hosted vs «оставить свою АТС». `COMM` | все provider docs |
| A3 | **AI voice agents for Odoo: what they can actually do** | Главный крючок продукта: агент открывает тикеты, оформляет заказы, бронирует встречи. `INFO` | connect/docs/user/ai-agents.md |
| A4 | **Six ways a phone call finds its record in Odoo** | Лид, тикет, заказ, счёт, задача, сотрудник — таблица правил сопоставления. `INFO` | все bridge configuration.md |
| A5 | **One phone system, eleven providers: the architecture** | Технологически-агностичное ядро + провайдеры; несколько провайдеров в одной базе. `BRAND` | specs/architecture.md |
| A6 | **From ringing phone to closed deal: the full Odoo call lifecycle** | Сквозной сценарий: звонок → карточка → запись → транскрипт → резюме → лид. `INFO` | connect/docs/user/* |
| A7 | **Self-hosted vs cloud telephony for Odoo: total cost and control** | FreeSWITCH/LiveKit против Twilio/Telnyx: деньги, данные, ответственность. `COMM` | freeswitch + twilio docs |
| A8 | **The Odoo telephony buyer's checklist** | 20 вопросов, которые надо задать любому вендору (мы на все отвечаем «да»). `COMM` | синтез |

---

## B. Сравнения и статьи под коммерческий запрос — ловят готовый спрос

| # | Заголовок | Мысль / интент | Источник |
|---|---|---|---|
| B1 | **Odoo VoIP vs Oduist Connect: what the built-in module doesn't do** | ⭐ Уже написан пост. IVR, запись, AI, SMS. `COMM` | connect_twilio docs |
| B2 | **Twilio vs Telnyx for Odoo: a practical comparison** | Цена, TwiML vs TeXML, у Telnyx — RCS и нативные AI-ассистенты. `COMM` | twilio + telnyx |
| B3 | **FreeSWITCH vs Asterisk with Odoo: which self-hosted path** | Новый PBX под ключ vs «оставить существующий». `COMM` | freeswitch + asterisk |
| B4 | **ElevenLabs vs Pipecat vs Dograh vs LiveKit: choosing an AI voice engine** | Хостед vs self-hosted, набор инструментов, ограничения. `COMM` | E-кластер |
| B5 | **3CX vs Odoo-native telephony: keep both** | 3CX остаётся, Odoo получает данные. `COMM` | connect_3cx |
| B6 | **Bird vs Twilio for Odoo messaging** | Bird — messaging-first, без web phone. `COMM` | bird + twilio |
| B7 | **Infobip vs Twilio: event-driven voice without markup** | Нет TwiML — REST-события. `COMM` | infobip |
| B8 | **Vonage NCCO vs TwiML: programmable calls in JSON** | Тем, кто уже знает TwiML. `COMM` | vonage |
| B9 | **Do you need a PBX at all? Cloud numbers vs self-hosted FreeSWITCH** | `COMM` | freeswitch + twilio |
| B10 | **AI receptionist vs traditional IVR: an honest comparison** | Когда «нажмите 1» всё ещё лучше. `COMM` | ai-agents.md |
| B11 | **Ring group vs call queue: which one do you actually need** | `INFO` | connect/docs/user/callflows.md |
| B12 | **Odoo 17 / 18 / 19: telephony compatibility** | Поддерживаем все три. `COMM` | connect/docs/admin/installation.md |
| B13 | **Running two carriers in one Odoo database** | Per-user выбор провайдера — уникальная возможность. `COMM` | twilio/installation.md |
| B14 | **What Connect deliberately does NOT do (per provider)** | Честный список ограничений — статья доверия, конвертит лучше рекламы. `COMM` | v1-limitations во всех provider docs |

---

## C. Пошаговые интеграции — «Подключить X к Odoo» (высокий поисковый спрос)

| # | Заголовок | Мысль / интент | Источник |
|---|---|---|---|
| C1 | **How to connect Twilio to Odoo (step by step)** | Самый низкий порог: pip, 4 креденшла, Sync. `COMM` | twilio/installation.md |
| C2 | **How to connect 3CX V20 to Odoo** | ⭐ Уже написан пост. Один XML-шаблон. `COMM` | 3cx-setup.md |
| C3 | **How to connect FreePBX / Issabel / Asterisk to Odoo** | Sidecar-агент, дialplan не трогаем. `COMM` | asterisk-setup.md |
| C4 | **How to set up Telnyx with Odoo** | TeXML + SIP-домены + AI-ассистент. `COMM` | telnyx-setup.md |
| C5 | **Deploy a FreeSWITCH PBX for Odoo with Docker Compose** | `docker compose up -d` → рабочая АТС. `COMM` | freeswitch-setup.md |
| C6 | **How to connect Infobip to Odoo** | `COMM` | infobip-setup.md |
| C7 | **How to connect Bird (MessageBird) to Odoo** | `COMM` | bird-setup.md |
| C8 | **How to connect Vonage to Odoo** | Одна кнопка создаёт всё приложение. `COMM` | vonage-setup.md |
| C9 | **Video meetings in Odoo with LiveKit** | Комната с карточки контакта, гостевая ссылка. `COMM` | livekit/user/meetings.md |
| C10 | **Store Twilio call recordings in your own S3 bucket** | Своё хранилище + retention. `COMM` | connect_s3/setup.md |
| C11 | **Try the whole stack on your laptop: the all-in-one Docker file** | `docker-compose.full.yml` с Odoo 19 + Postgres. `INFO` | freeswitch-setup.md |

---

## D. AI-голосовые агенты — наш главный крючок (писать больше всего)

| # | Заголовок | Мысль / интент | Источник |
|---|---|---|---|
| D1 | **Your Odoo phone number can open tickets, take orders and book meetings** | Флагман: весь набор инструментов агента. `INFO` | elevenlabs *_helpdesk/_sale/agents.md |
| D2 | **An AI agent that answers your helpdesk at 3 AM** | ⭐ Уже написан пост. `INFO` | elevenlabs_helpdesk/tools.md |
| D3 | **Voice ordering: an AI agent that places real sale orders** | `create_sale_order` → S00001 голосом. `INFO` | elevenlabs_sale/tools.md |
| D4 | **"Where is my order?" — self-service order status by phone** | Читает строки, дату доставки, менеджера. `INFO` | elevenlabs_sale/tools.md |
| D5 | **Book an appointment by phone: five calendar tools** | Свободные слоты 08:00–18:00, создание, отмена. `INFO` | elevenlabs/agents.md |
| D6 | **The AI answers, the human finishes: how warm transfer works** | Агент брифует коллегу приватно, потом соединяет. Сильный дифференциатор. `INFO` | ai-agents.md, telnyx |
| D7 | **When the transfer fails: what a good AI agent does next** | Не бросает звонок — предлагает записать запрос. `INFO` | ai-agents.md |
| D8 | **Ground your voice agent in your own documents** | PDF/DOCX/URL → база знаний, только active-документы. `INFO` | elevenlabs_knowledge |
| D9 | **AI that reads the customer's file before it says hello** | Инъекция контекста в момент установления звонка. `INFO` | elevenlabs/maintenance.md |
| D10 | **"Last time you called about…": conversation continuity** | `{{previous_topics}}` из прошлого разговора. `INFO` | elevenlabs/agents.md |
| D11 | **Prompt versioning: roll back an agent that got worse** | v1, v2, … откат в один клик. `INFO` | elevenlabs/agents.md |
| D12 | **Choosing the LLM for your voice agent (GPT, Gemini, Claude)** | Модель, температура, лимит токенов на агента. `COMM` | elevenlabs/agents.md |
| D13 | **Voice cloning, speed and the settings that break your agent** | Speed вне 0.5–1.5 → звонок падает через секунду. `PROBLEM` | ai-agents.md, telnyx |
| D14 | **Making an AI agent truly multilingual (it's not just the prompt)** | Нужны и multilingual STT, и подходящий TTS-голос. `INFO` | ai-agents.md |
| D15 | **The agent greets callers in their own Odoo language** | Язык берётся с карточки контакта. `INFO` | ai-agents.md, telnyx |
| D16 | **Barge-in: why callers must be able to interrupt the AI** | + Protect Greeting. `INFO` | ai-agents.md, pipecat |
| D17 | **Turn-taking: stop your AI agent finishing your sentences** | Endpointing, Wait Before Speaking, пауза после цифр. `PROBLEM` | telnyx-setup.md |
| D18 | **Cost and abuse guardrails for voice agents** | Лимит звонков в день, конкурентность, max duration. `INFO` | elevenlabs/agents.md |
| D19 | **Who is the AI allowed to call? The published-extension allowlist** | Только Published-расширения видны агенту. `INFO` | elevenlabs/agents.md |
| D20 | **Agent-to-agent transfer: routing by natural-language conditions** | Ресепшен → специалист по смыслу запроса. `INFO` | elevenlabs/agents.md |
| D21 | **Self-hosted AI voice agents on your own hardware** | Pipecat/Dograh/LiveKit: свои ключи, свой звук. `COMM` | pipecat, dograh, livekit |
| D22 | **Drag-and-drop voice workflows with Dograh** | Не-разработчик собирает сценарий визуально. `INFO` | dograh-setup.md |
| D23 | **Outbound AI campaigns through your own trunks** | Dograh-кампании, LiveKit «Call with Agent». `INFO` | dograh, livekit |
| D24 | **Under 1.4 seconds: latency targets for voice AI** | Инженерная планка Pipecat. `BRAND` | pipecat-setup.md |
| D25 | **Every AI call is a normal call record** | Агентские звонки в общей истории с записью. `INFO` | ai-agents.md |
| D26 | **Why we never transcribe an AI call twice** | Транскрипт вендора уже есть — не платим OpenAI повторно. `BRAND` | elevenlabs/maintenance.md, telnyx |

---

## E. Транскрипция, резюме и данные из разговоров

| # | Заголовок | Мысль / интент | Источник |
|---|---|---|---|
| E1 | **Every call summarized in your CRM automatically** | Whisper + GPT-5.4 mini → чаттер. `INFO` | recordings.md, core-setup.md |
| E2 | **What AI call transcription actually costs** | Поле Transcription Price в долларах на запись. `INFO` | core-setup.md |
| E3 | **Write your own summary prompt** | Резюме под ваш бизнес, а не «перескажи звонок». `INFO` | core-setup.md |
| E4 | **Keep the transcript, delete the audio: a GDPR-friendly policy** | Транскрипт живёт вечно, аудио удаляется. `INFO` | core-setup.md |
| E5 | **ElevenLabs Scribe as your transcription engine** | Альтернатива Whisper с диаризацией. `INFO` | elevenlabs/configuration.md |
| E6 | **The transcription pipeline, step by step** | Очередь → крон 2 мин → Whisper → цена → резюме → чаттер. `INFO` | core-setup.md |
| E7 | **"Why isn't my AI summary appearing?"** | Отключённые крон-задачи в staging-базе. `PROBLEM` | core-setup.md |
| E8 | **Speaker diarization: who said what on the call** | `INFO` | elevenlabs/configuration.md |

---

## F. Связь звонков с бизнес-записями (мосты в приложения Odoo)

| # | Заголовок | Мысль / интент | Источник |
|---|---|---|---|
| F1 | **Turn missed calls into CRM leads automatically** | Матрица из 7 переключателей. `COMM` | connect_crm/configuration.md |
| F2 | **See which opportunity is calling before you pick up** | Живое сопоставление на входящем. `INFO` | connect_crm |
| F3 | **Call tracking for marketing: UTM attribution by phone number** | Номер на кампанию → атрибуция лида. `COMM` | connect_crm |
| F4 | **Number matching vs partner matching: two models explained** | CRM/Helpdesk/HR по номеру; Sale/Account/Project по партнёру. `INFO` | sale/index.md, hr/index.md |
| F5 | **One number written three ways still finds one contact** | E.164-нормализация. `INFO` | changelog 2026-06, crm |
| F6 | **Support tickets created from calls nobody had to log** | `COMM` | connect_helpdesk |
| F7 | **Collections calls that open with the right unpaid invoice** | Только posted + неоплаченные, только клиентские. `COMM` | connect_account |
| F8 | **Play the client call from inside the project task** | Вкладка Recorded Calls на задаче и проекте — самая «показываемая» фича. `INFO` | connect_project |
| F9 | **Task-first, project-fallback: how project linking works** | `INFO` | connect_project |
| F10 | **Every quotation call logged on the quotation** | `INFO` | connect_sale |
| F11 | **Create a lead, ticket, task or sale order in one click from a call** | Идемпотентно — второй клик открывает созданное. `INFO` | business-records.md |
| F12 | **Why we never create an invoice or an employee from a phone call** | Осознанная сдержанность в дизайне. `BRAND` | account/index.md, hr/index.md |
| F13 | **Employee call history without a single manual tag** | `INFO` | connect_hr |
| F14 | **Manual corrections always win: linking that respects humans** | Ручную привязку автоматика не перезаписывает. `INFO` | business-records.md |
| F15 | **Ringing vs hung up: why linking and creating happen at different moments** | `process_call_event` vs `register_call`. `BRAND` | bridge docs |
| F16 | **No new menus: integrating without cluttering Odoo** | 5 из 6 мостов не добавляют ни одного пункта меню. `BRAND` | bridge docs |
| F17 | **Inbound SMS that becomes a CRM lead** | `INFO` | connect_crm_twilio |

---

## G. Телефонные функции: IVR, очереди, запись, парковка, расписания

| # | Заголовок | Мысль / интент | Источник |
|---|---|---|---|
| G1 | **Build a multi-level IVR in Odoo without touching a dialplan** | DTMF + распознавание речи. `COMM` | callflows.md |
| G2 | **Speech-driven IVR: let callers say "sales" instead of pressing 1** | `INFO` | callflows.md, twilio |
| G3 | **Call queues you can reconfigure without restarting the PBX** | Изменения применяются со следующего звонка. `INFO` | callflows.md |
| G4 | **Four ways to route a caller into a queue** | `INFO` | callflows.md |
| G5 | **Fallback routing: a queue nobody answers shouldn't drop the call** | `INFO` | changelog 2026-08 |
| G6 | **Voicemail that actually works: precedence rules explained** | `INFO` | callflows.md |
| G7 | **Jinja2 voicemail greetings per user** | `INFO` | core-setup.md |
| G8 | **Call recording consent: manual recording when auto is off** | Кнопка остаётся доступной. `INFO` | recordings.md |
| G9 | **Why the recording button must trust the PBX, not the settings** | Оптимистичное состояние + коррекция от провайдера. `BRAND` | recordings.md |
| G10 | **Pause and resume recording mid-call** | `INFO` | changelog 2026-07 |
| G11 | **Call parking with BLF lamps on desk phones** | Весь офис видит занятые слоты. `INFO` | freeswitch/parking.md |
| G12 | **Opening hours for your phone numbers, three layers deep** | Спец-дни > праздники > расписание. `INFO` | freeswitch_website |
| G13 | **Show your phone status on your website** | Сниппеты Phone Status и Opening Hours. `COMM` | freeswitch_website |
| G14 | **After-hours routing that doesn't leave callers in silence** | `INFO` | freeswitch_website |
| G15 | **The Availability calendar: see your phone schedule at a glance** | `INFO` | calls.md |
| G16 | **Local neural TTS: 26 voices, no cloud bill** | Piper на своём железе. `COMM` | freeswitch-setup.md |
| G17 | **Add your own TTS voice from HuggingFace** | `INFO` | freeswitch-setup.md |
| G18 | **Click-to-call from any phone field in Odoo** | `INFO` | getting-started.md |
| G19 | **A softphone that survives a suspended browser tab** | `PROBLEM` | getting-started.md |
| G20 | **Your softphone now speaks German, French, Italian and Russian** | `INFO` | changelog 2026-08 |

---

## H. Сообщения: SMS, MMS, WhatsApp, RCS

| # | Заголовок | Мысль / интент | Источник |
|---|---|---|---|
| H1 | **One inbox for SMS, MMS and WhatsApp inside Odoo** | Общий реестр сообщений. `INFO` | messages.md |
| H2 | **The WhatsApp 24-hour window, explained for Odoo users** | Шаблон vs свободный текст. `INFO` | messages.md |
| H3 | **Submit a WhatsApp template for Meta approval from Odoo** | Без похода в портал. `COMM` | telnyx, infobip |
| H4 | **WhatsApp voice calls from Odoo — and where they don't work** | Ограничения по странам, ошибка 37007. `PROBLEM` | twilio/messaging.md |
| H5 | **RCS: branded business messaging with SMS fallback** | Только у Telnyx. `COMM` | telnyx-setup.md |
| H6 | **Auto-create contacts from inbound texts** | Message Configuration + default values. `INFO` | core-setup.md |
| H7 | **Delivery statuses that tell you the truth** | 8 статусов, включая Read. `INFO` | messages.md |
| H8 | **Send SMS from any Odoo record** | `INFO` | messages.md |
| H9 | **Different providers for voice and messaging, per user** | `INFO` | messages.md |
| H10 | **WhatsApp Business profile management from Odoo** | Quality rating, messaging tier. `INFO` | twilio, telnyx |
| H11 | **When your provider has no inbound webhooks: the polling fallback** | Честная статья про ограничение Bird. `BRAND` | bird-setup.md |
| H12 | **MMS media that plays inline in Odoo** | `INFO` | messages.md |

---

## I. Безопасность и соответствие требованиям

| # | Заголовок | Мысль / интент | Источник |
|---|---|---|---|
| I1 | **Row-level call privacy: reps see only their own calls** | Record rules. `COMM` | connect/admin/security.md |
| I2 | **Securing a public FreeSWITCH: kernel-level SIP brute-force blocking** | ipset/iptables + аудит в Odoo. `COMM` | freeswitch/firewall.md |
| I3 | **Anatomy of a SIP attack: how scanners are dropped in three packets** | `BRAND` | firewall.md |
| I4 | **Toll fraud: the attack that empties your telecom budget** | `sofia::wrong_call_state`. `COMM` | firewall.md |
| I5 | **Webhook signature verification: Twilio, Telnyx, Bird compared** | HMAC vs Ed25519 vs Standard Webhooks. `BRAND` | webhooks-security.md ×3 |
| I6 | **Least privilege for telephony webhooks** | Отдельный webhook-пользователь, без unlink. `BRAND` | все security.md |
| I7 | **Why menu hiding is not a permission** | AccessError остаётся при прямом URL. `BRAND` | admin/security.md |
| I8 | **Masked secrets: API keys even admins can't read** | `INFO` | admin/security.md |
| I9 | **When a user has no Connect role, the web phone doesn't even load** | `INFO` | admin/security.md |
| I10 | **Recording retention as a single number** | S3 lifecycle → GDPR. `COMM` | connect_s3/setup.md |
| I11 | **Proxy your recordings: don't expose provider URLs** | `INFO` | core-setup.md |
| I12 | **Your data never leaves until you deploy the gateway** | Outbox-модель памяти. `BRAND` | connect_memory |
| I13 | **A generated IAM policy that can't touch anything but your bucket** | `BRAND` | connect_s3/setup.md |
| I14 | **Rotating credentials without dropping calls** | Runbook по ротации транковых паролей. `INFO` | freeswitch-setup.md |
| I15 | **Restrict which IPs may send calls to your AI agent** | Inbound Allowed IPs. `INFO` | elevenlabs/agents.md |

---

## J. Проблемные запросы (long-tail) — дешёвый трафик, высокая лояльность

| # | Заголовок | Источник |
|---|---|---|
| J1 | **"Recording plays as 0 seconds" in Odoo — what it means** (ведёт к connect_s3) | twilio/maintenance.md |
| J2 | **"Call failed" on Telnyx: the outbound country whitelist** | telnyx-setup.md |
| J3 | **Telnyx 404 UNALLOCATED_NUMBER: your account is billing-blocked** | telnyx-setup.md |
| J4 | **403 Forbidden on Telnyx SIP: turn on "SIP URI calling = internal"** | telnyx-setup.md |
| J5 | **Your AI agent hangs up after one second (voice speed)** | telnyx-setup.md, ai-agents.md |
| J6 | **Inbound DID doesn't match: the leading "+" problem** | freeswitch-setup.md |
| J7 | **Phones behind NAT don't receive calls** | freeswitch-setup.md |
| J8 | **Echo test 9196: proving your media path works** | freeswitch-setup.md |
| J9 | **CHECK STATUS says UNREACHABLE / AUTH FAILED: a decision table** | freeswitch-setup.md |
| J10 | **Odoo rejects your self-signed certificate (and why that's correct)** | freeswitch-setup.md |
| J11 | **"Why isn't it creating tickets?" — the OR-ed sub-rules** | helpdesk/configuration.md |
| J12 | **HMAC mismatch on ElevenLabs webhooks** | elevenlabs/webhooks-security.md |
| J13 | **"No public extension" — the agent can't transfer anyone** | elevenlabs/maintenance.md |
| J14 | **TTS silently falls back to robotic `<Say>`** | elevenlabs/agents.md |
| J15 | **Phantom active calls in the list (and the reconcile cron)** | asterisk-setup.md |
| J16 | **Bird: "authenticates fine but 403s" — the scope problem** | bird-setup.md |
| J17 | **Vonage private key is shown only once** | vonage-setup.md |
| J18 | **Holiday prompts missing after a dialplan customization** | freeswitch_website |
| J19 | **Infobip web phone misses calls in a background tab** | infobip-setup.md |
| J20 | **Which ports must I open — and which must I never expose** | freeswitch-setup.md |

---

## K. Админские руководства и runbook'и

| # | Заголовок | Источник |
|---|---|---|
| K1 | **From empty VM to live PBX: a 10-step onboarding runbook** | customer-onboarding.md |
| K2 | **The 8-point smoke test before you declare a customer live** | customer-onboarding.md |
| K3 | **Capacity planning: 1000 RTP ports ≈ 500 concurrent calls** | freeswitch-setup.md |
| K4 | **fs_cli cheat sheet: 11 commands every operator needs** | fs_cli.md |
| K5 | **Customizing generated FreeSWITCH XML from an Odoo form** | freeswitch-setup.md |
| K6 | **Least-cost routing rules with regex and priorities** | freeswitch-setup.md |
| K7 | **Bring your own SIP trunk to any carrier** | freeswitch-setup.md, livekit |
| K8 | **Caller ID fallback chains explained** | twilio/users-and-sip.md, freeswitch |
| K9 | **Passphrases a human can type into a desk phone** | freeswitch-setup.md |
| K10 | **Moving to a new vendor account safely (UNBIND)** | elevenlabs/configuration.md |
| K11 | **Re-pointing webhooks after a domain change** | vonage-setup.md |
| K12 | **AWS key rotation for S3 recording storage** | connect_s3/setup.md |
| K13 | **Per-call cost tracking and chargeback reporting** | twilio/configuration.md |
| K14 | **Region and edge selection: latency and data residency** | twilio/configuration.md |

---

## L. Память о клиенте (connect_memory) — отдельный продуктовый сюжет

| # | Заголовок | Мысль / интент | Источник |
|---|---|---|---|
| L1 | **Your ERP already knows who pays late — now your AI does too** | Дайджест платёжного поведения. `INFO` | memory_sale/payment-digest.md |
| L2 | **A durable AI memory of every customer, built from your daily work** | `INFO` | memory/user/memory.md |
| L3 | **One-click customer summary on any contact** | `INFO` | memory/user/memory.md |
| L4 | **Detecting renegotiation: when a confirmed order changes** | Диффы old→new по строкам. `INFO` | memory_sale/events.md |
| L5 | **Backfill your history without breaking anything** | Идемпотентный фоновый джоб. `INFO` | memory/admin/memory-setup.md |
| L6 | **Internal conversations are never captured** | Только внешняя переписка. `COMM` | memory_sale/index.md |
| L7 | **Odoo never calls the AI engine — it writes an outbox** | Архитектура приватности. `BRAND` | memory-setup.md |
| L8 | **Capture that can never break your business** | Ошибка памяти не откатит заказ. `BRAND` | memory_sale/index.md |
| L9 | **Engine-neutral memory: Hindsight, Cognee or your own** | `BRAND` | specs/connect_memory.md |

---

## M. Лицензирование и коммерческая модель

| # | Заголовок | Мысль / интент | Источник |
|---|---|---|---|
| M1 | **Try before you buy: a 30-day trial per module, no signup** | `COMM` | admin/licensing.md |
| M2 | **BSL 1.1 explained for Odoo buyers** | Что можно, что нельзя, когда станет LGPL. `COMM` | admin/licensing.md |
| M3 | **Per-instance licensing and what happens when you clone your database** | Instance UID. `COMM` | admin/licensing.md |
| M4 | **What happens when a licence lapses (and what keeps working)** | Записи всё равно ведутся. `COMM` | licensing.md, bridge docs |
| M5 | **Buying modules from inside Odoo** | `COMM` | admin/licensing.md |
| M6 | **Source-available telephony: why you can read every line** | `BRAND` | admin/licensing.md |

---

## N. Инженерный бренд — для партнёров, разработчиков, Reddit/HN

| # | Заголовок | Мысль / интент | Источник |
|---|---|---|---|
| N1 | **One ledger, eleven providers: how we keep the core technology-agnostic** | `BRAND` | specs/architecture.md |
| N2 | **Why we deliberately duplicate code across provider modules** | ADR-031 — спорное решение, отличная дискуссия. `BRAND` | specs/decisions/ |
| N3 | **Identical Python across three Odoo branches: an invariant, not a preference** | `BRAND` | AGENTS.md |
| N4 | **Documentation that ships inside the product** | connect_book: только установленные модули. `BRAND` | connect_book |
| N5 | **A Markdown renderer with zero dependencies (and why)** | `BRAND` | book-setup.md |
| N6 | **Odoo as the dialplan: configuring FreeSWITCH through mod_xml_curl** | `BRAND` | freeswitch-setup.md |
| N7 | **A sidecar that is never in the media path** | `BRAND` | asterisk-setup.md |
| N8 | **Idempotent webhooks: designing for replay** | `BRAND` | parking.md, elevenlabs |
| N9 | **The auto-installed glue module pattern** | connect_crm_twilio: ноль моделей. `BRAND` | crm_twilio/index.md |
| N10 | **Fail-soft docs: one bad file never takes the book down** | `BRAND` | book-setup.md |
| N11 | **Liveness vs readiness: getting container probes right** | `BRAND` | firewall.md |
| N12 | **Writing a changelog when every module versions independently** | `BRAND` | docs/changelog.md |

---

## O. Анонсы (из changelog) — сезонные, теряют ценность со временем

| # | Заголовок | Когда | Источник |
|---|---|---|---|
| O1 | **Introducing Connect Book: documentation inside Odoo** | свежее (2026-08) | changelog |
| O2 | **Telnyx AI receptionist routing** | 2026-08 | changelog |
| O3 | **The month Connect became multi-provider: eleven integrations** | ретроспектива 2026-07 | changelog |
| O4 | **Working schedules for inbound calls** | 2026-07 | changelog |
| O5 | **All modules move to BSL 1.1** | 2026-07 | changelog |
| O6 | **Every module's Apps Store page, rebuilt** | 2026-08 | changelog |

---

## Итого и порядок запуска

**Всего 150 статей.** По приоритетам: **P1 ≈ 45** (кластеры A, B, C, D +
F1–F3), **P2 ≈ 60** (E, F, G, H, I, L, M), **P3 ≈ 45** (J, K, N, O).

Реалистичный темп для одного маркетолога — **1–2 статьи в неделю**, то есть
плана хватает примерно на два года. Не пытайтесь писать всё.

**Первые 10 статей (месяцы 1–3), в этом порядке:**

1. A2 — Which telephony provider should you use with Odoo? (опора для всех C)
2. B1 — Odoo VoIP vs Oduist Connect (пост уже есть, разворачиваем в статью)
3. C2 — How to connect 3CX V20 to Odoo (пост есть)
4. D2 — AI agent answers your helpdesk at 3 AM (пост есть)
5. A3 — AI voice agents for Odoo: what they can actually do
6. C1 — How to connect Twilio to Odoo
7. D1 — Your Odoo phone number can open tickets, take orders and book meetings
8. F1 — Turn missed calls into CRM leads automatically
9. C3 — How to connect FreePBX / Issabel / Asterisk to Odoo
10. A4 — Six ways a phone call finds its record in Odoo

**Правила работы с планом**

- Каждая статья → один пост в LinkedIn по конвейеру из `README.md`. Статья
  ловит поиск годами, пост даёт охват в день публикации.
- Кластер `PROBLEM` (J) пишется быстрее всех — это по сути переписанные разделы
  troubleshooting из документации. Отличный способ набрать объём.
- Проверяйте факты по указанному источнику перед публикацией: документация
  меняется вместе с кодом.
- Не публикуйте сравнения с конкурентами (B) без перепроверки их актуальных
  возможностей — устаревшее сравнение бьёт по доверию сильнее, чем помогает.
