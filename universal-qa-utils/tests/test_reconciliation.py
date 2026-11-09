"""Reconciliation behavior, using synthetic rows rather than a real application."""

from __future__ import annotations

import inspect
import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from universal_utils import compare_excel
from universal_utils.data_reader import read_excel_table
from universal_utils.exceptions import DataReadError, DuplicateKeyError, ValidationError
from universal_utils.reconciliation import compare_csv, reconcile_data
from tests.conftest import write_csv, write_excel

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _excel(tmp_path: Path, rows_a: list[list[object]], rows_b: list[list[object]], **kwargs):
    source_a = write_excel(tmp_path / "a.xlsx", {"Data": rows_a})
    source_b = write_excel(tmp_path / "b.xlsx", {"Data": rows_b})
    return compare_excel(
        str(source_a),
        str(source_b),
        sheet_a="Data",
        sheet_b="Data",
        **kwargs,
    )


def test_all_records_match_and_report_rows(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [["ID", "Name"], ["001", "Ada"]],
        [["ID", "Name"], ["001", "Ada"]],
        key_a="ID",
        key_b="ID",
    )
    assert result.passed is True
    assert result.exceptions == 0
    assert result.total_records == 2
    assert result.matched == 1
    assert result.details["matched"][0]["row_a"] == 2
    assert result.details["matched"][0]["row_b"] == 2
    assert result.details["matched"][0]["key"] == "001"


def test_field_mismatch_is_a_result_not_an_exception(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [["ID", "Name"], ["1", "Ada"]],
        [["ID", "Name"], ["1", "Grace"]],
        key_a="ID",
        key_b="ID",
    )
    assert result.passed is False
    assert result.matched == 0
    assert result.mismatched == 1
    assert result.exceptions == 1
    reasons = [field["reason"] for field in result.details["mismatched"][0]["fields"]]
    assert reasons == ["mismatch"]
    assert result.details["field_issues"][0]["value_a"] == "Ada"
    assert result.details["field_issues"][0]["value_b"] == "Grace"


def test_missing_records_in_both_directions(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [["ID", "Name"], ["1", "Ada"], ["2", "Grace"]],
        [["ID", "Name"], ["2", "Grace"], ["3", "Alan"]],
        key_a="ID",
        key_b="ID",
    )
    assert result.matched == 1
    assert result.missing_in_b == 1
    assert result.missing_in_a == 1
    assert result.exceptions == 2
    assert {item["key"] for item in result.details["missing_in_b"]} == {"1"}
    assert {item["key"] for item in result.details["missing_in_a"]} == {"3"}


def test_duplicate_keys_are_not_expanded(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [["ID", "Name"], ["9", "First"], ["9", "Second"]],
        [["ID", "Name"], ["9", "First"], ["9", "Other"]],
        key_a="ID",
        key_b="ID",
    )
    assert result.matched == 0
    assert result.mismatched == 0
    assert result.duplicates == 4
    assert result.exceptions == 4
    assert result.details["compared"] == []
    assert {item["occurrences"] for item in result.details["duplicates"]} == {2}


def test_duplicate_blocks_unique_counterpart_without_counting_it_twice(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [["ID", "Name"], ["9", "Only"]],
        [["ID", "Name"], ["9", "One"], ["9", "Two"]],
        key_a="ID",
        key_b="ID",
    )
    assert result.duplicates == 2
    assert result.missing_in_a == 0
    assert result.missing_in_b == 0
    assert result.matched == 0
    assert len(result.details["blocked"]) == 1
    assert result.details["blocked"][0]["source"] == "A"
    assert result.exceptions == 2
    assert result.details["duplicates"][0]["counterpart_rows"] == [2]


def test_invalid_keys_are_not_counted_as_missing(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [["ID", "Name"], ["", "Ghost"], ["1", "Ada"]],
        [["ID", "Name"], ["1", "Ada"]],
        key_a="ID",
        key_b="ID",
    )
    assert result.invalid_keys == 1
    assert result.matched == 1
    assert result.missing_in_a == 0
    assert result.missing_in_b == 0
    assert result.details["invalid_keys"][0]["reason"] == "empty_key"
    assert result.exceptions == 1


