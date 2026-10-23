import unittest
from benchmark.local_temporal_check import date_roles


class TemporalRoleTests(unittest.TestCase):
    def test_roles_not_interchangeable(self):
        r=date_roles('采样时间：2020-01-02 09:10:11\n报告时间：2020-01-03 12:00')
        self.assertEqual(r['collection']['candidates'][0]['local_date_time'],'2020-01-02T09:10:11')
        self.assertEqual(r['reported']['candidates'][0]['precision'],'minute')

    def test_missing_collection_is_not_filled_from_next_line_or_report(self):
        r=date_roles('采样时间：\n2020-01-02 09:10\n接收时间：2020-01-02 10:00\n检验时间：2020-01-02 11:00')
        self.assertEqual(r['collection']['candidates'],[])
        self.assertEqual(len(r['received']['candidates']),1)
        self.assertEqual(len(r['reported']['candidates']),1)

    def test_invalid_dates_and_unrelated_dates_rejected(self):
        r=date_roles('采样日期：2020-02-31\n出生日期：2020-01-01')
        self.assertFalse(any(v['candidates'] for v in r.values()))
        for value in ('2020-01-019', '2020-01-01 100:12',
                      '2020-01-01 12:301', '2020-01-01 12:30:00:01',
                      '2020-01-01T12:30'):
            with self.subTest(value=value):
                self.assertEqual(date_roles('采样时间：'+value)['collection']['candidates'], [])

    def test_multiple_adjacent_roles_remain_separate(self):
        r=date_roles('采样日期：2020年1月2日 报告日期：2020年1月3日')
        self.assertEqual(r['collection']['candidates'][0]['local_date_time'],'2020-01-02')
        self.assertEqual(r['reported']['candidates'][0]['local_date_time'],'2020-01-03')


if __name__=='__main__':
    unittest.main()
