from costpilot_core.material.material_extractor import MaterialExtractor
from psycopg import Connection

from src.models.commodity_record import CommodityRecord
from src.repositories.catalog_repository import CatalogRepository
from src.repositories.search_repository import SearchRepository


class SearchImporter:
    def __init__(
        self,
        conn: Connection,
        extractor: MaterialExtractor,
    ) -> None:
        self._conn = conn
        self._extractor = extractor

        self._catalog_repository = CatalogRepository(conn)
        self._search_repository = SearchRepository(conn)

    def import_commodity(
        self,
        commodity: CommodityRecord,
    ) -> None:
        search_text = self._build_text(commodity)

        # Only product-specific factual descriptions are suitable for attributes.
        # Group descriptions and business codes are useful for search, but may
        # describe a category rather than the individual commodity.
        extraction_text = self._build_extraction_text(commodity)
        result = self._extractor.extract(extraction_text)

        material_type = None
        attributes = {}

        if result is not None:
            material_type = result.material_type

            core = result.core_attributes
            supplementary = result.supplementary_attributes

            duplicates = core.keys() & supplementary.keys()

            if duplicates:
                raise ValueError(f"Duplicate material attributes: {sorted(duplicates)}")

            attributes = {
                **core,
                **supplementary,
            }

        self._search_repository.upsert_commodity_search(
            commodity_id=commodity.id,
            material_type=material_type,
            normalized_unit=None,
            attributes=attributes,
            search_text=search_text,
        )

    def import_commodities(
        self,
        *,
        data_source_id: int,
    ) -> int:
        if data_source_id <= 0:
            raise ValueError("data_source_id must be greater than 0.")

        with self._conn.transaction():
            commodities = self._catalog_repository.read_commodities(
                data_source_id=data_source_id,
            )

            for commodity in commodities:
                self.import_commodity(commodity)

        return len(commodities)

    @staticmethod
    def _build_text(
        commodity: CommodityRecord,
    ) -> str:
        parts = [
            commodity.code,
            commodity.description,
            commodity.group_description,
        ]

        return " ".join(
            part.strip() for part in parts if part is not None and part.strip()
        )

    @staticmethod
    def _build_extraction_text(commodity: CommodityRecord) -> str:
        parts = [commodity.description]
        if commodity.remarks and not commodity.remarks.startswith(
            "Synthetic test data for CostPilot development"
        ):
            parts.append(commodity.remarks)
        return " ".join(part.strip() for part in parts if part and part.strip())
