from pymongo import MongoClient
import os
from datetime import datetime
import sys

# --- CONFIG ---
MONGO_URI = "mongodb://localhost:27017"

# Setup logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"delete_dbs_{timestamp}.log"
log_path = os.path.join(log_dir, log_filename)

# Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler(log_path),
#         logging.StreamHandler()  # Also print to console
#     ]
# )


def list_databases():
    """List all databases in MongoDB"""
    try:
        client = MongoClient(MONGO_URI)
        databases = client.list_database_names()
        client.close()
        return databases
    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {e}")
        return []

def get_database_info(db_name):
    """Get information about a specific database"""
    try:
        client = MongoClient(MONGO_URI)
        db = client[db_name]
        
        # Get collection names and their document counts
        collections = db.list_collection_names()
        collection_info = {}
        
        for collection in collections:
            count = db[collection].count_documents({})
            collection_info[collection] = count
        
        client.close()
        return collection_info
    except Exception as e:
        print(f"❌ Error getting info for database {db_name}: {e}")
        return {}

def delete_database(db_name, force=False):
    """Delete a database with confirmation"""
    try:
        client = MongoClient(MONGO_URI)
        
        # Get database info before deletion
        collection_info = get_database_info(db_name)
        total_docs = sum(collection_info.values())
        
        print(f"📊 Database '{db_name}' contains:")
        for collection, count in collection_info.items():
            print(f"   - {collection}: {count} documents")
        print(f"   Total: {total_docs} documents")
        
        if not force:
            # Ask for confirmation
            response = input(f"\n⚠️  Are you sure you want to delete database '{db_name}'? (yes/no): ").lower().strip()
            if response not in ['yes', 'y']:
                print("❌ Deletion cancelled by user")
                client.close()
                return False
        
        # Delete the database
        client.drop_database(db_name)
        client.close()
        
        print(f"✅ Successfully deleted database '{db_name}'")
        return True
        
    except Exception as e:
        print(f"❌ Error deleting database '{db_name}': {e}")
        return False

def delete_multiple_databases(db_names, force=False):
    """Delete multiple databases"""
    results = []
    
    for db_name in db_names:
        print("\n" + "="*50)
        print(f"Processing database: {db_name}")
        success = delete_database(db_name, force)
        results.append((db_name, success))
    
    return results

def main():
    """Main function with interactive menu"""
    print("🗑️  MongoDB Database Deletion Tool")
    print("=" * 50)
    
    # List all databases
    databases = list_databases()
    
    if not databases:
        print("❌ No databases found or unable to connect to MongoDB")
        return
    
    print(f"📋 Available databases ({len(databases)}):")
    for i, db in enumerate(databases, 1):
        collection_info = get_database_info(db)
        total_docs = sum(collection_info.values())
        print(f"   {i}. {db} ({total_docs} total documents)")
    
    while True:
        print("\n" + "="*50)
        print("🗑️  MongoDB Database Deletion Tool")
        print("="*50)
        print("1. Delete a single database")
        print("2. Delete multiple databases")
        print("3. Delete all databases (DANGEROUS!)")
        print("4. Show database information")
        print("5. Exit")
        
        choice = input("\nSelect an option (1-5): ").strip()
        
        if choice == "1":
            # Delete single database
            print(f"\nAvailable databases: {', '.join(databases)}")
            db_name = input("Enter database name to delete: ").strip()
            
            if db_name in databases:
                delete_database(db_name)
            else:
                print(f"❌ Database '{db_name}' not found")
        
        elif choice == "2":
            # Delete multiple databases
            print(f"\nAvailable databases: {', '.join(databases)}")
            db_names_input = input("Enter database names separated by commas: ").strip()
            db_names = [name.strip() for name in db_names_input.split(",")]
            
            # Validate database names
            valid_names = [name for name in db_names if name in databases]
            invalid_names = [name for name in db_names if name not in databases]
            
            if invalid_names:
                print(f"⚠️  Invalid database names: {', '.join(invalid_names)}")
            
            if valid_names:
                print(f"📋 Will delete: {', '.join(valid_names)}")
                results = delete_multiple_databases(valid_names)
                
                print("\n📊 Deletion Results:")
                for db_name, success in results:
                    status = "✅ Success" if success else "❌ Failed"
                    print(f"   {db_name}: {status}")
            else:
                print("❌ No valid database names provided")
        
        elif choice == "3":
            # Delete all databases (DANGEROUS!)
            print("⚠️  WARNING: This will delete ALL databases!")
            print("⚠️  This action cannot be undone!")
            
            response = input("Type 'DELETE ALL' to confirm: ").strip()
            if response == "DELETE ALL":
                print("🗑️  Deleting all databases...")
                results = delete_multiple_databases(databases, force=True)
                
                print("\n📊 Deletion Results:")
                for db_name, success in results:
                    status = "✅ Success" if success else "❌ Failed"
                    print(f"   {db_name}: {status}")
            else:
                print("❌ Operation cancelled")
        
        elif choice == "4":
            # Show detailed database information
            print(f"\nAvailable databases: {', '.join(databases)}")
            db_name = input("Enter database name for detailed info: ").strip()
            
            if db_name in databases:
                collection_info = get_database_info(db_name)
                print(f"\n📊 Database: {db_name}")
                print("=" * 30)
                for collection, count in collection_info.items():
                    print(f"   Collection: {collection}")
                    print(f"   Documents: {count}")
                print(f"   Total documents: {sum(collection_info.values())}")
            else:
                print(f"❌ Database '{db_name}' not found")
        
        elif choice == "5":
            print("👋 Exiting...")
            break
        
        else:
            print("❌ Invalid choice. Please select 1-5.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Operation cancelled by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    finally:
        print(f"📝 Log saved to: {log_path}") 