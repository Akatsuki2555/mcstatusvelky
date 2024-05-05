import random
import string
import sqlite3
from datetime import datetime
import pymongo
from mcstatus import JavaServer

# Constants

# Load constants from JSON file
import json
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(current_dir, "constants.json")) as f:
    constants = json.load(f)

MONGO_URI = constants["MONGO_URI"]
DB_NAME = constants["DB_NAME"]
MONGO_DB = constants["MONGO_DB"]
KV_COLLECTION = constants["KV_COLLECTION"]
PLAYERS_COLLECTION = constants["PLAYERS_COLLECTION"]
PLAYTIMES_COLLECTION = constants["PLAYTIMES_COLLECTION"]
LOGS_COLLECTION = constants["LOGS_COLLECTION"]
LAST_PLAYTIMES_COLLECTION = constants["LAST_PLAYTIMES_COLLECTION"]
LAST_PLAYTIMES_COLLECTION = "LastPlaytimes"

# Connect to SQLite database
db = sqlite3.connect(DB_NAME)
cur = db.cursor()

# Connect to MongoDB
client = pymongo.MongoClient(MONGO_URI)
mongo_db = client[MONGO_DB]


def create_tables():
    # Create SQLite tables if not exist
    cur.execute("CREATE TABLE IF NOT EXISTS currentPlayers (name TEXT, uuid TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS pastPlayers (name TEXT, uuid TEXT, lastseen DATETIME)")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS connectionLogs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME, name TEXT, uuid TEXT, action TEXT)")


def kv_set_value(key, value):
    mongo_db[KV_COLLECTION].update_one({"key": key}, {"$set": {"value": value}}, upsert=True)


def kv_get_value(key):
    data = mongo_db[KV_COLLECTION].find_one({"key": key})
    return data["value"] if data else None


def human_format(seconds: int):
    intervals = (("w", 604800),  # 60 * 60 * 24 * 7
                 ("d", 86400),  # 60 * 60 * 24
                 ("h", 3600),  # 60 * 60
                 ("m", 60),)
    result = []
    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip("s")
            result.append("%d%s" % (value, name))
    return " ".join(result)


def update_mongo_db(status, player_playtimes):
    kv_set_value("motd", status.motd.to_plain())
    kv_set_value("online", status.players.online)
    kv_set_value("max", status.players.max)
    kv_set_value("ping", int(status.latency))

    mongo_db[PLAYERS_COLLECTION].delete_many({})
    if status.players.sample:
        players_data = [{"uuid": player.uuid, "name": player.name} for player in status.players.sample]
        mongo_db[PLAYERS_COLLECTION].insert_many(players_data)

    for uuid, username, humantime, seconds, online, lastjoin in player_playtimes:
        mongo_db[PLAYTIMES_COLLECTION].update_one(
            {"uuid": uuid},
            {"$set": {"name": username, "humantime": humantime, "seconds": seconds, "online": online, "lastjoin": lastjoin}},
            upsert=True
        )

    missing_tokens = mongo_db[PLAYTIMES_COLLECTION].find({"token": {"$exists": False}})
    for index, player in enumerate(missing_tokens, start=1):
        token = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
        mongo_db[PLAYTIMES_COLLECTION].update_one({"name": player["name"]}, {"$set": {"token": token}})

    missing_profiles = mongo_db[PLAYTIMES_COLLECTION].find({"profileStyle": {"$exists": False}})
    for index, player in enumerate(missing_profiles, start=1):
        mongo_db[PLAYTIMES_COLLECTION].update_one(
            {"name": player["name"]},
            {"$set": {"profileStyle": {"displayName": player["name"], "nameColour": "#ffffff"}}}
        )


def update_current_players(status):
    current_players = cur.execute("SELECT * FROM currentPlayers").fetchall()
    for player_row in current_players:
        uuid = player_row[1]
        if uuid not in (player.id for player in status.players.sample):
            cur.execute("INSERT INTO pastPlayers VALUES (?, ?, ?)", (player_row[0], uuid, datetime.now()))
            cur.execute("DELETE FROM currentPlayers WHERE uuid = ?", (uuid,))
            cur.execute("INSERT INTO connectionLogs VALUES (?, ?, ?, ?, ?)",
                        (None, datetime.now(), player_row[0], uuid, "leave"))
            print(f"[-] {player_row[0]} from the currentPlayers table")

    for player in status.players.sample:
        if cur.execute("SELECT * FROM currentPlayers WHERE uuid = ?", (player.id,)).fetchone() is None:
            cur.execute("INSERT INTO currentPlayers VALUES (?, ?)", (player.name, player.id))
            cur.execute("DELETE FROM pastPlayers WHERE uuid = ?", (player.id,))
            cur.execute("INSERT INTO connectionLogs VALUES (?, ?, ?, ?, ?)",
                        (None, datetime.now(), player.name, player.id, "join"))
            print(f"[+] {player.name} to the currentPlayers table")


