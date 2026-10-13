"""Flag eligibility criteria that a grant states but the matcher cannot evaluate.

This does not interpret the criteria. It only recognises, by topic keywords, that a clause in
the criteria column sets a requirement (a revenue cap, an employee limit, a licence, ...), so
the grant can be marked Needs Verification instead of Likely Eligible. Only the criteria
column is read; descriptions are promotional and never trigger a flag.
"""

from __future__ import annotations

import re

from app.data import requirements as rq
from app.domain.models import CriterionTopic, UncheckedCriterion

I = re.IGNORECASE

# The clause says there is no such requirement ("No minimum revenue or business age").
_NO_REQUIREMENT = re.compile(
    r"\bno (\w+ )?(minimum|maximum|requirements?|restrictions?|limits?)\b|not required|regardless|"
    r"\bany (stage|size|industry)\b|\ball (stages|sizes|industries)\b",
    I,
)
# The clause is about how to apply, what is awarded or how funds are used, not who qualifies.
_PROCESS = re.compile(
    r"\bapply\b|\bapplications?\b|\bdeadlines?\b|\bdue\b|\bsubmi(t|ts|tted|ssion)\b|\bfees?\b|announc|\bcycles?\b|"
    r"\bcontact\b|https?://|www\.|\bportal\b|\breview(ed|s)?\b|disburs|reimburs|\b(grant )?funds\b|\bproceeds\b|"
    r"\bfunding (may|must|can)\b|\bcash\b|\brecognition\b|\bprizes?\b|\bwinners?\b|\bfinalists?\b|\bhonorees?\b|"
    r"\bgrantees?\b|\brecipients?\b|\bnotif|\bphase\b|\bgrant terms?\b|\breapply\b|\bselected\b|"
    r"\bawards? (are|is|will|of|range)\b|\bgoverning law\b|\breceives?\b|\bjudged\b|\bsubmissions?\b|"
    r"\bpriorities\b",
    I,
)
# The clause admits small businesses in general ("Any small business owner in the US is eligible").
_GENERIC_OPEN = re.compile(
    r"\b(any|all)\b[^.]{0,40}\bbusiness(es| owners?)?\b[^.]{0,40}\b(eligible|welcome|may apply|can apply)\b|"
    r"^open to (all|any)\b|^open to small businesses\b|^(any|all) (\w+ ){0,4}business(es| owners?)?\W*$",
    I,
)
_MIN_WORDS = 3  # shorter clauses are headings or fragments
# A sentence about the programme itself with no rule wording ("These grants help businesses grow").
_PROGRAMME_STATEMENT = re.compile(
    r"^(these (grants|awards|funds)|this (grant|program|programme|fund|award)|"
    r"the (grant|program|programme|fund|foundation|award|competition)|our (mission|goal)|we (are|believe|were))\b",
    I,
)
_RULE_WORDING = re.compile(
    r"\bmust\b|\brequire|\bonly\b|\beligib|\bapplicants?\b|\bopen to\b|\bqualif|\bat least\b|\bno more\b|"
    r"\b(fewer|less|more) than\b",
    I,
)
# A number or comparison, needed before a mention of revenue or employees counts as a limit.
_QUANTITY = re.compile(
    r"\d|\b(fewer|less|more|least|most|under|over|below|above|maximum|minimum|up to|between|"
    r"one|two|three|four|five|six|seven|eight|nine|ten|fifty|hundred)\b",
    I,
)
_TOPICS: dict[CriterionTopic, re.Pattern[str]] = {
    "revenue": re.compile(
        r"\brevenues?\b|\bgross (sales|receipts)\b|\bannual (sales|budgets?)\b|\boperating budgets?\b", I
    ),
    "employees": re.compile(r"\bemployees?\b|\bemploys?\b|\bFTEs?\b|\bfull-time equivalents?\b", I),
    "tenure": re.compile(
        r"\byears? in (business|operation)\b|\bin (business|operation|existence) (for|since)\b|"
        r"\b(operating|operated|operational|established|existing|in operation|in business) (for )?"
        r"(at least |a minimum of |over |more than )?\w+\+? (years?|months?)\b|"
        r"\b\w+\+? (years?|months?) (of|in) (business|operations?|operating|publishing|history)\b|"
        r"\b(years?|months?) old\b|\bminimum of \w+ (years?|months?)\b|\bbusiness age\b|\b\w+\+ years? history\b",
        I,
    ),
    "personal": re.compile(
        r"\b18\+|\b\d\d (years|or older|or over)\b|\byears of age\b|\bages? \d|\blegal residents?\b|\bcitizens?\b|"
        r"\bauthorized to work\b|\bresiden(ts?|ce|cy)\b",
        I,
    ),
    "registration": re.compile(
        r"\blicen[sc]e[sd]?\b|\bregistered\b|\bgood standing\b|\bEIN\b|\btax (returns?|compliant)\b|"
        r"\binsur(ance|ed)\b|\bcertifi\w+",
        I,
    ),
    "area": re.compile(
        r"\bcount(y|ies)\b|\bdistricts?\b|\bcorridors?\b|\bneighbou?rhoods?\b|\bcensus tracts?\b|\bzip codes?\b|"
        r"\beligible areas?\b|\bcity limits\b|\bwards?\b|\bopportunity zones?\b|\brural\b|"
        r"\blow[- ]to[- ]moderate\b|\blow[- ]income\b|\bLMI\b",
        I,
    ),
}
# A mention of revenue or employees only counts with a number or comparison; these topics
# count even inside a clause about the application process ("submit proof of 2 years in business").
_NEEDS_QUANTITY = {"revenue", "employees"}
_COUNTS_IN_PROCESS_CLAUSE = {"revenue", "employees", "tenure"}

