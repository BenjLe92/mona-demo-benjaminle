"""Extract ownership, entity-type and premises requirements from a grant's text.

Each clause is classified as one of:

- a **firm requirement** ("must be at least 51% woman-owned") or an **explicit exclusion**
  ("for-profit businesses are ineligible"): `strict=True`, so a business that does not meet it fails;
- an **ambiguous statement** that names who the grant is for without stating a rule
  ("open to women and minority entrepreneurs", "per veteran entrepreneur"): `strict=False`,
  so a business that does not match is asked to verify and is never failed;
- a **preference or incidental mention** ("women are encouraged to apply"): nothing.

Anything not recognised here is left for the applicant to read in the full criteria text.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from app.domain.models import FounderGroup, Requirement

I = re.IGNORECASE

# Sentences, lines, semicolons and spaced dashes each start a new clause.
_CLAUSE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+|;\s+|\s[-–—]\s")
_BULLET_CHARS = " -•➢*\t"

# Wording that marks a preference or an extra, never a requirement.
_PREFERENCE = re.compile(
    r"encourag|\bpriority\b|prioritiz|prefer|especially|particularly|emphasis|not required|regardless|"
    r"open to all|bonus|booster|additional|optional|rising to|higher|categor",
    I,
)
# Wording that introduces examples; the clause can still carry a rule if it also says "must".
_EXAMPLE = re.compile(r"includ|such as|e\.g\.", I)
# Wording that states a firm rule. Ownership percentages only count for ownership requirements.
_STRONG = re.compile(r"\bmust\b|\brequired?\b|\bonly\b|\bat least\b", I)
_STRONG_OWNERSHIP = re.compile(_STRONG.pattern + r"|\d+\s?%|\bmajority\b", I)
# Wording that says who may apply without excluding anyone else.
_INCLUSION = re.compile(r"\bopen to\b|\b(are|is|also) eligible\b|\beligible (to|for)\s", I)
# Who-it-is-for wording immediately before a group ("per veteran", "supports women").
_BENEFICIARY = re.compile(
    r"\b(for|per|supports?|supporting|honou?ring|recogni[sz]\w*|helps?|helping|funds|funding|"
    r"reimburses?|open to|eligible)\s+(?:[\w$,.%'’-]+\s+){0,3}?$",
    I,
)
# The clause is one of several routes to eligibility.
_DANGLING_OR = re.compile(r"^\W*OR\b|\bOR\W*$")
_INLINE_OR = re.compile(r"\bOR\b")
_ENTITY_ALTERNATION = re.compile(r"for-profits?\s+or\s+non-?profits?|non-?profits?\s+or\s+for-profits?", I)
# A group the business profile cannot represent, named alongside the ones it can.
_OTHER_GROUPS = re.compile(
    r"disab|lgbt|non-?binary|immigrant|refugee|spouse|low[- ]income|disadvantaged|formerly incarcerated", I
)
# The clause is about another organisation, not the applicant ("affiliated with ... Black Business Alliance").
_THIRD_PARTY = re.compile(r"affiliat|partner|member(ship)? of|sponsored by|presented by", I)

# A clause that is itself a list of who is excluded, up to any contrast ("... but only X may apply").
_EXCLUSION_LEAD = re.compile(r"^\W*(ineligible|not eligible|excluded|excludes|exclusions?|not open to)\b", I)
# A bare "excluded" is not enough ("groups historically excluded from funding"): it needs a verb,
# or must follow the subject directly ("nonprofits ineligible").
_NEGATION = re.compile(
    r"\b(?:are|is|be|remain)\s+(?:not\s+(?:\w+\s+){0,2}?eligible|ineligible|excluded|not permitted|outside)\b|"
    r"\bnot\s+(?:named|listed)\s+as\s+eligible\b|\bcannot apply\b|\bmay not apply\b|^\s*(?:ineligible|excluded)\b",
    I,
)
# Wording between a subject and a negation that means the negation belongs to something else.
_NEGATION_BREAK = re.compile(r"\b(but|only|while|however|eligible|may apply|can apply|welcome)\b|:", I)
_NEGATED_BEFORE = re.compile(r"\b(not open to|excluding|excludes?|except)\s+(?:\w+\s+){0,2}$|\bnot (?:a |an )?$", I)

_GROUP_PATTERNS: dict[FounderGroup, re.Pattern[str]] = {
    "woman": re.compile(r"\bwom[ae]n\b|\bfemales?\b", I),
    "black": re.compile(r"\bblack\b|\bafrican[- ]americans?\b", I),
    "bipoc": re.compile(
        r"\bbipoc\b|\bminorit\w*|\bpeople of colou?r\b|\blatin[oaxe]s?\b|\bhispanics?\b|\bindigenous\b|"
        r"\bnative americans?\b|\baapi\b|\basian[- ]americans?\b",
        I,
    ),
    "veteran": re.compile(r"\bveterans?\b", I),
}
# Group words inside a programme name ("WomanUp", "Veteran Grant Program").
_NAME_PATTERNS: dict[FounderGroup, re.Pattern[str]] = {
    "woman": re.compile(r"wom[ae]n|female", I),
    "black": re.compile(r"\bblack\b", I),
    "bipoc": re.compile(r"\bbipoc\b|minorit|latin[oax]\b|hispanic", I),
    "veteran": re.compile(r"veteran", I),
}
_OWNERSHIP = re.compile(r"\b(owned|led|founded)\b", I)
_OWNERSHIP_WINDOW = 45  # characters either side of "owned" searched for a group word
_ROLE = re.compile(
    r"\b(co-?founders?|founders?|entrepreneurs?|business owners?|owners?|business(?:es)?|ceo|president|designers?)\b", I
)
_ROLE_WINDOW = 40  # characters after a group word searched for a role word
# A criteria clause that opens with the entity type or the group is itself the rule
# ("For-profit businesses in Sacramento", "U.S. military veteran serving as CEO").
_LIST_ITEM_START = 30  # characters before an entity term
_LIST_ITEM_WORDS = 2  # words before a group term

_FOR_PROFIT = re.compile(r"(?<!not-)(?<!not )\bfor-profits?\b", I)
_NONPROFIT = re.compile(r"\bnon-?profits?\b|\bnot[- ]for[- ]profit\b|501\s?\(c\)|\bcharitable organi[sz]ations?\b", I)
_FOR_PROFIT_RULE = re.compile(
    r"for-profits?\s+(?:\w+\s+){0,2}?(business|compan|entit|venture|entrepreneur|organi[sz]ation|firm)|"
    r"\b(be|is|are)\s+(a |an )?(\w+\s+){0,2}?for-profit",
    I,
)
_NONPROFIT_RULE = re.compile(
    r"non-?profits? only|\bonly\s+(to |for )?(\w+\s+){0,2}?(non-?profit|501)|"
    r"\b(be|have)\s+(a |an )?([\w.-]+\s+){0,4}?(non-?profit|not[- ]for[- ]profit|501\s?\(c\))|"
    r"^(eligible:\s*)?(registered\s+)?(\w+\s+){0,2}?(non-?profits?|not[- ]for[- ]profit|501\s?\(c\))",
    I,
)
# Other applicant types named alongside nonprofits.
_BUSINESS_APPLICANT = re.compile(r"business|compan|for-profit|entrepreneur", I)
_OTHER_APPLICANT = re.compile(r"individual|artist|fiscal|teacher|educator|government|public bod|tribe|school", I)

_BRICK = re.compile(
    r"must (have|operate|own|lease|occupy) (a |an )?(physical|brick[- ]and[- ]mortar|storefront|commercial) "
    r"|brick[- ]and[- ]mortar (business|location|storefront|retail|establishment)|"
    r"home-based businesses (are )?(not eligible|ineligible)",
    I,
)


class _Found(NamedTuple):
    requirement: Requirement
    emphatic: bool  # stated with rule wording or as an explicit exclusion, not just implied by position


def _clauses(text: str) -> list[str]:
    return [c.strip(_BULLET_CHARS) for c in _CLAUSE_SPLIT.split(text) if c and c.strip(_BULLET_CHARS)]


def _strictness(
    clause: str, from_criteria: bool, self_evident: bool, beneficiary: bool, strong: re.Pattern[str]
) -> tuple[bool | None, bool]:
    """Return (strict, emphatic). strict is True for a firm rule, False for an ambiguous
    statement and None for no requirement.

    `self_evident` means the clause is a criteria item whose wording is itself the rule
    ("Woman-owned business in the U.S.").
    """
    if _PREFERENCE.search(clause):
        return None, False
    emphatic = bool(strong.search(clause))
    if _EXAMPLE.search(clause):
        return (False if emphatic else None), emphatic
    inclusion = bool(_INCLUSION.search(clause))
    if emphatic or (from_criteria and self_evident and not inclusion):
        return True, emphatic
    if inclusion or beneficiary:
        return False, False
    return None, False


def _exclusion_end(clause: str) -> int:
    """Characters from the start of the clause that form an exclusion list (0 when it is not one)."""
    lead = _EXCLUSION_LEAD.match(clause)
    if not lead:
        return 0
    contrast = re.search(r"\bbut\b|\bonly\b", clause[lead.end() :], I)
    return lead.end() + contrast.start() if contrast else len(clause)


def _is_excluded(clause: str, match: re.Match[str], exclusion_end: int) -> bool:
    """Is this term named as excluded: in an exclusion list, or as the subject of a negation?"""
    if match.start() < exclusion_end or _NEGATED_BEFORE.search(clause[: match.start()]):
        return True
    rest = clause[match.end() :]
    negation = _NEGATION.search(rest)
    return bool(negation) and not _NEGATION_BREAK.search(rest[: negation.start()])


def _founder_requirement(clause: str, from_criteria: bool, exclusion_end: int, alternative: bool) -> _Found | None:
    groups: list[FounderGroup] = []
    ownership_worded = False
    first_start = len(clause)
    beneficiary = False
    owned_windows = [
        (max(0, m.start() - _OWNERSHIP_WINDOW), m.end() + _OWNERSHIP_WINDOW) for m in _OWNERSHIP.finditer(clause)
    ]
    for group, pattern in _GROUP_PATTERNS.items():
        for match in pattern.finditer(clause):
            near_ownership = any(start <= match.start() < end for start, end in owned_windows)
            has_role = bool(_ROLE.search(clause[match.end() : match.end() + _ROLE_WINDOW]))
            if not (near_ownership or has_role):
                continue
            if _is_excluded(clause, match, exclusion_end):
                return None
            ownership_worded = ownership_worded or near_ownership
            first_start = min(first_start, match.start())
            beneficiary = beneficiary or bool(_BENEFICIARY.search(clause[: match.start()]))
            if group not in groups:
                groups.append(group)
    if not groups or (_THIRD_PARTY.search(clause) and not ownership_worded):
        return None
    self_evident = ownership_worded or len(clause[:first_start].split()) <= _LIST_ITEM_WORDS
    strict, emphatic = _strictness(clause, from_criteria, self_evident, beneficiary, _STRONG_OWNERSHIP)
    if strict is None:
        return None
    other_route = alternative or _INLINE_OR.search(_ENTITY_ALTERNATION.sub("", clause)) or _OTHER_GROUPS.search(clause)
    requirement = Requirement(kind="founder", groups=groups, strict=strict and not other_route, source=clause[:300])
    return _Found(requirement, emphatic)


def _entity_requirement(clause: str, from_criteria: bool, exclusion_end: int, alternative: bool) -> _Found | None:
    for_profit = [(m, _is_excluded(clause, m, exclusion_end)) for m in _FOR_PROFIT.finditer(clause)]
    nonprofit = [(m, _is_excluded(clause, m, exclusion_end)) for m in _NONPROFIT.finditer(clause)]
    for_profit_out = any(excluded for _, excluded in for_profit)
    # Excluding one tax class ("501(c)(4)s are not eligible") does not exclude nonprofits as a whole.
    nonprofit_out = any(excluded and "501" not in m.group() for m, excluded in nonprofit)
    for_profit_in = [m for m, excluded in for_profit if not excluded]
    nonprofit_in = [m for m, excluded in nonprofit if not excluded]
    if any(excluded for _, excluded in nonprofit) and not nonprofit_out:
        return None  # only a sub-class of nonprofits is excluded: nothing to conclude
    source = clause[:300]

    # An explicit exclusion of one entity type is a firm requirement for the other.
    if for_profit_out and not nonprofit_out:
        return _Found(Requirement(kind="nonprofit", source=source), True)
    if nonprofit_out and not for_profit_out:
        return _Found(Requirement(kind="for_profit", source=source), True)
    if for_profit_out or (for_profit_in and nonprofit_in):
        return None  # both excluded, or both admitted: no entity restriction

    if for_profit_in and _FOR_PROFIT_RULE.search(clause):
        first = for_profit_in[0]
        beneficiary = bool(_BENEFICIARY.search(clause[: first.start()]))
        strict, emphatic = _strictness(clause, from_criteria, first.start() <= _LIST_ITEM_START, beneficiary, _STRONG)
        if strict is None:
            return None
        return _Found(Requirement(kind="for_profit", strict=strict and not alternative, source=source), emphatic)

    if nonprofit_in and _NONPROFIT_RULE.search(clause):
        if _BUSINESS_APPLICANT.search(clause) or _THIRD_PARTY.search(clause):
            return None  # businesses are admitted too, or the clause describes a partner
        strict, emphatic = _strictness(clause, from_criteria, nonprofit_in[0].start() <= _LIST_ITEM_START, False, _STRONG)
        if not strict:
            return None  # "nonprofits are also eligible" widens the pool; it restricts nobody
        firm = not alternative and not _OTHER_APPLICANT.search(clause)
        return _Found(Requirement(kind="nonprofit", strict=firm, source=source), emphatic)
    return None


def _scan(clause: str, from_criteria: bool, alternative: bool) -> list[_Found]:
    """Every requirement in one clause; a clause can carry several independent ones."""
    exclusion_end = _exclusion_end(clause)
    found = [
        _founder_requirement(clause, from_criteria, exclusion_end, alternative),
        _entity_requirement(clause, from_criteria, exclusion_end, alternative),
    ]
    if _BRICK.search(clause) and not _PREFERENCE.search(clause):
        found.append(_Found(Requirement(kind="brick_and_mortar", source=clause[:300]), True))
    return [f for f in found if f]


def _scan_text(text: str, from_criteria: bool) -> list[_Found]:
    clauses = _clauses(text)
    found: list[_Found] = []
    for index, clause in enumerate(clauses):
        next_clause = clauses[index + 1] if index + 1 < len(clauses) else ""
        alternative = bool(_DANGLING_OR.search(clause) or re.match(r"\W*OR\b", next_clause))
        found += _scan(clause, from_criteria, alternative)
    return found


def _admits(text: str, pattern: re.Pattern[str]) -> bool:
    """Does any clause mention this entity type without excluding it?"""
    for clause in _clauses(text):
        end = _exclusion_end(clause)
        if any(not _is_excluded(clause, m, end) for m in pattern.finditer(clause)):
            return True
    return False


def _reconcile(found: list[_Found], name: str, text: str) -> list[Requirement]:
    requirements = [f.requirement for f in found]
    firm_founders = [r for r in requirements if r.kind == "founder" and r.strict]
    loose_founders = [r for r in requirements if r.kind == "founder" and not r.strict]
    result: list[Requirement] = []

    # Firm ownership rules are independent of each other; keep each distinct one.
    for requirement in firm_founders:
        if not any(r.kind == "founder" and r.groups == requirement.groups for r in result):
            result.append(requirement)
    if not firm_founders:
        # Without a firm rule, merge every hint about who the grant is for into one check.
        groups: list[FounderGroup] = [g for r in loose_founders for g in r.groups]
        named = [g for g, pattern in _NAME_PATTERNS.items() if pattern.search(name) and g not in groups]
        source = loose_founders[0].source if loose_founders else f"Programme name: {name}"
        groups = list(dict.fromkeys([*groups, *named]))
        if groups:
            result.append(Requirement(kind="founder", groups=groups, strict=False, source=source))

    entity = {kind: [f for f in found if f.requirement.kind == kind] for kind in ("for_profit", "nonprofit")}
    conflicting = bool(entity["for_profit"] and entity["nonprofit"])
    for kind, opposite in (("for_profit", _NONPROFIT), ("nonprofit", _FOR_PROFIT)):
        if not entity[kind]:
            continue
        chosen = next((f for f in entity[kind] if f.requirement.strict), entity[kind][0])
        strict = chosen.requirement.strict and not conflicting
        if _admits(text, opposite):
            # Elsewhere the listing admits the other entity type. A rule that was only implied
            # by position is not a restriction at all; an emphatic one becomes ambiguous.
            if not chosen.emphatic:
                continue
            strict = False
        result.append(chosen.requirement.model_copy(update={"strict": strict}))

    brick = next((r for r in requirements if r.kind == "brick_and_mortar"), None)
    if brick:
        result.append(brick)
    return result


def extract_requirements(eligibility_text: str, description: str = "", name: str = "") -> list[Requirement]:
    """Requirements stated in the criteria column, the description, or implied by the programme name."""
    found = _scan_text(eligibility_text, from_criteria=True) + _scan_text(description, from_criteria=False)
    return _reconcile(found, name, f"{eligibility_text}\n{description}")