def test_blank_rows_are_skipped(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [["ID", "Name"], ["1", "Ada"], ["", ""], ["   ", "   "]],
        [["ID", "Name"], ["1", "Ada"]],
        key_a="ID",
        key_b="ID",
    )
    assert result.passed is True
    assert result.total_records == 2
    assert result.invalid_keys == 0
    assert result.metadata["blank_rows_skipped"] == {"source_a": 2, "source_b": 0}


def test_composite_empty_component_is_invalid(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [["Country", "ID", "Name"], ["US", "", "Ada"]],
        [["Country", "ID", "Name"], ["US", "1", "Ada"]],
        key_a=["Country", "ID"],
        key_b=["Country", "ID"],
    )
    assert result.invalid_keys == 1
    assert result.missing_in_a == 1
    assert result.details["invalid_keys"][0]["reason"] == "empty_key_component"
    assert result.details["invalid_keys"][0]["empty_components"] == ["ID"]


def test_unmapped_and_mismatch_count_once(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [["ID", "Name", "Status Code"], ["1", "Nope", "S9999"]],
        [["ID", "Name", "Status"], ["1", "Yes", "Approved"]],
        key_a="ID",
        key_b="ID",
        field_mapping={"Name": "Name", "Status Code": "Status"},
        value_mappings={"Status Code": {"S0011": "Approved"}},
    )
    assert result.mismatched == 1
    assert result.unmapped == 1
    assert result.exceptions == 1
    assert len(result.details["field_issues"]) == 3
    assert {item["reason"] for item in result.details["field_issues"]} == {"mismatch", "unmapped"}


def test_unmapped_equal_text_is_still_not_a_match(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [["ID", "Status Code"], ["1", "S9999"]],
        [["ID", "Status"], ["1", "S9999"]],
        key_a="ID",
        key_b="ID",
        field_mapping={"Status Code": "Status"},
        value_mappings={"Status Code": {"S0011": "Approved"}},
    )
    assert result.matched == 0
    assert result.mismatched == 0
    assert result.unmapped == 1
    assert result.exceptions == 1
    assert result.details["compared"][0]["status"] == "unmapped"


def test_value_mapping_translates_before_compare(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [["ID", "Status Code"], ["1", "S0011"], ["2", "S0023"]],
        [["ID", "Status"], ["1", "Abandoned"], ["2", "Approved"]],
        key_a="ID",
        key_b="ID",
        field_mapping={"Status Code": "Status"},
        value_mappings={"Status Code": {"S0011": "Abandoned", "S0023": "Approved"}},
    )
    assert result.passed is True
    assert result.matched == 2
    assert result.details["compared"][0]["fields"][0]["value_a"] == "Abandoned"


def test_empty_datasets_pass(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [["ID", "Name"]],
        [["ID", "Name"]],
        key_a="ID",
        key_b="ID",
    )
    assert result.passed is True
    assert result.total_records == 0
    assert result.exceptions == 0


def test_one_empty_source_reports_missing_keys(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [["ID", "Name"], ["1", "Ada"]],
        [["ID", "Name"]],
        key_a="ID",
        key_b="ID",
    )
    assert result.passed is False
    assert result.missing_in_b == 1
    assert result.total_records == 1


def test_null_values_and_ignore_nulls(tmp_path: Path) -> None:
    rows_a = [["ID", "Name"], ["1", None], ["2", None]]
    rows_b = [["ID", "Name"], ["1", "Ada"], ["2", None]]
    strict = _excel(tmp_path, rows_a, rows_b, key_a="ID", key_b="ID", ignore_nulls=False)
    ignored = _excel(
        tmp_path / "nulls",
        rows_a,
        rows_b,
        key_a="ID",
        key_b="ID",
        ignore_nulls=True,
    )
    assert strict.mismatched == 1
    assert strict.matched == 1
    assert strict.details["field_issues"][0]["reason"] == "null_mismatch"
    assert ignored.passed is True
    assert ignored.matched == 2


