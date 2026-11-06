"""Source-locked reviewer interpretations and inert previews; no model authority."""
from copy import deepcopy
from dataclasses import asdict
from datetime import timedelta
import json

from .contracts import fingerprint
from .correspondence import authorize, audit
from .correspondence_history import apply_response_state, historical_reply, receipt_chain
from .correspondence_interpretation import Interpretation, primary_proposition_index, proposal_for_review, text_digest, validate_grounding, visible_source
from .correspondence_types import instant
from .storage import database

SCHEMA = '''
CREATE TABLE IF NOT EXISTS inbox_interpretation (
 id TEXT PRIMARY KEY, tenant TEXT NOT NULL, claim_id TEXT NOT NULL, actor TEXT NOT NULL,
 kind TEXT NOT NULL, context TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS inbox_interpretation_effect (
 review_id TEXT PRIMARY KEY, tenant TEXT NOT NULL, claim_id TEXT NOT NULL,
 preview TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL);
'''


def _fingerprint_at(rows, i):
    return fingerprint(rows[i]) if rows is not None and i < len(rows) else None


def alignment(proposed, blind_rows, candidate_rows, verdicts, count):
    """Positional audit: stable identity of blind, candidate and reviewed meaning at each index.

    Matches list every original index holding the identical reviewed proposition, so a
    reorder (allowed only as an explained correction) is explicit rather than inferred.
    """
    rows = []
    for i in range(count):
        reviewed = proposed[i] if i < len(proposed) else None
        rows.append(dict(index=i, verdict=verdicts[i], blind=_fingerprint_at(blind_rows, i),
                         candidate=_fingerprint_at(candidate_rows, i), reviewed=_fingerprint_at(proposed, i),
                         reviewed_matches_blind=[j for j, row in enumerate(blind_rows) if reviewed is not None and row == reviewed],
                         reviewed_matches_candidate=[j for j, row in enumerate(candidate_rows or []) if reviewed is not None and row == reviewed]))
    return rows


