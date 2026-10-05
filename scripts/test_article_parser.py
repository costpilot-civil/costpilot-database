from pathlib import Path

from src.parsers.article_xml_parser import ArticleXmlParser


def main() -> None:
    file_path = Path("data/imports/Artikel.xml")

    parser = ArticleXmlParser()
    data = parser.parse(file_path)

    print("Product groups:", len(data.product_groups))
    print("Commodity groups:", len(data.commodity_groups))
    print("Commodities:", len(data.commodities))

    commodity_prices = sum(len(commodity.prices) for commodity in data.commodities)

    estimate_prices = sum(
        len(commodity.estimate_prices) for commodity in data.commodities
    )

    print("Commodity prices:", commodity_prices)
    print("Estimate prices:", estimate_prices)

    print()
    print("First product group:")
    print(data.product_groups[0])

    print()
    print("First commodity group:")
    print(data.commodity_groups[0])

    print()
    print("First commodity:")
    print(data.commodities[0])


if __name__ == "__main__":
    main()
