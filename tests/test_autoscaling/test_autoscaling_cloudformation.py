import json

import boto3

from moto import mock_autoscaling, mock_cloudformation, mock_ec2, mock_elb
from tests import EXAMPLE_AMI_ID

from .utils import setup_networking


@mock_autoscaling
@mock_cloudformation
def test_launch_configuration():
    cf_client = boto3.client("cloudformation", region_name="us-east-1")
    client = boto3.client("autoscaling", region_name="us-east-1")

    stack_name = "test-launch-configuration"

    cf_template = """
Resources:
    LaunchConfiguration:
        Type: AWS::AutoScaling::LaunchConfiguration
        Properties:
            ImageId: {0}
            InstanceType: t2.micro
            LaunchConfigurationName: test_launch_configuration
Outputs:
    LaunchConfigurationName:
        Value: !Ref LaunchConfiguration
""".strip().format(
        EXAMPLE_AMI_ID
    )

    cf_client.create_stack(StackName=stack_name, TemplateBody=cf_template)
    stack = cf_client.describe_stacks(StackName=stack_name)["Stacks"][0]
    assert stack["Outputs"][0]["OutputValue"] == "test_launch_configuration"

    lc = client.describe_launch_configurations()["LaunchConfigurations"][0]
    assert lc["LaunchConfigurationName"] == "test_launch_configuration"
    assert lc["ImageId"] == EXAMPLE_AMI_ID
    assert lc["InstanceType"] == "t2.micro"

    cf_template = """
Resources:
    LaunchConfiguration:
        Type: AWS::AutoScaling::LaunchConfiguration
        Properties:
            ImageId: {0}
            InstanceType: m5.large
            LaunchConfigurationName: test_launch_configuration
Outputs:
    LaunchConfigurationName:
        Value: !Ref LaunchConfiguration
""".strip().format(
        EXAMPLE_AMI_ID
    )

    cf_client.update_stack(StackName=stack_name, TemplateBody=cf_template)
    stack = cf_client.describe_stacks(StackName=stack_name)["Stacks"][0]
    assert stack["Outputs"][0]["OutputValue"] == "test_launch_configuration"

    lc = client.describe_launch_configurations()["LaunchConfigurations"][0]
    assert lc["LaunchConfigurationName"] == "test_launch_configuration"
    assert lc["ImageId"] == EXAMPLE_AMI_ID
    assert lc["InstanceType"] == "m5.large"


@mock_autoscaling
@mock_cloudformation
def test_autoscaling_group_from_launch_config():
    subnet_id = setup_networking()["subnet1"]

    cf_client = boto3.client("cloudformation", region_name="us-east-1")
    client = boto3.client("autoscaling", region_name="us-east-1")

    client.create_launch_configuration(
        LaunchConfigurationName="test_launch_configuration",
        InstanceType="t2.micro",
        ImageId=EXAMPLE_AMI_ID,
    )
    stack_name = "test-auto-scaling-group"

    cf_template = """
Parameters:
    SubnetId:
        Type: AWS::EC2::Subnet::Id
Resources:
    AutoScalingGroup:
        Type: AWS::AutoScaling::AutoScalingGroup
        Properties:
            AutoScalingGroupName: test_auto_scaling_group
            AvailabilityZones:
                - us-east-1a
            LaunchConfigurationName: test_launch_configuration
            MaxSize: "5"
            MinSize: "1"
            VPCZoneIdentifier:
                - !Ref SubnetId
Outputs:
    AutoScalingGroupName:
        Value: !Ref AutoScalingGroup
""".strip()

    cf_client.create_stack(
        StackName=stack_name,
        TemplateBody=cf_template,
        Parameters=[{"ParameterKey": "SubnetId", "ParameterValue": subnet_id}],
    )
    stack = cf_client.describe_stacks(StackName=stack_name)["Stacks"][0]
    assert stack["Outputs"][0]["OutputValue"] == "test_auto_scaling_group"

    asg = client.describe_auto_scaling_groups()["AutoScalingGroups"][0]
    assert asg["AutoScalingGroupName"] == "test_auto_scaling_group"
    assert asg["MinSize"] == 1
    assert asg["MaxSize"] == 5
    assert asg["LaunchConfigurationName"] == "test_launch_configuration"

    client.create_launch_configuration(
        LaunchConfigurationName="test_launch_configuration_new",
        InstanceType="t2.micro",
        ImageId=EXAMPLE_AMI_ID,
    )

    cf_template = """
Parameters:
    SubnetId:
        Type: AWS::EC2::Subnet::Id
Resources:
    AutoScalingGroup:
        Type: AWS::AutoScaling::AutoScalingGroup
        Properties:
            AutoScalingGroupName: test_auto_scaling_group
            AvailabilityZones:
                - us-east-1a
            LaunchConfigurationName: test_launch_configuration_new
            MaxSize: "6"
            MinSize: "2"
            VPCZoneIdentifier:
                - !Ref SubnetId
Outputs:
    AutoScalingGroupName:
        Value: !Ref AutoScalingGroup
""".strip()

    cf_client.update_stack(
        StackName=stack_name,
        TemplateBody=cf_template,
        Parameters=[{"ParameterKey": "SubnetId", "ParameterValue": subnet_id}],
    )
    stack = cf_client.describe_stacks(StackName=stack_name)["Stacks"][0]
    assert stack["Outputs"][0]["OutputValue"] == "test_auto_scaling_group"

    asg = client.describe_auto_scaling_groups()["AutoScalingGroups"][0]
    assert asg["AutoScalingGroupName"] == "test_auto_scaling_group"
    assert asg["MinSize"] == 2
    assert asg["MaxSize"] == 6
    assert asg["LaunchConfigurationName"] == "test_launch_configuration_new"


