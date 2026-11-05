"""Independent audit financial vectors, adapted from evidence/financial/probes.py.

Original SHA256 196539928b62eca8e8e576b21d0b4d495c019bf14e88b92d1c0b61f334c5a289.
Expectations predate V4 implementation. Execution wrapping/temp placement changed;
the missing-reference ticket check also honors a failed preflight before construction.
This module is a callable probe library; pytest infrastructure tests live separately.
"""


def collect_financial(rows=None):
    from pathlib import Path
    import json
    from copy import deepcopy
    from dataclasses import replace
    from datetime import UTC, date, datetime, timedelta
    from decimal import Decimal as D, localcontext
    from zoneinfo import ZoneInfo

    from uptime import onboarding_rules as jira
    from uptime.contracts import Principal, Source
    from uptime import pricing, twilio
    from uptime.twilio_demo import demo_inputs
    from uptime.pricing_demo import load_agreement, load_demo_inputs
    from uptime import other_obligations as ob, reconciliation as rec
    from uptime.disputes_claimant import preflight, ticket_for
    from uptime.disputes_wire import FIXTURES

    rows=[] if rows is None else rows
    def record(id, observed, expected, category):
        rows.append(dict(id=id, category=category, observed=observed, expected=expected, matches=observed==expected))
    def result(r):
        value = r.amount.amount if r.amount else None
        # Fixed audit precision for sub-cent entitlements; representation is not a monetary defect.
        amount = format(value, '.4f') if value is not None and 0 < abs(value) < D('.01') else str(value) if value is not None else None
        return (r.outcome.value, amount)
    def price(r):
        return (r.evaluation.outcome.value, str(r.overcharge), [l.version for l in r.lines])
    T=demo_inputs()[0][1]
    I=T.intervals[0]
    A=load_agreement()
    N=load_demo_inputs()[0][1]
    tm='ELIGIBLE'
    gap='INSUFFICIENT_EVIDENCE'
    no='INELIGIBLE'
    unsupported='UNSUPPORTED_RULE'
    J=jira.compile_template(jira.fixture('extraction'))
    O=jira.fixture('overlay')
    F=jira.fixture('observations')
    USER=Principal(O['tenant'],'synthetic','viewer')
    def je(changes=None, overlay=None):
        return jira.evaluate(J,USER,O | (overlay or {}),F | (changes or {}))
    SCHED=twilio.Exclusion.SCHEDULED_MAINTENANCE
    def t_eval(intervals=None, **changes):
        return twilio.evaluate(replace(T,intervals=T.intervals if intervals is None else intervals,**changes))

    # Two real instants with the same IANA clock label during the November fallback.
    L=ZoneInfo('America/Los_Angeles')
    def fold(minute, n):
        return datetime(2026,11,1,1,minute,tzinfo=L,fold=n)
    # Amendment effective at 01:15 PST (09:15Z); all service is 01:30-01:45 PDT (08:30-08:45Z).
    amend=replace(A.versions[1],effective_at=fold(15,1))
    agreement=replace(A,versions=(A.versions[0],amend))
    line=replace(N.lines[0],start=fold(30,0),end=fold(45,0),quantity=D(1),net=D("20.00"))
    invoice=replace(N,lines=(line,),total=line.net)
    normalized=replace(agreement,versions=(A.versions[0],replace(amend,effective_at=amend.effective_at.astimezone(UTC))))
    utc_invoice=replace(invoice,lines=(replace(line,start=line.start.astimezone(UTC),end=line.end.astimezone(UTC)),))
    correct=(no,'0.00',['agreement-v1'])
    record('P-UTC-control',price(pricing.evaluate_price(normalized,utc_invoice)),correct,'control')
    record('P-fold-incorrect-version',price(pricing.evaluate_price(agreement,invoice)),correct,'defect')
    # Date binding should reject 09:30Z in a read when the mapped instant is 08:30Z.
    mapping=replace(invoice,id='synthetic-bind',provider_vendor_id='synthetic-vendor')
    provided=pricing.ProviderBill(mapping.id,mapping.total,'USD',mapping.payment_status,mapping.provider_vendor_id,
              Source.RAMP,True,'hypothetical-read',N.issued_at,'https://demo-api.ramp.com',
              (pricing.ProviderLine(line.id,start=fold(30,1)),))
    try:
        pricing.bind_sandbox_bill(provided,mapping)
        bound='accepted'
    except pricing.PricingInputError:
        bound='rejected'
    record('P-fold-conflicting-provider-date',bound,'rejected','defect')

    record('T-proven-month',result(t_eval()),(tm,'100.0000'),'control')
    # September 1 is disjoint from the October 10 incident and October month.
    unrelated=replace(I,start=datetime(2026,9,1,tzinfo=UTC),end=datetime(2026,9,1,0,6,tzinfo=UTC),customer_affected=None)
    record('T-distant-out-of-period-unknown',result(t_eval((I,unrelated))), (tm,'100.0000'),'defect')
    # Two IDs differ only by a trailing space. The invoice and underlying classification evidence are identical.
    twoline=replace(T.fees[0],id=T.fees[0].id+' ')
    record('T-padded-repeat',result(t_eval(fees=T.fees + (twoline,))),(gap,None),'defect')
    record('T-exact-repeat',result(t_eval(fees=T.fees + (T.fees[0],))),(gap,None),'control')

    # A clean money calculation alone does not establish that the dispute package can claim it.
    dossiers=json.loads((FIXTURES/'claimant'/'dossiers.json').read_text())
    dossier=deepcopy(dossiers['dispute-cure'])
    at=datetime(2026,11,3,12,tzinfo=UTC)
    record('D-known-ordinary-case',result(preflight(dossier,at)),(tm,'100.00'),'control')
    cent_dossier=deepcopy(dossier)
    cent_dossier['invoice_lines']=[{'id':'one-cent','kind':'affected_api','usd':'0.01'}]
    from test_v4_audit_protocol import scoped_dossier
    scoped_dossier(cent_dossier)
    record('D-cent-positive-W2',result(t_eval(fees=(replace(T.fees[0],amount=D('0.01')),))),(tm,'0.0010'),'control')
    record('D-cent-claim-drops-to-zero',result(preflight(cent_dossier,at)),(tm,'0.0010'),'defect')

    # No test field outside the claimant schema is necessary; all timestamps & source tags match.
    old=deepcopy(dossier)
    def historically(obj):
        if isinstance(obj,dict):
            return {k:historically(v) for k,v in obj.items()}
        if isinstance(obj,list):
            return [historically(v) for v in obj]
        return obj.replace('2026-10','2025-10') if isinstance(obj,str) else obj
    old=historically(old)
    record('D-predates-governing-SLA',result(preflight(old,at.replace(year=2025))),(unsupported,None),'defect')
    record('T-historical-version-control',result(t_eval(month=T.month.replace(year=2025))),(unsupported,None),'control')

    bad_doc=deepcopy(dossier)
    del bad_doc['initial_documents'][0]['ref']
    record('D-missing-doc-reference',result(preflight(bad_doc,at)),(gap,None),'defect')
    if preflight(bad_doc, at).outcome.value != tm:
        issued='blocked prior to approval'
    else:
        try:
            ticket_for(USER.tenant,bad_doc,[])
            issued='constructed'
        except KeyError as e:
            issued='KeyError '+str(e)
    record('D-missing-ref-at-ticket-construction',issued,'blocked prior to approval','defect')

    # Directly reserved operations and public-term branch invariants.
    e=datetime(2026,11,1,tzinfo=UTC)
    receipt=e+timedelta(days=30)-timedelta(microseconds=1)
    record('T-last-instant',result(t_eval(as_of=receipt)),(tm,'100.0000'),'control')
    record('T-first-late-instant',result(t_eval(as_of=receipt+timedelta(microseconds=1))),(no,None),'control')
    record('T-prior-receipt',result(t_eval(as_of=receipt+timedelta(days=31),submitted_at=receipt,submission_ref='sim-ticket-1')),(tm,'100.0000'),'control')
    record('T-no-attribution',result(t_eval((replace(I,customer_affected=None),))),(gap,None),'control')
    record('T-incomplete-status-month',result(t_eval(status_coverage=replace(T.status_coverage,complete=False))),(gap,None),'control')
    record('T-tax-carrier-third-party',result(t_eval(fees=T.fees[1:])),(no,None),'control')
    record('T-partial-coverage',result(t_eval(subscription_coverage=replace(T.subscription_coverage,start=T.subscription_coverage.start+timedelta(minutes=1)))),(gap,None),'control')
    record('T-connection-throughput',result(t_eval(basis=twilio.ClaimBasis.CONNECTION_RATE)),(unsupported,None),'boundary')
    def duration_test(minutes, **changes):
        return t_eval((replace(I,end=I.start+timedelta(minutes=minutes)),),**changes)
    # October has 44,640 minutes => 22m19.2s ordinary threshold boundary; enterprise 4m27.84s, min 5m.
    def secs(s,**changes):
        return result(t_eval((replace(I,end=I.start+timedelta(milliseconds=s)),),**changes))
    record('T-base-boundary-at',secs(1339200),(no,None),'control')
    record('T-base-boundary-above',secs(1339201),(tm,'100.0000'),'control')
    record('T-min-5-exact',secs(300000,plan=twilio.Plan.ENTERPRISE),(tm,'100.0000'),'control')
    record('T-min-below-5',secs(299999,plan=twilio.Plan.ENTERPRISE),(no,None),'control')
    c=datetime(2026,10,24)
    record('T-admin-before-cutoff',secs(300000,plan=twilio.Plan.ADMINISTRATION,administration_purchased_on=c.date().replace(year=2024)-timedelta(days=1)),(tm,'100.0000'),'control')
    record('T-admin-cutoff',secs(300000,plan=twilio.Plan.ADMINISTRATION,administration_purchased_on=c.date().replace(year=2024)),(no,None),'control')
    short=replace(I,end=I.start+timedelta(minutes=8))
    others=replace(short,start=I.start+timedelta(minutes=2),end=I.start+timedelta(minutes=6),exclusion=SCHED,scheduled_notice_hours=D('24'))
    record('T-exclusion-splits-short-spans',result(t_eval((short,others),plan=twilio.Plan.ENTERPRISE)),(no,None),'control')
    record('T-short-notice',result(t_eval((short,replace(others,scheduled_notice_hours=D('23.999'))),plan=twilio.Plan.ENTERPRISE)),(tm,'100.0000'),'control')
    month_start=datetime(2026,10,1,tzinfo=UTC)
    cross=replace(I,start=month_start-timedelta(minutes=2),end=month_start+timedelta(minutes=3))
    standalone=replace(I,end=I.start+timedelta(minutes=20))
    record('T-across-month-five-before-clipping',result(t_eval((standalone,cross))),(tm,'100.0000'),'control')
    record('T-across-month-fraction-under-five',result(t_eval((standalone,replace(cross,start=cross.start+timedelta(microseconds=1))))),(no,None),'control')

    # Jira calculations against public UTC month, authority, plans, exact bands and date edges.
    record('J-positive',result(je()),(tm,'120.00'),'control')
    record('J-explicit-vendor-aggregate', result(je({'monitor_source':'status_page'})),(gap,None),'control')
    record('J-threshold-operator',result(je({'monitor_rate_operator':'greater_or_equal'})),(gap,None),'control')
    record('J-june-43min-premium',result(je({'downtime_minutes':43})),(no,None),'control')
    record('J-june-44min-premium',result(je({'downtime_minutes':44})),(tm,'120.00'),'control')
    record('J-june-22min-enterprise',result(je({'downtime_minutes':22},{'plan':'Enterprise'})),(tm,'60.00'),'control')
    record('J-june-21min-enterprise',result(je({'downtime_minutes':21},{'plan':'Enterprise'})),(no,None),'control')
    record('J-99-exact',result(je({'downtime_minutes':432})),(tm,'120.00'),'control')
    record('J-99-below',result(je({'downtime_minutes':433})),(tm,'300.00'),'control')
    record('J-95-exact',result(je({'downtime_minutes':2160})),(tm,'300.00'),'control')
    record('J-95-below',result(je({'downtime_minutes':2161})),(tm,'600.00'),'control')
    record('J-on-time',result(je({'received_at':'2026-07-15T23:59:59.999999Z'})),(tm,'120.00'),'control')
    record('J-late',result(je({'received_at':'2026-07-16T00:00:00Z'})),(no,None),'control')
    record('J-sandbox',result(je({}, {'instance':'sandbox'})),(no,None),'control')
    record('J-general-surface',result(je({}, {'surface':'mobile'})),(no,None),'control')
    record('J-other-product',result(je({}, {'product':'Confluence'})),(unsupported,None),'boundary')
    record('J-reseller',result(je({}, {'agreement':'reseller'})),(unsupported,None),'boundary')
    record('J-technical-ticket',result(je({'tech_ticket_during_incident':False})),(no,None),'control')
    record('J-good-standing',result(je({'good_standing':False})),(tm,'120.00'),'defect')
    record('J-challenge-local-holiday',str(jira.challenge_through(J,datetime(2026,7,4,1,tzinfo=UTC),'America/Los_Angeles',{date(2026,7,6)})),'2026-07-09','control')
    record('J-unknown-holiday-list',jira.challenge_through(J,at,'UTC',None),None,'control')
    with localcontext() as ctx:
        ctx.prec=4
        record('J-ambient-rounding-alters-tier',result(je({'downtime_minutes':44})),(tm,'120.00'),'defect')

    # With under USD 100,000 in real spend, an ID alias flips an entire rebate on.
    def paid(id, amount):
        return dict(id=id,date='2026-09-30',product='Core',kind='paid',amount=amount,currency='USD')
    def rebate(charges,credits=None,**options):
        return result(ob.evaluate_rebate(dict(complete=True,through='2026-09-30',charges=charges,credits=credits or [])|options))
    single=paid('invoice-1','50000.00')
    record('B-single-below-threshold',rebate([single]),(no,None),'control')
    record('B-identical-repeat',rebate([single,single.copy()]),(no,None),'control')
    record('B-padded-repeat-triggers-tier',rebate([single,single|{'id':single['id']+' '}]),(gap,None),'defect')
    record('B-inclusive-and-earlier-credit',rebate([paid('c','110000'),paid('r','10000')|{'kind':'return'}],[dict(id='memo',clause='R-1',year_end='2026-09-30',amount='250',currency='USD')]),(tm,'1750.00'),'control')
    record('B-inclusive-minus-one-cent',rebate([paid('c','99999.99')]),(no,None),'control')
    record('B-only-closed-year',rebate([paid('c','100000')],through='2026-09-29'),(gap,None),'control')
    record('B-cross-currency',rebate([paid('c','100000')|{'currency':'EUR'}]),(unsupported,None),'boundary')

    # Undocumented blank evidence strings pass as substantiation on identical inputs.
    record('T-blank-document-provenance',result(t_eval((replace(I,documentation_refs=('   ',)),))),(gap,None),'defect')
    record('T-no-document-provenance',result(t_eval((replace(I,documentation_refs=()),))),(gap,None),'control')

    # Award matching checks one memo at a time. Construct honest intended distinct grants, one shared bill.
    def credit_inputs(name,bill_amount='100.00',grant='80.00'):
        base={'tenant':'bears','vendor_id':'fictional-api-vendor','currency':'USD'}
        award=base|dict(id='award-'+name,confirmed=True,memo_ref='memo-'+name,amount=grant,source='SIMULATED_VENDOR')
        credit=base|dict(id='credit-'+name,award_id=award['id'],memo_ref=award['memo_ref'],amount=grant,source='DETERMINISTIC_REPLAY')
        bill=base|dict(id='shared-bill',amount=bill_amount,source='SYNTHETIC_CUSTOMER')
        app=base|dict(id='app-'+name,credit_id=credit['id'],bill_id=bill['id'],amount=grant,source='DETERMINISTIC_REPLAY')
        return award,credit,app,bill
    def ledger(a,c,x,b):
        return rec.reconcile('bears',a,c,x,b)
    A1,C1,X1,B1=credit_inputs('one')
    A2,C2,X2,B2=credit_inputs('two')
    r1=ledger(A1,[C1,C1],[X1,X1],[B1,B1])
    r2=ledger(A2,[C2],[X2],[B2])
    record('R-idempotent-positive',(r1['awarded'],r1['posted'],r1['applied'],r1['actual_recovery']),('80.00','80.00','80.00',None),'control')
    shared_total = str(D(r1['applied'])+D(r2['applied']))
    try:
        ledger(A1,[C1],[X1],[B1|{'amount':'79.99'}])
        cap='accepted'
    except ValueError:
        cap='rejected'
    record('R-single-award-bill-cap',cap,'rejected','control')
    from test_v4_audit_protocol import is_v4
    if is_v4():
        import tempfile
        from uptime.allocations import settlement_reconciliation
        from uptime.storage import initialize, transition_settlement
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'one-cent.sqlite'
            initialize(path)
            reviewer = Principal('bears', 'qa-reviewer', 'reviewer')
            transition_settlement(path, reviewer, 'audit-one-cent', 'record-credit', '0.01')
            try:
                transition_settlement(path, reviewer, 'audit-one-cent', 'apply-partial', '0.01')
            except ValueError:
                pass
            tiny=settlement_reconciliation(path, 'bears', 'audit-one-cent', '0.01')
    else:
        tiny=rec.demo_reconciliation('0.01','PARTIALLY_APPLIED')
    record('R-zero-cent-partial-stage',(tiny['stage'],tiny['applied'],len(tiny['application_ids'])),('POSTED','0.00',0),'defect')
    # A mapping helper has no product or account-period test in its schema. Trace explicit contradictory facts.
    a=A1 | dict(product='Jira',account='customer-1',period='2026-10')
    b=B1 | dict(product='Confluence',account='customer-2',period='2026-09')
    wrong=ledger(a,[C1],[X1],[b])
    scoped_applied = wrong['applied']
    if is_v4():
        from test_v4_audit_ledger import allocation_counterexamples
        shared_total, scoped_applied = allocation_counterexamples()
    record('R-multi-award-same-bill-total', shared_total, '80.00', 'defect')
    record('R-different-product-account-before-award', scoped_applied, '0.00', 'defect')

    # Dated two-tier pricing has a separate graduation bucket per attested performance slice.
    for units,cost in [(999,14985),(1000,15000),(1001,15010)]:
        ul=replace(N.lines[0],quantity=D(units),net=D(cost))
        v=replace(N,lines=(ul,),total=D(cost))
        record('P-tier-'+str(units),price(pricing.evaluate_price(A,v)),(no,'0.00',['amendment-v2']),'control')
    v1,v2=A.versions
    for label,left,right,rate,version in [('end',-1,0,20,v1),('start',0,1,15,v2)]:
        ul=replace(N.lines[0],quantity=D(1),net=D(rate),start=v2.effective_at+timedelta(seconds=left),end=v2.effective_at+timedelta(seconds=right))
        record('P-amendment-'+label,price(pricing.evaluate_price(A,replace(N,lines=(ul,),total=ul.net))),(no,'0.00',[version.id]),'control')
    cross=replace(ul,start=v2.effective_at-timedelta(minutes=1),end=v2.effective_at+timedelta(minutes=1))
    record('P-unsplit-amendment',price(pricing.evaluate_price(A,replace(N,lines=(cross,),total=cross.net))),(gap,'None',[]),'boundary')
    for key,val in [('mode','all_units'),('quantity_scope','monthly_cumulative')]:
        custom=replace(v2,rates=(replace(v2.rates[0],**{key:val}),))
        record('P-unimplemented-'+key,price(pricing.evaluate_price(replace(A,versions=(v1,custom)),N)),(unsupported,'None',[]),'boundary')
    other=replace(v2,signed_at=v2.effective_at+timedelta(seconds=1))
    record('P-late-amendment',price(pricing.evaluate_price(replace(A,versions=(v1,other)),N)),(unsupported,'None',[]),'boundary')
    # Exercise genuine DRAFTED -> CLAIM_APPROVED entry points with only an isolated synthetic fixture root.
    import tempfile
    from unittest.mock import patch
    from uptime import disputes
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp)
        (base/'claimant').mkdir()
        (base/'claimant'/'dossiers.json').write_text(json.dumps({'dispute-audit-old':old}))
        reviewer=Principal('bears','synthetic-reviewer','reviewer')
        with patch.object(disputes,'FIXTURES',base):
            desk=disputes.DisputeDesk(base/'audit.sqlite',clock=lambda:at.replace(year=2025))
            desk.seed(reviewer.tenant)
            before=desk.case(reviewer,'dispute-audit-old')
            if before['actions']:
                after=desk.act(reviewer,'dispute-audit-old','approve-claim')
                actual=after['stage']
            else:
                actual='no approval action'
            record('D-desk-old-terms-can-approve',actual,'no approval action','defect')
    # Input advertised by its public read model as historical. Distinguish the timing of filing and issuance.
    standing=je({'good_standing':False})
    record('J-issuance-vs-filing', {
        'outcome': standing.outcome.value, 'amount': str(standing.amount.amount) if standing.amount else None,
        'filing': getattr(standing, 'filing_status', None), 'issuance': getattr(standing, 'issuance_status', None)},
        {'outcome': tm, 'amount': '120.00', 'filing': 'TIMELY', 'issuance': 'BLOCKED_ACCOUNT_STANDING'}, 'defect')
    # Individual authority/exclusion records examined when they have no economic effect on this claim.
    vscope=replace(T.service,api_id='mail-send',family=twilio.ServiceFamily.SENDGRID)
    sgrid=replace(I,api_id='mail-send',status_url='https://status.sendgrid.com/',end=I.start+timedelta(minutes=5))
    paidmail=replace(T.fees[0],kind=twilio.FeeKind.EMAIL_PACKAGE,api_id='mail-send')
    record('T-enhanced-SendGrid-region-is-not-availability-input',result(t_eval((sgrid,),service=vscope,plan=twilio.Plan.EMAIL_EXPERTS,fees=(paidmail,))),(tm,'100.0000'),'control')
    record('T-base-SendGrid-at-same-duration',result(t_eval((sgrid,),service=vscope,plan=twilio.Plan.BASE,fees=(paidmail,))),(no,None),'control')
    record('T-enhanced-SendGrid-independent-remedy',result(t_eval((),service=vscope,plan=twilio.Plan.EMAIL_EXPERTS,fees=(paidmail,))),(unsupported,None),'boundary')
    record('T-foreign-status-host',result(t_eval((replace(I,status_url='https://status.sendgrid.com'),))),(gap,None),'control')
    record('T-region-scope-dispute-preflight',result(preflight(dossier|{'region':'AU1'},at)),(gap,None),'control')

    # Deterministic randomized differential test. The oracle computes a Boolean minute mask, groups
    # consecutive true minutes, then clips to the October UTC measurement period.
    import random
    from itertools import groupby
    rng=random.Random(752949)
    origin=datetime(2026,10,1,tzinfo=UTC)
    differentials=[]
    for case_no in range(500):
        spans=[(rng.randrange(-13,30),rng.randrange(1,15),bool(rng.randrange(4)==0)) for _ in range(rng.randrange(1,7))]
        known=set()
        excluded=set()
        inc=[]
        for offset,length,exclude in spans:
            (excluded if exclude else known).update(range(offset,offset+length))
            inc.append(replace(I,start=origin+timedelta(minutes=offset),end=origin+timedelta(minutes=offset+length),
                               exclusion=twilio.Exclusion.EMERGENCY_MAINTENANCE if exclude else twilio.Exclusion.NONE))
        available=known-excluded
        runs=[list(g) for _,g in groupby(sorted(available),key=lambda m,n=iter(range(len(available))):m-next(n))]
        count=sum(sum(m>=0 for m in run) for run in runs if len(run)>=5)
        observed=result(t_eval(tuple(inc),plan=twilio.Plan.ENTERPRISE))
        expected=(tm,'100.0000') if count*10000>44640 else (no,None)
        if expected!=observed:
            differentials.append(case_no)
    record('T-500-overlap-gap-cross-boundary-patterns',differentials,[],'control')
    return rows
