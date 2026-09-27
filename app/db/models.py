from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    __table_args__ = (
        CheckConstraint(
            "balance >= 0",
            name="balance_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    balance: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    # Transfers sent by this account
    outgoing_transfers: Mapped[list["Transfer"]] = relationship(
        foreign_keys="Transfer.from_account_id",
        back_populates="from_account",
    )

    # Transfers received by this account
    incoming_transfers: Mapped[list["Transfer"]] = relationship(
        foreign_keys="Transfer.to_account_id",
        back_populates="to_account",
    )


class Transfer(Base):
    __tablename__ = "transfers"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="amount_positive",
        ),
        CheckConstraint(
            "from_account_id <> to_account_id",
            name="distinct_accounts",
        ),
        Index(
            "ix_transfers_from_account_id",
            "from_account_id",
        ),
        Index(
            "ix_transfers_to_account_id",
            "to_account_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    from_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"),
        nullable=False,
    )

    to_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"),
        nullable=False,
    )

    amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    idempotency_key: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    # Sender
    from_account: Mapped["Account"] = relationship(
        foreign_keys=[from_account_id],
        back_populates="outgoing_transfers",
    )

    # Receiver
    to_account: Mapped["Account"] = relationship(
        foreign_keys=[to_account_id],
        back_populates="incoming_transfers",
    )