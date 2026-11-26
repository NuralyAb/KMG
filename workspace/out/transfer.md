# Перенос конвейера

Считается из файлов главы, без модели. claims_per_page — подробность слоя: меньше, чем на обучении, значит глава сжата. flagged_share — доля утверждений с расхождением при сверке кодом. verify_follows — доля, которую вторая модель признала следующей из цитаты (если запускали verify).

Падение — изменение против среднего по обучающим главам с полным слоем: −0.3 значит на 30 % хуже, для flagged_share знак перевёрнут. complete=False — слой собран не на все узлы плана, сравнение по такой главе предварительное.

## Главы

| chapter | split | complete | pages | nodes | planned_nodes | claims | claims_per_page | units | covered_share | skipped_with_reason | units_lost | flagged_share | early_terms | verify_follows | tasks | task_types | usd_per_node | person_minutes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| latyshova_gl5_par17-20 | обучение | True | 19 | 44 | 44 | 596 | 31.4 | 186 | 0.919 | 15 | 0 | 0.122 | 13 | — | 84 | 5 | 0.743 | 4.0 |
| basniev_gl23-24_1 | обучение | True | 27 | 42 | 42 | 619 | 22.9 | 428 | 0.853 | 63 | 0 | 0.097 | 9 | — | 84 | 5 | 0.59 | 0.0 |
| rehearsal_keys_en | тест или репетиция | False | 6 | 13 | 25 | 136 | 22.7 | 42 | 0.976 | 1 | 0 | 0.066 | 7 | — | 0 | 0 | 0.18 | 0.0 |

## Падение от обучения

| chapter | complete | claims_per_page | covered_share | flagged_share | tasks |
|---|---|---|---|---|---|
| rehearsal_keys_en | False | -0.164 | 0.102 | 0.397 | -1.0 |
