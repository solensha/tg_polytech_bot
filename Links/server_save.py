from aiohttp import web
from pymongo import MongoClient
import sys

cluster = MongoClient("mongodb+srv://tatyanastartseva2020:IIr08PTqUBbyK0Jq@parserdb.gwhsqxg.mongodb.net/Parserdb")
db = cluster["Parserdb"]


async def Users(data):
    attempts = 0
    while attempts < 10:
        try:
            username = None
            collection = db["Client"]
            for key in data['accounts']:
                exist_user = collection.find_one({'user_id': key})
                if exist_user is None:
                    if data['accounts'][key]['info'].get('username') is not None:
                        username = data['accounts'][key]['info'].get('username').lower()
                    collection.insert_one({
                        'user_id': key,
                        'username': username,
                        'first_name': data['accounts'][key]['info'].get('first_name'),
                        'last_name': data['accounts'][key]['info'].get('last_name'),
                        'last_online': data['accounts'][key]['info'].get('last_online'),
                        'premium': data['accounts'][key]['info'].get('premium'),
                        'phone': data['accounts'][key]['info'].get('phone'),
                        'image': data['accounts'][key]['info'].get('image'),
                        'past_first_name': None,
                        'past_last_name': None
                    })
                else:
                    query = {'user_id': key}
                    current_name = collection.find_one({'user_id': key})['first_name']
                    current_last_name = collection.find_one({'user_id': key})['last_name']
                    if current_name != data['accounts'][key]['info'].get('first_name'):
                        update = {
                            '$set': {
                                'first_name': data['accounts'][key]['info'].get('first_name'),
                                'past_first_name': current_name
                            }
                        }
                        collection.update_one(query, update)
                    if current_last_name != data['accounts'][key]['info'].get('last_name'):
                        update = {
                            '$set': {
                                'last_name': data['accounts'][key]['info'].get('last_name'),
                                'past_last_name ': current_last_name
                            }
                        }
                        collection.update_one(query, update)
                    update = {
                        '$set': {
                            'username': username,
                            'last_online': data['accounts'][key]['info'].get('last_name'),
                            'premium': data['accounts'][key]['info'].get('premium'),
                            'phone': data['accounts'][key]['info'].get('phone'),
                            'image': data['accounts'][key]['info'].get('image')
                        }
                    }
                    collection.update_one(query, update)
            return
        except Exception as e:
            attempts += 1
            print('Client_DataBase')
            print(f'Error: {e}')
            print(sys.exc_info())


async def Messages(user_data):
    attempts = 0
    while attempts < 10:
        try:
            collection = db["Messages"]
            for key in user_data['accounts']:
                for key_chat in user_data['chats']:
                    for messages in user_data['accounts'][key]['chats']:
                        for i in range(len(user_data['accounts'][key]['chats'][messages])):
                            message_id = user_data['accounts'][key]['chats'][messages][i]['message_id']
                            exist_message = collection.find_one({'message_id': message_id})
                            if exist_message is None:
                                collection.insert_one({
                                    'message_id': message_id,
                                    'user_id': key,
                                    'chat_id': key_chat,
                                    'text': user_data['accounts'][key]['chats'][messages][i]['text']
                                })
            return
        except Exception as e:
            attempts += 1
            print(f'Error: {e}')
            print(sys.exc_info())


async def Chats(data):
    attempts = 0
    while attempts < 10:
        try:
            collection = db["Chats"]
            for key in data['chats']:
                exist_chat = collection.find_one({'chat_id': key})
                if exist_chat is None:
                    collection.insert_one({
                        'chat_id': key,
                        'username': data['chats'][key].get('username'),
                        'title': data['chats'][key].get('title'),
                        'last_online': data['chats'][key].get('last_online')
                    })
                else:
                    query = {'chat_id': key}
                    current_title = collection.find_one({'chat_id': key})['title']
                    if current_title != data['chats'][key].get('title'):
                        update = {
                            '$set': {
                                'title': data['chats'][key].get('title'),
                                'past_title': current_title
                            }
                        }
                        collection.update_one(query, update)
                    update = {
                        '$set': {
                            'username': data['chats'][key].get('username'),
                            'last_online': data['chats'][key].get('last_online')
                        }
                    }
                    collection.update_one(query, update)
            return
        except Exception as e:
            attempts += 1
            print(f'Error: {e}')
            print(sys.exc_info())


async def background_save(user_data):
    try:
        await Chats(user_data)
        await Users(user_data)
        await Messages(user_data)
        return web.Response(text="Запрос выполнен.")
    except Exception as e:
        print(f'Error: {e}')
        print(sys.exc_info())
