import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import LineString

def read_data_from_file(file_name):
    with open(file_name, 'r') as file:
        return [float(line.strip()) for line in file]

def normalize_data(data):
    min_value = min(data)
    return [x - min_value for x in data]

# Load data from files
#time_data = read_data_from_file('time.txt')
default_packet_list_data = read_data_from_file('default_packet_list1.txt')
#group_time_data = read_data_from_file('group_time.txt')
group_packet_list_data = read_data_from_file('group_packet_list1.txt')
# Assuming the lengths of default_packet_list_data and group_packet_list_data are known
length_of_default_packet_list = len(default_packet_list_data)
length_of_group_packet_list = len(group_packet_list_data)

# Generate time_data and group_time_data using list comprehension
time_data = [i*2 for i in range(length_of_default_packet_list)]
group_time_data = [i*2 for i in range(length_of_group_packet_list)]

# Normalize group packet list data
normalized_group_packet_list_data = normalize_data(group_packet_list_data)

default_packet_list_data_scaled = [x * 28 for x in default_packet_list_data]
group_packet_list_data_scaled = [x * 28 for x in group_packet_list_data]
#intersections = np.argwhere(np.diff(np.sign(default_packet_list_data, group_packet_list_data))).flatten()
#print(intersections)
first_line = LineString(np.column_stack((time_data, default_packet_list_data)))
second_line = LineString(np.column_stack((group_time_data, group_packet_list_data)))
intersection = first_line.intersection(second_line)
print(intersection)

plt.rcParams.update({'font.size': 20})
# Plotting the data
plt.figure(figsize=(12, 8))

# Plot for default packet list
plt.plot(time_data, default_packet_list_data_scaled, color='blue', label='Default Bytes')

plt.plot(group_time_data, group_packet_list_data_scaled, color='red', label='MTD Bytes')
# Adding the legend with a specific font size

# Adding titles and labels
plt.xlabel('Time (s)',fontsize=20, fontweight='bold')
plt.ylabel('Bytes',fontsize=20, fontweight='bold')
plt.legend(fontsize=20)
plt.grid(True)

# Display the plot
plt.show()
