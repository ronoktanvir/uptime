"""Additive startup fence preserves the authority and immutable history bytes."""
from uptime.auth import bind_workspace
from uptime.storage import database


def test_migration_preserves_keys_artifacts_and_is_byte_idempotent(tmp_path):
    path=tmp_path/'legacy.sqlite'
    with database(path) as db, db:
        db.execute('CREATE TABLE authority_workspace(id INTEGER PRIMARY KEY,mode TEXT,rehearsal INTEGER,tenant TEXT)')
        db.execute("INSERT INTO authority_workspace VALUES(1,'replay',0,'bears')")
        db.execute('CREATE TABLE authority_user(subject TEXT PRIMARY KEY,role TEXT NOT NULL,public_key BLOB NOT NULL UNIQUE)')
        db.execute('INSERT INTO authority_user VALUES(?,?,?)',('named.synthetic.reviewer','reviewer',b'public-test-verifier'))
        db.execute('CREATE TABLE immutable_receipt(id TEXT PRIMARY KEY,payload BLOB)')
        db.execute('INSERT INTO immutable_receipt VALUES(?,?)',('original',b'{ "literal": "successful_samples", "amount":"12.51" }'))
    bind_workspace(path,'replay',False)
    with database(path) as db:
        assert tuple(db.execute('SELECT subject,role,public_key,schema_epoch FROM authority_user').fetchone()) == (
            'named.synthetic.reviewer','reviewer',b'public-test-verifier',61)
        assert db.execute('SELECT payload FROM immutable_receipt').fetchone()[0] == b'{ "literal": "successful_samples", "amount":"12.51" }'
        db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    first=path.read_bytes()
    bind_workspace(path,'replay',False)
    with database(path) as db:
        db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    assert path.read_bytes() == first


def test_unknown_authority_schema_never_silently_migrates(tmp_path):
    import pytest
    path=tmp_path/'unknown.sqlite'
    with database(path) as db, db:
        db.execute('CREATE TABLE authority_workspace(id INTEGER PRIMARY KEY,mode TEXT,rehearsal INTEGER,tenant TEXT)')
        db.execute("INSERT INTO authority_workspace VALUES(1,'replay',0,'bears')")
        db.execute('CREATE TABLE authority_user(subject TEXT,role TEXT,password TEXT)')
    with pytest.raises(ValueError,match='Legacy password'):
        bind_workspace(path,'replay',False)
