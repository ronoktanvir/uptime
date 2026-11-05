"""Filesystem custody and exact installation checks, with no provider network."""
import json
import os
from pathlib import Path
import socket
import traceback

import pytest

from uptime import ramp_credentials as credentials, ramp_native_binding as native
from uptime.ramp import RampError, SandboxRampProvider, Token
from uptime.ramp_installation import browser_bill_id, verify_browser_bill


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('No real credential test network'))


@pytest.fixture
def profile(tmp_path, monkeypatch):
    home = tmp_path.resolve()/'home'
    folder = home/'.config/uptime'
    folder.mkdir(parents=True, mode=0o700)
    path = folder/'ramp-sandbox.json'
    path.write_text(json.dumps({'base_url':credentials.ORIGIN,'client_id':'test-client','client_secret':'SECRET_MARKER'}))
    path.chmod(0o600)
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls:home))
    monkeypatch.setenv('RAMP_ENV','sandbox')
    monkeypatch.setenv('RAMP_BASE_URL',credentials.ORIGIN)
    monkeypatch.delenv(credentials.SELECTOR, raising=False)
    return path


def test_default_and_explicit_profiles_use_shared_loader_and_hide_secrets(profile, monkeypatch):
    calls = []
    real = credentials.load
    def observed(path=None):
        calls.append(path)
        return real(path)
    monkeypatch.setattr(credentials,'load',observed)
    first = SandboxRampProvider()
    assert native._credentials() == first._basic
    assert calls == [profile,None]
    value = real()
    assert 'SECRET_MARKER' not in repr(value) and value.basic not in repr(value)
    second = profile.with_name('ramp-demo-native.json')
    second.write_text(profile.read_text().replace('test-client','new-test-client'))
    second.chmod(0o600)
    monkeypatch.setenv(credentials.SELECTOR,str(second))
    assert native._credentials() == SandboxRampProvider()._basic != first._basic
    assert real().client_fingerprint != first.client_fingerprint
    assert first._credential_path == profile  # Existing read adapter retains its original selection.


@pytest.mark.parametrize('fault', ['relative','empty','missing','symlink','ancestor-symlink','hardlink','shared-file',
    'shared-parent','writable-ancestor','directory','fifo','oversize','bad-json','duplicate','unknown','non-dict',
    'number','null','empty-secret','newline','space','unicode','colon-client','wrong-origin','wrong-env'])
def test_unsafe_credentials_refuse_without_leaking(profile, monkeypatch, fault):
    if fault == 'relative': monkeypatch.setenv(credentials.SELECTOR,'relative.json')
    elif fault == 'empty': monkeypatch.setenv(credentials.SELECTOR,'')
    elif fault == 'missing': profile.unlink()
    elif fault in {'symlink','ancestor-symlink'}:
        link = profile.with_name('link')
        link.symlink_to(profile if fault == 'symlink' else profile.parent, target_is_directory=fault != 'symlink')
        monkeypatch.setenv(credentials.SELECTOR,str(link if fault == 'symlink' else link/profile.name))
    elif fault == 'hardlink': os.link(profile,profile.with_name('copy'))
    elif fault == 'shared-file': profile.chmod(0o644)
    elif fault == 'shared-parent': profile.parent.chmod(0o755)
    elif fault == 'writable-ancestor': profile.parent.parent.chmod(0o777)
    elif fault == 'directory': profile.unlink(); profile.mkdir(mode=0o700)
    elif fault == 'fifo': profile.unlink(); os.mkfifo(profile,mode=0o600)
    elif fault == 'oversize': profile.write_text('SECRET_MARKER'*2000)
    elif fault == 'bad-json': profile.write_text('{SECRET_MARKER')
    elif fault == 'duplicate': profile.write_text(profile.read_text()[:-1]+',"client_secret":"SECOND_SECRET_MARKER"}')
    elif fault == 'non-dict': profile.write_text('["SECRET_MARKER"]')
    elif fault == 'wrong-env': monkeypatch.setenv('RAMP_ENV','production')
    else:
        value = json.loads(profile.read_text())
        if fault == 'unknown': value['extra']='SECRET_MARKER'
        elif fault == 'colon-client': value['client_id']='bad:id'
        elif fault == 'wrong-origin': value['base_url']='https://api.ramp.com'
        else: value['client_secret']={'number':123,'null':None,'empty-secret':'','newline':'SECRET_MARKER\r\n',
                                      'space':'SECRET MARKER','unicode':'SECRET_MARKERé'}[fault]
        profile.write_text(json.dumps(value))
    with pytest.raises((credentials.CredentialError, RampError)) as caught:
        SandboxRampProvider()
    assert 'SECRET_MARKER' not in ''.join(traceback.format_exception(caught.value))
    assert 'SECRET_MARKER' not in str(caught.value)