def upload_logs_to_mongo():
    last_id = mongo_db[LOGS_COLLECTION].find_one(sort=[("id", -1)], projection=["id"])
    last_id = last_id["id"] if last_id else 0

    data = []
    cur.execute("SELECT * FROM connectionLogs WHERE id > ?", (last_id,))
    for row in cur.fetchall():
        data.append({'id': row[0], 'timestamp': row[1], 'name': row[2], 'uuid': row[3], 'action': row[4]})

    new_data = [row for row in data if last_id < row['id']]

    print(f"Uploading past players to MongoDB... uploading {len(new_data)} new rows...                          ",
          end='\r')
    for index, row in enumerate(new_data, start=1):
        action_text = "joined the server" if row['action'] == 'join' else "left the server"
        print(f"[{index}/{len(new_data)}]Uploading... {row['name']} {action_text}                           ", end='\r')
        mongo_db[LOGS_COLLECTION].insert_one(row)
    print("Uploading past players to MongoDB... done.                           ")


def upload_last_playtimes(cur: sqlite3.Cursor):
    uuid_list = []

    for row in cur.execute("SELECT uuid FROM connectionLogs").fetchall():
        if row[0] not in uuid_list:
            uuid_list.append(row[0])

    mongodb_requests = [
        pymongo.operations.DeleteMany({}),
    ]

    for uuid in uuid_list:
        last_action = cur.execute("SELECT * FROM connectionLogs WHERE uuid = ? ORDER BY id DESC LIMIT 1",
                                  (uuid,)).fetchone()
        joins = cur.execute("SELECT * FROM connectionLogs WHERE uuid = ? AND action = ? ORDER BY id DESC LIMIT 10",
                            (uuid, "join")).fetchall()
        leaves = cur.execute("SELECT * FROM connectionLogs WHERE uuid = ? AND action = ? ORDER BY id DESC LIMIT 10",
                             (uuid, "leave")).fetchall()

        if last_action[4] == "join":
            joins.pop(0)

        for join, leave in zip(joins, leaves):
            mongodb_requests.append(
                pymongo.operations.InsertOne({
                    "uuid": uuid,
                    "join_timestamp": join[1],
                    "leave_timestamp": leave[1],
                    "playtime": (datetime.fromisoformat(leave[1]) - datetime.fromisoformat(join[1])).total_seconds(),
                    "humanplaytime": human_format((datetime.fromisoformat(leave[1]) - datetime.fromisoformat(join[1])).total_seconds()),
                    "name": join[2]
                })
            )

        if last_action[4] == "join":
            mongodb_requests.append(
                pymongo.operations.InsertOne({
                    "uuid": uuid,
                    "join_timestamp": last_action[1],
                    "leave_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "playtime": (datetime.now() - datetime.fromisoformat(last_action[1])).total_seconds(),
                    "humanplaytime": human_format((datetime.now() - datetime.fromisoformat(last_action[1])).total_seconds()),
                    "name": last_action[2]
                })
            )

    mongo_db[LAST_PLAYTIMES_COLLECTION].bulk_write(mongodb_requests)


def main():
    create_tables()

    server = JavaServer.lookup("velkysmp.com")
    status = server.status()
    print(f"MOTD: {status.motd}")

    motd = cur.execute("SELECT * FROM motdHistory ORDER BY id DESC LIMIT 1").fetchone()
    if motd is None or motd[2] != status.motd.to_plain():
        print("New MOTD detected, adding to history")
        cur.execute("INSERT INTO motdHistory VALUES (?, ?, ?)", (None, datetime.now(), status.motd.to_plain()))

    print(f"The server has {status.players.online} player(s) online and replied in {int(status.latency)} ms")

    player_uuids = cur.execute("SELECT DISTINCT uuid FROM connectionLogs").fetchall()
    player_playtimes = []

    for row in player_uuids:
        uuid = row[0]
        playtime = 0  # seconds

        joins = cur.execute("SELECT * FROM connectionLogs WHERE uuid = ? AND action = ?", (uuid, "join")).fetchall()
        leaves = cur.execute("SELECT * FROM connectionLogs WHERE uuid = ? AND action = ?", (uuid, "leave")).fetchall()

        for join, leave in zip(joins, leaves):
            playtime += (datetime.fromisoformat(leave[1]) - datetime.fromisoformat(join[1])).total_seconds()

        last_leave = cur.execute("SELECT * FROM connectionLogs WHERE uuid = ? ORDER BY id DESC LIMIT 1",
                                 (uuid,)).fetchone()
        if last_leave[4] == "join":
            last_leave = datetime.now()
        else:
            last_leave = datetime.fromisoformat(last_leave[1])

        username = \
            cur.execute("SELECT name FROM connectionLogs WHERE uuid = ? ORDER BY id DESC LIMIT 1", (uuid,)).fetchone()[
                0]
        player_playtimes.append((uuid, username, human_format(playtime), playtime, len(joins) != len(leaves), last_leave))

    if status.players.sample is not None:
        update_mongo_db(status, player_playtimes)
        update_current_players(status)
    else:
        update_mongo_db(status, player_playtimes)
        current_players = cur.execute("SELECT * FROM currentPlayers").fetchall()
        for player_row in current_players:
            uuid = player_row[1]
            cur.execute("INSERT INTO pastPlayers VALUES (?, ?, ?)", (player_row[0], uuid, datetime.now()))
            cur.execute("DELETE FROM currentPlayers WHERE uuid = ?", (uuid,))
            cur.execute("INSERT INTO connectionLogs VALUES (?, ?, ?, ?, ?)",
                        (None, datetime.now(), player_row[0], uuid, "leave"))
            print(f"[-] {player_row[0]} from the currentPlayers table")

    upload_last_playtimes(cur)

    if datetime.now().minute == 0:
        upload_logs_to_mongo()

    db.commit()


if __name__ == "__main__":
    main()