@mock_autoscaling
@mock_cloudformation
@mock_ec2
def test_autoscaling_group_from_launch_template():
    subnet_id = setup_networking()["subnet1"]

    cf_client = boto3.client("cloudformation", region_name="us-east-1")
    ec2_client = boto3.client("ec2", region_name="us-east-1")
    client = boto3.client("autoscaling", region_name="us-east-1")

    template_response = ec2_client.create_launch_template(
        LaunchTemplateName="test_launch_template",
        LaunchTemplateData={"ImageId": EXAMPLE_AMI_ID, "InstanceType": "t2.micro"},
    )
    launch_template_id = template_response["LaunchTemplate"]["LaunchTemplateId"]
    stack_name = "test-auto-scaling-group"

    cf_template = """
Parameters:
    SubnetId:
        Type: AWS::EC2::Subnet::Id
    LaunchTemplateId:
        Type: String
Resources:
    AutoScalingGroup:
        Type: AWS::AutoScaling::AutoScalingGroup
        Properties:
            AutoScalingGroupName: test_auto_scaling_group
            AvailabilityZones:
                - us-east-1a
            LaunchTemplate:
                LaunchTemplateId: !Ref LaunchTemplateId
                Version: "1"
            MaxSize: "5"
            MinSize: "1"
            VPCZoneIdentifier:
                - !Ref SubnetId
Outputs:
    AutoScalingGroupName:
        Value: !Ref AutoScalingGroup
""".strip()

    cf_client.create_stack(
        StackName=stack_name,
        TemplateBody=cf_template,
        Parameters=[
            {"ParameterKey": "SubnetId", "ParameterValue": subnet_id},
            {"ParameterKey": "LaunchTemplateId", "ParameterValue": launch_template_id},
        ],
    )
    stack = cf_client.describe_stacks(StackName=stack_name)["Stacks"][0]
    assert stack["Outputs"][0]["OutputValue"] == "test_auto_scaling_group"

    asg = client.describe_auto_scaling_groups()["AutoScalingGroups"][0]
    assert asg["AutoScalingGroupName"] == "test_auto_scaling_group"
    assert asg["MinSize"] == 1
    assert asg["MaxSize"] == 5
    lt = asg["LaunchTemplate"]
    assert lt["LaunchTemplateId"] == launch_template_id
    assert lt["LaunchTemplateName"] == "test_launch_template"
    assert lt["Version"] == "1"

    template_response = ec2_client.create_launch_template(
        LaunchTemplateName="test_launch_template_new",
        LaunchTemplateData={"ImageId": EXAMPLE_AMI_ID, "InstanceType": "m5.large"},
    )
    launch_template_id = template_response["LaunchTemplate"]["LaunchTemplateId"]

    cf_template = """
Parameters:
    SubnetId:
        Type: AWS::EC2::Subnet::Id
    LaunchTemplateId:
        Type: String
Resources:
    AutoScalingGroup:
        Type: AWS::AutoScaling::AutoScalingGroup
        Properties:
            AutoScalingGroupName: test_auto_scaling_group
            AvailabilityZones:
                - us-east-1a
            LaunchTemplate:
                LaunchTemplateId: !Ref LaunchTemplateId
                Version: "1"
            MaxSize: "6"
            MinSize: "2"
            VPCZoneIdentifier:
                - !Ref SubnetId
Outputs:
    AutoScalingGroupName:
        Value: !Ref AutoScalingGroup
""".strip()

    cf_client.update_stack(
        StackName=stack_name,
        TemplateBody=cf_template,
        Parameters=[
            {"ParameterKey": "SubnetId", "ParameterValue": subnet_id},
            {"ParameterKey": "LaunchTemplateId", "ParameterValue": launch_template_id},
        ],
    )
    stack = cf_client.describe_stacks(StackName=stack_name)["Stacks"][0]
    assert stack["Outputs"][0]["OutputValue"] == "test_auto_scaling_group"

    asg = client.describe_auto_scaling_groups()["AutoScalingGroups"][0]
    assert asg["AutoScalingGroupName"] == "test_auto_scaling_group"
    assert asg["MinSize"] == 2
    assert asg["MaxSize"] == 6
    lt = asg["LaunchTemplate"]
    assert lt["LaunchTemplateId"] == launch_template_id
    assert lt["LaunchTemplateName"] == "test_launch_template_new"
    assert lt["Version"] == "1"


