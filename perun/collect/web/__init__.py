"""Trace collector collects running times of C/C++ functions.
The collected data are suitable for further postprocessing using
the regression analysis and visualization by scatter plots.
"""

COLLECTOR_TYPE = "web"
COLLECTOR_DEFAULT_UNITS = {
    "page_requests":           "",
    "error_count":             "",
    "error_code_count":        "",
    "error_message_count":     "",
    "memory_usage_counter":    "bits",
    "request_latency_summary": "ms",
}
