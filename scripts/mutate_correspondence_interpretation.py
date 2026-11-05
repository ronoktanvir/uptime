"""Public guard mutations in isolated copies; never edits the real candidate."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
MUTATIONS=[
 ('context','uptime/correspondence_review.py',"if context['digest'] != digest:",'if False:', 'test_all_original_context_pins_are_server_derived_and_cannot_be_changed'),
 ('partition','uptime/correspondence_interpretation.py',"if cursor != len(text.encode('utf-8')):",'if False:', 'test_valid_source_span_cannot_omit_a_trailing_material_objection'),
 ('annotation','uptime/correspondence_interpretation.py','if covered != segment.source.end:','if False:', 'test_full_segment_cannot_hide_unannotated_material_outside_proposition'),
 ('quote','uptime/correspondence_interpretation.py',"if span.start >= span.end or raw[span.start:span.end] != span.quote.encode('utf-8'):",'if False:', 'test_grounding_and_residual_obligation_falsifiers'),
 ('allowlist','uptime/correspondence_model.py','if not self.enabled or self.provider is None or digest not in self.allowed_requests:','if not self.enabled or self.provider is None:', 'test_provider_requires_blind_entry_and_exact_full_outbound_manifest'),
 ('prepare','uptime/correspondence_review.py',"if preview['digest']!=body.preview_digest or not preview['prepare_allowed']:","if preview['digest']!=body.preview_digest:", 'test_semantic_uncertainty_cannot_prepare_a_disposition'),
 ('compound','uptime/correspondence_interpretation.py',"len(interpretation.propositions) != 1 or any(s.role == 'unsupported'", "False or any(s.role == 'unsupported'",'test_two_grounded_families_are_not_collapsed_to_one_disposition'),
 ('replay','uptime/correspondence_review.py',"or old['preview'] != body.preview_digest:",":",'test_conflicting_preparation_replay_cannot_rebind_an_accepted_review'),
 ('blind','uptime/correspondence_review.py',"        self._blind(db,p,claim_id,context)\n        row,review=", "        row,review=",'test_another_reviewer_must_enter_blind_before_previewing'),
]


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output-dir',type=Path,required=True); args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=False)
    files=sorted({m[1] for m in MUTATIONS})
    before={f:sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
    results=[]
    for name,file,old,new,test in MUTATIONS:
        target=args.output_dir/name; target.mkdir()
        for directory in ('uptime','tests','fixtures','web'):
            shutil.copytree(ROOT/directory,target/directory,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache'))
        shutil.copy(ROOT/'pyproject.toml',target/'pyproject.toml')
        source=(target/file).read_text()
        if source.count(old)!=1:raise ValueError('Mutation anchor changed: '+name)
        (target/file).write_text(source.replace(old,new))
        run=subprocess.run([sys.executable,'-m','pytest','-q','tests/test_correspondence_interpretation.py::'+test,'--basetemp='+str(target/'temp')],cwd=target,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
        (args.output_dir/(name+'.log')).write_bytes(run.stdout)
        killed=run.returncode==1 and b'FAILED tests/' in run.stdout and b'ERROR collecting' not in run.stdout
        results.append(dict(mutation=name,status='DETECTED' if killed else 'NOT_DETECTED',returncode=run.returncode,test=test))
    after={f:sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
    receipt=dict(results=results,source_before=before,source_after=after,source_stable=before==after)
    (args.output_dir/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'detected':sum(r['status']=='DETECTED' for r in results),'total':len(results),'source_stable':before==after}))


if __name__=='__main__': main()
