# db_consumer.py
from kafka import KafkaConsumer
import json
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import time

image_consumer = KafkaConsumer(
    "image_data",
    bootstrap_servers="192.168.5.43:9092",
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

inference_consumer = KafkaConsumer(
    "inference_results",
    bootstrap_servers="192.168.5.250:9092",
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

def get_mongo_client():
    max_retries = 5
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            client = MongoClient('mongodb://adminuser:team6@192.168.5.176:27017/?authSource=admin')
            client.admin.command('ismaster')
            print("Successfully connected to MongoDB")
            return client
        except ConnectionFailure as e:
            print(f"Failed to connect to MongoDB (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("Max retries reached. Exiting.")
                raise

def process_data():
    mongo_client = get_mongo_client()
    db = mongo_client['image_database']
    collection = db['image_data']
    image_data_dict = {}

    def handle_image_data():
        for message in image_consumer:
            data = message.value
            image_data_dict[data['ID']] = data
            try:
                result = collection.insert_one(data)
                print(f"Inserted new image data with ID: {result.inserted_id}")
            except Exception as e:
                print(f"Error inserting image data: {e}")

    def handle_inference_results():
        for message in inference_consumer:
            data = message.value
            try:
                result = collection.update_one(
                    {"ID": data['ID']},
                    {"$set": {
                        "InferredValue": data['InferredValue'],
                        "GroundTruth": data['GroundTruth']
                    }}
                )
                if result.modified_count > 0:
                    print(f"Updated document {data['ID']} with inference result")
                else:
                    print(f"Failed to update document {data['ID']}. Document may not exist.")
            except Exception as e:
                print(f"Error updating inference result: {e}")

    from threading import Thread
    image_thread = Thread(target=handle_image_data)
    inference_thread = Thread(target=handle_inference_results)

    image_thread.start()
    inference_thread.start()

    image_thread.join()
    inference_thread.join()

if __name__ == "__main__":
    process_data()
