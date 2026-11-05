"""Reissue LOCAL_TEST_SIGNATURE specimens after deliberate authored source edits.

Run from the repository root with `python -m fixtures.northwind.refresh_integrity`.
This writes fixture hashes/citations only. It cannot issue operational grants,
human approvals, provider certificates or commercial signatures. Git preserves
prior source/specimen revisions; private specimen key material is discarded.
"""
import base64
from datetime import datetime,UTC
from hashlib import sha256
import json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from .loader import ROOT,INPUTS


def refresh(root=ROOT):
    def read(name):return json.loads((root/name).read_text())
    def write(name,value):(root/name).write_text(json.dumps(value,indent=2)+'\n')
    agreement=read('agreement.json')
    for version in agreement['versions']:
        version['source_sha256']=sha256((root/version['source_file']).read_bytes()).hexdigest()
        for rate in version['rates']:
            if fixed:=rate.get('fixed_monthly'):
                fixed['source_text']=(root/fixed['source_file']).read_text()
                fixed['source_sha256']=sha256(fixed['source_text'].encode()).hexdigest()
    write('agreement.json',agreement)
    citations=[]
    for name in ('order-form.txt','amendment-2026-03.txt','order-monthly-rate.txt','amendment-monthly-rate.txt'):
        source=(root/name).read_text();cursor=0
        for index,line in enumerate(source.splitlines(keepends=True),1):
            quote=line.rstrip('\r\n')
            citations.append(dict(id=f'{name}:{index}',source_file=name,source_sha256=sha256(source.encode()).hexdigest(),
                                  start=cursor,end=cursor+len(quote),quote=quote,quote_sha256=sha256(quote.encode()).hexdigest()))
            cursor+=len(line)
    write('citations.json',citations)
    settlement=read('settlement_invoice.json')
    citation=next(c for c in citations if c['id']=='amendment-2026-03.txt:4')
    settlement['unchanged_sla']=dict(sla_source_sha256=sha256(read('document.json')['text'].encode()).hexdigest(),
                                    citation_id=citation['id'],citation=citation)
    write('settlement_invoice.json',settlement)
    records=read('signatures.json')
    if any(row.get('kind')!='LOCAL_TEST_SIGNATURE' or row.get('certificate') is not None for row in records):
        raise ValueError('Only explicitly local signature specimens can be reissued.')
    key=Ed25519PrivateKey.generate()
    public=base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).decode()
    for row in records:
        row['public_key_base64']=public
        payload=row['payload'];payload['created_at']=datetime.now(UTC).isoformat()
        payload['source_sha256']=sha256((root/payload['source_file']).read_bytes()).hexdigest()
        payload['pricing_input_sha256']=sha256((root/'agreement.json').read_bytes()).hexdigest()
        row['signature_base64']=base64.b64encode(key.sign(json.dumps(payload,sort_keys=True,separators=(',',':')).encode())).decode()
    write('signatures.json',records)
    index=read('package.json');index['input_sha256']={name:sha256((root/name).read_bytes()).hexdigest() for name in INPUTS}
    write('package.json',index)


if __name__=='__main__':refresh()