# Location is evaluated against the grant's Location column.
_LOCATION_WORDING = re.compile(
    r"\blocated\b|\bbased in\b|-based\b|\bheadquartered\b|\boperat\w+ in\b|\bwithin the (united states|u\.s\.)", I
)

_MAX_SOURCE = 220


def _is_evaluated(clause: str) -> bool:
    """Does the matcher already act on this clause (ownership, entity type, premises, location)?"""
    return bool(rq._scan(clause, from_criteria=True, alternative=False)) or bool(_LOCATION_WORDING.search(clause))


def review_criteria(eligibility_text: str) -> tuple[list[UncheckedCriterion], bool]:
    """Return (criteria that cannot be evaluated, whether the text says who qualifies at all).

    The first item has one entry per topic, quoting the first clause that raised it. The
    criteria column is eligibility prose, so a clause is treated as a requirement unless it is
    recognisably something else: a statement that nothing is required, a preference, a process
    note, a sentence about the programme, a general "any small business" line, or a clause the
    matcher evaluates.
    """
    found: dict[CriterionTopic, str] = {}
    says_who_qualifies = False
    for clause in rq._clauses(eligibility_text):
        if _NO_REQUIREMENT.search(clause) or rq._PREFERENCE.search(clause):
            continue
        process = bool(_PROCESS.search(clause))
        topics = [
            topic
            for topic, pattern in _TOPICS.items()
            if pattern.search(clause)
            and (topic not in _NEEDS_QUANTITY or _QUANTITY.search(clause))
            and (not process or topic in _COUNTS_IN_PROCESS_CLAUSE)
        ]
        if not topics:
            if _GENERIC_OPEN.search(clause) or (not process and _is_evaluated(clause)):
                says_who_qualifies = True
                continue
            programme_statement = _PROGRAMME_STATEMENT.search(clause) and not _RULE_WORDING.search(clause)
            if process or programme_statement or len(clause.split()) < _MIN_WORDS:
                continue
            topics = ["other"]
        says_who_qualifies = True
        for topic in topics:
            found.setdefault(topic, clause[:_MAX_SOURCE])
    order = [*_TOPICS, "other"]
    return [UncheckedCriterion(topic=topic, source=found[topic]) for topic in order if topic in found], says_who_qualifies
