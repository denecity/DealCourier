"""SQLAlchemy ORM models for DealCourier."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    JSON,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("platform", "platform_id", name="uq_platform_listing"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    platform_id: Mapped[str] = mapped_column(String, nullable=False)
    search_item_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("search_items.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String, default="CHF")
    url: Mapped[str] = mapped_column(String, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    search_term: Mapped[str | None] = mapped_column(String, nullable=True)
    seller_name: Mapped[str | None] = mapped_column(String, nullable=True)
    postcode: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    shipping_cost: Mapped[float] = mapped_column(Float, default=0.0)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    listed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    auction_end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # AI evaluation
    evaluated: Mapped[bool] = mapped_column(Boolean, default=False)
    eval_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    components: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    component_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    filter_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Outcome
    passed_filters: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    search_item: Mapped["SearchItem | None"] = relationship(back_populates="listings")


class SearchItem(Base):
    __tablename__ = "search_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    platforms: Mapped[list] = mapped_column(JSON, default=["tutti"])
    search_terms_specific_prompt: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    search_terms_general_prompt: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    search_terms_specific_count: Mapped[int] = mapped_column(Integer, default=50)
    search_terms_general_count: Mapped[int] = mapped_column(Integer, default=50)
    cached_search_terms: Mapped[list | None] = mapped_column(JSON, nullable=True)
    terms_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    min_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_profit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_value_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    eval_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    knowledge_base: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_filters: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    listings: Mapped[list["Listing"]] = relationship(back_populates="search_item")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    properties: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    estimated_value: Mapped[int] = mapped_column(Integer, nullable=False)
    value_trend: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=1)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, default="running")
    search_item_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("search_items.id", ondelete="SET NULL"), nullable=True
    )
    listings_found: Mapped[int] = mapped_column(Integer, default=0)
    listings_new: Mapped[int] = mapped_column(Integer, default=0)
    listings_evaluated: Mapped[int] = mapped_column(Integer, default=0)
    listings_passed: Mapped[int] = mapped_column(Integer, default=0)
    notifications_sent: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    response_schema: Mapped[dict] = mapped_column(JSON, nullable=False)
    model: Mapped[str] = mapped_column(String, default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Setting(Base):
    """Key-value settings store for global configuration like enabled shops."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class LogEntry(Base):
    """Stores log entries for the web UI log viewer."""

    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    level: Mapped[str] = mapped_column(String, nullable=False)
    logger_name: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
