"""Rejection evidence can be revalidated locally but never occupies the accepted artifact path."""
from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

from uptime.vendor_model import MODEL, RejectedProposal, generate, replay_rejection, save_rejection, staged_extraction
from uptime.vendor_terms import Document


def test_model_semantic_rejection_is_separate_immutable_and_replayable(tmp_path,monkeypatch):
    document=Document(name='Synthetic precedence test',uri='urn:synthetic:precedence',classification='synthetic_public',
                      text='The other agreement establishes additional eligibility conditions.')
    digest=sha256(document.text.encode()).hexdigest()
    payload={'blocks':[{'id':1,'value':{'unsupported':'Unpinned external eligibility conditions.'}}]}
    def runner(args,**kwargs):
        assert 'tenant-private-account' not in kwargs['input'] and 'synthetic-local-auth' not in kwargs['input']
        return SimpleNamespace(returncode=0,stdout=json.dumps({'session_id':'synthetic-test-rejection','is_error':False,
                             'modelUsage':{MODEL:{}},'result':json.dumps(payload)}))
    monkeypatch.setenv('CLAUDE_CODE_OAUTH_TOKEN','synthetic-local-auth')
    monkeypatch.setattr('uptime.vendor_model.subprocess.run',runner)
    with pytest.raises(RejectedProposal) as err:
        generate(document,digest,allow_propositions=True,profile='resource-month')
    path=save_rejection(err.value.receipt,tmp_path)
    assert path.parent==tmp_path/'rejections'/digest and not (tmp_path/(digest+'.json')).exists()
    assert save_rejection(err.value.receipt,tmp_path)==path
    saved=json.loads(path.read_text())
    assert saved['raw_proposal']==payload and saved['session']=='synthetic-test-rejection'
    assert 'synthetic-local-auth' not in path.read_text()
    monkeypatch.setattr('uptime.vendor_model.subprocess.run',lambda *a,**kw:pytest.fail('offline replay contacted model'))
    assert replay_rejection(document,path,digest)['current_validation']=='REJECTED'
    with pytest.raises(ValueError,match='integrity'):
        replay_rejection(document,path,'0'*64)
    monkeypatch.setenv('UPTIME_PUBLIC_EXTRACTIONS',str(tmp_path))
    with pytest.raises(ValueError):
        staged_extraction(document)
    path.chmod(0o600)
    path.write_text(json.dumps(saved|{'raw_proposal':{'blocks':[]}}))
    with pytest.raises(ValueError,match='integrity'):
        replay_rejection(document,path,digest)
