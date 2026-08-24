import math
import sys
import os
from concurrent import futures
import grpc

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from proto import pricing_pb2_grpc
from proto import pricing_pb2

class PricingServicer(pricing_pb2_grpc.PricingServiceServicer):
   """
   Impl the gRPC PricingServer contract defined in pricing.proto
   """

   def CalculateFare(self, request, context):
      print(f"[Pricing Service] Received request: {request.ride_type} from ({request.pickup_lat}, {request.pickup_lng}) to ({request.dropoff_lat}, {request.dropoff_lng})")

      # 1. calculating the approximate distance 
      # (euclidean distance)

      lat_diff = request.dropoff_lat - request.pickup_lat
      lng_diff = request.dropoff_lng - request.pickup_lng

      distance_km = round(math.sqrt(lat_diff**2 + lng_diff**2)* 111, 2) # 1 deg ~ 111.3 km

      if distance_km == 0:
         distance_km = 1.0 # this is min distance

      #2 pricing logic
      base_fare = 0.5
      rate_per_km= 1.5
      surge_multiplier = 1.2 if request.ride_type == "UBER_BLACK" else 1.0

      total_fare = round((base_fare + (distance_km * rate_per_km)) * surge_multiplier, 2)

      #3 construct gRPC response 
      return pricing_pb2.FareResponse(
         fare_amount=total_fare,
         currency="INR",
         distance_km=distance_km,
         surge_multiplier=surge_multiplier
      )

def serve():
   server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

   pricing_pb2_grpc.add_PricingServiceServicer_to_server(PricingServicer(), server)

   server.add_insecure_port('[::]:50051')
   print("[Pricing Service] gRPC Server running on port 50051...")

   server.start()

   server.wait_for_termination()

if __name__ == '__main__':
   serve()