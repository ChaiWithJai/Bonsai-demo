import unittest
from workspace_bond_math import price_bond

class BondMathTest(unittest.TestCase):
    def test_par_and_zero_yield(self):
        result=price_bond(1000,.05,.05,20)
        self.assertAlmostEqual(result['price'],1000,places=9)
        self.assertEqual(result['payments'][-1]['cash_flow'],1025)
        self.assertEqual(sum(row['principal'] for row in result['payments']),1000)
        self.assertAlmostEqual(price_bond(1000,.05,0,20)['price'],1500)
    def test_zero_coupon_and_duration(self):
        result=price_bond(1000,0,.10,4)
        self.assertAlmostEqual(result['price'],822.7024747918819)
        self.assertAlmostEqual(result['macaulay_duration_years'],2)
        center=price_bond(1000,.04,.05,10)
        delta=.000001
        low=price_bond(1000,.04,.05-delta,10)['price'];high=price_bond(1000,.04,.05+delta,10)['price']
        self.assertLess(high,center['price']);self.assertLess(center['price'],low)
        measured=(low-high)/(2*delta)/center['price']
        self.assertAlmostEqual(measured,center['modified_duration_years'],places=7)
    def test_invalid_units_and_inputs_fail(self):
        for args in [(True,.05,.05,4),(1000,float('nan'),.05,4),(1000,.05,-2,4),(1000,.05,.05,2.5),(1000,-.01,.05,4)]:
            with self.assertRaises(ValueError):price_bond(*args)
