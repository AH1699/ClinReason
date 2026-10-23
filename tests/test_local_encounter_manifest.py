import hashlib
import tempfile
import unittest
from pathlib import Path
from benchmark.local_encounter_manifest import build_manifest, temporal_index


class OwnerEncounterTests(unittest.TestCase):
    def record(self,path):
        return {'source_path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'pages':[{'page':1,'text':'报告时间:2024-01-03 11:05\n采样时间:2024-01-02 10:00'}]}

    def test_explicit_owner_scope_not_clinical_or_privacy_clearance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'synthetic.pdf';path.write_bytes(b'synthetic')
            record=self.record(path)
            manifest=build_manifest([record],'all files belong to one encounter','2026-10-23',root)
            self.assertEqual(manifest['file_count'],1)
            self.assertFalse(manifest['source_identifier_linkage_verified'])
            self.assertFalse(manifest['external_model_use_allowed'])
            index=temporal_index([record],manifest)
            self.assertEqual(index['relative_events'],[])
            self.assertEqual(len(index['pages'][0]['roles']['collection']['candidates']),1)

    def test_missing_confirmation_changed_duplicate_or_outside_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'synthetic.pdf';path.write_bytes(b'synthetic');r=self.record(path)
            with self.assertRaisesRegex(ValueError,'explicit'):build_manifest([r],'probably','2026-10-23',root)
            with self.assertRaisesRegex(ValueError,'repeated'):build_manifest([r,r],'all files belong to one encounter','2026-10-23',root)
            with self.assertRaisesRegex(ValueError,'outside'):build_manifest([r],'all files belong to one encounter','2026-10-23',root/'other')
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Changed'):build_manifest([r],'all files belong to one encounter','2026-10-23',root)

    def test_membership_and_page_count_not_silently_extended(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'synthetic.pdf';path.write_bytes(b'synthetic');r=self.record(path)
            m=build_manifest([r],'all files belong to one encounter','2026-10-23',root)
            with self.assertRaisesRegex(ValueError,'membership'):temporal_index([],m)
            r['pages'].append({'page':2,'text':''})
            with self.assertRaisesRegex(ValueError,'page count'):temporal_index([r],m)


if __name__=='__main__':unittest.main()
