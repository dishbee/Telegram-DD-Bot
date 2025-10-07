from utils import clean_product_name

# Test the specific failing case
input_name = 'Veganer-Monats-Bio-Burger „BBQ Oyster" - Pommes'
result = clean_product_name(input_name)

print(f"Input:    '{input_name}'")
print(f"Output:   '{result}'")
print(f"Expected: 'BBQ Oyster - Pommes'")
print(f"Match:    {result == 'BBQ Oyster - Pommes'}")
