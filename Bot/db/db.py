from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()
MONGO_URL = os.getenv("MONGO_URL")
connection = None


def db():
    global connection
    while not connection:
        try:
            connection = MongoClient(MONGO_URL)
        except Exception as e:
            print(e)
    return connection['core']
