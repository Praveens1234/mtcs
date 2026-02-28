import pytest
from app.core.trade_copier import TradeCopier
from app.core.trade_types import RiskConfig, LotSizingMode

@pytest.fixture
def mock_worker_manager():
    class MockWM:
        pass
    return MockWM()

@pytest.fixture
def mock_db():
    class MockDB:
        pass
    return MockDB()

def test_compute_slave_lot_multiplier(mock_worker_manager, mock_db):
    copier = TradeCopier(mock_worker_manager, mock_db)
    config = RiskConfig(lot_mode=LotSizingMode.MULTIPLIER, lot_multiplier=2.5)

    assert copier.compute_slave_lot(1.0, config) == 2.50
    assert copier.compute_slave_lot(0.01, config) == 0.03 # 0.01 * 2.5 = 0.025 rounded to 0.03
    assert copier.compute_slave_lot(0.05, config) == 0.12

def test_compute_slave_lot_fixed(mock_worker_manager, mock_db):
    copier = TradeCopier(mock_worker_manager, mock_db)
    config = RiskConfig(lot_mode=LotSizingMode.FIXED, fixed_lot=0.15)

    assert copier.compute_slave_lot(1.0, config) == 0.15
    assert copier.compute_slave_lot(10.0, config) == 0.15

def test_compute_slave_lot_equity_percent(mock_worker_manager, mock_db):
    copier = TradeCopier(mock_worker_manager, mock_db)
    # 50% of master lot
    config = RiskConfig(lot_mode=LotSizingMode.EQUITY_PERCENT, equity_percent=50, fixed_lot=0.01)

    assert copier.compute_slave_lot(1.0, config) == 0.50
    assert copier.compute_slave_lot(0.01, config) == 0.01 # minimum lot test
