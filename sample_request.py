import requests


url = "http://localhost:1313/predict"

test_input = {
    "cement": 402,
    "blast_furnace_slag": 0,
    "fly_ash": 0,
    "silica_fume": 0,
    "coarse_aggregate": 992,
    "fine_aggregate": 732,
    "water": 205,
    "superplasticizer": 0,
    "age": 28
}

response = requests.post(url, json=test_input)
result = response.json()

pred_concrete_strength = result.get("concrete_strength")
print("Input: ", test_input)
print("Predicted concrete strength: ", pred_concrete_strength)