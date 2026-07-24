import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.reports.summary import build_summary
from app.reports.excel_export import build_summary_workbook
from app.parsers.fortigate.parser import FortiGateParser

SAMPLE_PATH = Path(__file__).resolve().parents[2] / "samples" / "fortigate_sample.conf"


def _parse_sample():
    text = SAMPLE_PATH.read_text()
    return FortiGateParser(raw_text=text, filename="fortigate_sample.conf").parse()


def test_summary_counts_match_config():
    cfg = _parse_sample()
    summary = build_summary(cfg)
    assert summary["counts"]["addresses"] == len(cfg.addresses)
    assert summary["counts"]["policies"] == len(cfg.policies)
    assert summary["counts"]["nat_rules"] == len(cfg.nat_rules)


def test_summary_tables_have_expected_rows():
    cfg = _parse_sample()
    summary = build_summary(cfg)
    address_names = {row["Name"] for row in summary["tables"]["addresses"]}
    assert "Server01" in address_names
    assert "InternalNet" in address_names

    policy_names = {row["Name"] for row in summary["tables"]["policies"]}
    assert "Allow_LAN_to_WebServers" in policy_names

    # table row count matches the object count exactly
    assert len(summary["tables"]["addresses"]) == len(cfg.addresses)
    assert len(summary["tables"]["services"]) == len(cfg.services)


def test_excel_workbook_has_one_sheet_per_category_plus_overview():
    cfg = _parse_sample()
    wb = build_summary_workbook(cfg, vendor="fortigate", source_filename="fortigate_sample.conf")
    sheet_names = set(wb.sheetnames)
    assert "Overview" in sheet_names
    assert "Addresses" in sheet_names
    assert "Security Policies" in sheet_names
    assert "NAT Rules" in sheet_names


def test_excel_workbook_address_sheet_has_correct_row_count():
    cfg = _parse_sample()
    wb = build_summary_workbook(cfg, vendor="fortigate", source_filename="fortigate_sample.conf")
    ws = wb["Addresses"]
    # header row + one row per address object
    data_rows = ws.max_row - 1
    assert data_rows == len(cfg.addresses)


def test_excel_workbook_handles_empty_category_gracefully():
    cfg = _parse_sample()
    cfg.routes = []  # force an empty category
    wb = build_summary_workbook(cfg, vendor="fortigate", source_filename="fortigate_sample.conf")
    ws = wb["Routes"]
    assert ws.cell(row=1, column=1).value.startswith("No objects")
