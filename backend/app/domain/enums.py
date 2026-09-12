"""Domain-level constants that are validated in Python, not enforced by a
native PostgreSQL enum type.

Convention (applies to this file and to whatever gets added in later
phases, e.g. `document_type` in FASE 4 or `entity_type` in FASE 7): a
native Postgres ENUM is reserved for values that are genuinely closed and
stable. Anything whose set of values is likely to grow while we're still
validating the product — `packaging_type` is the clearest example, but the
same reasoning will apply to `document_type` and extraction `entity_type`
once those tables exist — is stored as a plain VARCHAR column and validated
here / in Pydantic schemas instead. A native enum requires an `ALTER TYPE
... ADD VALUE` migration (and, in older Postgres versions, one that can't
run inside the same transaction as other changes) every time the set
grows; a VARCHAR + application-level validation needs a one-line code
change and no migration at all.

`ComplianceStatus` is different: it is never a database column at all (see
`StatusCalculationService`), only ever the return type of a computation, so
the enum-vs-varchar tradeoff doesn't apply to it — it lives here simply
because it's a shared domain type.
"""

from enum import Enum


class PackagingType(str, Enum):
    BOX = "box"
    BAG = "bag"
    LABEL = "label"
    FILLER = "filler"
    OUTER_ENVELOPE = "outer_envelope"
    OTHER = "other"


class ComplianceStatus(str, Enum):
    """Traffic-light status computed on the fly by StatusCalculationService —
    never cached on Product/PackagingComponent (see that service's
    docstring for why).
    """

    GREEN = "green"
    ORANGE = "orange"
    RED = "red"


class Locale(str, Enum):
    """Reserved for two future, related uses — kept as one shared type
    rather than two, since they're the same concept:

    1. `ComplianceRequest.language` (FASE 3): the request/email/public
       supplier portal all need to speak the language the *supplier* works
       in, which is independent of the buyer company's own language — a
       Spanish company can have a supplier in Germany or China. That column
       doesn't exist yet (`ComplianceRequest` isn't built until FASE 3);
       this enum exists now purely so that column has an obvious, already-
       agreed type to use instead of inventing one under time pressure.
    2. The Angular app's own locale switching, if/when it's implemented —
       see frontend README for why that isn't built out yet either.

    Only ES/EN for now, matching the initial Spain-first go-to-market — not
    a statement that Sourcelya only ever supports two languages.
    """

    ES = "es"
    EN = "en"
