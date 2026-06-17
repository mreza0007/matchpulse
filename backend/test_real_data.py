from real_data_service import get_real_fixtures

data = get_real_fixtures()

print("TYPE:", type(data))
print("LENGTH:", len(data) if isinstance(data, list) else "not list")

first = data[0] if isinstance(data, list) and len(data) > 0 else data

print("FIRST ITEM:")
print(first)

print("KEYS:")
print(first.keys() if isinstance(first, dict) else "not dict")