def test_leading_zero_identifiers_stay_text(tmp_path: Path) -> None:
    same = _excel(
        tmp_path / "same",
        [["ID", "Name"], ["00123", "Ada"]],
        [["ID", "Name"], ["00123", "Ada"]],
        key_a="ID",
        key_b="ID",
    )
    different = _excel(
        tmp_path / "different",
        [["ID", "Name"], ["00123", "Ada"]],
        [["ID", "Name"], ["123", "Ada"]],
        key_a="ID",
        key_b="ID",
        numeric_tolerance=0.1,
    )
    numeric_cells = _excel(
        tmp_path / "numeric",
        [["ID", "Name"], [123, "Ada"]],
        [["ID", "Name"], ["123", "Ada"]],
        key_a="ID",
        key_b="ID",
    )
    assert same.passed is True
    assert same.details["matched"][0]["key"] == "00123"
    assert different.matched == 0
    assert different.missing_in_a == 1
    assert different.missing_in_b == 1
    assert numeric_cells.passed is True


def test_composite_keys_use_every_component(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [["Country", "ID", "Name"], ["US", "001", "Ada"], ["US", "002", "Grace"]],
        [["Nation", "Code", "Name"], ["US", "001", "Ada"], ["CA", "001", "Grace"]],
        key_a=["Country", "ID"],
        key_b=["Nation", "Code"],
    )
    assert result.matched == 1
    assert result.details["matched"][0]["key"] == "US||001"
    assert result.missing_in_a == 1
    assert result.missing_in_b == 1


def test_numeric_tolerance_and_explicit_number_type(tmp_path: Path) -> None:
    within = _excel(
        tmp_path / "within",
        [["ID", "Amount"], ["1", "10.00"]],
        [["ID", "Amount"], ["1", "10.05"]],
        key_a="ID",
        key_b="ID",
        numeric_tolerance=0.05,
    )
    outside = _excel(
        tmp_path / "outside",
        [["ID", "Amount"], ["1", "10.00"]],
        [["ID", "Amount"], ["1", "10.05"]],
        key_a="ID",
        key_b="ID",
        numeric_tolerance=0.04,
    )
    text_form = _excel(
        tmp_path / "text",
        [["ID", "Amount"], ["1", "10.00"]],
        [["ID", "Amount"], ["1", "10"]],
        key_a="ID",
        key_b="ID",
    )
    explicit = _excel(
        tmp_path / "explicit",
        [["ID", "Amount"], ["1", "10.00"]],
        [["ID", "Amount"], ["1", "10"]],
        key_a="ID",
        key_b="ID",
        comparison_rules={"Amount": {"type": "number"}},
    )
    identifiers = _excel(
        tmp_path / "ids",
        [["ID", "Code"], ["1", "001"]],
        [["ID", "Code"], ["1", "1"]],
        key_a="ID",
        key_b="ID",
        numeric_tolerance=0.1,
    )
    coerced = _excel(
        tmp_path / "coerced",
        [["ID", "Code"], ["1", "001"]],
        [["ID", "Code"], ["1", "1"]],
        key_a="ID",
        key_b="ID",
        comparison_rules={"Code": {"type": "number"}},
    )
    assert within.passed is True
    assert outside.mismatched == 1
    assert text_form.mismatched == 1
    assert explicit.passed is True
    assert identifiers.mismatched == 1
    assert coerced.passed is True


def test_case_sensitivity_for_values_and_keys(tmp_path: Path) -> None:
    sensitive = _excel(
        tmp_path / "sensitive",
        [["ID", "Name"], ["ABC", "Ada"]],
        [["ID", "Name"], ["abc", "ada"]],
        key_a="ID",
        key_b="ID",
    )
    folded = _excel(
        tmp_path / "folded",
        [["ID", "Name"], ["ABC", "Ada"]],
        [["ID", "Name"], ["abc", "ada"]],
        key_a="ID",
        key_b="ID",
        ignore_case=True,
    )
    assert sensitive.matched == 0
    assert sensitive.missing_in_a == 1
    assert sensitive.missing_in_b == 1
    assert folded.passed is True
    assert folded.details["matched"][0]["key"] == "ABC"


def test_case_insensitive_keys_collapse_duplicates(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [["ID", "Name"], ["ABC", "One"], ["abc", "Two"]],
        [["ID", "Name"], ["abc", "One"]],
        key_a="ID",
        key_b="ID",
        ignore_case=True,
    )
    assert result.duplicates == 2
    assert result.matched == 0
    assert len(result.details["blocked"]) == 1


