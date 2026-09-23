import unittest
from unittest.mock import Mock
from treasury_insights_mcp import call

class TreasuryMcpTests(unittest.TestCase):
    def setUp(self):
        self.service=Mock();self.service.create.return_value={'id':'test'}
        self.service.act.return_value={'status':'completed','result':{'source_url':'https://home.treasury.gov','fetched_at':'2026-09-23','sha256':'abc','observations':[{'observation_date':'2020-03-16','yields_percent':{'BC_10YEAR':.73,'BC_2YEAR':None}}]}}
    def test_no_silent_date_substitution(self):
        value=call(self.service,'get_curve',{'date':'2020-03-15'})
        self.assertEqual(value['observations'],[])
        self.assertEqual(value['status'],'no_observation_on_requested_dates')
    def test_null_is_not_zero(self):
        value=call(self.service,'get_rate_history',{'start':'2020-03-16','end':'2020-03-16','tenor':'BC_2YEAR'})
        self.assertIsNone(value['observations'][0]['yield_percent'])
    def test_unbounded_range_rejected_before_fetch(self):
        with self.assertRaises(ValueError):call(self.service,'get_rate_history',{'start':'1994-01-01','end':'2026-01-01','tenor':'BC_10YEAR'})
        self.service.act.assert_not_called()
