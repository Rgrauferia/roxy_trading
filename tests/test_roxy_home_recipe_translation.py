import json
from types import SimpleNamespace
import pytest
from roxy_os.home_recipe_translation import validate, task
from roxy_os.home_ai import HomeAIConfig, RoxyHomeAI

SOURCE={"title":"2-Step Test", "ingredients":["1/2 cup water", "1.5 cups rice"], "steps":["Heat to 350 F for 5 minutes.", "Do not cover."]}
SPANISH={"title":"Prueba en 2 pasos", "ingredients":["1/2 taza de agua", "1.5 tazas de arroz"], "steps":["Calienta a 350 F durante 5 minutos.", "No tapes."]}

def test_source_quantities_and_all_lines_survive_translation():
    assert validate(SPANISH,SOURCE)==SPANISH

@pytest.mark.parametrize("change",[
    {"ingredients":["1 taza de agua","1.5 tazas de arroz"]},
    {"steps":["Calienta a 350 C durante 5 minutos.","No tapes."]},
    {"steps":["Calienta a 350 F durante 6 minutos.","No tapes."]},
    {"steps":["Calienta a 350 F durante 5 minutos."]},
    {"ingredients":["1/2 taza de agua","1,5 tazas de arroz"]},
])
def test_changed_amount_temperature_or_missing_line_is_rejected(change):
    with pytest.raises(ValueError):validate({**SPANISH,**change},SOURCE)

def test_translation_input_is_bounded_and_excludes_private_context():
    assert "private" not in task({**SOURCE,"profile":"private","history":"private"})
    with pytest.raises(ValueError):task({**SOURCE,"steps":["x"*15000]})

def test_translation_uses_home_responses_luna_and_accounts_for_tokens(tmp_path):
    calls=[]
    def create(**kw):
        calls.append(kw)
        return SimpleNamespace(output_text=json.dumps(SPANISH),usage=SimpleNamespace(input_tokens=180,output_tokens=80))
    config=HomeAIConfig(api_key="synthetic-home-only",budget_path=str(tmp_path/"budget.json"))
    agent=RoxyHomeAI(config,client=SimpleNamespace(responses=SimpleNamespace(create=create)))
    assert agent.translate_recipe(SOURCE,actor_key="member-a")==SPANISH
    assert calls[0]["model"]=="gpt-5.6-luna" and calls[0]["store"] is False
    assert "tools" not in calls[0] and "member-a" not in json.dumps(calls[0])
    ledger=json.loads((tmp_path/"budget.json").read_text())
    assert ledger["requests"]==1 and ledger["output_tokens"]==80
