"""Verbatim email copy for the FASE 3 supplier-request flow.

Deliberately plain and short: no legal threats, no aggressive language — a
supplier who has never heard of Sourcelya needs to understand in one read
that this is a normal business request, not a scam or a legal notice.
"""

from dataclasses import dataclass

from app.domain.enums import Locale
from app.integrations.email.base import EmailMessage

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
