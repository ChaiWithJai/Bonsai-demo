import unittest
from mayor_bond_exercises import exercise, grade, ERAS
from workspace_bond_math import price_bond

class MayorExerciseTests(unittest.TestCase):
    def test_all_eras_are_explicit_scenarios(self):
        for era in ERAS:
            task=exercise(era)
            self.assertIn('NOT historical', ' '.join(task['assumptions']))
            correct=price_bond(**task['inputs'])[task['metric']]
            unit={'price':'USD','modified_duration_years':'years','dv01_approx':'USD/bp','convexity_years_squared':'years^2'}[task['metric']]
            self.assertTrue(grade(era,correct,unit)['passed'])
            self.assertFalse(grade(era,correct+1,unit)['passed'])
            self.assertEqual(grade(era,correct,'percent')['status'],'needs_unit_correction')

    def test_convexity_matches_finite_difference(self):
        args=dict(face=1000,coupon_rate=.05,annual_yield=.05,periods=20,frequency=2)
        result=price_bond(**args); h=.00001
        up=price_bond(**{**args,'annual_yield':.05+h})['price']
        down=price_bond(**{**args,'annual_yield':.05-h})['price']
        self.assertAlmostEqual(result['convexity_years_squared'],(up+down-2*result['price'])/(h*h*result['price']),places=3)

    def test_nonfinite_answer_rejected(self):
        for value in [True,float('nan'),float('inf')]:
            with self.assertRaises(ValueError): grade('giuliani',value,'USD')
