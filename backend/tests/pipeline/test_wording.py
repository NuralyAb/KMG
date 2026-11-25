"""Служебные слова конвейера не попадают к читателю, форма слоёв выравнивается кодом."""

from glava.modules.layer.wording import normal_layers, plain_node, plain_text


def test_service_words_are_replaced():
    assert plain_text("В этих единицах порогов нет.") == "В этой части главы порогов нет."
    assert plain_text("Узел объясняет корку, другие узлы — раствор.") == "Шаг объясняет корку, другие шаги — раствор."
    assert plain_text("По описанию распознавателя видно две кривые.") == "По описанию программы распознавания видно две кривые."
    assert plain_text("Единица не называет порогов.") == "Глава здесь не называет порогов."
    assert plain_text("описание рисунка в единицах отсутствует") == "описание рисунка в этой части главы отсутствует"


def test_measurement_units_and_similar_words_are_kept():
    for text in ("Время дано в единицах мкс/м.", "распознаваемый пласт", "узловатый"):
        assert plain_text(text) == text


def test_quotes_and_ids_are_not_touched():
    node = {"id": "x.узел", "claims": [{"quote": "Узел трещин", "text": "Узел трещин"}], "unit_ids": ["узел"]}
    assert plain_node(node) == {"id": "x.узел", "claims": [{"quote": "Узел трещин", "text": "Шаг трещин"}], "unit_ids": ["узел"]}


def test_deeper_is_always_a_list_of_objects():
    item = {"text": "а", "by_model": True}
    assert normal_layers({"deeper": "а"})["deeper"] == [item]
    assert normal_layers({"deeper": ["а"]})["deeper"] == [item]
    assert normal_layers({"deeper": item})["deeper"] == [item]
    assert normal_layers({})["deeper"] == []
    assert normal_layers({"deeper": [item]})["deeper"] == [item]
