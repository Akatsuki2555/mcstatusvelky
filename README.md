# MCStatusVelky

MCStatusVelky is a project which scans velkysmp.com minecraft server and stores info in a database. 
It's then put in a MongoDB database, which can be used by [my other project](https://codeberg.org/Akatsuki/velkysmpmon).

## Building

To build MCStatusVelky, you need to define `constants.json` file in the same directory as `main.py`. 
`constants.json` should contain MongoDB URI, DB name, collection names and other options.


Here is an example of what the `constants.json` file should look like:

```json
{
    "MONGO_URI": "",
    "DB_NAME": "",
    "MONGO_DB": "",
    "KV_COLLECTION": "",
    "PLAYERS_COLLECTION": "",
    "PLAYTIMES_COLLECTION": "",
    "LOGS_COLLECTION": "",
    "LAST_PLAYTIMES_COLLECTION": ""
}
```

After that, you need to install dependencies from `requirements.txt`.

Finally, you can run `main.py`.

## Contributing

To contribute to MCStatusVelky, fork the project, modify it and make a pull request.

