from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_networth_history_is_a_separate_service_with_its_own_schema():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    setup = (ROOT / "services/networth_history/scripts/setup_schema.sql").read_text(encoding="utf-8")

    assert "  networth-history:" in compose
    assert "NETWORTH_HISTORY_SCHEMA: GREENLINE_NW_HISTORY" in compose
    assert "CREATE USER GREENLINE_NW_HISTORY" in setup
    assert "GRANT SELECT ON ADMIN.transactions TO GREENLINE_NW_HISTORY" in setup
    assert "CREATE TABLE GREENLINE_NW_HISTORY.networth_snapshots" in setup
    assert "GRANT INSERT, UPDATE, DELETE ON ADMIN.transactions" not in setup


def test_legacy_snapshot_paths_are_proxied_to_the_history_service():
    main = (ROOT / "services/networth/app/main.py").read_text(encoding="utf-8")
    assert "networth_history_proxy" in main
    assert "include_router(snapshots.router" not in main
