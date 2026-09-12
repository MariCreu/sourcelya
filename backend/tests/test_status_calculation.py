from app.domain.enums import ComplianceStatus
from app.models.packaging_component import PackagingComponent
from app.models.product import Product
from app.services.status_calculation_service import StatusCalculationService

service = StatusCalculationService()


def _complete_component(**overrides) -> PackagingComponent:
    defaults = dict(
        name="Outer box",
        packaging_type="box",
        material="cardboard",
        weight_grams=120.0,
        recycled_content_percentage=80.0,
    )
    defaults.update(overrides)
    return PackagingComponent(**defaults)


def test_component_is_green_when_all_required_fields_present():
    result = service.calculate_component_status(_complete_component())
    assert result.status == ComplianceStatus.GREEN
    assert result.missing_fields == ()


def test_component_is_orange_when_a_required_field_is_missing():
    result = service.calculate_component_status(_complete_component(material=None))
    assert result.status == ComplianceStatus.ORANGE
    assert "material" in result.missing_fields


def test_component_reports_every_missing_field():
    component = _complete_component(weight_grams=None, recycled_content_percentage=None)
    result = service.calculate_component_status(component)
    assert set(result.missing_fields) == {"weight_grams", "recycled_content_percentage"}


def test_product_with_no_components_is_orange():
    product = Product(name="Widget")
    product.packaging_components = []
    assert service.calculate_product_status(product) == ComplianceStatus.ORANGE


def test_product_is_green_only_when_every_component_is_green():
    product = Product(name="Widget")
    product.packaging_components = [_complete_component(), _complete_component(name="Label")]
    assert service.calculate_product_status(product) == ComplianceStatus.GREEN


def test_product_is_orange_when_any_component_is_incomplete():
    product = Product(name="Widget")
    product.packaging_components = [_complete_component(), _complete_component(material=None)]
    assert service.calculate_product_status(product) == ComplianceStatus.ORANGE
