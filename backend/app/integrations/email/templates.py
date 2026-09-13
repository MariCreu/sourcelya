"""Verbatim email copy for the supplier-request flow (FASE 3: initial
request; FASE 6: missing-information follow-up and the completion
thank-you).

Deliberately plain and short: no legal threats, no aggressive language — a
supplier who has never heard of Sourcelya needs to understand in one read
that this is a normal business request, not a scam or a legal notice.
Deterministic copy throughout, never LLM-generated — see the FASE 6 spec's
"NO meter IA para redactar emails".
"""

from dataclasses import dataclass

from app.domain.enums import ExtractableFieldName, Locale
from app.integrations.email.base import EmailMessage

_FIELD_LABELS = {
    Locale.ES.value: {
        ExtractableFieldName.PACKAGING_TYPE.value: "Tipo de packaging",
        ExtractableFieldName.MATERIAL.value: "Material",
        ExtractableFieldName.WEIGHT_GRAMS.value: "Peso",
        ExtractableFieldName.RECYCLED_CONTENT_PERCENTAGE.value: "Contenido reciclado",
        ExtractableFieldName.PACKAGING_REFERENCE.value: "Referencia de packaging",
    },
    Locale.EN.value: {
        ExtractableFieldName.PACKAGING_TYPE.value: "Packaging type",
        ExtractableFieldName.MATERIAL.value: "Material",
        ExtractableFieldName.WEIGHT_GRAMS.value: "Weight",
        ExtractableFieldName.RECYCLED_CONTENT_PERCENTAGE.value: "Recycled content",
        ExtractableFieldName.PACKAGING_REFERENCE.value: "Packaging reference",
    },
}


def field_label(field_name: str, language: str) -> str:
    return _FIELD_LABELS[language].get(field_name, field_name)

_SUBJECT = {
    Locale.ES.value: "Solicitud de información de productos",
    Locale.EN.value: "Product information request",
}

_BODY_TEMPLATE = {
    Locale.ES.value: (
        "Hola {supplier_name},\n\n"
        "{company_name} necesita información y documentación de {number_of_products} "
        "producto(s).\n\n"
        "Puedes completar la solicitud desde este enlace seguro:\n\n"
        "{request_url}\n\n"
        "No necesitas crear una cuenta.\n\n"
        "Gracias."
    ),
    Locale.EN.value: (
        "Hello {supplier_name},\n\n"
        "{company_name} needs information and documentation for {number_of_products} "
        "product(s).\n\n"
        "You can complete the request using this secure link:\n\n"
        "{request_url}\n\n"
        "No account is required.\n\n"
        "Thank you."
    ),
}


@dataclass(frozen=True)
class ComplianceRequestEmailContext:
    supplier_email: str
    supplier_name: str
    company_name: str
    number_of_products: int
    request_url: str
    language: str


def build_compliance_request_email(context: ComplianceRequestEmailContext) -> EmailMessage:
    subject = _SUBJECT[context.language]
    body = _BODY_TEMPLATE[context.language].format(
        supplier_name=context.supplier_name,
        company_name=context.company_name,
        number_of_products=context.number_of_products,
        request_url=context.request_url,
    )
    # Plain-text copy, wrapped in <pre> so ResendEmailSender's html-only API
    # renders it without collapsing the newlines — no rich HTML template
    # exists yet, on purpose, this is MVP transactional copy.
    html_body = f"<pre style=\"font-family: inherit; white-space: pre-wrap;\">{body}</pre>"
    return EmailMessage(to=context.supplier_email, subject=subject, html_body=html_body)


def _as_pre(body: str) -> str:
    return f"<pre style=\"font-family: inherit; white-space: pre-wrap;\">{body}</pre>"


_FOLLOW_UP_SUBJECT = {
    Locale.ES.value: "Falta información para completar tu solicitud",
    Locale.EN.value: "A few things are still missing to complete your submission",
}

_FOLLOW_UP_BODY_TEMPLATE = {
    Locale.ES.value: (
        "Hola {supplier_name},\n\n"
        "Gracias por la información que ya nos has enviado.\n\n"
        "Todavía necesitamos lo siguiente:\n\n"
        "{missing_fields_list}\n\n"
        "No es necesario que vuelvas a enviar lo que ya nos diste.\n\n"
        "Puedes completarlo desde este enlace seguro:\n\n"
        "{request_url}\n\n"
        "Gracias,\n{company_name}"
    ),
    Locale.EN.value: (
        "Hello {supplier_name},\n\n"
        "Thank you for the information you've already provided.\n\n"
        "We still need the following:\n\n"
        "{missing_fields_list}\n\n"
        "You don't need to resend the information you've already provided.\n\n"
        "You can complete it using this secure link:\n\n"
        "{request_url}\n\n"
        "Thanks,\n{company_name}"
    ),
}


@dataclass(frozen=True)
class MissingFieldRef:
    component_name: str
    field_name: str


@dataclass(frozen=True)
class MissingInformationFollowUpEmailContext:
    supplier_email: str
    supplier_name: str
    company_name: str
    missing_fields: tuple[MissingFieldRef, ...]
    request_url: str
    language: str
    # Only shown per-line when the request covers more than one component —
    # a single-component request (the common case) gets a plain field list,
    # matching the spec's own example email exactly.
    multiple_components: bool = False


def build_missing_information_follow_up_email(
    context: MissingInformationFollowUpEmailContext,
) -> EmailMessage:
    subject = _FOLLOW_UP_SUBJECT[context.language]
    bullet = "•" if context.language == Locale.ES.value else "-"

    def _line(ref: MissingFieldRef) -> str:
        label = field_label(ref.field_name, context.language)
        if context.multiple_components:
            return f"{bullet} {ref.component_name} — {label}"
        return f"{bullet} {label}"

    missing_fields_list = "\n".join(_line(ref) for ref in context.missing_fields)
    body = _FOLLOW_UP_BODY_TEMPLATE[context.language].format(
        supplier_name=context.supplier_name,
        company_name=context.company_name,
        missing_fields_list=missing_fields_list,
        request_url=context.request_url,
    )
    return EmailMessage(to=context.supplier_email, subject=subject, html_body=_as_pre(body))


_COMPLETE_SUBJECT = {
    Locale.ES.value: "Gracias — tu envío está completo",
    Locale.EN.value: "Thank you — your submission is complete",
}

_COMPLETE_BODY_TEMPLATE = {
    Locale.ES.value: (
        "Hola {supplier_name},\n\n"
        "Gracias. {company_name} ha recibido y revisado toda la información "
        "solicitada.\n\n"
        "No necesitas hacer nada más por ahora."
    ),
    Locale.EN.value: (
        "Hello {supplier_name},\n\n"
        "Thank you. {company_name} has received and reviewed all the requested "
        "information.\n\n"
        "You don't need to do anything else for now."
    ),
}


@dataclass(frozen=True)
class RequestCompleteEmailContext:
    supplier_email: str
    supplier_name: str
    company_name: str
    language: str


def build_request_complete_email(context: RequestCompleteEmailContext) -> EmailMessage:
    subject = _COMPLETE_SUBJECT[context.language]
    body = _COMPLETE_BODY_TEMPLATE[context.language].format(
        supplier_name=context.supplier_name, company_name=context.company_name
    )
    return EmailMessage(to=context.supplier_email, subject=subject, html_body=_as_pre(body))