class InterpretationDesk:
    def __init__(self, desk, adapter=None):
        self.desk, self.adapter = desk, adapter
        with database(desk.path) as db:
            db.executescript(SCHEMA)

    def _context(self, db, p, claim_id):
        authorize(p)
        scope, state = self.desk._read(db, p.tenant, claim_id)
        if state['stage'] != 'HUMAN_REVIEW' or not state['replies'] or state['replies'][-1]['reason'] != 'unknown':
            raise ValueError('This bridge requires a current unresolved vendor reply.')
        reply = state['replies'][-1]
        facts = [e for e in state['evidence'] if e['kind'] == 'message' and e['digest'] == reply['digest']]
        if len(facts) != 1 or facts[0]['source'] != 'vendor':
            raise ValueError('An exact authenticated vendor message is required.')
        fact = facts[0]
        current = self.desk._assess(p.tenant, scope, state, self.desk._now())
        chain = receipt_chain(state)
        original = chain[0]['digest'] if chain else state['submissions'][0]['digest'] if state['submissions'] else None
        if not original:
            raise ValueError('The original filing is unavailable.')
        text = fact['body']['text']
        context = dict(tenant=p.tenant, claim=claim_id, scope=scope.model_dump(), receipt=reply['receipt'], original_digest=original,
                       event_digest=fact['digest'], text=text, text_sha256=text_digest(text),
                       requested=None if chain else state['submissions'][0]['requested'], currency=scope.currency,
                       contract_version=current.version, contract_source_sha256=current.contract_source_sha256,
                       evaluator_binding=self.desk._approval_binding(current), state_digest=fingerprint([scope.model_dump(), state]),
                       filing_fields=list(current.procedure['missing']) if current.procedure else [])
        context['digest'] = fingerprint(context)
        return context, scope, state, fact, current

    @staticmethod
    def _same(context, digest):
        if context['digest'] != digest:
            raise ValueError('Interpretation context changed; review the current original and evidence again.')

    def _put(self, db, p, claim_id, kind, context, body):
        now = self.desk._now()
        encoded = json.dumps(body)
        existing = db.execute('SELECT id FROM inbox_interpretation WHERE tenant=? AND claim_id=? AND actor=? AND kind=? AND context=? AND body=? AND expires_at>?',
                              (p.tenant,claim_id,p.subject,kind,context,encoded,now.isoformat())).fetchone()
        if existing:
            return existing['id']
        identity = fingerprint([p.tenant, claim_id, p.subject, kind, context, body, now.isoformat()])
        db.execute('INSERT OR IGNORE INTO inbox_interpretation VALUES(?,?,?,?,?,?,?,?,?)',
                   (identity,p.tenant,claim_id,p.subject,kind,context,now.isoformat(),(now+timedelta(minutes=30)).isoformat(),json.dumps(body)))
        return identity

    def _row(self, db, p, claim_id, kind, identity, context):
        row = db.execute('SELECT * FROM inbox_interpretation WHERE id=? AND tenant=? AND claim_id=? AND kind=?',
                         (identity,p.tenant,claim_id,kind)).fetchone()
        if not row or row['context'] != context['digest'] or instant(row['expires_at']) <= self.desk._now():
            raise ValueError('The interpretation record is absent, expired or stale.')
        return row, json.loads(row['body'])

    def _blind(self, db, p, claim_id, context):
        row = db.execute("SELECT * FROM inbox_interpretation WHERE tenant=? AND claim_id=? AND actor=? AND kind='blind' AND context=? ORDER BY created_at DESC LIMIT 1",
                         (p.tenant,claim_id,p.subject,context['digest'])).fetchone()
        if not row or instant(row['expires_at']) <= self.desk._now():
            raise ValueError('Enter your own semantic judgment before viewing any candidate.')
        return json.loads(row['body'])

    def view(self, p, claim_id):
        with database(self.desk.path) as db:
            context, *_ = self._context(db,p,claim_id)
            try:
                blind = self._blind(db,p,claim_id,context)
            except ValueError:
                blind = None
            candidates = []
            if blind is not None:
                for row in db.execute("SELECT * FROM inbox_interpretation WHERE tenant=? AND claim_id=? AND kind='candidate' AND context=? ORDER BY created_at",(p.tenant,claim_id,context['digest'])):
                    if instant(row['expires_at']) > self.desk._now():
                        candidates.append(dict(id=row['id'], **json.loads(row['body'])))
            return dict(context=context, visible_text=visible_source(context['text']), blind_entry=blind,
                        candidates=candidates, model_enabled=bool(self.adapter and self.adapter.enabled),
                        notice='Interpretations are allegations, not evidence or action permissions. Awards and denial closure are informational only.')

    def blind(self,p,claim_id,entry):
        authorize(p,True)
        with self.desk._write(p.tenant) as db:
            context,*_ = self._context(db,p,claim_id)
            self._same(context,entry.context_digest)
            validate_grounding(context['text'],entry.interpretation)
            # Blind entry cannot be revised after a candidate has been exposed.
            previous = db.execute("SELECT id FROM inbox_interpretation WHERE tenant=? AND claim_id=? AND actor=? AND context=? AND kind='blind' AND expires_at>?",(p.tenant,claim_id,p.subject,context['digest'],self.desk._now().isoformat())).fetchone()
            body=entry.interpretation.model_dump()
            if previous:
                _, old = self._row(db,p,claim_id,'blind',previous['id'],context)
                if old != body:
                    raise ValueError('Blind entry is immutable; reconcile differences in the review.')
                return dict(id=previous['id'])
            return dict(id=self._put(db,p,claim_id,'blind',context['digest'],body))

    def candidate(self,p,claim_id,entry):
        authorize(p,True)
        with self.desk._write(p.tenant) as db:
            context,*_=self._context(db,p,claim_id)
            self._same(context,entry.context_digest)
            self._blind(db,p,claim_id,context)
            validate_grounding(context['text'],entry.interpretation)
            body=dict(origin='manual',interpretation=entry.interpretation.model_dump())
            return dict(id=self._put(db,p,claim_id,'candidate',context['digest'],body))

    def snapshot(self,p,claim_id,expected_digest=None,require_blind=False):
        """Current server-derived context only; no candidate, provider or write effect."""
        if require_blind:
            authorize(p,True)
        # Submissions keep the existing write-mode (observe-only) gate; status reads do not.
        with (self.desk._write(p.tenant) if require_blind else database(self.desk.path)) as db:
            context,*_=self._context(db,p,claim_id)
            if expected_digest is not None:
                self._same(context,expected_digest)
            if require_blind:
                self._blind(db,p,claim_id,context)
        return context

    def has_blind(self,p,claim_id,context):
        with database(self.desk.path) as db:
            try:
                self._blind(db,p,claim_id,context)
            except ValueError:
                return False
        return True

    def store_model_result(self,p,claim_id,context_digest,result):
        """Attach one inert model candidate atomically, only to the exact current context.

        Re-checks the actor's own blind entry, candidate shape and grounding in the same
        write transaction. Never reviews, previews, prepares or acts.
        """
        authorize(p,True)
        if (not isinstance(result,dict) or set(result)!={'interpretation','provenance'}
                or not isinstance(result['provenance'],dict) or not isinstance(result['provenance'].get('request_sha256'),str)):
            raise ValueError('The model result is not an inert, attributable proposal.')
        interpretation=Interpretation.model_validate(result['interpretation'])
        with self.desk._write(p.tenant) as db:
            latest,*_=self._context(db,p,claim_id)
            self._same(latest,context_digest)
            self._blind(db,p,claim_id,latest)
            validate_grounding(latest['text'],interpretation)
            body=dict(origin='model',interpretation=interpretation.model_dump(),provenance=result['provenance'],
                      source=dict(context_digest=latest['digest'],event_digest=latest['event_digest'],
                                  text_sha256=latest['text_sha256'],original_digest=latest['original_digest']))
            return self._put(db,p,claim_id,'candidate',latest['digest'],body)

    def model(self,p,claim_id,entry):
        authorize(p,True)
        # No database write lock or privileged source is held across provider IO.
        context=self.snapshot(p,claim_id,entry.context_digest,require_blind=True)
        if self.adapter is None:
            raise PermissionError('External interpretation is disabled.')
        result=self.adapter.propose(context)
        interpretation=Interpretation.model_validate(result['interpretation'])
        validate_grounding(context['text'],interpretation)
        return dict(id=self.store_model_result(p,claim_id,context['digest'],result))

    def review(self,p,claim_id,entry):
        authorize(p,True)
        with self.desk._write(p.tenant) as db:
            context,*_=self._context(db,p,claim_id)
            self._same(context,entry.context_digest)
            blind=self._blind(db,p,claim_id,context)
            validate_grounding(context['text'],entry.interpretation)
            candidate=None
            if entry.candidate_id:
                _, candidate=self._row(db,p,claim_id,'candidate',entry.candidate_id,context)
            proposed=entry.interpretation.model_dump()['propositions']
            blind_rows=blind['propositions']
            candidate_rows=candidate['interpretation']['propositions'] if candidate else None
            originals=[blind_rows] + ([candidate_rows] if candidate else [])
            count=max(len(proposed),len(blind_rows),len(candidate_rows) if candidate else 0)
            if (not entry.residuals_reviewed or not entry.complete_meaning_reviewed
                    or sorted(r.proposition for r in entry.resolutions) != list(range(count))):
                raise ValueError('A separate decision for each proposition and all residual obligations is required.')
            verdicts={r.proposition:r.verdict for r in entry.resolutions}
            for i in range(count):
                if i>=len(proposed) and verdicts[i]!='reject':
                    # A correction or acceptance can never silently remove an original meaning.
                    raise ValueError('A proposition absent from the reviewed meaning must be explicitly rejected.')
                if verdicts[i]=='accept' and any(i>=len(proposed) or i>=len(rows) or proposed[i]!=rows[i] for rows in originals):
                    raise ValueError('Changed semantic judgments require an explicit correction and explanation.')
            body=entry.model_dump()
            body['alignment']=alignment(proposed,blind_rows,candidate_rows,verdicts,count)
            body['actor']=p.subject
            body['authority']='authenticated_reviewer_interpretation_only'
            return dict(id=self._put(db,p,claim_id,'review',context['digest'],body))

    def _preview(self,db,p,claim_id,review_id):
        authorize(p,True)
        context,scope,state,fact,current=self._context(db,p,claim_id)
        self._blind(db,p,claim_id,context)
        row,review=self._row(db,p,claim_id,'review',review_id,context)
        interpretation=Interpretation.model_validate(review['interpretation'])
        proposal=proposal_for_review(context,interpretation)
        primary=primary_proposition_index(context,interpretation)
        projected=deepcopy(state)
        stage='HUMAN_REVIEW'
        if any(r['verdict']=='reject' for r in review['resolutions']):
            proposal=type(proposal)('unknown')
        if proposal.reason=='unknown':
            primary=None
        if proposal.reason not in {'unknown','award'}:
            projected['replies'].pop()
            if receipt_chain(projected):
                reply=historical_reply(projected,fact,self.desk._now(),proposal)
                reply['sources']=state['replies'][-1].get('sources',[])
                if proposal.reason=='filing_fields':
                    reply['requested_fields']=interpretation.propositions[primary].filing_fields
                projected['replies'].append(reply)
                apply_response_state(projected,current)
            else:
                self.desk._reply_proposal(p.tenant,scope,projected,fact,self.desk._now(),proposal)
            stage=projected['stage']
        projected['interpretation_review']=dict(review_id=review_id,context_digest=context['digest'],event_digest=context['event_digest'],text_sha256=context['text_sha256'],contract_version=context['contract_version'],contract_source_sha256=context['contract_source_sha256'])
        prepare=stage in {'RESPONSE_DRAFTED','NEEDS_EVIDENCE','AWAITING_NOTICE'}
        packet=None
        if stage=='RESPONSE_DRAFTED':
            try:
                packet=self.desk._packet(p.tenant,claim_id,scope,projected,current)
            except ValueError:
                prepare=False
        if projected['awarded'] != state['awarded']:
            raise ValueError('An interpretation preview cannot create awarded money.')
        preview=dict(review_id=review_id,context_digest=context['digest'],interpretation=asdict(proposal),
                     disposition=stage if prepare else 'INFORMATIONAL_REVIEW',prepare_allowed=prepare,packet=packet,
                     reported_award=proposal.amount if proposal.reason=='award' else None,
                     closure_suggested=stage=='DENIAL_ACCEPTED',ledger_unchanged=True,external_actions=[],
                     reviewer=row['actor'],expires_at=row['expires_at'],
                     reviewed_interpretation=interpretation.model_dump(),primary_proposition_index=primary,
                     # Every other proposition is retained for display only; never award or action authority.
                     retained_propositions=[dict(index=i,family=q.family,polarity=q.polarity,modality=q.modality,referent=q.referent,
                                                 source=q.source.model_dump(),effect='informational_only')
                                            for i,q in enumerate(interpretation.propositions) if i!=primary],
                     alignment=review.get('alignment',[]))
        preview['digest']=fingerprint(preview)
        return preview,projected,context,scope

    def preview(self,p,claim_id,review_id):
        with database(self.desk.path) as db:
            return self._preview(db,p,claim_id,review_id)[0]

    def prepare(self,p,claim_id,body):
        authorize(p,True)
        with self.desk._write(p.tenant) as db:
            old=db.execute('SELECT * FROM inbox_interpretation_effect WHERE review_id=?',(body.review_id,)).fetchone()
            if old:
                if old['tenant'] != p.tenant or old['claim_id'] != claim_id or old['preview'] != body.preview_digest:
                    raise ValueError('Conflicting interpretation preparation replay.')
            else:
                preview,projected,context,scope=self._preview(db,p,claim_id,body.review_id)
                if preview['digest']!=body.preview_digest or not preview['prepare_allowed']:
                    raise ValueError('The exact current evidence-backed preview must permit preparation.')
                projected['approval']=None
                projected['replies'][-1]['reviewed_interpretation']=body.review_id
                projected['replies'][-1]['original_reason']='unknown'
                audit(projected,self.desk._now(),p.subject,'Prepared a reviewed interpretation using unchanged signed source and independently verified evidence.',review_id=body.review_id,preview=body.preview_digest)
                self.desk._save(db,p.tenant,claim_id,projected)
                db.execute('INSERT INTO inbox_interpretation_effect VALUES(?,?,?,?,?,?)',(body.review_id,p.tenant,claim_id,body.preview_digest,p.subject,self.desk._now().isoformat()))
        return self.desk.case(p,claim_id)
