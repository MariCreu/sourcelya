"""The exact JSON shape Claude is constrained to via structured outputs
(`output_config.format` / `client.messages.parse`). This IS the mechanism
that stops the model from inventing fields or free-form shapes: a response
that doesn't validate against this schema is not returned as a successful
parse at all — see `claude_extraction.py`.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FieldName = Literal[
    "packaging_type",
    "material",
    "weight_grams",
    "recycled_content_percentage",
    "packaging_reference",
]


class ExtractedFieldModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: FieldName
    status: Literal["found", "not_found", "unknown"] = Field(
        description=(
            "'found' only if the document clearly and unambiguously states this "
            "value and you can quote it verbatim. 'not_found' if the document "
            "never mentions it. 'unknown' if it's mentioned but ambiguous, "
            "contradictory, or you are not confident — NEVER guess a plausible "
            "value instead of choosing not_found/unknown."
        )
    )
    value: str | None = Field(
        default=None,
        description=(
            "The extracted value as plain text, only when status is 'found'. "
            "For weight_grams/recycled_content_percentage: a bare number as a "
            "string, no units (e.g. '47', not '47g' or '47 grams'). For "
            "packaging_type: one of box, bag, label, filler, outer_envelope, "
            "other. Null for not_found/unknown."
        ),
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description=(
            "Your own honest assessment that this exact value is correct as "
            "stated in the document — not a probability, just how sure you are "
            "given how explicit and unambiguous the source text is."
        )
    )
    source_page: int | None = Field(
        default=None, description="1-indexed page/sheet number where this was found."
    )
    source_quote: str | None = Field(
        default=None,
        max_length=240,
        description=(
            "A short verbatim excerpt (<=240 characters) copied EXACTLY from the "
            "document's own text that supports this value — never a paraphrase "
            "or summary. Required whenever status is 'found'."
        ),
    )


class DocumentExtractionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_classification: Literal[
        "packaging_specification",
        "technical_datasheet",
        "certificate",
        "declaration",
        "invoice_commercial",
        "other",
    ]
    fields: list[ExtractedFieldModel]