def test_date_normalization(tmp_path: Path) -> None:
    normalized = _excel(
        tmp_path / "normalized",
        [["ID", "Start"], ["1", datetime(2024, 1, 2)]],
        [["ID", "Start"], ["1", "01/02/2024"]],
        key_a="ID",
        key_b="ID",
        comparison_rules={"Start": {"type": "date", "date_formats": ["%m/%d/%Y"]}},
    )
    timestamp = _excel(
        tmp_path / "timestamp",
        [["ID", "Start"], ["1", "2024-01-02 15:30:00"]],
        [["ID", "Start"], ["1", "2024-01-02"]],
        key_a="ID",
        key_b="ID",
        comparison_rules={"Start": {"type": "date"}},
    )
    invalid = _excel(
        tmp_path / "invalid",
        [["ID", "Start"], ["1", "not-a-date"]],
        [["ID", "Start"], ["1", "2024-01-02"]],
        key_a="ID",
        key_b="ID",
        comparison_rules={"Start": {"type": "date"}},
    )
    assert normalized.passed is True
    assert timestamp.passed is True
    assert invalid.details["field_issues"][0]["reason"] == "date_parse_failure"


def test_excel_dates_are_canonical_before_comparison(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [["ID", "Start"], ["1", datetime(2024, 1, 2)]],
        [["ID", "Start"], ["1", datetime(2024, 1, 2)]],
        key_a="ID",
        key_b="ID",
    )
    assert result.passed is True
    assert result.details["matched"][0]["fields"][0]["value_a"] == "2024-01-02"


def test_different_sheet_names_and_indexes(tmp_path: Path) -> None:
    source_a = write_excel(
        tmp_path / "a.xlsx",
        {
            "Wrong": [["ID", "Name"], ["9", "Wrong"]],
            "Accounts": [["ID", "Name"], ["1", "Ada"]],
        },
    )
    source_b = write_excel(
        tmp_path / "b.xlsx",
        {"Directory": [["ID", "Name"], ["1", "Ada"]]},
    )
    by_name = compare_excel(
        str(source_a),
        str(source_b),
        sheet_a="Accounts",
        sheet_b="Directory",
        key_a="ID",
        key_b="ID",
    )
    by_index = compare_excel(
        str(source_a),
        str(source_b),
        sheet_a=1,
        sheet_b=0,
        key_a="ID",
        key_b="ID",
    )
    assert by_name.passed is True
    assert by_index.passed is True
    assert by_index.metadata["sheet_a"] == 1


def test_different_column_names_and_auto_mapping(tmp_path: Path) -> None:
    renamed = _excel(
        tmp_path / "renamed",
        [["Customer ID", "Customer Name", "Extra"], ["1", "Ada", "ignore"]],
        [["Cust ID", "Name", "Other"], ["1", "Ada", "different"]],
        key_a="Customer ID",
        key_b="Cust ID",
        field_mapping={"Customer Name": "Name"},
    )
    shared = _excel(
        tmp_path / "shared",
        [["ID", "Name", "Extra"], ["1", "Ada", "left"]],
        [["ID", "Name", "Other"], ["1", "Ada", "right"]],
        key_a="ID",
        key_b="ID",
    )
    key_only = _excel(
        tmp_path / "keys",
        [["ID", "Name"], ["1", "Ada"]],
        [["ID", "Name"], ["1", "Grace"]],
        key_a="ID",
        key_b="ID",
        field_mapping={},
    )
    assert renamed.passed is True
    assert shared.passed is True
    assert shared.metadata["compared_fields"] == [{"source_a": "Name", "source_b": "Name"}]
    assert key_only.passed is True
    assert key_only.metadata["compared_fields"] == []


def test_headers_are_stripped(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [[" ID ", " Name "], ["1", "Ada"]],
        [["ID", "Name"], ["1", "Ada"]],
        key_a="ID",
        key_b="ID",
    )
    assert result.passed is True


