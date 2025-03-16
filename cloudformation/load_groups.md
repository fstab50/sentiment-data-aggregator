## Group Assignments

    # North Asia + South America
    group_1 = [ap-northeast-1, ap-northeast-2, ap_northeast-3, sa-east-1]

    # South Asia Pac
    group_2 = [ap-south-1, ap-southeast-1, ap-southeast-2]

    # Europe
    group_3 = [eu-north-1, eu-central-1, eu-west-1, eu-west-2, eu-west-3]

    # North America West
    group_4 = [ca-central-1, us-west-1, us-west-2, us-east-2]

    # North America East
    group_5 = [us-east-1]


## Data size of each lambda group (raw GB, uncompressed) to be processed:

    * Group 1 (North Asia + South America): 15.74 GB (13.6% of total)

    * Group 2 (South Asia): 16.59 GB (14.34% of total)

    * Group 3 (Europe): 19.4 GB (16.76% of total)

    * Group 4 (NA West): 29.48 GB (25.48% of total)

    * Group 5 (NA East): 34.51 GB (29.82% of total)


## Lambda Runtime Estimates (per respective run group)

    Estimated cumulative lambda runtime required, all groups:  17 minutes
    Additional runtime buffer to ensure loads complete:         5 minutes

    Yields the following allowable runtimes for each lambda group:

            - Group 1 (N. Asia + SA):   3.0 minutes
            - Group 2 (S. Asia):        3.0 minutes
            - Group 3 (Europe):         4.0 minutes
            - Group 4 (NA West):        6.0 minutes
            - Group 5 (NA East):        7.0 minutes


## AWS S3 Bucket Keyspace Profile used to generate these estimates:

      AWS S3 Bucket spot-history Keyspace storage

            Keyspace     | Size (GB)
        ---------------- | --------
        2.57             |     2.57
        0.0              |      0.0
        0.01             |     0.01
        1.33             |     1.33
        11.04            |    11.04
        0.0              |      0.0
        2.78             |     2.78
        7.44             |     7.44
        1.12             |     1.12
        5.52             |     5.52
        7.68             |     7.68
        6.34             |     6.34
        7.02             |     7.02
        34.51            |    34.51
        2.03             |     2.03
        7.45             |     7.45
        18.88            |    18.88

        TOTAL All Regions: 115.72 GB