@mock_autoscaling
@mock_elb
@mock_cloudformation
@mock_ec2
def test_autoscaling_group_with_elb():
    web_setup_template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Resources": {
            "my-as-group": {
                "Type": "AWS::AutoScaling::AutoScalingGroup",
                "Properties": {
                    "AvailabilityZones": ["us-east-1a"],
                    "LaunchConfigurationName": {"Ref": "my-launch-config"},
                    "MinSize": "2",
                    "MaxSize": "2",
                    "DesiredCapacity": "2",
                    "LoadBalancerNames": [{"Ref": "my-elb"}],
                    "Tags": [
                        {
                            "Key": "propagated-test-tag",
                            "Value": "propagated-test-tag-value",
                            "PropagateAtLaunch": True,
                        },
                        {
                            "Key": "not-propagated-test-tag",
                            "Value": "not-propagated-test-tag-value",
                            "PropagateAtLaunch": False,
                        },
                    ],
                },
            },
            "ScheduledAction": {
                "Type": "AWS::AutoScaling::ScheduledAction",
                "Properties": {
                    "AutoScalingGroupName": "test-scaling-group",
                    "DesiredCapacity": 10,
                    "EndTime": "2022-08-01T00:00:00Z",
                    "MaxSize": 15,
                    "MinSize": 5,
                    "Recurrence": "* * * * *",
                    "StartTime": "2022-07-01T00:00:00Z",
                },
            },
            "my-launch-config": {
                "Type": "AWS::AutoScaling::LaunchConfiguration",
                "Properties": {
                    "ImageId": EXAMPLE_AMI_ID,
                    "InstanceType": "t2.medium",
                    "UserData": "some user data",
                },
            },
            "my-elb": {
                "Type": "AWS::ElasticLoadBalancing::LoadBalancer",
                "Properties": {
                    "AvailabilityZones": ["us-east-1a"],
                    "Listeners": [
                        {
                            "LoadBalancerPort": "80",
                            "InstancePort": "80",
                            "Protocol": "HTTP",
                        }
                    ],
                    "LoadBalancerName": "my-elb",
                    "HealthCheck": {
                        "Target": "HTTP:80",
                        "HealthyThreshold": "3",
                        "UnhealthyThreshold": "5",
                        "Interval": "30",
                        "Timeout": "5",
                    },
                },
            },
        },
    }

    web_setup_template_json = json.dumps(web_setup_template)

    cf = boto3.client("cloudformation", region_name="us-east-1")
    ec2 = boto3.client("ec2", region_name="us-east-1")
    elb = boto3.client("elb", region_name="us-east-1")
    client = boto3.client("autoscaling", region_name="us-east-1")

    cf.create_stack(StackName="web_stack", TemplateBody=web_setup_template_json)

    autoscale_group = client.describe_auto_scaling_groups()["AutoScalingGroups"][0]
    asg_name = autoscale_group["AutoScalingGroupName"]
    assert "my-launch-config" in autoscale_group["LaunchConfigurationName"]
    assert autoscale_group["LoadBalancerNames"] == ["my-elb"]
    assert len(autoscale_group["Tags"]) == 2
    assert {
        "ResourceId": asg_name,
        "ResourceType": "auto-scaling-group",
        "Key": "propagated-test-tag",
        "Value": "propagated-test-tag-value",
        "PropagateAtLaunch": True,
    } in autoscale_group["Tags"]
    assert {
        "ResourceId": asg_name,
        "ResourceType": "auto-scaling-group",
        "Key": "not-propagated-test-tag",
        "Value": "not-propagated-test-tag-value",
        "PropagateAtLaunch": False,
    } in autoscale_group["Tags"]

    tags = client.describe_tags(
        Filters=[{"Name": "auto-scaling-group", "Values": [asg_name]}]
    )["Tags"]
    assert tags == autoscale_group["Tags"]

    # Confirm the Launch config was actually created
    assert len(client.describe_launch_configurations()["LaunchConfigurations"]) == 1

    # Confirm the ELB was actually created
    assert len(elb.describe_load_balancers()["LoadBalancerDescriptions"]) == 1

    resources = cf.list_stack_resources(StackName="web_stack")["StackResourceSummaries"]
    as_group_resource = [
        resource
        for resource in resources
        if resource["ResourceType"] == "AWS::AutoScaling::AutoScalingGroup"
    ][0]
    assert "my-as-group" in as_group_resource["PhysicalResourceId"]

    launch_config_resource = [
        resource
        for resource in resources
        if resource["ResourceType"] == "AWS::AutoScaling::LaunchConfiguration"
    ][0]
    assert "my-launch-config" in launch_config_resource["PhysicalResourceId"]

    elb_resource = [
        resource
        for resource in resources
        if resource["ResourceType"] == "AWS::ElasticLoadBalancing::LoadBalancer"
    ][0]
    assert "my-elb" in elb_resource["PhysicalResourceId"]

    # confirm the instances were created with the right tags
    reservations = ec2.describe_instances()["Reservations"]

    assert len(reservations) == 1
    assert len(reservations[0]["Instances"]) == 2
    for instance in reservations[0]["Instances"]:
        tag_keys = [t["Key"] for t in instance["Tags"]]
        assert "propagated-test-tag" in tag_keys
        assert "not-propagated-test-tag" not in tag_keys

    # confirm scheduled scaling action was created
    response = client.describe_scheduled_actions(
        AutoScalingGroupName="test-scaling-group"
    )["ScheduledUpdateGroupActions"]
    assert len(response) == 1


