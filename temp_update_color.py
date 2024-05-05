import json
import pymongo

# Load constants from "constants.json"
with open("constants.json") as f:
    constants = json.load(f)

MONGO_URI = constants["MONGO_URI"]
client = pymongo.MongoClient(MONGO_URI)

result = client[constants["MONGO_DB"]][constants["PLAYTIMES_COLLECTION"]].update_many(
    {"profileStyle.nameColour": {"$eq": "white"}},
    {"$set": {"profileStyle.nameColour": "#ffffff"}}
)

print("Updated", result.modified_count, "documents.")
