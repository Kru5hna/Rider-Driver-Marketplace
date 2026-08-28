import sys
import os
import json
import grpc
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

# Add project root to sys.path so Python can resolve imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from proto import pricing_pb2
from proto import pricing_pb2_grpc
from services.dispatch.db import SessionLocal, init_db, Trip, Driver, IdempotencyKey
from services.matching.engine import find_and_reserve_driver

app = FastAPI(title="Dispatch Service")
@app.on_event("startup")
def on_startup():
   init_db()

def get_db():
   db = SessionLocal()
   try:
      yield db # gives that session to the fastapi route that needs it. why use 'yield' then? because it can use before and after code also not like 'return'
   finally:
      db.close()

class RideRequestSchema(BaseModel):
   rider_id: str
   pickup_lat: float
   pickup_lng: float
   dropoff_lat: float
   dropoff_lng: float
   ride_type: Optional[str] = "UBER_X"

PRICING_SERVICE_HOST = os.getenv("PRICING_SERVICE_HOST", "localhost")

@app.post("/trips/request")
def request_ride(
   request: RideRequestSchema,
   idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
   db: Session = Depends(get_db)
):
   print(f"\n[Dispatch Gateway] Received Ride Request for Rider: {request.rider_id}")

   #1 IDEMPOTENCY CHECK

   if idempotency_key:
      existing_key = db.query(IdempotencyKey).filter(IdempotencyKey.key == idempotency_key).first()
      if existing_key:
         print(f"[Dispatch Gateway] Idempotent Request Detected (Key: {idempotency_key}). Returning cached trip!")
         return json.loads(existing_key.response_json)

   #2 Matching Engine: Find & Atomically Reserve Nearest Driver
   driver = find_and_reserve_driver(request.pickup_lat, request.pickup_lng, db)
   if not driver:
      raise HTTPException(
         status_code=503,
         detail="No available drivers nearby. Please try again shortly."
      )


   #3 grpc pricing service call 

   try:
      channel = grpc.insecure_channel(f"{PRICING_SERVICE_HOST}:50051")
      stub = pricing_pb2_grpc.PricingServiceStub(channel)

      grpc_request = pricing_pb2.FareRequest(
         pickup_lat=request.pickup_lat,
         pickup_lng=request.pickup_lng,
         dropoff_lat=request.dropoff_lat,
         dropoff_lng=request.dropoff_lng,
         ride_type=request.ride_type
      )
      fare_response = stub.CalculateFare(grpc_request)
      print(f"[Dispatch Gateway] gRPC Fare Calculated: ${fare_response.fare_amount}(Surge: {fare_response.surge_multiplier}x)")

   except Exception as e:
      print(f"[Dispatch Gateway] gRPC Pricing Service Error: {e}")
      # Rollbacking the driver status if pricing fails
      driver.status = "AVAILABLE"
      db.commit()
      raise HTTPException(status_code=503, detail=f"Pricing service unavailable: {str(e)}")

   #4 Save trip to mysql

   new_trip = Trip(
      rider_id = request.rider_id,
      driver_id=driver.id,
        ride_type=request.ride_type,
        pickup_lat=request.pickup_lat,
        pickup_lng=request.pickup_lng,
        dropoff_lat=request.dropoff_lat,
        dropoff_lng=request.dropoff_lng,
        fare_amount=fare_response.fare_amount,
        status="MATCHED"
   )
   db.add(new_trip)
   db.commit()
   db.refresh(new_trip)

   response_payload = {
      "message": "Trip successfully matched and created",
      "trip_id": new_trip.id,
      "status": new_trip.status,
      "driver": {
         "id": driver.id,
         "name": driver.name,
         "location": {"lat": driver.lat, "lng": driver.lng}
      },
      "fare": {
         "amount": new_trip.fare_amount,
         "currency": fare_response.currency,
         "distance_km": fare_response.distance_km,
         "surge_multiplier": fare_response.surge_multiplier
      }
   }


   # saving idempotency key record
   if idempotency_key:
      idempotency_record = IdempotencyKey(
         key=idempotency_key,
         trip_id=new_trip.id,
         response_json = json.dumps(response_payload)
      )
      db.add(idempotency_record)
      db.commit()

   return response_payload