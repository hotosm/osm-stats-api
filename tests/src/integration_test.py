from fastapi.testclient import TestClient
from requests.models import Response
from typing import List

from API.main import app as fastapi_app
from src.galaxy.validation.models import UserStatistics

client = TestClient(fastapi_app)
usernames = ["mspray6", "mspray7"]

def assert_missing_field(response: Response, field_name: str):
    assert response.status_code == 422
    res = response.json()
    assert res["detail"][0]["loc"][1] == field_name
    assert res["detail"][0]["msg"] == "field required"

################################################################

def test_countries():
    response = client.get("/latest/countries")
    assert response.status_code == 200
    res = response.json()
    assert res["type"] == "FeatureCollection"
    assert len(res["features"]) > 0
    for feature in res["features"]:
        assert feature["type"] == "Feature"
        assert type(feature["properties"]["name"]) == str
        print(feature["properties"]["name"])
        assert feature["geometry"]["type"] == "MultiPolygon"
        coordinates = feature["geometry"]["coordinates"]
        assert len(coordinates) == 1
        assert len(coordinates[0]) > 0
        for i in range(len(coordinates[0])):
            assert len(coordinates[0][i]) > 0
            for point in coordinates[0][i]:
                assert len(point) == 2
                assert type(point[0]) == float
                assert type(point[1]) == float

################################################################

def test_osm_users_ids_OK():
    response = client.post("/latest/osm-users/ids/", json={"userNames":usernames,"fromTimestamp":"2018-07-11T00:00:00Z","toTimestamp":"2018-07-12T00:00:00Z"})
    assert response.status_code == 200
    res = response.json()
    assert len(res) == len(usernames)
    for i in range(len(res)):
        assert type(res[i]["userId"]) == int
        assert res[i]["userName"] == usernames[i]

def test_osm_users_ids_old_date():
    response = client.post("/latest/osm-users/ids/", json={"userNames":usernames,"fromTimestamp":"2000-07-11T00:00:00Z","toTimestamp":"2000-07-12T00:00:00Z"})
    assert response.status_code == 200
    assert len(response.json()) == 0

def test_osm_users_ids_no_user():
    response = client.post("/latest/osm-users/ids/", json={"userNames":[],"fromTimestamp":"2018-07-11T00:00:00Z","toTimestamp":"2018-07-12T00:00:00Z"})
    assert response.status_code == 200
    assert len(response.json()) == 0

def test_osm_users_ids_missing_param():
    response = client.post("/latest/osm-users/ids/", json={"fromTimestamp":"2018-07-11T00:00:00Z","toTimestamp":"2018-07-12T00:00:00Z"})
    assert_missing_field(response, "userNames")
    response = client.post("/latest/osm-users/ids/", json={"userNames":usernames,"toTimestamp":"2018-07-12T00:00:00Z"})
    assert_missing_field(response, "fromTimestamp")
    response = client.post("/latest/osm-users/ids/", json={"userNames":usernames,"fromTimestamp":"2018-07-11T00:00:00Z"})
    assert_missing_field(response, "toTimestamp")

def test_osm_users_ids_bad_timestamp_order():
    response = client.post("/latest/osm-users/ids/", json={"userNames":usernames,"fromTimestamp":"2018-07-11T00:00:00Z","toTimestamp":"2018-07-10T00:00:00Z"})
    assert response.status_code == 422

def test_osm_users_ids_too_short_username():
    response = client.post("/latest/osm-users/ids/", json={"userNames":['a'],"fromTimestamp":"2018-07-11T00:00:00Z","toTimestamp":"2018-07-10T00:00:00Z"})
    assert response.status_code == 422

################################################################

# TODO Replace res[0] by res if osm-users/statistics/ doesn't return anymore a list

def assert_osm_users_statistics_OK(res: UserStatistics):
    assert type(res["addedBuildings"]) == int
    assert res["addedBuildings"] >= 0
    assert type(res["modifiedBuildings"]) == int
    assert res["modifiedBuildings"] >= 0
    assert type(res["addedHighway"]) == int
    assert res["addedHighway"] >= 0
    assert type(res["modifiedHighway"]) == int
    assert res["modifiedHighway"] >= 0
    assert type(res["addedHighwayMeters"]) == float
    assert res["addedHighwayMeters"] >= 0
    assert type(res["modifiedHighwayMeters"]) == float
    assert res["modifiedHighwayMeters"] >= 0

