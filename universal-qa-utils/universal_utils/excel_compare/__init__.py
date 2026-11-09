"""openpyxl-based workbook comparison.

This module compares worksheets by position. It does not reconcile rows by
business key, and it does not claim parity with any commercial Excel engine.
"""

from universal_utils.excel_compare.engine import compare_workbooks

__all__ = ["compare_workbooks"]
