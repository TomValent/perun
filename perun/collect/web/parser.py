import json
import string


class Parser:
    """ Parser for OpenTelemetry logs"""

    def parse_metric(self, line: string, order: int) -> tuple[int, string, float]:
        """Parse metric from log for profile"""
        data = json.loads(line)
        current = data['aggregator']['_current']

        if not isinstance(current, int):
            value = current.get("sum")
        else:
            value = current

        return order, data["descriptor"]["name"], value

    def parse_trace(self, line: string):
        """Parse trace from log for profile"""
        data_dict = json.loads(line)
        pass

# {
#   "descriptor": {
#     "name": "request_latency_summary",
#     "description": "Latency of requests in milliseconds",
#     "unit": "ms",
#     "metricKind": 2,
#     "valueType": 1
#   },
#   "labels": {
#     "route": "/"
#   },
#   "aggregator": {
#     "kind": 2,
#     "_boundaries": [null],
#     "_current": {
#       "buckets": {
#         "boundaries": [null],
#         "counts": [1, 0]
#       },
#       "sum": 18.845782,
#       "count": 1
#     },
#     "_lastUpdateTime": [1710015898, 591803882]
#   },
#   "aggregationTemporality": 2,
#   "resource": {
#     "attributes": {
#       "service.name": "unknown_service:/usr/local/nodejs/bin/node",
#       "telemetry.sdk.language": "nodejs",
#       "telemetry.sdk.name": "opentelemetry",
#       "telemetry.sdk.version": "0.24.0"
#     }
#   },
#   "instrumentationLibrary": {
#     "name": "OpenTelemetry-metrics"
#   }
# }
