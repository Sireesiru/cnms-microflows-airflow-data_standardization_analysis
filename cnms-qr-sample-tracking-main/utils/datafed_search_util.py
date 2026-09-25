from datafed.CommandLib import API
df_api = API()

print('Context:')
print(df_api.getContext())

print()

pl_resp = df_api.projectList()
print('Project List:')
print(pl_resp[0])