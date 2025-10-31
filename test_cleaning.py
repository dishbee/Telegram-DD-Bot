# -*- coding: utf-8 -*-
"""Test script for clean_product_name() updates"""

import sys
sys.path.insert(0, '.')

from utils import clean_product_name

# Test cases from user requirements
test_cases = [
    # Issue 1: Remove dietary labels in parentheses
    ("2 x Grillkäse - (vegetarisch) - Halb P. / Halb S.", "Grillkäse - Halb P. / Halb S."),
    ("Falafel - (vegan) - Halb P. / Halb S.", "Falafel - Halb P. / Halb S."),
    
    # Issue 2: Remove "/ Classic" when followed by "/ Glutenfrei"
    ("Bergkäse - Classic / Glutenfrei", "Bergkäse - Glutenfrei"),
    
    # Issue 3: Burger quote extraction
    ("Veganer-Monats-Bio-Burger „BBQ Oyster" - Pommes", "BBQ Oyster - Pommes"),
    
    # Issue 4: B- prefix with side dish
    ("B-umpkin - Süßkartoffel-Pommes", "umpkin - Süßkartoffel"),
    
    # Issue 5: Süßkartoffel-Pommes suffix
    ("Classic Cheese - Süßkartoffel-Pommes", "Classic Cheese - Süßkartoffel"),
    
    # Issue 6: Price removal (should already work)
    ("Spaghetti - Cacio e Pepe (13,50€)", "Spaghetti - Cacio e Pepe"),
    
    # Issue 7: Exception for Cinnamon roll - Classic
    ("Cinnamon roll - Classic", "Cinnamon roll - Classic"),
    
    # Additional existing tests
    ('[Bio-Burger "Classic"]', 'Classic'),
    ('Special roll - Salted Caramel Apfel', 'Salted Caramel Apfel'),
    ('Prosciutto - Prosciutto Funghi', 'Prosciutto Funghi'),
]

print("=" * 80)
print("PRODUCT NAME CLEANING TESTS")
print("=" * 80)

all_passed = True
for i, (input_name, expected) in enumerate(test_cases, 1):
    # Note: Remove "2 x " prefix if present (that's added by message builders)
    clean_input = input_name.replace("2 x ", "").replace("1 x ", "")
    result = clean_product_name(clean_input)
    
    passed = result == expected
    all_passed = all_passed and passed
    
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status} Test {i}")
    print(f"  Input:    {clean_input}")
    print(f"  Expected: {expected}")
    print(f"  Got:      {result}")

print("\n" + "=" * 80)
if all_passed:
    print("✅ ALL TESTS PASSED")
else:
    print("❌ SOME TESTS FAILED")
print("=" * 80)
