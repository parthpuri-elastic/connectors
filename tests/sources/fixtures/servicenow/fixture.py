#
# Copyright Elasticsearch B.V. and/or licensed to Elasticsearch B.V. under one
# or more contributor license agreements. Licensed under the Elastic License 2.0;
# you may not use this file except in compliance with the Elastic License 2.0.
#
"""Module to responsible to generate ServiceNow documents using the Flask framework.
"""
import base64
import io
import os
from urllib.parse import parse_qs, urlparse

from flask import Flask, make_response, request

from tests.commons import WeightedFakeProvider

fake_provider = WeightedFakeProvider()

DATA_SIZE = os.environ.get("DATA_SIZE", "medium").lower()

match DATA_SIZE:
    case "small":
        RECORDS = 250
        TABLE_PAGES = 3
    case "medium":
        RECORDS = 500
        TABLE_PAGES = 6
    case "large":
        RECORDS = 5000
        TABLE_PAGES = 12
    case _:
        raise Exception(
            f"Unknown DATA_SIZE: {DATA_SIZE}. Expecting 'small', 'medium' or 'large'"
        )

TABLE_PAGE_SIZE = 50
RECORDS_TO_DELETE = 50


class ServiceNowAPI:
    def __init__(self):
        self.app = Flask(__name__)
        self.table_length = RECORDS
        self.get_table_length_call = TABLE_PAGES
        self.files = {}
        self.app.route("/api/now/table/<string:table>", methods=["GET"])(
            self.get_table_length
        )
        self.app.route("/api/now/attachment/<string:sys_id>/file", methods=["GET"])(
            self.get_attachment_content
        )
        self.app.route("/api/now/v1/batch", methods=["POST"])(self.get_batch_data)

    def get_servicenow_formatted_data(self, response_key, response_data):
        return bytes(str({response_key: response_data}).replace("'", '"'), "utf-8")

    def get_url_data(self, url):
        parsed_url = urlparse(url)
        return parsed_url.path, parse_qs(parsed_url.query)

    def decode_response(self, response):
        return base64.b64encode(response).decode()

    def get_batch_data(self):
        batch_data = request.get_json()
        response = []
        for rest_request in batch_data["rest_requests"]:
            path, query_params = self.get_url_data(url=rest_request["url"])
            last_endpoint = path.split("/")[-1]
            if last_endpoint == "attachment":
                table_sys_id = query_params["table_sys_id"]
                attachment_data = self.get_attachment_data(table_sys_id=table_sys_id[0])
                response.append(
                    {
                        "body": self.decode_response(response=attachment_data),
                        "status_code": 200,
                    }
                )
            else:
                table_name = last_endpoint
                table_offset = query_params["sysparm_offset"]
                table_data = self.get_table_data(
                    table=table_name, offset=int(table_offset[0])
                )
                response.append(
                    {
                        "body": self.decode_response(response=table_data),
                        "status_code": 200,
                    }
                )
        batch_response = make_response(
            self.get_servicenow_formatted_data(
                response_key="serviced_requests", response_data=response
            )
        )
        batch_response.headers["Content-Type"] = "application/json"
        return batch_response

    def get_table_length(self, table):
        response = make_response(bytes(str({"Response": "Dummy"}), "utf-8"))
        response.headers["Content-Type"] = "application/json"
        if int(request.args["sysparm_limit"]) == 1:
            response.headers["x-total-count"] = self.table_length
        else:
            response.headers["x-total-count"] = 0
        self.get_table_length_call -= 1
        if self.get_table_length_call == 0:
            self.table_length = (
                RECORDS - RECORDS_TO_DELETE
            )  # to delete RECORDS_TO_DELETE records per service in next sync
        return response

    def get_table_data(self, table, offset):
        records = []
        for i in range(offset - TABLE_PAGE_SIZE, offset):
            records.append(
                {
                    "sys_id": f"{table}-{i}",
                    "sys_updated_on": "1212-12-12",
                    "sys_class_name": table,
                }
            )
        return self.get_servicenow_formatted_data(
            response_key="result", response_data=records
        )

    def get_attachment_data(self, table_sys_id):
        file = fake_provider.get_html()
        attachment_id = f"attachment-{table_sys_id}"
        self.files[attachment_id] = file
        record = [
            {
                "sys_id": attachment_id,
                "sys_updated_on": "2012-12-12",
                "size_bytes": len(file.encode("utf-8")),
                "file_name": f"{table_sys_id}.html",
            }
        ]
        return self.get_servicenow_formatted_data(
            response_key="result", response_data=record
        )

    def get_attachment_content(self, sys_id):
        file = self.files[sys_id]
        return io.BytesIO(bytes(file, encoding="utf-8"))


if __name__ == "__main__":
    ServiceNowAPI().app.run(host="0.0.0.0", port=9318)
