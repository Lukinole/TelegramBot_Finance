# constants.py

from enum import Enum, auto

class ProcessingState(Enum):
    NORMAL_PROCESSING = auto()
    ADD_TO_LIST = auto()
    ADD_CATEGORY = auto()
    DELETE_CATEGORY = auto()
    EDIT_CATEGORY = auto()
    EDIT_CATEGORY_NAME = auto()
    EDIT_FOR_FILTER = auto()
    NEW_TRANSACTION_DATA = auto()
    XLSX = auto()
    CSV = auto()
    JSON = auto()
    REPORT_DATE_RANGE = auto()
    SET_DEFAULT_CURRENCY = auto()

# Для обратной совместимости
NORMAL_PROCESSING = ProcessingState.NORMAL_PROCESSING
ADD_TO_LIST = ProcessingState.ADD_TO_LIST
ADD_CATEGORY = ProcessingState.ADD_CATEGORY
DELETE_CATEGORY = ProcessingState.DELETE_CATEGORY
EDIT_CATEGORY = ProcessingState.EDIT_CATEGORY
EDIT_CATEGORY_NAME = ProcessingState.EDIT_CATEGORY_NAME
EDIT_FOR_FILTER = ProcessingState.EDIT_FOR_FILTER
NEW_TRANSACTION_DATA = ProcessingState.NEW_TRANSACTION_DATA
XLSX = ProcessingState.XLSX
CSV = ProcessingState.CSV
JSON = ProcessingState.JSON
REPORT_DATE_RANGE = ProcessingState.REPORT_DATE_RANGE
SET_DEFAULT_CURRENCY = ProcessingState.SET_DEFAULT_CURRENCY
