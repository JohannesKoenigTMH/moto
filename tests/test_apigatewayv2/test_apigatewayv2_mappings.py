import boto3
import botocore.exceptions
import pytest

from moto import mock_apigatewayv2


@mock_apigatewayv2
def test_create_api_mapping():
    client = boto3.client("apigatewayv2", region_name="us-east-1")
    api = client.create_api(Name="test-api", ProtocolType="HTTP")
    dev_domain = client.create_domain_name(DomainName="dev.service.io")
    expected_keys = ["ApiId", "ApiMappingId", "ApiMappingKey", "Stage"]

    post_resp = client.create_api_mapping(
        DomainName=dev_domain["DomainName"],
        ApiMappingKey="v1/api",
        Stage="$default",
        ApiId=api["ApiId"],
    )

    get_resp = client.get_api_mapping(
        DomainName="dev.service.io", ApiMappingId=post_resp["ApiMappingId"]
    )

    # check post response has all expected keys
    for key in expected_keys:
        assert key in post_resp

    # check get response has all expected keys
    for key in expected_keys:
        assert key in get_resp

    # check that values are equal for post and get of same resource
    for key in expected_keys:
        assert post_resp.get(key) == get_resp.get(key)

    # ensure known values are set correct in post response
    assert post_resp.get("ApiId") is not None
    assert post_resp.get("ApiMappingId") is not None
    assert post_resp.get("ApiMappingKey") == "v1/api"
    assert post_resp.get("Stage") == "$default"


@mock_apigatewayv2
def test_create_api_mapping_missing_api():
    client = boto3.client("apigatewayv2", region_name="us-east-1")
    dev_domain = client.create_domain_name(DomainName="dev.service.io")
    with pytest.raises(botocore.exceptions.ClientError) as exc:
        client.create_api_mapping(
            DomainName=dev_domain["DomainName"],
            Stage="$default",
            ApiId="123dne",
        )

    err = exc.value.response["Error"]
    assert err["Code"] == "NotFoundException"
    assert (
        err["Message"]
        == "Invalid API identifier specified The resource specified in the request was not found."
    )


@mock_apigatewayv2
def test_create_api_mapping_missing_domain():
    client = boto3.client("apigatewayv2", region_name="us-east-1")
    api = client.create_api(Name="test-api", ProtocolType="HTTP")

    with pytest.raises(botocore.exceptions.ClientError) as exc:
        client.create_api_mapping(
            DomainName="domain.dne",
            Stage="$default",
            ApiId=api["ApiId"],
        )

    err = exc.value.response["Error"]
    assert err["Code"] == "NotFoundException"
    assert (
        err["Message"]
        == "The domain name resource specified in the request was not found."
    )


@mock_apigatewayv2
def test_create_api_mapping_bad_mapping_keys():
    client = boto3.client("apigatewayv2", region_name="us-east-1")
    api = client.create_api(Name="test-api", ProtocolType="HTTP")
    dev_domain = client.create_domain_name(DomainName="dev.service.io")
    bad_keys = {
        "/api": "API mapping key should not start with a '/' or have consecutive '/'s.",
        "v1//api": "API mapping key should not start with a '/' or have consecutive '/'s.",
        "api/": "API mapping key should not end with a '/'.",
    }

    for bad_key, message in bad_keys.items():
        with pytest.raises(botocore.exceptions.ClientError) as exc:
            client.create_api_mapping(
                DomainName=dev_domain["DomainName"],
                ApiMappingKey=bad_key,
                Stage="$default",
                ApiId=api["ApiId"],
            )

        err = exc.value.response["Error"]
        assert err["Code"] == "BadRequestException"
        assert err["Message"] == message


@mock_apigatewayv2
def test_get_api_mappings():
    client = boto3.client("apigatewayv2", region_name="eu-west-1")
    api = client.create_api(Name="test-api", ProtocolType="HTTP")
    included_domain = client.create_domain_name(DomainName="dev.service.io")
    excluded_domain = client.create_domain_name(DomainName="hr.service.io")

    v1_mapping = client.create_api_mapping(
        DomainName=included_domain["DomainName"],
        ApiMappingKey="v1/api",
        Stage="$default",
        ApiId=api["ApiId"],
    )

    v2_mapping = client.create_api_mapping(
        DomainName=included_domain["DomainName"],
        ApiMappingKey="v2/api",
        Stage="$default",
        ApiId=api["ApiId"],
    )

    hr_mapping = client.create_api_mapping(
        DomainName=excluded_domain["DomainName"],
        ApiMappingKey="hr/api",
        Stage="$default",
        ApiId=api["ApiId"],
    )

    # sanity check responses
    assert v1_mapping["ApiMappingKey"] == "v1/api"
    assert v2_mapping["ApiMappingKey"] == "v2/api"
    assert hr_mapping["ApiMappingKey"] == "hr/api"

    # make comparable
    del v1_mapping["ResponseMetadata"]
    del v2_mapping["ResponseMetadata"]
    del hr_mapping["ResponseMetadata"]

    get_resp = client.get_api_mappings(DomainName=included_domain["DomainName"])
    assert "Items" in get_resp
    assert v1_mapping in get_resp.get("Items")
    assert v2_mapping in get_resp.get("Items")
    assert hr_mapping not in get_resp.get("Items")


@mock_apigatewayv2
def test_delete_api_mapping():
    client = boto3.client("apigatewayv2", region_name="eu-west-1")
    api = client.create_api(Name="test-api", ProtocolType="HTTP")
    api_domain = client.create_domain_name(DomainName="dev.service.io")

    v1_mapping = client.create_api_mapping(
        DomainName=api_domain["DomainName"],
        ApiMappingKey="v1/api",
        Stage="$default",
        ApiId=api["ApiId"],
    )

    del v1_mapping["ResponseMetadata"]

    get_resp = client.get_api_mappings(DomainName=api_domain["DomainName"])
    assert "Items" in get_resp
    assert v1_mapping in get_resp.get("Items")

    client.delete_api_mapping(
        DomainName=api_domain["DomainName"], ApiMappingId=v1_mapping["ApiMappingId"]
    )

    get_resp = client.get_api_mappings(DomainName=api_domain["DomainName"])
    assert "Items" in get_resp
    assert v1_mapping not in get_resp.get("Items")


@mock_apigatewayv2
def test_delete_api_mapping_dne():
    client = boto3.client("apigatewayv2", region_name="eu-west-1")
    client.create_api(Name="test-api", ProtocolType="HTTP")
    api_domain = client.create_domain_name(DomainName="dev.service.io")

    with pytest.raises(botocore.exceptions.ClientError) as exc:
        client.delete_api_mapping(
            DomainName=api_domain["DomainName"], ApiMappingId="123dne"
        )

    err = exc.value.response["Error"]
    assert err["Code"] == "NotFoundException"
    assert (
        err["Message"]
        == "The api mapping resource specified in the request was not found."
    )
