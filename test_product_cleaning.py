# Test product name cleaning function
from utils import clean_product_name

# Test cases based on requirements
test_cases = [
    # Rule 1: Burger names
    ('[Bio-Burger "Classic"]', 'Classic'),
    ('[Veganer-Monats-Bio-Burger „BBQ Oyster"]', 'BBQ Oyster'),
    ('[Monats-Bio-Burger „B-umpkin"]', 'B-umpkin'),
    
    # Rule 2: Bio-Pommes
    ('Bio-Pommes', 'Pommes'),
    
    # Rule 3: Chili-Cheese-Fries
    ('Chili-Cheese-Fries (+2.6€)', 'Fries: Chili-Cheese-Style'),
    
    # Rule 4: Sloppy-Fries (remove price)
    ('Sloppy-Fries (+1.7€)', 'Sloppy-Fries'),
    
    # Rule 5: Chili-Cheese-Süßkartoffelpommes
    ('Chili-Cheese-Süßkartoffelpommes', 'Süßkartoffel: Chili-Cheese-Style'),
    
    # Rule 6: Pizza
    ('Sauerteig-Pizza Margherita', 'Margherita'),
    
    # Rule 7: Spätzle dishes
    ('Bergkäse-Spätzle', 'Bergkäse'),
    
    # Rule 8: Curry
    ('Gemüse Curry & Spätzle', 'Curry'),
    
    # Rule 9: Gulasch
    ('Gulasch vom Rind & Spätzle', 'Gulasch'),
    
    # Rule 10: Walnuss Pesto
    ('Walnuss Pesto Spätzle', 'Walnuss Pesto'),
    
    # Rule 11: Selbstgemachte
    ('Selbstgemachte Tagliatelle', 'Tagliatelle'),
    
    # Rule 12: Cinnamon roll
    ('Cinnamon roll - Classic', 'Classic'),
    
    # Rule 13: Special roll
    ('Special roll - Oreo', 'Oreo'),
    
    # Rule 16: Complex spätzle with extras
    ('Bergkäse-Spätzle - + Preiselbeere (1.9€) / Standard', 'Bergkäse + Preiselbeere'),
    
    # Rule 17: Bio-Salat
    ('Bio-Salat', 'Salat'),
]

print("Testing Product Name Cleaning Function")
print("=" * 60)

passed = 0
failed = 0

for input_name, expected_output in test_cases:
    result = clean_product_name(input_name)
    status = "✓" if result == expected_output else "✗"
    
    if result == expected_output:
        passed += 1
        print(f"{status} PASS: '{input_name}' → '{result}'")
    else:
        failed += 1
        print(f"{status} FAIL: '{input_name}'")
        print(f"  Expected: '{expected_output}'")
        print(f"  Got:      '{result}'")

print("=" * 60)
print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")

if failed == 0:
    print("✅ All tests passed!")
else:
    print(f"⚠️ {failed} test(s) failed")
