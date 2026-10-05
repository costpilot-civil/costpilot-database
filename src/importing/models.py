from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(slots=True)
class ParsedProductGroup:
    code: str
    name: str


@dataclass(slots=True)
class ParsedCommodityGroup:
    code: str
    description: str | None

    parent_code: str | None
    product_group_code: str | None

    source_ref: str | None

    cost_code: str | None
    unit: str | None

    discount: Decimal | None
    wastage: Decimal | None
    estimation_factor: Decimal | None
    regie_factor: Decimal | None

    addition_1: str | None
    addition_2: str | None
    addition_3: str | None
    addition_4: str | None

    remarks: str | None

    fixed_hours: bool | None


@dataclass(slots=True)
class ParsedCommodityPrice:
    unit_price: Decimal
    currency: str

    discount: Decimal | None
    freight_costs: Decimal | None
    miscellaneous: Decimal | None
    wastage: Decimal | None

    modified_date: date | None
    modified_user: str | None


@dataclass(slots=True)
class ParsedEstimatePrice:
    price_type: str

    factor: Decimal | None
    price: Decimal
    currency: str

    modified_date: date | None
    modified_user: str | None

    fixed_price: bool | None


@dataclass(slots=True)
class ParsedCommodity:
    code: str
    description: str | None

    commodity_group_code: str
    product_group_code: str | None

    source_ref: str | None

    unit: str | None

    cost_code: str | None
    cost_code_unit: str | None

    weight: Decimal | None
    weight_unit: str | None

    volume: Decimal | None
    volume_unit: str | None

    addition_1: str | None
    addition_2: str | None
    addition_3: str | None
    addition_4: str | None

    remarks: str | None

    external_price_update: bool | None
    selected: bool | None
    fixed_hours: bool | None

    change_date: date | None
    change_user: str | None

    prices: list[ParsedCommodityPrice] = field(default_factory=list)
    estimate_prices: list[ParsedEstimatePrice] = field(default_factory=list)


@dataclass(slots=True)
class ParsedArticleData:
    product_groups: list[ParsedProductGroup] = field(default_factory=list)
    commodity_groups: list[ParsedCommodityGroup] = field(default_factory=list)
    commodities: list[ParsedCommodity] = field(default_factory=list)