@mock_autoscaling
@mock_cloudformation
@mock_ec2
def test_autoscaling_group_update():
    asg_template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Resources": {
            "my-as-group": {
                "Type": "AWS::AutoScaling::AutoScalingGroup",
                "Properties": {
                    "AvailabilityZones": ["us-west-1a"],
                    "LaunchConfigurationName": {"Ref": "my-launch-config"},
                    "MinSize": "2",
                    "MaxSize": "2",
                    "DesiredCapacity": "2",
                },
            },
            "my-launch-config": {
                "Type": "AWS::AutoScaling::LaunchConfiguration",
                "Properties": {
                    "ImageId": EXAMPLE_AMI_ID,
                    "InstanceType": "t2.medium",
                    "UserData": "some user data",
                },
            },
        },
    }
    asg_template_json = json.dumps(asg_template)

    cf = boto3.client("cloudformation", region_name="us-west-1")
    ec2 = boto3.client("ec2", region_name="us-west-1")
    client = boto3.client("autoscaling", region_name="us-west-1")
    cf.create_stack(StackName="asg_stack", TemplateBody=asg_template_json)

    asg = client.describe_auto_scaling_groups()["AutoScalingGroups"][0]
    assert asg["MinSize"] == 2
    assert asg["MaxSize"] == 2
    assert asg["DesiredCapacity"] == 2

    asg_template["Resources"]["my-as-group"]["Properties"]["MaxSize"] = 3
    asg_template["Resources"]["my-as-group"]["Properties"]["Tags"] = [
        {
            "Key": "propagated-test-tag",
            "Value": "propagated-test-tag-value",
            "PropagateAtLaunch": True,
        },
        {
            "Key": "not-propagated-test-tag",
            "Value": "not-propagated-test-tag-value",
            "PropagateAtLaunch": False,
        },
    ]
    asg_template_json = json.dumps(asg_template)
    cf.update_stack(StackName="asg_stack", TemplateBody=asg_template_json)
    asg = client.describe_auto_scaling_groups()["AutoScalingGroups"][0]
    assert asg["MinSize"] == 2
    assert asg["MaxSize"] == 3
    assert asg["DesiredCapacity"] == 2

    # confirm the instances were created with the right tags
    reservations = ec2.describe_instances()["Reservations"]
    running_instance_count = 0
    for res in reservations:
        for instance in res["Instances"]:
            if instance["State"]["Name"] == "running":
                running_instance_count += 1
                assert {
                    "Key": "propagated-test-tag",
                    "Value": "propagated-test-tag-value",
                } in instance["Tags"]
                tag_keys = [t["Key"] for t in instance["Tags"]]
                assert "not-propagated-test-tag" not in tag_keys
    assert running_instance_count == 2
