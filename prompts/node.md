Ты пишешь один узел учебного слоя по выданным единицам главы. Слой — единственный источник правды для курса, поэтому ничего из единиц не теряется и ничего не додумывается.

Правила:
- claims: каждая мысль единиц — отдельное утверждение; их число не ограничено. Условия применимости, оговорки («обычно», «при условии», «в некоторых случаях»), направления (выше/ниже), числа и единицы сохраняются;
- quote — дословный непрерывный кусок текста одной единицы, скопированный символ в символ, включая опечатки и разметку формул; от 25 до 300 знаков;
- page_pdf — страница этой единицы; unit_id — её id; kind: observation (автор сообщает факт или измерение), inference (вывод, интерпретация), assumption (допущение, условность);
- source_kind: text, formula, table, task, figure_caption, figure_description_model. Единицы с пометкой [описание распознавателя] — это figure_description_model, у таких утверждений by_model: true и needs_scan: true; тексту автора они не противопоставляются;
- каждая единица, кроме заголовков, подтверждает хотя бы одно утверждение, пример или задачу;
- числа только из единиц. Не пересчитывай и не округляй;
- layers.main — суть, 2–3 фразы, первая главная. layers.topic — одна фраза, о чём узел. Всё остальное подробно раскрывай в mechanism, practice, nuances
- layers.topic, main, mechanism, practice, nuances — связный текст своими словами, фразы до 20 слов, термин объясняется при первом употреблении; если для слоя в главе ничего нет, оставь одну короткую фразу об этом и не придумывай; не повторяй в каждом абзаце, что чего-то нет;
- deeper — уточнения и детали, которые не поместились;
- data_meaning.from_chapter — только то, что прямо следует из главы, для данных (вход, выход, какие столбцы и кривые); breaks — где данные или правило ломаются; остальное в hypotheses с hypothesis: true;
- it_analogy — аналогия из ИТ и breaks_where: где она перестаёт работать;
- misconception — заблуждение из списка (ref = misc.*) или своё (ref: null), если узел его исправляет, иначе null;
- now_practice — как это делается сейчас, если книга описывает устаревшее (это слова модели, hypothesis: true), иначе null;
- inefficiency_lens — ручной труд специалиста, если узел о работе, иначе null; time: «в главе не указано», если не указано;
- decision_on_data — признаки → правило → вывод и контрпример, если узел позволяет решать по данным, иначе null;
- worked_examples — все разобранные автором примеры: условие, шаги, итог с числами автора; book_tasks — все задачи книги: номер, текст, какой рисунок нужен;
- terms_used — термины из списка «Уже объяснены», на которые узел опирается. Термины, которых нет ни там, ни в terms_introduced, объясни на месте простыми словами.

Верни только JSON с полями: layers, claims (без id), misconception, data_meaning, it_analogy, now_practice, inefficiency_lens, decision_on_data, worked_examples, book_tasks, terms_used, needs_scan, prerequisites (slug узлов-предпосылок из списка), glossary.
Поле-текст — {"text":"…","by_model":true}. claims: {"text","kind","page_pdf","unit_id","quote","source_kind","by_model","needs_scan"}; by_model: false, если утверждение прямо из текста автора. glossary: [{"term":"…","definition":"…"}] для всех terms_introduced.

Точные формы вложенных полей:
- misconception: {"ref":"misc.…" или null,"text":"…","by_model":true} или null
- data_meaning: {"from_chapter":поле,"breaks":поле,"hypotheses":[{"text":"…","by_model":true,"hypothesis":true}]}
- it_analogy: {"text":"…","breaks_where":"…","by_model":true}
- inefficiency_lens: {"inputs":"…","manual_steps":"…","judgment_points":"…","time":"…","typical_errors":"…","by_model":true} или null
- decision_on_data: {"features":["…"],"rule":"…","conclusion":"…","counterexample":"…"} или null
- worked_examples: [{"page_pdf":100,"condition":"…","steps":["…"],"result":"…","figure":"рис. N, стр. M" или null}]
- book_tasks: [{"number":"85","page_pdf":90,"text":"…","figure":"…" или null}]
- needs_scan: [{"page":95,"what":"…"}]
