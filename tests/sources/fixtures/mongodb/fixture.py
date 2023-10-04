import os

import bson
from pymongo import MongoClient
from tests.commons import WeightedFakeProvider

fake_provider = WeightedFakeProvider(weights=[0.65, 0.3, 0.05, 0]) # extra large is too large for MongoDB record

NUMBER_OF_RECORDS_TO_DELETE = 50

fake = fake_provider.fake

client = MongoClient("mongodb://admin:justtesting@127.0.0.1:27021")

DATA_SIZE = os.environ.get("DATA_SIZE", "medium").lower()

match DATA_SIZE:
    case "small":
        RECORD_COUNT = 1000
    case "medium":
        RECORD_COUNT = 10000
    case "large":
        RECORD_COUNT = 100000

def get_num_docs():
    print(RECORD_COUNT - NUMBER_OF_RECORDS_TO_DELETE)


def setup():
    pass


def load():
    def _random_record():
        return {
            "id": bson.ObjectId(),
            "name": fake.name(),
            "address": fake.address(),
            "birthdate": fake.date(),
            "time": fake.time(),
            "comment": fake_provider.get_text(),
        }

    print(f"Generating {RECORD_COUNT} random records")
    db = client.sample_database
    collection = db.sample_collection

    data = []
    for _ in range(RECORD_COUNT):
        data.append(_random_record())
    collection.insert_many(data)


def remove():
    db = client.sample_database
    collection = db.sample_collection

    records = collection.find().limit(NUMBER_OF_RECORDS_TO_DELETE)
    doc_ids = [rec.get("_id") for rec in records]

    query = {"_id": {"$in": doc_ids}}
    collection.delete_many(query)


def teardown():
    pass
