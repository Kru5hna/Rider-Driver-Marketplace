from sqlalchemy import text
import math
from sqlalchemy.orm import Session
from services.dispatch.db import Driver


def calculate_distance(lat1:float, lng1:float, lat2:float, lng2:float) -> float:
   # Calculates approximate distance in km between two lat/lng points.
   lat_diff = lat2 - lat1
   lng_diff = lng2 - lng1
   return round(math.sqrt(lat_diff**2 + lng_diff**2) * 111, 2)

def find_and_reserve_driver(rider_lat:float, rider_lng:float, db: Session) -> Driver:
   """
   1) fetches all currently available drivers
   2) ranks them by distance 
   3) uses ATOMIC CONDITIONAL SQL UPDATES to reserve the driver safely
               prevents race conditions 
   """
   # 1) 
   available_drivers = db.query(Driver).filter(Driver.status == "AVAILABLE").all()

   if not available_drivers:
      print("[Matching Engine] ❌ No available drivers found")
      return None

   # 2) 
   drivers_with_distance = []
   for driver in available_drivers:
      dist = calculate_distance(rider_lat, rider_lng, driver.lat, driver.lng)

      drivers_with_distance.append((dist, driver))
   
   # rank them
   drivers_with_distance.sort(key=lambda item:item[0])
   print(f"[Matching Engine] Evaluated {len(drivers_with_distance)} candidate drivers.")

   # 3) ATOMIC LOCK QUERY 
   for dist, driver in drivers_with_distance:
      print(f"[Matching Engine] attempting atomic lock on Driver ID {driver.id} ({driver.name}, {dist} km away)...")

      # atomic lock query only updates if status is still 'AVAILABLE'
      # if another concurrent thread updated it a ms ago, rowcount will be 0!

      result = db.execute(
         text("UPDATE drivers SET status = 'MATCHED' WHERE id = :driver_id AND status = 'AVAILABLE'"),
         {"driver_id": driver.id}
      )
      db.commit()

      if result.rowcount == 1:
         # yeah success
         print(f"✅ Successfully reserved Driver {driver.name} (ID: {driver.id})!")
         db.refresh(driver)
         return driver
      else:
         print(f"[Matching Engine] ⚠️ Race Condition Detected! Driver {driver.id} was taken by another request. Trying next candidate...")
         
   print("[Matching Engine] ❌ All candidate drivers were claimed by concurrent requests.")

   return None

   

   