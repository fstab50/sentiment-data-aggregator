#!/usr/bin/env python3


import os
import sys
import boto3
from libtools import Colors

c = Colors()

profile = 'default'
bucket = 'spot-history'
tab2 = '\t'.expandtabs(2)
tab4 = '\t'.expandtabs(4)
bdyl = c.BRIGHT_YELLOW2 + c.BOLD
reset = c.RESET


#---------------------------------- Subroutines --------------------------------


def _get_regions():
    client = boto3.client('ec2')
    return [x['RegionName'] for x in client.describe_regions()['Regions']]


def sum_list_contents(list):
    a = 0
    for item in list:
        a = item + a
    return a


#---------------------------------- Statics ------------------------------------


# s3 resource object
s3 = boto3.resource('s3')

# Bucket object
bucket_resource = s3.Bucket(bucket)

# ec2 client object
session = boto3.Session(profile_name=profile)
client = boto3.client('ec2')

grand_total = 0
regions = []

# Print title header
print('\n' + tab2 + 'AWS S3 Bucket {}{}{} Keyspace storage'.format(bdyl, bucket, reset))
print('\n' + tab4 + '{: ^16} | {: ^8}'.format('Keyspace', 'Size (GB)'))
print(tab4 + '{: ^16} | {: ^8}'.format('-' * 16, '-' * 8))

for region in _get_regions():
    # reset counters
    total_bytes, size_byte, n = 0, 0, 0

    for bucket_object in bucket_resource.objects.filter(Prefix=region):
        size_byte = size_byte + bucket_object.size

    totalsize_GB = round(size_byte/1000/1024/1024, 2)
    region = totalsize_GB
    regions.append(region)
    print('    {: <16} | {: >8}'.format(region, totalsize_GB))
    grand_total = grand_total + totalsize_GB

print('\n    TOTAL All Regions: {: >6} GB\n'.format(round(grand_total, 2)))


#------------------- Group regions into equal sectors -------------------------

ap_south_1 = 2.57
eu_north_1 = 0
eu_west_1 = 11.04
eu_west_2 = 1.33
eu_west_3 = 0.01
ap_northeast_1 = 7.44
ap_northeast_2 = 2.78
ap_northeast_3 = 0.0
ca_central_1 = 1.12
sa_east_1 = 5.52
ap_southeast_1 = 7.68
ap_southeast_2 = 6.34
eu_central_1 = 7.02
us_east_1 = 34.51
us_east_2 = 2.03
us_west_1 = 7.45
us_west_2 = 18.88

# North Asia + South America
group_1 = [ap_northeast_1, ap_northeast_2, ap_northeast_3, sa_east_1]

# South Asia Pac
group_2 = [ap_south_1, ap_southeast_1, ap_southeast_2]

# Europe
group_3 = [eu_north_1, eu_central_1, eu_west_1, eu_west_2, eu_west_3]

# North America West
group_4 = [ca_central_1, us_west_1, us_west_2, us_east_2]

# North America East
group_5 = [us_east_1]

## Group totals

total = sum_list_contents(group_1) + sum_list_contents(group_2) + sum_list_contents(group_3) + \
        sum_list_contents(group_4) + sum_list_contents(group_5)

print('\nTotal for regions contained each group:\n')

# Group 1
percentage1 = round((sum_list_contents(group_1) / total) * 100, 2)
print(tab4 + 'Group 1 (North Asia + South America): {} GB ({}%)\n'.format(round(sum_list_contents(group_1), 2), percentage1))

# Group 2
percentage2 = round((sum_list_contents(group_2) / total) * 100, 2)
print(tab4 + 'Group 2 (South Asia): {} GB ({}%)\n'.format(round(sum_list_contents(group_2), 2), percentage2))

percentage3 = round((sum_list_contents(group_3) / total) * 100, 2)
print(tab4 + 'Group 3 (Europe): {} GB ({}%)\n'.format(round(sum_list_contents(group_3), 2), percentage3))

percentage4 = round((sum_list_contents(group_4) / total) * 100, 2)
print(tab4 + 'Group 4 (NA West): {} GB ({}%)\n'.format(round(sum_list_contents(group_4), 2), percentage4))

percentage5 = round((sum_list_contents(group_5) / total) * 100, 2)
print(tab4 + 'Group 5 (NA East): {} GB ({}%)\n'.format(round(sum_list_contents(group_5), 2), percentage5))


# -------------------- Estimated Lambda Runtimes ------------------------------

# lambda runtime with all regions together (minutes)
avg_runtime = 17

# additional buffer to ensure loads complete (minutes):
buffer_time = 5

# total runtime, all regions (minutes)
total_runtime = avg_runtime + buffer_time

print('Estimated cumulative lambda runtime required, all groups:' + tab2 + '{} minutes'.format(avg_runtime))
print('Additional runtime buffer to ensure loads complete: ' + tab4 * 2 + '{} minutes'.format(buffer_time))
print('\nYields the following allowable runtimes for each lambda group:\n')

# Group 1 runtime estimate
print(tab4 * 2 + '{: <26}{}{} minutes'.format('- Group 1 (N. Asia + SA):', tab2, round((total_runtime * percentage1 / 100), 0)))
# Group 2 runtime estimate
print(tab4 * 2 + '{: <26}{}{} minutes'.format('- Group 2 (S. Asia):', tab2, round((total_runtime * percentage2 / 100), 0)))
# Group 3 runtime estimate
print(tab4 * 2 + '{: <26}{}{} minutes'.format('- Group 3 (Europe):', tab2, round((total_runtime * percentage3 / 100), 0)))
# Group 4 runtime estimate
print(tab4 * 2 + '{: <26}{}{} minutes'.format('- Group 4 (NA West):', tab2, round((total_runtime * percentage4 / 100), 0)))
# Group 5 runtime estimate
print(tab4 * 2 + '{: <26}{}{} minutes\n'.format('- Group 5 (NA East):', tab2, round((total_runtime * percentage5 / 100), 0)))
