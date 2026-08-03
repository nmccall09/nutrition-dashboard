from dataclasses import dataclass


@dataclass(frozen=True)
class UnitDefinition:
    dimension: str
    to_base_factor: float


UNIT_DEFINITIONS = {
    # Weight base unit: gram
    "g": UnitDefinition(
        dimension="weight",
        to_base_factor=1.0,
    ),
    "kg": UnitDefinition(
        dimension="weight",
        to_base_factor=1000.0,
    ),
    "oz": UnitDefinition(
        dimension="weight",
        to_base_factor=28.349523125,
    ),
    "lb": UnitDefinition(
        dimension="weight",
        to_base_factor=453.59237,
    ),

    # Volume base unit: teaspoon
    "tsp": UnitDefinition(
        dimension="volume",
        to_base_factor=1.0,
    ),
    "tbsp": UnitDefinition(
        dimension="volume",
        to_base_factor=3.0,
    ),
    "cup": UnitDefinition(
        dimension="volume",
        to_base_factor=48.0,
    ),

    # Discrete/package units
    "each": UnitDefinition(
        dimension="each",
        to_base_factor=1.0,
    ),
    "can": UnitDefinition(
        dimension="can",
        to_base_factor=1.0,
    ),
    "bag": UnitDefinition(
        dimension="bag",
        to_base_factor=1.0,
    ),
    "container": UnitDefinition(
        dimension="container",
        to_base_factor=1.0,
    ),
}


def normalize_unit(unit: str | None) -> str | None:
    """
    Normalize unit text before conversion.
    """
    if unit is None:
        return None

    normalized = unit.strip().lower()

    aliases = {
        "gram": "g",
        "grams": "g",
        "kilogram": "kg",
        "kilograms": "kg",
        "ounce": "oz",
        "ounces": "oz",
        "pound": "lb",
        "pounds": "lb",
        "teaspoon": "tsp",
        "teaspoons": "tsp",
        "tablespoon": "tbsp",
        "tablespoons": "tbsp",
        "cups": "cup",
        "items": "each",
        "item": "each",
    }

    return aliases.get(normalized, normalized)


def can_convert_units(
    from_unit: str | None,
    to_unit: str | None,
) -> bool:
    """
    Return whether two units belong to the same dimension.
    """
    normalized_from = normalize_unit(from_unit)
    normalized_to = normalize_unit(to_unit)

    if normalized_from is None or normalized_to is None:
        return False

    if normalized_from not in UNIT_DEFINITIONS:
        return normalized_from == normalized_to

    if normalized_to not in UNIT_DEFINITIONS:
        return normalized_from == normalized_to

    return (
        UNIT_DEFINITIONS[normalized_from].dimension
        == UNIT_DEFINITIONS[normalized_to].dimension
    )


def convert_quantity(
    quantity: float,
    from_unit: str,
    to_unit: str,
) -> float:
    """
    Convert a quantity between compatible units.
    """
    normalized_from = normalize_unit(from_unit)
    normalized_to = normalize_unit(to_unit)

    if normalized_from == normalized_to:
        return float(quantity)

    if not can_convert_units(
        normalized_from,
        normalized_to,
    ):
        raise ValueError(
            f"Cannot convert from {from_unit} to {to_unit}."
        )

    from_definition = UNIT_DEFINITIONS[
        normalized_from
    ]

    to_definition = UNIT_DEFINITIONS[
        normalized_to
    ]

    base_quantity = (
        float(quantity)
        * from_definition.to_base_factor
    )

    return (
        base_quantity
        / to_definition.to_base_factor
    )