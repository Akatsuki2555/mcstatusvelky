import sqlite3
from mcstatus import JavaServer
from datetime import datetime

db = sqlite3.connect('main.db')

cur = db.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS currentPlayers (name TEXT, uuid TEXT)')
cur.execute('CREATE TABLE IF NOT EXISTS pastPlayers (name TEXT, uuid TEXT, lastseen DATETIME)')
cur.execute('CREATE TABLE IF NOT EXISTS connectionLogs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME, name TEXT, uuid TEXT, action TEXT)')

# print last 10 logs
print('Last 10 logs:')

for row in cur.execute('SELECT * FROM connectionLogs ORDER BY id DESC LIMIT 10').fetchall():
    if row[4] == 'join':
        print(f"{row[0]}: [+] {row[2]} joined the server at {row[1]}")
    elif row[4] == 'leave':
        print(f"{row[0]}: [-] {row[2]} left the server at {row[1]}")
        
print('List of players currently online:')
for row in cur.execute('SELECT * FROM currentPlayers').fetchall():
    print(row[0])

db.commit()
