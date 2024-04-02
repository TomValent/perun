import datetime
import json
import string


class Parser:
    """ Parser for OpenTelemetry logs"""

    def parse_metric(self, line: str) -> tuple[str, float, str, datetime.date]:
        """Parse metric from log for profile"""

        data = json.loads(line)
        current = data['aggregator']['_current']

        timestamp_seconds = data['aggregator']['_lastUpdateTime'][0]
        timestamp_microseconds = data['aggregator']['_lastUpdateTime'][1]
        timestamp = datetime.datetime.fromtimestamp(timestamp_seconds) + datetime.timedelta(
            microseconds=timestamp_microseconds)

        if not isinstance(current, float):
            value = current.get("sum")
        else:
            value = current

        return data["descriptor"]["name"], value, data["labels"].get("route", ""), timestamp.isoformat()

    def parse_trace(self, line: str) -> None:
        """Parse trace from log for profile"""

        data_dict = json.loads(line)
        pass
