from costpilot_core.material.attribute_extractor import AttributeExtractor
from costpilot_core.material.classifier import MaterialClassifier
from costpilot_core.material.config_loader import MaterialConfigLoader
from costpilot_core.material.material_extractor import MaterialExtractor
from costpilot_core.material.registry import MaterialRegistry

from src.database.connector import DBConnector
from src.models.commodity_record import CommodityRecord


def read_commodity(
    commodity_id: int,
) -> CommodityRecord:
    connector = DBConnector()

    with connector.connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
                SELECT
                    c.id,
                    c.code,
                    c.description,
                    c.unit,
                    c.cost_code,
                    cg.code,
                    cg.description
                FROM commodities AS c
                JOIN commodity_groups AS cg
                    ON cg.id = c.commodity_group_id
                WHERE c.id = %s;
                """,
            (commodity_id,),
        )

        row = cursor.fetchone()

    if row is None:
        raise ValueError(f"Commodity with id {commodity_id} not found.")

    return CommodityRecord(
        id=row[0],
        code=row[1],
        description=row[2],
        unit=row[3],
        cost_code=row[4],
        group_code=row[5],
        group_description=row[6],
    )


def build_text(
    commodity: CommodityRecord,
) -> str:
    parts = [
        commodity.code,
        commodity.description,
        commodity.group_description,
    ]

    return " ".join(part.strip() for part in parts if part is not None and part.strip())


def create_material_extractor() -> MaterialExtractor:
    config_loader = MaterialConfigLoader()

    templates = config_loader.load_all()

    registry = MaterialRegistry(templates)

    classifier = MaterialClassifier(registry)

    attribute_extractor = AttributeExtractor()

    return MaterialExtractor(
        registry=registry,
        classifier=classifier,
        attribute_extractor=attribute_extractor,
    )


def main() -> None:
    commodity = read_commodity(
        commodity_id=1,
    )

    print("Commodity:")
    print(commodity)

    text = build_text(commodity)

    print()
    print("Extraction text:")
    print(text)

    extractor = create_material_extractor()

    result = extractor.extract(text)

    print()
    print("Extracted material:")
    print(result)


if __name__ == "__main__":
    main()
