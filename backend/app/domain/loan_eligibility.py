"""Hard requirements for a loan offer. Each rule returns its outcome with a reason."""

from __future__ import annotations

from app.domain.models import BusinessProfile, LoanOffer, NumericRange
from app.domain.results import Eligibility, Outcome, RuleResult, build_eligibility, compare_minimum


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _years(value: float) -> str:
    return f"{value:g} year{'s' if value != 1 else ''}"


def check_state(business: BusinessProfile, offer: LoanOffer) -> RuleResult:
    rule = offer.state_rule
    base = dict(rule="state", label="State availability", required=rule.raw, actual=business.state)
    if rule.mode == "all":
        return RuleResult(**base, outcome=Outcome.PASS, reason=f"{offer.lender} lends in all states.")
    listed = business.state in rule.states
    available = listed if rule.mode == "only" else not listed
    if available:
        return RuleResult(**base, outcome=Outcome.PASS, reason=f"{offer.lender} lends in {business.state_name}.")
    return RuleResult(**base, outcome=Outcome.FAIL, reason=f"{offer.lender} does not lend in {business.state_name}.")


def _check_minimum(
    rule: str,
    label: str,
    actual: NumericRange | None,
    actual_label: str | None,
    minimum: float,
    minimum_label: str,
    noun: str,
) -> RuleResult:
    base = dict(rule=rule, label=label, required=f"at least {minimum_label}", actual=actual_label or "not on file")
    outcome = compare_minimum(actual, minimum)
    if actual is None:
        reason = f"Requires {noun} of at least {minimum_label}; yours is not on file."
    elif outcome is Outcome.PASS:
        reason = f"Your {noun} ({actual_label}) meets the minimum of {minimum_label}."
    elif outcome is Outcome.FAIL:
        reason = f"Your {noun} ({actual_label}) is below the minimum of {minimum_label}."
    else:
        reason = (
            f"Borderline: your {noun} range ({actual_label}) includes values above and below "
            f"the minimum of {minimum_label}. Confirm your exact figure."
        )
    return RuleResult(**base, outcome=outcome, reason=reason)


def check_credit_score(business: BusinessProfile, offer: LoanOffer) -> RuleResult:
    if offer.min_credit_score is None:
        return RuleResult(
            rule="credit_score",
            label="Minimum credit score",
            outcome=Outcome.NOT_APPLICABLE,
            reason="No minimum credit score is published.",
            actual=business.credit_score_label,
        )
    result = _check_minimum(
        "credit_score",
        "Minimum credit score",
        business.credit_score,
        business.credit_score_label,
        offer.min_credit_score,
        str(offer.min_credit_score),
        "credit score",
    )
    if result.outcome is Outcome.FAIL and offer.credit_flexible:
        # The dataset says the lender makes exceptions, so a miss is not a confirmed failure.
        result.outcome = Outcome.NEEDS_VERIFICATION
        result.reason += f" The lender notes \"{offer.credit_note}\", so ask whether you qualify."
    elif offer.credit_note:
        result.reason += f" Lender note: {offer.credit_note}."
    return result


def check_revenue(business: BusinessProfile, offer: LoanOffer) -> RuleResult:
    base = dict(rule="annual_revenue", label="Minimum annual revenue", actual=business.revenue_label or "not on file")
    if offer.revenue_rule_text:
        return RuleResult(
            **base,
            outcome=Outcome.NEEDS_VERIFICATION,
            required=offer.revenue_rule_text,
            reason=f"The lender requires: \"{offer.revenue_rule_text}\". This cannot be checked from your profile.",
        )
    if offer.min_revenue is None:
        return RuleResult(**base, outcome=Outcome.NOT_APPLICABLE, reason="No minimum annual revenue is published.")
    if offer.min_revenue <= 0:
        return RuleResult(**base, outcome=Outcome.PASS, required="none", reason="No minimum revenue; startups are welcome.")
    return _check_minimum(
        "annual_revenue",
        "Minimum annual revenue",
        business.revenue,
        business.revenue_label,
        offer.min_revenue,
        _money(offer.min_revenue),
        "annual revenue",
    )


def check_years_in_business(business: BusinessProfile, offer: LoanOffer) -> RuleResult:
    base = dict(
        rule="years_in_business",
        label="Minimum time in business",
        actual=business.years_in_business_label or "not on file",
    )
    if offer.min_years is None:
        return RuleResult(**base, outcome=Outcome.NOT_APPLICABLE, reason="No minimum time in business is published.")
    if offer.min_years <= 0:
        return RuleResult(**base, outcome=Outcome.PASS, required="none", reason="No minimum time in business.")
    return _check_minimum(
        "years_in_business",
        "Minimum time in business",
        business.years_in_business,
        business.years_in_business_label,
        offer.min_years,
        _years(offer.min_years),
        "time in business",
    )


LOAN_RULES = (check_state, check_credit_score, check_revenue, check_years_in_business)


def classify_loan(business: BusinessProfile, offer: LoanOffer) -> Eligibility:
    checks = [rule(business, offer) for rule in LOAN_RULES]
    warnings = list(offer.limitations)
    warnings.append("Lenders make the final decision after reviewing a full application.")
    return build_eligibility(checks, warnings)
