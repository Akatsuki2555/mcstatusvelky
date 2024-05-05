import sqlite3
from datetime import datetime


def human_format(seconds: int):
    result = []
    intervals = (('weeks', 604800),  # 60 * 60 * 24 * 7
                 ('days', 86400),  # 60 * 60 * 24
                 ('hours', 3600),  # 60 * 60
                 ('minutes', 60), ('seconds', 1),)
    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append(f"{value} {name}")
    return ', '.join(result)


db = sqlite3.connect('main.db')
cur = db.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS currentPlayers (name TEXT, uuid TEXT)')
cur.execute('CREATE TABLE IF NOT EXISTS pastPlayers (name TEXT, uuid TEXT, lastseen DATETIME)')
cur.execute('CREATE TABLE IF NOT EXISTS connectionLogs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME, '
            'name TEXT, uuid TEXT, action TEXT)')
cur.execute('CREATE TABLE IF NOT EXISTS pingHistory(id INTEGER PRIMARY KEY AUTOINCREMENT, '
            'ping INTEGER)')
cur.execute('CREATE TABLE IF NOT EXISTS motdHistory(id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME, '
            'motd TEXT)')

cur.execute('SELECT * FROM pastPlayers')

player_playtimes = []

for row in cur.fetchall():
    username = row[0]
    playtime = 0  # seconds

    cur.execute('SELECT * FROM connectionLogs WHERE name = ? AND action = ?', (username, "join"))
    joins = cur.fetchall()
    cur.execute('SELECT * FROM connectionLogs WHERE name = ? AND action = ?', (username, "leave"))
    leaves = cur.fetchall()
    for join, leave in zip(joins, leaves):
        playtime += (datetime.fromisoformat(leave[1]) - datetime.fromisoformat(join[1])).total_seconds()

    # print(f"{username} has played for {human_format(playtime)} seconds")
    player_playtimes.append((username, playtime, len(joins) != len(leaves)))

player_playtimes.sort(key=lambda x: x[1], reverse=True)
for player, playtime, is_online in player_playtimes:
    print(f"{player} has played for {human_format(playtime)} {'(online)' if is_online else ''}")
