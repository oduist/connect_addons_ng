---
title: <короткое рабочее название>
slug: <yyyy-mm-dd-slug>
status: draft            # draft | approved | scheduled | published
language: en
platforms: [linkedin]    # linkedin | x | facebook | ...
publish_date:            # ISO, заполняется при постановке в Postiz
card_template: card-thesis   # card-thesis | card-comparison | card-diagram | card-dialog
card_file: out/<slug>.png
postiz_post_id:          # заполняется после публикации
published_url:           # ссылка на живой пост
---

# Пост

<!--
Формула:
1. HOOK (1–2 строки) — боль, парадокс или история. LinkedIn показывает в
   превью только первые ~2 строки, они решают всё.
2. Суть — 3–5 буллетов с эмодзи-маркерами, каждый = конкретная возможность
   или факт. Продукт: **Oduist Connect**.
3. Дифференциатор одной строкой (no lock-in / внутри Odoo / open source).
4. CTA — вопрос или призыв прокомментировать (комментарии > лайки).
5. 3–5 хэштегов: #Odoo + тематические.
-->

<текст поста>

# Карточка

<!-- Что меняем в HTML-шаблоне: kicker, заголовок, лид, плитки/строки/реплики,
     футер. Размер 1200×627. После рендера посмотреть PNG глазами. -->

- kicker: Oduist Connect · <тема>
- headline: <заголовок, градиентная часть в span.grad>
- lede: <подзаголовок>
- элементы: <плитки / строки таблицы / реплики диалога>
