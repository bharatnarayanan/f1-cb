"""Seed watchlist_constituents + sector_indices (F4.1, heavyweight/sector
correlation engine).

Symbol list matches docs/assumptions.md #6's documented default: top-15
NIFTY constituents by index weight + 5 sector indices. index_weight_pct is
left NULL rather than hardcoding a weight percentage — those drift over
time and NSE publishes the authoritative current figures; stating a
possibly-stale number here would misrepresent it as current fact. Both
tables are configurable at runtime (is_active flag) per that same
assumption.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTITUENTS = [
    ("RELIANCE", "Reliance Industries", "Energy"),
    ("HDFCBANK", "HDFC Bank", "Banking"),
    ("ICICIBANK", "ICICI Bank", "Banking"),
    ("INFY", "Infosys", "IT"),
    ("TCS", "Tata Consultancy Services", "IT"),
    ("LT", "Larsen & Toubro", "Infrastructure"),
    ("BHARTIARTL", "Bharti Airtel", "Telecom"),
    ("ITC", "ITC", "FMCG"),
    ("KOTAKBANK", "Kotak Mahindra Bank", "Banking"),
    ("AXISBANK", "Axis Bank", "Banking"),
    ("SBIN", "State Bank of India", "Banking"),
    ("BAJFINANCE", "Bajaj Finance", "Financial Services"),
    ("HINDUNILVR", "Hindustan Unilever", "FMCG"),
    ("M&M", "Mahindra & Mahindra", "Auto"),
    ("SUNPHARMA", "Sun Pharmaceutical", "Pharma"),
]

_SECTOR_INDICES = [
    ("NIFTY BANK", "Nifty Bank"),
    ("NIFTY IT", "Nifty IT"),
    ("NIFTY FMCG", "Nifty FMCG"),
    ("NIFTY PHARMA", "Nifty Pharma"),
    ("NIFTY AUTO", "Nifty Auto"),
]

_watchlist_table = sa.table(
    "watchlist_constituents",
    sa.column("symbol", sa.Text),
    sa.column("display_name", sa.Text),
    sa.column("sector", sa.Text),
)

_sector_table = sa.table(
    "sector_indices",
    sa.column("symbol", sa.Text),
    sa.column("display_name", sa.Text),
)


def upgrade() -> None:
    op.bulk_insert(
        _watchlist_table,
        [{"symbol": symbol, "display_name": name, "sector": sector} for symbol, name, sector in _CONSTITUENTS],
    )
    op.bulk_insert(
        _sector_table,
        [{"symbol": symbol, "display_name": name} for symbol, name in _SECTOR_INDICES],
    )


def downgrade() -> None:
    op.execute("DELETE FROM watchlist_constituents WHERE symbol IN ({})".format(
        ", ".join(f"'{symbol}'" for symbol, _, _ in _CONSTITUENTS)
    ))
    op.execute("DELETE FROM sector_indices WHERE symbol IN ({})".format(
        ", ".join(f"'{symbol}'" for symbol, _ in _SECTOR_INDICES)
    ))
