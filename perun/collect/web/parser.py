import datetime
import json
import string


class Parser:
    """ Parser for OpenTelemetry logs"""

    def parse_metric(self, line: string) -> tuple[string, float, string, datetime]:
        """Parse metric from log for profile"""

        data = json.loads(line)
        current = data['aggregator']['_current']

        timestamp_seconds = data['aggregator']['_lastUpdateTime'][0]
        timestamp_microseconds = data['aggregator']['_lastUpdateTime'][1]
        timestamp = datetime.datetime.fromtimestamp(timestamp_seconds) + datetime.timedelta(
            microseconds=timestamp_microseconds)

        if not isinstance(current, int):
            value = current.get("sum")
        else:
            value = current

        return data["descriptor"]["name"], value, data["labels"].get("route", ""), timestamp.isoformat()


    def parse_trace(self, line: string):
        """Parse trace from log for profile"""

        data_dict = json.loads(line)
        pass