def test_swap_to_symlink_between_check_and_open_is_refused(profile, monkeypatch):
    real_open = os.open
    def raced(path, flags, *args, **kwargs):
        if path == profile.name and kwargs.get('dir_fd') is not None:
            preserved = profile.with_name('preserved.json')
            profile.rename(preserved)
            profile.symlink_to(preserved)
        return real_open(path,flags,*args,**kwargs)
    monkeypatch.setattr(os,'open',raced)
    with pytest.raises(credentials.CredentialError): credentials.load()


def test_native_binding_captures_profile_at_construction(tmp_path, monkeypatch):
    from test_ramp_native_binding import Installation
    i = Installation(tmp_path.resolve(), monkeypatch)
    original = i.binding._credential_path
    monkeypatch.setenv(credentials.SELECTOR,str(tmp_path.resolve()/'missing-other-profile.json'))
    try:
        assert i.binding.preflight()['preflight']['comment_ready'] is True
        assert i.binding._credential_path == original
    finally:
        i.binding.close(); i.client.close()


BILL = '20000000-0000-4000-8000-000000000001'
BUSINESS = '10000000-0000-4000-8000-000000000001'
URL = 'https://demo.ramp.com/bill-pay/bills/list/'+BILL


class ReadProvider:
    _basic = 'synthetic-test-auth'
    client_fingerprint = 'a'*64
    def __init__(self):
        self.calls=[]; self.returned_id=BILL; self.granted={'bills:read'}
    def _http(self, method, path, headers, body=None):
        self.calls.append((method,path))
        if (method,path)==('POST','token'):
            assert body=='grant_type=client_credentials&scope=business%3Aread'
            return {'access_token':'synthetic','token_type':'bearer','scope':'business:read'}
        assert (method,path)==('GET','business')
        return {'id':BUSINESS}
    def token(self, scopes):
        assert scopes=={'bills:read'}
        return Token('synthetic',frozenset(self.granted),frozenset(scopes),True)
    def request(self, token, method, path):
        self.calls.append((method,path))
        assert (method,path)==('GET','bills/'+BILL)
        return {'id':self.returned_id,'status':'OPEN','approval_status':'PENDING','vendor':{'id':BUSINESS},'entity_id':BUSINESS,
                'amount':{'amount':84000,'currency_code':'USD','minor_unit_conversion_rate':100}}


def test_one_bill_association_uses_exact_read_and_declares_limits():
    provider=ReadProvider()
    result=verify_browser_bill(provider,URL)
    assert result['bill_id']==BILL and result['business_id']==BUSINESS
    assert result['browser_url']==URL and result['client_id_sha256']=='a'*64
    assert result['status']=='ONE_BILL_READ_VERIFIED' and result['write_attempted'] is False
    assert result['inventory_comparison'] is False
    assert provider.calls==[('POST','token'),('GET','business'),('GET','bills/'+BILL)]


@pytest.mark.parametrize('url',[URL+'/',URL+'?x=1',URL+'#x',URL.replace('demo.ramp.com','app.ramp.com'),
    URL.replace('demo.ramp.com','demo.ramp.com.attacker.invalid'),URL.replace('https://','http://'),
    URL.replace('/list/','/'),URL.replace('/list/','/list/%2e%2e/'),URL.replace('demo.ramp.com','demo.ramp.com:443'),
    URL.replace('demo.ramp.com','user@demo.ramp.com')])
def test_browser_association_rejects_unobserved_routes_before_network(url):
    provider=ReadProvider()
    with pytest.raises(RampError): verify_browser_bill(provider,url)
    assert provider.calls==[]


@pytest.mark.parametrize('fault',['wrong-id','extra-grant','missing-grant'])
def test_api_mismatch_never_becomes_browser_association(fault):
    provider=ReadProvider()
    if fault=='wrong-id': provider.returned_id=BUSINESS
    elif fault=='extra-grant': provider.granted.add('bills:write')
    else: provider.granted=set()
    with pytest.raises(RampError): verify_browser_bill(provider,URL)