def test_csv_comparison_preserves_text_and_delimiter(tmp_path: Path) -> None:
    source_a = write_csv(
        tmp_path / "a.csv",
        [["ID", "Name"], ["001", "Ada"]],
        delimiter=";",
    )
    source_b = write_csv(
        tmp_path / "b.csv",
        [["ID", "Name"], ["001", "Ada"]],
        delimiter=";",
    )
    result = compare_csv(
        str(source_a),
        str(source_b),
        key_a="ID",
        key_b="ID",
        delimiter=";",
    )
    assert result.passed is True
    assert result.details["matched"][0]["key"] == "001"
    assert result.details["matched"][0]["row_a"] == 2
    assert result.metadata["origin_a"] == "csv"


def test_csv_bom_is_removed_from_header(tmp_path: Path) -> None:
    source_a = tmp_path / "a.csv"
    source_b = tmp_path / "b.csv"
    payload = "ID,Name\n001,Ada\n".encode("utf-8")
    source_a.write_bytes(b"\xef\xbb\xbf" + payload)
    source_b.write_bytes(payload)
    result = compare_csv(str(source_a), str(source_b), key_a="ID", key_b="ID")
    assert result.passed is True


def test_dataframe_comparison_uses_positional_row_numbers() -> None:
    source_a = pd.DataFrame([{"ID": "001", "Amount": "10.00"}])
    source_b = pd.DataFrame([{"Code": "001", "Amount": "10.02"}])
    result = reconcile_data(
        source_a,
        source_b,
        key_a="ID",
        key_b="Code",
        field_mapping={"Amount": "Amount"},
        numeric_tolerance=0.05,
    )
    assert result.passed is True
    assert result.details["matched"][0]["row_a"] == 1
    assert result.metadata["origin_a"] == "dataframe"


def test_two_unrelated_layouts_share_one_function(tmp_path: Path) -> None:
    customers = _excel(
        tmp_path / "customers",
        [["Customer ID", "City"], ["1", "Paris"]],
        [["Customer ID", "City"], ["1", "Paris"]],
        key_a="Customer ID",
        key_b="Customer ID",
    )
    invoices = _excel(
        tmp_path / "invoices",
        [["Invoice No", "Total"], ["A-1", "5"]],
        [["Invoice No", "Total"], ["A-1", "5"]],
        key_a="Invoice No",
        key_b="Invoice No",
    )
    assert customers.passed is True
    assert invoices.passed is True


def test_requested_call_shape_with_synthetic_rows(tmp_path: Path) -> None:
    source_a = write_excel(
        tmp_path / "left.xlsx",
        {
            "CAM": [
                ["PCID", "PCID Name", "PCID Description", "Status Code"],
                ["001", "Ada", "First program", "S0011"],
            ]
        },
    )
    source_b = write_excel(
        tmp_path / "right.xlsx",
        {
            "MDG": [
                ["ID", "Name", "Program Description", "Status Description"],
                ["001", "Ada", "First program", "Abandoned"],
            ]
        },
    )
    output = tmp_path / "reports" / "cam_mdg.xlsx"
    result = compare_excel(
        source_a=str(source_a),
        source_b=str(source_b),
        sheet_a="CAM",
        sheet_b="MDG",
        key_a="PCID",
        key_b="ID",
        field_mapping={
            "PCID Name": "Name",
            "PCID Description": "Program Description",
            "Status Code": "Status Description",
        },
        value_mappings={"Status Code": {"S0011": "Abandoned", "S0023": "Approved"}},
        generate_report=True,
        output_path=str(output),
    )
    assert result.passed is True
    assert result.exceptions == 0
    assert result.report_path == str(output.resolve())
    parsed = json.loads(result.to_json())
    assert parsed["passed"] is True
    assert output.is_file()


def test_json_is_deterministic(tmp_path: Path) -> None:
    source_a = write_excel(tmp_path / "a.xlsx", {"Data": [["ID", "Name"], ["1", "Ada"]]})
    source_b = write_excel(tmp_path / "b.xlsx", {"Data": [["ID", "Name"], ["1", "Ada"]]})
    kwargs = {
        "source_a": str(source_a),
        "source_b": str(source_b),
        "sheet_a": "Data",
        "sheet_b": "Data",
        "key_a": "ID",
        "key_b": "ID",
        "generate_report": False,
    }
    first = compare_excel(**kwargs)
    second = compare_excel(**kwargs)
    assert first.to_json() == second.to_json()
    assert first.report_path is None
    payload = json.loads(first.to_json())
    assert payload["metadata"]["numeric_tolerance"] is None
    assert list(payload) == sorted(payload)


