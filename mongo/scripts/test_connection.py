import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from config import MONGO_URI, DB_NAME

client = MongoClient(MONGO_URI)

# "ping" asks the server to respond; it raises an error if it can't connect
client.admin.command("ping")
print("Connected to MongoDB server version:", client.server_info()["version"])
print("Using database:", DB_NAME)

client.close()