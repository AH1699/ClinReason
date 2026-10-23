import unittest
from benchmark.local_time_excerpt import time_cells


class LocalTimeExcerptTests(unittest.TestCase):
    def source(self,method='inline',bounds=None):
        return {'fields':{'collection':[{'value':'2024-01-02','method':method,
                    'bounds':bounds or [.1,.2,.3,.23]}],'received':[],'reported':[],
                    'patient_name':[{'value':'do not render'}]}}

    def test_inline_time_only(self):
        self.assertEqual(len(time_cells(self.source())),1)
        self.assertEqual(time_cells(self.source('same_visual_row')),[])
        self.assertNotIn('patient_name',str(time_cells(self.source())))

    def test_overbroad_or_invalid_bounds_rejected(self):
        for bounds in ([0,0,1,1],[-.1,.2,.3,.23],[.3,.2,.1,.23],[.1,.2,.3,.5]):
            with self.assertRaisesRegex(ValueError,'Unsafe'):time_cells(self.source(bounds=bounds))


if __name__=='__main__':unittest.main()
