"""
MongoDB Client for ELT Process
Handles connections and operations for Bronze/Silver/Gold layers
"""
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import os
from dotenv import load_dotenv
from datetime import datetime
import logging

load_dotenv()

class MongoDBClient:
    def __init__(self):
        self.uri = os.getenv('MONGO_URI')
        self.db_name = os.getenv('MONGO_DB', 'runagen_ml_warehouse')
        self.client = None
        self.db = None
        self.logger = logging.getLogger(__name__)
        
    def connect(self):
        """Establish MongoDB connection"""
        try:
            # Added timeouts for resilience during parallel AI/ML execution
            self.client = MongoClient(
                self.uri,
                connectTimeoutMS=30000,
                socketTimeoutMS=60000,
                serverSelectionTimeoutMS=30000
            )
            # Test connection
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.logger.info(f"Connected to MongoDB: {self.db_name}")
            return True
        except ConnectionFailure as e:
            self.logger.error(f"Failed to connect to MongoDB: {e}")
            return False
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            self.logger.info("MongoDB connection closed")
    
    # Bronze Layer Operations
    def insert_bronze(self, collection_name, data, metadata=None):
        """Insert raw data into Bronze layer"""
        collection = self.db[f"bronze_{collection_name}"]
        
        document = {
            'data': data,
            'metadata': metadata or {},
            'inserted_at': datetime.utcnow(),
            'layer': 'bronze'
        }
        
        result = collection.insert_one(document)
        self.logger.info(f"Inserted into bronze_{collection_name}: {result.inserted_id}")
        return result.inserted_id
    
    def insert_bronze_many(self, collection_name, data_list, metadata=None):
        """Insert multiple documents into Bronze layer"""
        collection = self.db[f"bronze_{collection_name}"]
        
        documents = [{
            'data': item,
            'metadata': metadata or {},
            'inserted_at': datetime.utcnow(),
            'layer': 'bronze'
        } for item in data_list]
        
        result = collection.insert_many(documents)
        self.logger.info(f"Inserted {len(result.inserted_ids)} documents into bronze_{collection_name}")
        return result.inserted_ids
    
    def get_bronze_data(self, collection_name, query=None, limit=None):
        """Retrieve data from Bronze layer"""
        collection = self.db[f"bronze_{collection_name}"]
        cursor = collection.find(query or {})
        
        if limit:
            cursor = cursor.limit(limit)
        
        return list(cursor)
    
    # Silver Layer Operations
    def insert_silver(self, collection_name, data):
        """Insert cleaned/standardized data into Silver layer"""
        collection = self.db[f"silver_{collection_name}"]
        
        if isinstance(data, list):
            for item in data:
                item['transformed_at'] = datetime.utcnow()
                item['layer'] = 'silver'
            result = collection.insert_many(data)
            self.logger.info(f"Inserted {len(result.inserted_ids)} documents into silver_{collection_name}")
            return result.inserted_ids
        else:
            data['transformed_at'] = datetime.utcnow()
            data['layer'] = 'silver'
            result = collection.insert_one(data)
            self.logger.info(f"Inserted into silver_{collection_name}: {result.inserted_id}")
            return result.inserted_id
    
    def get_silver_data(self, collection_name, query=None, limit=None):
        """Retrieve data from Silver layer"""
        collection = self.db[f"silver_{collection_name}"]
        cursor = collection.find(query or {})
        
        if limit:
            cursor = cursor.limit(limit)
        
        return list(cursor)
    
    # Gold Layer Operations (Feature Store)
    def insert_gold(self, collection_name, data):
        """Insert aggregated features into Gold layer"""
        collection = self.db[f"gold_{collection_name}"]
        
        if isinstance(data, list):
            for item in data:
                item['aggregated_at'] = datetime.utcnow()
                item['layer'] = 'gold'
            result = collection.insert_many(data)
            self.logger.info(f"Inserted {len(result.inserted_ids)} features into gold_{collection_name}")
            return result.inserted_ids
        else:
            data['aggregated_at'] = datetime.utcnow()
            data['layer'] = 'gold'
            result = collection.insert_one(data)
            self.logger.info(f"Inserted into gold_{collection_name}: {result.inserted_id}")
            return result.inserted_id
    
    def get_gold_data(self, collection_name, query=None, limit=None):
        """Retrieve features from Gold layer"""
        collection = self.db[f"gold_{collection_name}"]
        cursor = collection.find(query or {})
        
        if limit:
            cursor = cursor.limit(limit)
        
        return list(cursor)
    
    def upsert_gold(self, collection_name, query, data):
        """Update or insert feature in Gold layer"""
        collection = self.db[f"gold_{collection_name}"]
        data['aggregated_at'] = datetime.utcnow()
        data['layer'] = 'gold'
        
        result = collection.update_one(query, {'$set': data}, upsert=True)
        self.logger.info(f"Upserted into gold_{collection_name}")
        return result
    
    def is_connected(self) -> bool:
        """Check if MongoDB connection is alive"""
        try:
            if self.client:
                self.client.admin.command('ping')
                return True
            return False
        except Exception:
            return False
    
    def get_collection(self, collection_name):
        """Get a MongoDB collection by name (without layer prefix)"""
        if self.db is None:
            if not self.connect():
                raise ConnectionError("MongoDB not connected")
        return self.db[collection_name]
    
    # Utility Methods
    def get_collection_stats(self, layer=None):
        """Get statistics for all collections"""
        stats = {}
        
        for collection_name in self.db.list_collection_names():
            if layer and not collection_name.startswith(f"{layer}_"):
                continue
            
            count = self.db[collection_name].count_documents({})
            stats[collection_name] = count
        
        return stats
    
    def clear_layer(self, layer):
        """Clear all collections in a specific layer (use with caution!)"""
        for collection_name in self.db.list_collection_names():
            if collection_name.startswith(f"{layer}_"):
                self.db[collection_name].drop()
                self.logger.warning(f"Dropped collection: {collection_name}")

if __name__ == "__main__":
    # Test connection
    logging.basicConfig(level=logging.INFO)
    
    client = MongoDBClient()
    if client.connect():
        print("✓ MongoDB connection successful")
        print(f"Database: {client.db_name}")
        
        # Show existing collections
        stats = client.get_collection_stats()
        print("\nCollection Statistics:")
        for collection, count in stats.items():
            print(f"  {collection}: {count} documents")
        
        client.close()
    else:
        print("✗ MongoDB connection failed")
