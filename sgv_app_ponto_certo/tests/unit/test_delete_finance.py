"""Tests for delete functionality in financial management"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datetime import datetime

from models.db_models import Expense, Receivable, get_session, init_db


def test_delete_expense():
    """Test deleting an expense"""
    engine = init_db()
    session = get_session(engine)

    # Create a test expense
    expense = Expense(
        descricao="Despesa Teste Delete",
        valor=100.00,
        status="Pendente",
        vencimento=datetime(2025, 12, 31),
    )
    session.add(expense)
    session.commit()
    expense_id = expense.id

    # Verify it was created
    exp_before = session.get(Expense, expense_id)
    assert exp_before is not None

    # Delete it
    session.delete(exp_before)
    session.commit()

    # Verify it's gone
    exp_after = session.get(Expense, expense_id)
    assert exp_after is None


def test_delete_receivable():
    """Test deleting a receivable"""
    engine = init_db()
    session = get_session(engine)

    # Create a test receivable
    receivable = Receivable(
        descricao="Receita Teste Delete",
        valor=200.00,
        status="Pendente",
        vencimento=datetime(2025, 12, 31),
    )
    session.add(receivable)
    session.commit()
    receivable_id = receivable.id

    # Verify it was created
    rec_before = session.get(Receivable, receivable_id)
    assert rec_before is not None

    # Delete it
    session.delete(rec_before)
    session.commit()

    # Verify it's gone
    rec_after = session.get(Receivable, receivable_id)
    assert rec_after is None
