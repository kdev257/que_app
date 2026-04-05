def simulate_barbers(customers, barbers=2):
#     """
#     customers: list of service times for each customer (minutes)
#     barbers: number of barbers (default = 2)
#     """

#     # Track when each barber becomes free
#     barber_free_time = [0] * barbers

#     # Store results
#     events = []

#     current_time = 0

#     for i, service_time in enumerate(customers):
#         # simulate minute-by-minute time progression
#         # not strictly required, but included since you asked for 1-min update
#         while True:
#             # find earliest free barber
#             earliest = min(barber_free_time)

#             if earliest <= current_time:
#                 break  # a barber is free at this minute
#             current_time += 1  # move 1 minute forward

#         # Assign customer
#         barber_index = barber_free_time.index(earliest)
#         waiting_time = max(0, earliest - current_time)
#         start_time = max(current_time, earliest)
#         finish_time = start_time + service_time

#         # update barber's availability
#         barber_free_time[barber_index] = finish_time

#         # store event
#         events.append({
#             "customer": i + 1,
#             "barber": chr(ord('A') + barber_index),
#             "start": start_time,
#             "wait": waiting_time,
#             "finish": finish_time
#         })

#     return events

# print(simulate_barbers([15,20,45,30]))    
