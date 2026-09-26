import contextlib, fcntl, hashlib, importlib.util, io, json, os, tempfile, unittest, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('local_importer',ROOT/'tools/import_workstation_art.py')
imp=importlib.util.module_from_spec(spec);spec.loader.exec_module(imp)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def tree(p):return {str(q.relative_to(p)):q.read_bytes() for q in p.rglob('*') if q.is_file()}
class ProjectSource(unittest.TestCase):
    def test_reference_unchanged(self):
        expected=sha(ROOT/'display/assets/birds/erithacus_rubecula.png')
        self.assertEqual(expected,sha(ROOT/'art_studio/reference/robin.png'))
        self.assertEqual(expected,sha(ROOT/'display/autoart_reference/robin.png'))
    def test_species_jobs_53_bundled_47(self):
        self.assertEqual(53,len(json.loads((ROOT/'art_studio/species.json').read_text())))
        self.assertEqual(47,len(list((ROOT/'display/assets/birds').glob('*.png'))))

class ImportPaidArt(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.target=self.root/'target'
        for p in [self.source,self.target]:
            (p/'reference').mkdir(parents=True)
            (p/'reference/robin.png').write_bytes(b'reference fixture')
            (p/'species.json').write_text('[{"scientific_name":"Branta canadensis","note":"TWO legs"}]')
            (p/'STYLE_BRIEF.txt').write_text('fixture unchanged reference')
        (self.target/'studio.py').write_text('# fake code must not be replaced')
        (self.source/'studio.py').write_text('# old code must not be imported')
        (self.source/'output/raw').mkdir(parents=True)
        (self.source/'output/state.json').write_text('{"fixture":{"status":"uncertain","approved":false}}')
        (self.source/'output/raw/bird.png').write_bytes(b'already-paid raw fixture')
    def call(self,apply=False):
        with contextlib.redirect_stdout(io.StringIO()):return imp.import_art(self.source,self.target,apply,self.root/'backup')
    def test_default_plan_changes_nothing(self):
        before_s=tree(self.source);before_t=tree(self.target)
        self.assertIsNone(self.call());self.assertEqual(before_s,tree(self.source));self.assertEqual(before_t,tree(self.target))
    def test_copies_ledger_and_raw_and_note_without_source_code(self):
        code=(self.target/'studio.py').read_bytes();self.call(True)
        self.assertEqual((self.source/'output/state.json').read_bytes(),(self.target/'output/state.json').read_bytes())
        self.assertEqual((self.source/'output/raw/bird.png').read_bytes(),(self.target/'output/raw/bird.png').read_bytes())
        self.assertEqual((self.source/'species.json').read_bytes(),(self.target/'species.json').read_bytes())
        self.assertEqual(code,(self.target/'studio.py').read_bytes())
    def test_backups_old_output(self):
        (self.target/'output').mkdir();(self.target/'output/old.txt').write_text('old-approved')
        backup=self.call(True);self.assertEqual('old-approved',(backup/'output/old.txt').read_text())
        self.assertFalse((self.target/'output/old.txt').exists())
    def test_keeps_output_lock_inode(self):
        (self.target/'output').mkdir();lock=self.target/'output/.studio.lock';lock.touch();inode=lock.stat().st_ino
        self.call(True);self.assertEqual(inode,lock.stat().st_ino)
    def test_source_credentials_outside_selection_not_imported(self):
        (self.source/'.secrets').mkdir();(self.source/'.secrets/openai-api-key').write_text('fixture')
        (self.source/'.venv').mkdir();(self.source/'.venv/not-source').write_text('fixture')
        self.call(True);self.assertFalse((self.target/'.secrets').exists());self.assertFalse((self.target/'.venv').exists())
    def test_credentials_inside_output_refused(self):
        (self.source/'output/token.txt').write_text('fixture')
        with self.assertRaises(ValueError):self.call()
    def test_symlink_source_entry_refused(self):
        (self.source/'output/raw/link.png').symlink_to(self.source/'reference/robin.png')
        with self.assertRaises(ValueError):self.call(True)
    def test_symlink_destination_refused(self):
        (self.root/'outside').mkdir();(self.target/'output').symlink_to(self.root/'outside')
        with self.assertRaises(ValueError):self.call(True)
    def test_same_target_refused(self):
        with self.assertRaises(ValueError):imp.import_art(self.target,self.target)
    def test_nested_target_refused(self):
        with self.assertRaises(ValueError):imp.import_art(self.source,self.source/'nested')
    def test_running_source_lock_refused(self):
        with (self.source/'output/.studio.lock').open('a') as f:
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(RuntimeError):self.call(True)
    def test_running_target_lock_refused(self):
        (self.target/'output').mkdir()
        with (self.target/'output/.studio.lock').open('a') as f:
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(RuntimeError):self.call(True)
    def test_import_receipt_zero_calls(self):
        backup=self.call(True);receipt=json.loads((backup/'IMPORT.json').read_text());self.assertEqual(0,receipt['api_calls'])
    def test_missing_reference_refused(self):
        (self.source/'reference/robin.png').unlink()
        with self.assertRaises(ValueError):self.call()

if __name__=='__main__':unittest.main()
