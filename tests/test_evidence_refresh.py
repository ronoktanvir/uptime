import json
import sys
from unittest.mock import Mock

import pytest

from uptime import evidence_refresh as refresh
from uptime.evidence import MAX_BYTES


def connection(monkeypatch, *, status=200, headers=None, chunks=None):
    response = Mock(status=status)
    headers = headers or {}
    response.getheader.side_effect = lambda key, default=None: headers.get(key, default)
    response.read1.side_effect = chunks or [b'{"incidents":[]}', b'']
    conn = Mock()
    conn.getresponse.return_value = response
    factory = Mock(return_value=conn)
    monkeypatch.setattr(refresh.http.client, 'HTTPSConnection', factory)
    return conn, factory


def test_https_allowlist_and_success(monkeypatch):
    conn, factory = connection(monkeypatch)
    assert json.loads(refresh.fetch_public()) == {'incidents': []}
    factory.assert_called_once_with('status.twilio.com', timeout=10.0)
    conn.close.assert_called_once()
    for uri in ['http://status.twilio.com/api/v2/incidents.json',
                'https://status.twilio.com.evil/api/v2/incidents.json',
                'https://user:pass@status.twilio.com/api/v2/incidents.json']:
        with pytest.raises(ValueError):
            refresh.fetch_public(uri=uri)
    assert factory.call_count == 1


@pytest.mark.parametrize('status', [301, 302, 307, 308, 403, 500])
def test_no_redirect_or_error_body(monkeypatch, status):
    conn, _ = connection(monkeypatch, status=status)
    with pytest.raises(ValueError):
        refresh.fetch_public()
    conn.getresponse.return_value.read1.assert_not_called()
    conn.close.assert_called_once()


@pytest.mark.parametrize('headers,chunks', [({'Content-Length': str(MAX_BYTES + 1)}, None),
                                           ({'Content-Encoding': 'gzip'}, None),
                                           ({}, [b'x' * (MAX_BYTES + 1)])])
def test_size_and_encoding_limits(monkeypatch, headers, chunks):
    conn, _ = connection(monkeypatch, headers=headers, chunks=chunks)
    with pytest.raises(ValueError):
        refresh.fetch_public()
    conn.close.assert_called_once()


def test_total_deadline(monkeypatch):
    conn, _ = connection(monkeypatch)
    clock = iter([0, 1, 11])
    monkeypatch.setattr(refresh.time, 'monotonic', lambda: next(clock))
    with pytest.raises(TimeoutError):
        refresh.fetch_public()
    conn.close.assert_called_once()


def test_cli_explicit_opt_in_and_failure_preserves_snapshot(monkeypatch, tmp_path, capsys):
    path = tmp_path / 'snapshot.json'
    path.write_text('original')
    fetch = Mock(side_effect=TimeoutError('sensitive transport text'))
    monkeypatch.setattr(refresh, 'fetch_public', fetch)
    monkeypatch.setattr(sys, 'argv', ['refresh', '--output', str(path)])
    with pytest.raises(SystemExit):
        refresh.main()
    fetch.assert_not_called()
    monkeypatch.setattr(sys, 'argv', ['refresh', '--live', '--output', str(path)])
    assert refresh.main() == 1
    assert path.read_text() == 'original'
    assert 'sensitive transport text' not in capsys.readouterr().out
