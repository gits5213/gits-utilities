"""Compatibility import for the installed Robot Framework library.

The keyword implementation is ``universal_utils.robot.ReconciliationLibrary``.
This module remains so ``adapters.robot`` imports keep resolving to that class.
"""

from universal_utils.robot.ReconciliationLibrary import ReconciliationLibrary

__all__ = ["ReconciliationLibrary"]
