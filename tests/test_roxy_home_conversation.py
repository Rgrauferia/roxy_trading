from roxy_os.home_conversation import HomeConversationStore


def test_home_conversation_memory_is_private_bounded_and_redacted(tmp_path):
    store = HomeConversationStore(tmp_path / "conversation.json", max_turns=4)

    store.remember("member:robert", user="Prefiero pollo", assistant="Lo tendré en cuenta.")
    store.remember(
        "member:robert",
        user="Mi api_key=sk-super-secret-value-123456",
        assistant="No guardaré esa credencial.",
    )
    store.remember("member:robert", user="¿Y mañana?", assistant="Podemos variar con pescado.")
    store.remember("member:roxy", user="Prefiero vegetariano", assistant="Entendido.")

    robert = store.turns("member:robert")
    partner = store.turns("member:roxy")

    assert len(robert) == 4
    assert robert[-1]["content"] == "Podemos variar con pescado."
    assert "sk-super-secret" not in " ".join(row["content"] for row in robert)
    assert partner[0]["content"] == "Prefiero vegetariano"
    assert all("vegetariano" not in row["content"] for row in robert)

