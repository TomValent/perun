import json
import string


class Parser:
    """ Parser for OpenTelemetry logs"""

    def parse_metric(self, line: string) -> tuple[string, float, string]:
        """Parse metric from log for profile"""

        data = json.loads(line)
        current = data['aggregator']['_current']

        if not isinstance(current, int):
            value = current.get("sum")
        else:
            value = current

        return data["descriptor"]["name"], value, data["labels"].get("route", "")

    def parse_trace(self, line: string):
        """Parse trace from log for profile"""

        data_dict = json.loads(line)
        pass
