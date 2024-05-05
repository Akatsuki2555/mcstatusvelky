import json
import pymongo


# Load the constants from the constants.json file
with open('constants.json') as f:
    constants = json.load(f)

client = pymongo.MongoClient(constants["MONGO_URI"])

result = client[constants["MONGO_DB"]]["Playtimes"].delete_many({"uuid": {"$exists": False}})

print(result.deleted_count, "documents deleted.")