def test_empty_key_parameter_is_rejected_before_reading(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="key_a"):
        compare_excel(str(tmp_path / "missing-a.xlsx"), str(tmp_path / "missing-b.xlsx"))
    with pytest.raises(ValidationError, match="key_b"):
        compare_excel("a.xlsx", "b.xlsx", key_a="ID", key_b=[])
    with pytest.raises(ValidationError, match="duplicate column"):
        compare_excel("a.xlsx", "b.xlsx", key_a=["ID", "ID"], key_b="ID")


def test_missing_column_file_and_sheet(tmp_path: Path) -> None:
    source_a = write_excel(tmp_path / "a.xlsx", {"Data": [["ID", "Name"], ["1", "Ada"]]})
    source_b = write_excel(tmp_path / "b.xlsx", {"Data": [["ID", "Name"], ["1", "Ada"]]})
    with pytest.raises(ValidationError, match="key_a"):
        compare_excel(str(source_a), str(source_b), key_a="Missing", key_b="ID")
    with pytest.raises(DataReadError, match="Excel file not found"):
        compare_excel(str(tmp_path / "absent.xlsx"), str(source_b), key_a="ID", key_b="ID")
    with pytest.raises(DataReadError, match="was not found"):
        compare_excel(str(source_a), str(source_b), sheet_a="Missing", key_a="ID", key_b="ID")
    with pytest.raises(ValidationError, match="sheet_a"):
        compare_excel(str(source_a), str(source_b), sheet_a=True, key_a="ID", key_b="ID")


def test_duplicate_header_and_extra_cell(tmp_path: Path) -> None:
    duplicated = write_excel(tmp_path / "dup.xlsx", {"Data": [["ID", "ID"], ["1", "Ada"]]})
    other = write_excel(tmp_path / "ok.xlsx", {"Data": [["ID", "Name"], ["1", "Ada"]]})
    with pytest.raises(DataReadError, match="duplicate column"):
        compare_excel(str(duplicated), str(other), key_a="ID", key_b="ID")
    extra = write_excel(tmp_path / "extra.xlsx", {"Data": [["ID", "Name"], ["1", "Ada", "unexpected"]]})
    with pytest.raises(DataReadError, match="outside the header"):
        read_excel_table(extra, "Data")


def test_conflicting_rules_are_rejected(tmp_path: Path) -> None:
    rows = [["ID", "Amount"], ["1", "10"]]
    with pytest.raises(ValidationError, match="conflict"):
        _excel(
            tmp_path / "number-date",
            rows,
            rows,
            key_a="ID",
            key_b="ID",
            comparison_rules={"Amount": {"type": "number", "date_formats": ["%Y-%m-%d"]}},
        )
    with pytest.raises(ValidationError, match="unknown option"):
        _excel(
            tmp_path / "unknown",
            rows,
            rows,
            key_a="ID",
            key_b="ID",
            comparison_rules={"Amount": {"numeric": True}},
        )
    with pytest.raises(ValidationError, match="numeric_tolerance"):
        _excel(
            tmp_path,
            rows,
            rows,
            key_a="ID",
            key_b="ID",
            numeric_tolerance=-1,
        )


def test_detect_duplicates_false_refuses_to_guess(tmp_path: Path) -> None:
    with pytest.raises(DuplicateKeyError, match="detect_duplicates is False") as captured:
        _excel(
            tmp_path,
            [["ID", "Name"], ["9", "One"], ["9", "Two"]],
            [["ID", "Name"], ["9", "One"]],
            key_a="ID",
            key_b="ID",
            detect_duplicates=False,
        )
    assert captured.value.duplicates[0]["key"] == "9"
    assert captured.value.duplicates[0]["occurrences"] == 2


