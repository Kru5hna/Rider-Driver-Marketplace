# 3 tables drivers, trips & idempotency_keys

from sqlalchemy import null
import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Index

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
DATABASE_URL = f"mysql+pymysql://app_user:app_password@{MYSQL_HOST}:3306/rider_driver_db"

engine = create_engine(
   DATABASE_URL, 
   pool_pre_ping=True, 
   pool_size=10, 
   max_overflow=20
   )
SessionLocal = sessionmaker(
   autocommit=False, 
   autoflush=False, 
   bind=engine
   )
Base= declarative_base() #creates a base class that your SQLAlchemy models inherit from 


# 1) Driver Model

class Driver(Base):
   __tablename__ = "drivers"

   id = Column(Integer, primary_key=True, index=True, autoincrement = True)
   name = Column(String(100), nullable=False)
   lat = Column(Float, nullable=False)
   lng = Column(Float, nullable=False)
   status = Column(String(20), default="AVAILABLE", index=True) # Available, matched, off_duty
   updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# 2) Trip model
class Trip(Base):
   __tablename__ = "trips"

   id = Column(Integer, primary_key=True, index=True, autoincrement=True)
   rider_id = Column(String(50), nullable=False, index=True)
   driver_id = Column(Integer, nullable=False, index=True)
   ride_type = Column(String(20), default="UBER_X")
   pickup_lat = Column(Float, nullable=False)
   pickup_lng = Column(Float, nullable=False)
   dropoff_lat = Column(Float, nullable=False)
   dropoff_lng = Column(Float, nullable=False)
   fare_amount = Column(Float, nullable=True)
   status = Column(String(20), default="REQUESTED", index=True) # Requested, Accepted, Picked_up, Completed, Cancelled
   created_at = Column(DateTime, default=datetime.datetime.utcnow)

# 3) Idempotency Key Model (used to prevent duplicates)

class IdempotencyKey(Base):
   __tablename__ = "idempotency_keys"

   key = Column(String(100), primary_key=True, index=True)
   trip_id = Column(Integer, nullable=False)
   response_json= Column(Text, nullable=False)
   created_at = Column(DateTime, default= datetime.datetime.utcnow)

def init_db():
   """Create all tables and seed sample drivers if DB is empty."""
   try:
      Base.metadata.create_all(bind=engine)
      print("[Dispatch DB] Tables initialized Successfully.")
      seed_drivers()
   except Exception as e:
      print(f"[Dispatch DB] ERROR: failed to initialize database: {str(e)}")

def seed_drivers():
   # sample data
   db = SessionLocal()
   try:
      count = db.query(Driver).count()
      if count == 0:
         print("[Dispatch DB] Seeding 5 initial available drivers...")
         sample_drivers = [
                Driver(name="Driver Alex", lat=21.1458, lng=79.0882, status="AVAILABLE"),
                Driver(name="Driver Bob", lat=21.1470, lng=79.0890, status="AVAILABLE"),
                Driver(name="Driver Charlie", lat=21.1500, lng=79.0910, status="AVAILABLE"),
                Driver(name="Driver Dave", lat=21.1400, lng=79.0800, status="AVAILABLE"),
                Driver(name="Driver Eve", lat=21.1600, lng=79.1000, status="AVAILABLE"),
         ]
         db.bulk_save_objects(sample_drivers)
         db.commit()
         print("[Dispatch DB] Successfully seeded 5 drivers")
   except Exception as e:
      print(f"[Dispatch DB] Seeding error: {e}")
      db.rollback()
   finally:
      db.close() 
      
