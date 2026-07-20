import os

import pytest

from roxy_os.document_vault import DocumentVault


def test_document_vault_ingests_deduplicates_and_isolates_users(tmp_path):
    vault = DocumentVault(tmp_path / "vault", key_path=tmp_path / "vault.key")
    first = vault.ingest("Robert", "../Reporte.md", b"contenido", content_type="text/markdown")
    duplicate = vault.ingest("robert", "otro.md", b"contenido")
    vault.ingest("alice", "privado.txt", b"secreto")

    assert first["id"] == duplicate["id"]
    assert first["name"] == "Reporte.md"
    assert len(vault.list_documents("robert")) == 1
    assert vault.list_documents("alice")[0]["name"] == "privado.txt"


def test_document_vault_read_checks_user_and_integrity(tmp_path):
    vault = DocumentVault(tmp_path / "vault", key_path=tmp_path / "vault.key")
    row = vault.ingest("robert", "datos.csv", b"a,b\n1,2")

    metadata, content = vault.read("robert", row["id"])

    assert metadata["sha256"] == row["sha256"]
    assert content == b"a,b\n1,2"
    with pytest.raises(KeyError):
        vault.read("alice", row["id"])


def test_document_vault_archive_is_recoverable(tmp_path):
    vault = DocumentVault(tmp_path / "vault", key_path=tmp_path / "vault.key")
    row = vault.ingest("robert", "nota.txt", b"nota")

    vault.archive("robert", row["id"])
    assert vault.list_documents("robert") == []
    assert vault.list_documents("robert", include_archived=True)[0]["status"] == "ARCHIVED"
    restored = vault.archive("robert", row["id"], restore=True)

    assert restored["status"] == "ACTIVE"
    assert vault.read("robert", row["id"])[1] == b"nota"


def test_document_vault_rejects_unsafe_empty_and_oversized_documents(tmp_path):
    vault = DocumentVault(tmp_path / "vault", key_path=tmp_path / "vault.key")
    with pytest.raises(ValueError):
        vault.ingest("robert", "script.exe", b"x")
    with pytest.raises(ValueError):
        vault.ingest("robert", "empty.txt", b"")
    with pytest.raises(ValueError):
        vault.ingest("robert", "large.txt", b"x" * (10 * 1024 * 1024 + 1))


def test_document_vault_uses_private_permissions_and_honest_sync_state(tmp_path):
    vault = DocumentVault(tmp_path / "vault", key_path=tmp_path / "vault.key")
    vault.ingest("robert", "nota.txt", b"privada")
    snapshot = vault.snapshot("robert")

    assert snapshot["sync_state"] == "LOCAL_ENCRYPTED"
    assert snapshot["at_rest_encryption"] is True
    assert snapshot["encryption_algorithm"] == "AES-256-GCM"
    assert snapshot["encryption_key_status"] == "READY"
    assert os.stat(vault.root).st_mode & 0o777 == 0o700
    assert os.stat(vault.index_path).st_mode & 0o777 == 0o600
    assert os.stat(vault.key_path).st_mode & 0o777 == 0o600


def test_document_vault_ciphertext_does_not_expose_plaintext_and_detects_tampering(tmp_path):
    vault = DocumentVault(tmp_path / "vault", key_path=tmp_path / "vault.key")
    row = vault.ingest("robert", "secreto.txt", b"contenido ultraprivado")
    object_path = vault.objects / row["sha256"][:2] / row["sha256"]
    encrypted = object_path.read_bytes()
    assert b"contenido ultraprivado" not in encrypted

    object_path.write_bytes(encrypted[:-1] + bytes([encrypted[-1] ^ 1]))
    with pytest.raises(ValueError, match="autenticacion"):
        vault.read("robert", row["id"])


def test_document_vault_migrates_legacy_plaintext_atomically(tmp_path):
    import hashlib

    vault = DocumentVault(tmp_path / "vault", key_path=tmp_path / "vault.key")
    content = b"contenido heredado"
    digest = hashlib.sha256(content).hexdigest()
    object_path = vault.objects / digest[:2] / digest
    object_path.parent.mkdir(parents=True)
    object_path.write_bytes(content)
    vault._write_unlocked({
        "documents": [{"id": "legacy", "user_id": "robert", "name": "viejo.txt", "suffix": ".txt", "sha256": digest, "status": "ACTIVE"}]
    })

    result = vault.migrate_plaintext_objects()

    assert result["encrypted"] == 1
    assert content not in object_path.read_bytes()
    assert vault.read("robert", "legacy")[1] == content


def test_document_vault_rejects_symbolic_key_path(tmp_path):
    real_key = tmp_path / "real.key"
    real_key.write_bytes(b"x" * 32)
    symbolic_key = tmp_path / "symbolic.key"
    symbolic_key.symlink_to(real_key)
    vault = DocumentVault(tmp_path / "vault", key_path=symbolic_key)

    snapshot = vault.snapshot("robert")

    assert snapshot["encryption_key_status"] == "UNAVAILABLE"
    assert snapshot["at_rest_encryption"] is False
    with pytest.raises(RuntimeError, match="enlace simbolico"):
        vault._encryption_key()
