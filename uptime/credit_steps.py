"""Exact completed percentage-point shortfalls; no display or intermediate rounding.

This operator contains no vendor, fixture, model or authorization lookup. The
source compiler and caller establish the cited rule and trusted evidence scope.
"""
UNITS_PER_PERCENT = 1_000_000
HUNDRED_PERCENT = 100 * UNITS_PER_PERCENT
KIND = 'completed_steps'
FIELDS = {'kind','product','plan','target_units','step_units','credit_units','cap_units','citation'}


def validate(rule):
    if not isinstance(rule,dict) or set(rule)!=FIELDS or rule.get('kind')!=KIND:
        raise ValueError('Unsupported credit rule variant.')
    if any(not isinstance(rule[k],str) or not rule[k] or len(rule[k])>100 for k in ('product','plan')):
        raise ValueError('A source-cited product and plan are required.')
    if any(type(rule[k]) is not int for k in ('target_units','step_units','credit_units','cap_units','citation')):
        raise ValueError('Exact bounded integer rule units are required.')
    if (not 0 < rule['step_units'] <= rule['target_units'] <= HUNDRED_PERCENT
            or not 0 < rule['credit_units'] <= rule['cap_units'] <= HUNDRED_PERCENT or rule['citation'] < 1):
        raise ValueError('Completed-step rule bounds are invalid.')
    return rule


def from_manifest(manifest):
    if 'credit_rule' not in manifest:
        return None
    rule=validate(manifest['credit_rule'])
    if ('tiers' in manifest or manifest.get('credit_rounding')!='nearest_cent_half_up'
            or manifest.get('family')!='monthly-availability/1'):
        raise ValueError('Completed-step rules require exclusive scope and explicit final HALF_UP rounding.')
    return rule


def completed(rule,available,total):
    validate(rule)
    if type(available) is not int or type(total) is not int or not 0 <= available <= total <= 10**18 or total == 0:
        raise ValueError('Bounded exact available/total measurement integers are required.')
    shortfall=max(0,rule['target_units']*total-HUNDRED_PERCENT*available)
    return shortfall//(rule['step_units']*total)


def rate(rule,available,total):
    return min(completed(rule,available,total)*rule['credit_units'],rule['cap_units'])


def final_cents(fee_cents,credit_units):
    if (type(fee_cents) is not int or not 0 <= fee_cents <= 10**15
            or type(credit_units) is not int or not 0 <= credit_units <= HUNDRED_PERCENT):
        raise ValueError('Nonnegative bounded fee cents and credit units are required.')
    return (2*fee_cents*credit_units+HUNDRED_PERCENT)//(2*HUNDRED_PERCENT)
