* * *
AWS CloudFormation README
* * *

**TEMPLATE**:  ``spotprice-lambda.template.yml``


**Note**:  

* There are 4 lambda execution groups
* Each lambda group processed in 1 lambda execution run
* This README details which regional Spot Price data is retrieved in which execution group


**Lambda Execution Groups**:

- __Group 1__:  ap-south-1,ca-central-1,ap-northeast-3,sa-east-1,ap-east-1,us-west-1

- __Group 2__:  ap-northeast-1,ap-northeast-2,ap-southeast-1,ap-southeast-2

- __Group 3__:  eu-central-1,eu-north-1,eu-west-1,eu-west-2,eu-west-3

- __Group 4__:  us-east-1,us-east-2,us-west-2


* * *

**TEMPLATE**:  ``dynamodb-table.template.yml``


**Note**:  

This template deploys the spot price auto-scalable DynamoDB database and all ancillary IAM configurations