def test_bidirectional_false_ignores_extra_source_b_rows(tmp_path: Path) -> None:
    rows_a = [["ID", "Name"], ["1", "Ada"]]
    rows_b = [["ID", "Name"], ["1", "Ada"], ["9", "Extra"], ["8", "Dup"], ["8", "Dup"]]
    one_way = _excel(
        tmp_path / "one-way",
        rows_a,
        rows_b,
        key_a="ID",
        key_b="ID",
        bidirectional=False,
    )
    both_ways = _excel(
        tmp_path / "both",
        rows_a,
        rows_b,
        key_a="ID",
        key_b="ID",
        bidirectional=True,
    )
    assert one_way.passed is True
    assert one_way.missing_in_a == 0
    assert {item["key"] for item in one_way.details["not_evaluated"]} == {"9", "8"}
    assert one_way.duplicates == 0
    assert both_ways.passed is False
    assert both_ways.missing_in_a == 1
    assert both_ways.duplicates == 2


def test_generate_report_false_does_not_write(tmp_path: Path) -> None:
    output = tmp_path / "should-not-exist.xlsx"
    result = _excel(
        tmp_path,
        [["ID", "Name"], ["1", "Ada"]],
        [["ID", "Name"], ["1", "Ada"]],
        key_a="ID",
        key_b="ID",
        generate_report=False,
        output_path=str(output),
    )
    assert result.report_path is None
    assert not output.exists()


def test_category_list_lengths_match_metrics(tmp_path: Path) -> None:
    result = _excel(
        tmp_path,
        [
            ["ID", "Name"],
            ["K1", "Ada"],
            ["K2", "Bob"],
            ["K3", "Only A"],
            ["K4", "Dup"],
            ["K4", "Dup"],
            ["K6", "Block"],
            ["", ""],
            ["", "Ghost"],
        ],
        [
            ["ID", "Name"],
            ["K1", "Ada"],
            ["K2", "Robert"],
            ["K5", "Only B"],
            ["K6", "One"],
            ["K6", "Two"],
        ],
        key_a="ID",
        key_b="ID",
    )
    assert result.total_records == 12
    assert result.matched == 1
    assert result.mismatched == 1
    assert result.missing_in_a == 1
    assert result.missing_in_b == 1
    assert result.duplicates == 4
    assert result.invalid_keys == 1
    assert result.unmapped == 0
    assert result.exceptions == 8
    assert len(result.details["blocked"]) == 1
    assert result.metadata["blank_rows_skipped"]["source_a"] == 1
    for name in (
        "matched",
        "mismatched",
        "missing_in_a",
        "missing_in_b",
        "duplicates",
        "invalid_keys",
        "unmapped",
    ):
        assert len(result.details[name]) == getattr(result, name)


def test_logs_do_not_include_source_values(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        _excel(
            tmp_path,
            [["ID", "Name"], ["1", "SUPER-SECRET-VALUE"]],
            [["ID", "Name"], ["1", "SUPER-SECRET-VALUE"]],
            key_a="ID",
            key_b="ID",
        )
    assert "Reconciliation finished" in caplog.text
    assert "SUPER-SECRET-VALUE" not in caplog.text


def test_engine_has_no_application_or_framework_terms() -> None:
    forbidden = ("PCID", "MDG", "CAM", "Tosca", "Playwright", "Robot Framework")
    for path in (PACKAGE_ROOT / "universal_utils").rglob("*.py"):
        # Framework adapters are allowed to contain framework-specific terminology.
        if "robot" in path.relative_to(PACKAGE_ROOT / "universal_utils").parts:
            continue
        source = path.read_text(encoding="utf-8")
        for term in forbidden:
            assert term not in source, f"{term} found in {path.name}"


def test_public_compare_excel_signature() -> None:
    signature = inspect.signature(compare_excel)
    assert list(signature.parameters) == [
        "source_a",
        "source_b",
        "sheet_a",
        "sheet_b",
        "key_a",
        "key_b",
        "field_mapping",
        "value_mappings",
        "comparison_rules",
        "ignore_case",
        "trim_whitespace",
        "ignore_nulls",
        "numeric_tolerance",
        "detect_duplicates",
        "bidirectional",
        "output_path",
        "generate_report",
    ]
    assert signature.parameters["sheet_a"].default == 0
    assert signature.parameters["key_a"].default == ""
    assert signature.parameters["trim_whitespace"].default is True
    assert signature.parameters["generate_report"].default is False
