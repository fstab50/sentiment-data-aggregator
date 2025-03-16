"""

lambda EC2 spotprice retriever, GPL v3 License

Copyright (c) 2018-2020 Blake Huber

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the 'Software'), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""
import os
import sys
import datetime
import json
import inspect
import subprocess
import boto3
import threading
from botocore.exceptions import ClientError
from spotlib import SpotPrices, UtcConversion
from libtools.js import export_iterobject
from libtools.oscodes_unix import exit_codes
from pyaws.awslambda import read_env_variable
from lambda_utils import sns_notification
import loggers
from _version import __version__

logger = loggers.getLogger(__version__)

# globals
module = os.path.basename(__file__)
sns_arn = read_env_variable('SNS_TOPIC_ARN')


def _debug_output(*args):
    """additional verbose information output"""
    for arg in args:
        if os.path.isfile(arg):
            print('Filename {}'.format(arg.strip(), 'lower'))
        elif str(arg):
            print('String {} = {}'.format(getattr(arg.strip(), 'title'), arg))


def _get_regions():
    client = boto3.client('ec2')
    return [x['RegionName'] for x in client.describe_regions()['Regions']]


def standardize_datetime(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def utc_datetime(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def datetimify_standard(s):
    """Function to create timezone unaware string"""
    return datetime.strptime(s, '%Y-%m-%d %H:%M:%S')


def default_endpoints(duration_days=1):
    """
    Supplies the default start and end datetime objects in absence
    of user supplied endpoints which frames time period from which
    to begin and end retrieving spot price data from Amazon APIs.

    Returns:  TYPE: tuple, containing:
        - start (datetime), midnight yesterday
        - end (datetime) midnight, current day

    """
    # end datetime calcs
    dt_date = datetime.datetime.today().date()
    dt_time = datetime.datetime.min.time()
    end = datetime.datetime.combine(dt_date, dt_time)

    # start datetime calcs
    duration = datetime.timedelta(days=duration_days)
    start = end - duration
    return start, end


def format_pricefile(key):
    """Adds path delimiter and color formatting to output artifacts"""
    region = key.split('/')[0]
    pricefile = key.split('/')[1]
    delimiter = '/'
    return region + delimiter + pricefile


def summary_statistics(data, instances):
    """
    Calculate stats across spot price data elements retrieved
    in the current execution.  Prints to stdout

    Args:
        :data (list): list of spot price dictionaries
        :instances (list): list of unique instance types found in data

    Returns:
        Success | Failure, TYPE:  bool
    """
    instance_dict, container = {}, []

    for itype in instances:
        try:
            cur_type = [
                x['SpotPrice'] for x in data['SpotPriceHistory'] if x['InstanceType'] == itype
            ]
        except KeyError as e:
            logger.exception('KeyError on key {} while printing summary report statistics.'.format(e))
            continue

        instance_dict['InstanceType'] = str(itype)
        instance_dict['AvgPrice'] = sum([float(x['SpotPrice']) for x in cur_type]) / len(cur_type)
        container.append(instance_dict)
    # output to stdout
    print_ending_summary(instances, container)
    return True


def print_ending_summary(itypes_list, summary_data):
    """
    Prints summary statics to stdout at the conclusion of spot
    price data retrieval
    """
    now = datetime.datetime.now().strftime('%Y-%d-%m %H:%M:%S')
    tab = '\t'.expandtabs(4)
    print('EC2 Spot price data retrieval concluded {}'.format(now))
    print('Found {} unique EC2 size types in spot data'.format(len(itypes_list)))
    print('Instance Type distribution:')
    for itype in itypes_list:
        for instance in container:
            if instance['InstanceType'] == itype:
                print('{} - {}'.format(tab, itype, instance['AvgPrice']))


def source_environment(env_variable):
    """
    Sources all environment variables
    """
    return {
        'duration_days': read_env_variable('DEFAULT_DURATION'),
        'page_size': read_env_variable('PAGE_SIZE', 700),
        'bucket': read_env_variable('S3_BUCKET', None)
    }.get(env_variable, None)


def s3upload(bucket, s3object, key):
    """
        Streams object to S3 for long-term storage

    Returns:
        Success | Failure, TYPE: bool
    """
    try:
        session = boto3.Session()
        s3client = session.client('s3')
        # dict --> str -->  bytes (utf-8 encoded)
        bcontainer = json.dumps(s3object, indent=4, default=str).encode('utf-8')
        response = s3client.put_object(Bucket=bucket, Body=bcontainer, Key=key)

        # http completion code
        statuscode = response['ResponseMetadata']['HTTPStatusCode']

    except ClientError as e:
        logger.exception(f'Unknown exception while calc start & end duration: {e}')
        return False
    return True if str(statuscode).startswith('20') else False


def split_list(mlist, n):
    """
    Summary.

        splits a list into equal parts as allowed, given n segments

    Args:
        :mlist (list):  a single list containing multiple elements
        :n (int):  Number of segments in which to split the list

    Returns:
        generator object

    """
    k, m = divmod(len(mlist), n)
    return (mlist[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))


def writeout_data(key, jsonobject, filename):
    """
        Persists json data to local filesystem

    Returns:
        Success | Failure, TYPE: bool

    """
    tab = '\t'.expandtabs(13)

    if export_iterobject({key: jsonobject}, filename):
        success = f'Wrote {filename}\n{tab}successfully to local filesystem'
        logger.info(success)
        return True
    else:
        failure = f'Problem writing {filename} to local filesystem'
        logger.warning(failure)
        return False


class AssignRegion():
    """Map AvailabilityZone to corresponding AWS region"""
    def __init__(self):
        self.client = boto3.client('ec2')
        self.regions = [x['RegionName'] for x in self.client.describe_regions()['Regions']]

    def assign_region(self, az):
        return [x for x in self.regions if x in az][0]


class DynamoDBPrices(threading.Thread):
    def __init__(self, region, table_name, price_dicts, start_date, end_date):
        super(DynamoDBPrices, self).__init__()
        self.ar = AssignRegion()
        self.sp = SpotPrices(start_dt=start_date, end_dt=end_date)
        self.regions = self.ar.regions
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)
        self.prices = price_dicts
        self.running = False

    def start(self):
        self.running = True
        super(DynamoDBPrices, self).start()

    def run(self):
        """
            Inserts data items into DynamoDB table
                - Partition Key:  Timestamp
                - Sort Key: Spot Price
        Args:
            region_list (list): AWS region code list from which to gen price data

        Returns:
            dynamodb table object

        """
        date = datetime.date.today()

        for item in self.prices:
            try:
                self.table.put_item(
                    Item={
                            'RegionName':  self.ar.assign_region(item['AvailabilityZone']),
                            'AvailabilityZone': item['AvailabilityZone'],
                            'InstanceType': item['InstanceType'],
                            'ProductDescription': item['ProductDescription'],
                            'SpotPrice': item['SpotPrice'],
                            'Timestamp': item['Timestamp'],
                            'OnDemandPrice': "0.12456789",
                            'Unit': 'USD/ Hr',
                            'RecordDate':  date.isoformat()
                    }
                )
                logger.info(
                    'Successful put item for AZ {} at time {}'.format(item['AvailabilityZone'], item['Timestamp'])
                )
                if not self.running:
                    break
            except ClientError as e:
                logger.info(f'Error inserting item {item}: \n\n{e}')
                continue

    def stop(self):
        self.running = False
        self.join()  # wait for run() method to terminate
        sys.stdout.flush()


def download_spotprice_data(region_list):
    sp = SpotPrices()
    start = sp.start.strftime("%Y-%m-%dT%H:%M:%S")
    end = sp.end.strftime("%Y-%m-%dT%H:%M:%S")
    # log datetime range of data pull
    logger.info('Spot Price data retrieval start: {}'.format(start))
    logger.info('Spot Price data retrieval end: {}'.format(end))
    prices = sp.generate_pricedata(regions=region_list)
    uc = UtcConversion(prices)      # converts datatime objects to str date times
    return prices['SpotPriceHistory']


def set_tempdirectory():
    TMPDIR = '/tmp'
    os.environ['TMPDIR'] = TMPDIR
    os.environ['TMP'] = TMPDIR
    os.environ['TEMP'] = TMPDIR
    subprocess.getoutput('export TMPDIR=/tmp')


def summary_report(upload_status, *args):
    """Log summary ending report statistics"""
    box = []
    try:
        logger.info('SPOTPRICE LOADER ENDING SUMMARY REPORT:')

        for index, arg in enumerate(args):
            box.append(arg)
            logger.info('\t- Processed {} records for Thread{}'.format(len(arg), index + 1))
        logger.info('Raw data archive upload to Amazon S3:')

        # print out s3 upload status for raw data archives
        for k, v in upload_status.items():
            logger.info('Region {} upload complete status: {}'.format(k, v))
        logger.info('<-- SPOTPRICE RETRIEVER VERSION {} END -->'.format(__version__))

        # SNS Report
        topic = sns_arn
        subject = 'SpotPrice data S3 Upload Status'
        p1, p2, p3, p4 = [x for x in box]
        msg = 'Records processed:\n\t- Thread 1: {},\n\t- Thread 2: {},\n\t- Thread 3: {},\n\t- Thread 4: {}'.format(len(p1), len(p2), len(p3), len(p4))
        sns_notification(topic, subject, msg)
    except Exception as e:
        fx = inspect.stack()[0][3]
        logger.exception('{}: Unknown error generating summary report: {}'.format(fx, e))
        return False
    return True


def lambda_handler(event, context):
    """
    Initialize spot price operations; process command line parameters
    """
    # change to writeable filesystem
    os.chdir('/tmp')
    logger.info('PWD is {}'.format(os.getcwd()))

    set_tempdirectory()

    # set local region, dynamoDB table
    REGION = read_env_variable('DEFAULT_REGION', 'us-east-2')
    #TARGET_REGIONS = read_env_variable('TARGET_REGIONS').split(',')
    TABLE = read_env_variable('DYNAMODB_TABLE', 'PriceData')
    BUCKET = read_env_variable('S3_BUCKET')
    DBUGMODE = 'True' if read_env_variable('DBUGMODE') in ('true', 'True') else 'False'

    # log status
    logger.info('<-- SPOTPRICE RETRIEVER VERSION {} START -->'.format(__version__))
    logger.info('Environment variable status:')
    logger.info('REGION: {}'.format(REGION))
    logger.info('DYNAMODB TABLE: {}'.format(TABLE))
    logger.info('BUCKET: {}'.format(BUCKET))
    logger.info('DBUGMODE is: {}'.format(DBUGMODE))

    try:

        if DBUGMODE:
            print('Received event: ')
            print(json.dumps(event, indent=2))
        # parse event
        region = event['region']
        detail = event['detail']
        TARGET_REGIONS = detail['responseElements'].split(',')
        eventname = detail['eventName']

    except KeyError as e:
        logger.info('KeyError for key %s' % str(e))
        pass
    except Exception:
        pass

    # create dt object start, end datetimes
    start, end = default_endpoints()

    price_list = download_spotprice_data(TARGET_REGIONS)

    # divide price list into multiple parts for parallel processing
    prices1, prices2, prices3, prices4 = split_list(price_list, 4)

    logger.info('prices1 contains: {} elements'.format(len(prices1)))
    logger.info('prices2 contains: {} elements'.format(len(prices2)))
    logger.info('prices3 contains: {} elements'.format(len(prices3)))
    logger.info('prices4 contains: {} elements'.format(len(prices4)))

    # prepare parallel thread facilities for dynamoDB loading
    db1 = DynamoDBPrices(
            region=REGION,
            table_name=TABLE,
            price_dicts=prices1,
            start_date=start,
            end_date=end
        )

    db2 = DynamoDBPrices(
            region=REGION,
            table_name=TABLE,
            price_dicts=prices2,
            start_date=start,
            end_date=end
        )

    db3 = DynamoDBPrices(
            region=REGION,
            table_name=TABLE,
            price_dicts=prices3,
            start_date=start,
            end_date=end
        )

    db4 = DynamoDBPrices(
            region=REGION,
            table_name=TABLE,
            price_dicts=prices4,
            start_date=start,
            end_date=end
        )

    # retrieve spot data, insert into dynamodb
    db1.start()
    db2.start()
    db3.start()
    db4.start()

    # need to join, concurrent end to all threads
    db1.join()
    db2.join()
    db3.join()
    db4.join()

    s3_uploads = {}

    # save raw data in Amazon S3, one file per region
    for region in TARGET_REGIONS:

        price_list = download_spotprice_data([region])

        fname = '_'.join(
                    [
                        start.strftime('%Y-%m-%dT%H:%M:%SZ'),
                        end.strftime('%Y-%m-%dT%H:%M:%SZ'),
                        'all-instance-spot-prices.json'
                    ]
                )

        # write to file on local filesystem
        key = os.path.join(region, fname)
        _completed = s3upload(BUCKET, {'SpotPriceHistory': price_list}, key)
        s3_uploads[region] = str(_completed)
        logger.info('Completed upload to Amazon S3 for region {}'.format(region))

        # log status
        tab = '\t'.expandtabs(13)
        fkey = format_pricefile(key)
        success = f'Wrote {fkey}\n{tab}successfully to local filesystem'
        failure = f'Problem writing {fkey} to local filesystem'
        logger.info(success) if _completed else logger.warning(failure)

    return summary_report(s3_uploads, prices1, prices2, prices3, prices4)
