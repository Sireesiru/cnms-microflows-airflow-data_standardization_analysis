from datafed.CommandLib import API
import json

df_api = API()

df_api.setContext("p/cnms") #Set the project
parent_collection = "c/p_cnms_root" #Set the collection within the project

parameters = {
    "a": 4,
    "b": [1, 2, -4, 7.123],
    "c": "Stirng metadata",
    "d": {"x": 14, "y": -19},  # Can use nested dictionaries
}

# parent_collection The parent collection, whose alias is your username
dc_resp = df_api.dataCreate(
    "Test data record creation",
    metadata=json.dumps(parameters),
    parent_id=parent_collection,
)
print('Data Create Response:')
print(dc_resp)

record_id = dc_resp[0].data[0].id
print(f'Data record id: {record_id}')