def test_osm_users_statistics_OK():
    response = client.post("/latest/osm-users/statistics/", json={"userId":8523985,"fromTimestamp":"2018-07-11T00:00:00Z","toTimestamp":"2018-07-12T00:00:00Z","projectIds":[],"hashtags":[]})
    assert response.status_code == 200
    res = response.json()
    assert_osm_users_statistics_OK(res[0])
    assert res[0]["addedHighwayMeters"] > 0

def test_osm_users_statistics_hashtag_OK():
    response = client.post("/latest/osm-users/statistics/", json={"userId":7665306,"fromTimestamp":"2018-07-11T00:00:00Z","toTimestamp":"2018-07-12T00:00:00Z","projectIds":[],"hashtags":["hotosm-project-4853"]})
    assert response.status_code == 200
    res = response.json()
    assert_osm_users_statistics_OK(res[0])
    assert res[0]["modifiedHighway"] == 1

def test_osm_users_statistics_hashtag_empty():
    response = client.post("/latest/osm-users/statistics/", json={"userId":8523985,"fromTimestamp":"2018-07-11T00:00:00Z","toTimestamp":"2018-07-12T00:00:00Z","projectIds":[],"hashtags":["hotosm-project-4853"]})
    assert response.status_code == 200
    res = response.json()
    assert_osm_users_statistics_OK(res[0])
    assert res[0]["addedHighwayMeters"] == 0

def test_osm_users_statistics_project_OK():
    response = client.post("/latest/osm-users/statistics/", json={"userId":7665306,"fromTimestamp":"2018-07-11T00:00:00Z","toTimestamp":"2018-07-12T00:00:00Z","projectIds":[4850],"hashtags":[]})
    assert response.status_code == 200
    res = response.json()
    assert_osm_users_statistics_OK(res[0])
    assert res[0]["modifiedHighway"] == 1

def test_osm_users_statistics_project_empty():
    response = client.post("/latest/osm-users/statistics/", json={"userId":7665306,"fromTimestamp":"2018-07-11T00:00:00Z","toTimestamp":"2018-07-12T00:00:00Z","projectIds":[4850],"hashtags":[]})
    assert response.status_code == 200
    res = response.json()
    assert_osm_users_statistics_OK(res[0])
    assert res[0]["modifiedHighway"] == 0

def test_osm_users_statistics_missing_param():
    response = client.post("/latest/osm-users/statistics/", json={"fromTimestamp":"2018-07-11T00:00:00Z","toTimestamp":"2018-07-12T00:00:00Z","projectIds":[],"hashtags":[]})
    assert_missing_field(response, "userId")
    response = client.post("/latest/osm-users/statistics/", json={"userId":8523985,"toTimestamp":"2018-07-12T00:00:00Z","projectIds":[],"hashtags":[]})
    assert_missing_field(response, "fromTimestamp")
    response = client.post("/latest/osm-users/statistics/", json={"userId":8523985,"fromTimestamp":"2018-07-11T00:00:00Z","projectIds":[],"hashtags":[]})
    assert_missing_field(response, "toTimestamp")
    response = client.post("/latest/osm-users/statistics/", json={"userId":8523985,"fromTimestamp":"2018-07-11T00:00:00Z","toTimestamp":"2018-07-12T00:00:00Z","hashtags":[]})
    assert_missing_field(response, "projectIds")
    response = client.post("/latest/osm-users/statistics/", json={"userId":8523985,"fromTimestamp":"2018-07-11T00:00:00Z","toTimestamp":"2018-07-12T00:00:00Z","projectIds":[]})
    assert_missing_field(response, "hashtags")

def test_osm_users_statisticsbad_timestamp_order():
    response = client.post("/latest/osm-users/statistics/", json={"fromTimestamp":"2018-07-11T00:00:00Z","toTimestamp":"2018-07-10T00:00:00Z","projectIds":[],"hashtags":[]})
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Timestamp difference should be in order"

def test_osm_users_statisticsbad_timestamp_diff_too_big():
    response = client.post("/latest/osm-users/statistics/", json={"fromTimestamp":"2018-07-11T00:00:00Z","toTimestamp":"2018-09-10T00:00:00Z","projectIds":[],"hashtags":[]})
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Statistics is available for a maximum period of 1 month."
