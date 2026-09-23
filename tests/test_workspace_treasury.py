import unittest
from workspace_treasury import parse_yields


def feed(entries):
    return ('''<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
      xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">'''+entries+'</feed>').encode()


def entry(date, rate):
    return ('<entry><content><m:properties><d:NEW_DATE>'+date+
            '</d:NEW_DATE><d:BC_10YEAR>'+rate+'</d:BC_10YEAR>'
            '<d:BC_1MONTH m:null="true"/></m:properties></content></entry>')


class TreasuryTest(unittest.TestCase):
    def test_dates_units_missing_and_order(self):
        rows = parse_yields(feed(entry('2026-09-22T00:00:00', '4.25')+
                                entry('2026-09-21T00:00:00', '0')))
        self.assertEqual(rows[-1]['observation_date'], '2026-09-22')
        self.assertEqual(rows[-1]['yields_percent']['BC_10YEAR'], 4.25)
        self.assertIsNone(rows[-1]['yields_percent']['BC_1MONTH'])
        self.assertEqual(rows[0]['yields_percent']['BC_10YEAR'], 0)

    def test_empty_nonfinite_and_entities_rejected(self):
        for raw in [feed(''), feed(entry('2026-09-22', 'NaN')),
                    b'<!DOCTYPE feed [<!ENTITY x "test">]><feed/>']:
            with self.assertRaises(ValueError):
                parse_yields(raw)
