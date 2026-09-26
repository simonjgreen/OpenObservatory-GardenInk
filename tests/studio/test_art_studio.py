import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error
import zipfile

PROJECT=Path(__file__).resolve().parents[2]
ROOT=PROJECT/'display'
spec=importlib.util.spec_from_file_location('studio',PROJECT/'art_studio/studio.py')
studio=importlib.util.module_from_spec(spec);spec.loader.exec_module(studio)
spec2=importlib.util.spec_from_file_location('apply_art',PROJECT/'art_studio/apply_art.py')
installer=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(installer)
from PIL import Image


def fake_png():
    # Test fixture only, not new artwork: use an enlarged copy of the reference.
    with Image.open(studio.REFERENCE) as source:
        im=Image.new('RGB',(1536,1024),'white')
        source=source.resize((780,632)).convert('RGB')
        im.paste(source,(370,170))
        output=io.BytesIO();im.save(output,format='PNG');return output.getvalue()


def args(*parts):
    return studio.parser().parse_args(list(parts))


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.out=Path(self.temp.name)/'output'
        self.addCleanup(self.temp.cleanup)
    def test_catalogue_has_53_and_52_targets(self):
        cat=studio.catalogue();self.assertEqual(len(cat),53)
        self.assertEqual(sum(not x['keep_reference'] for x in cat),52)
    def test_all_six_missing_from_log_included(self):
        expected={'Certhia familiaris','Coccothraustes coccothraustes','Phoenicurus ochruros',
                  'Pyrrhocorax pyrrhocorax','Rallus aquaticus','Regulus ignicapilla'}
        self.assertEqual({x['scientific_name'] for x in studio.select(studio.catalogue(),'missing')},expected)
    def test_jackdaw_alias(self):
        item=studio.select(studio.catalogue(),names=['Coloeus monedula'])[0]
        self.assertEqual(item['slug'],'corvus_monedula')
    def test_proof_is_four_visible_small_birds(self):
        self.assertEqual({x['display_name'] for x in studio.select(studio.catalogue(),'proof')},
                         {'Jackdaw','Rook','Dunnock','Spotted Flycatcher'})
    def test_ambiguous_or_unknown_species_refused(self):
        with self.assertRaises(ValueError):studio.select(studio.catalogue(),names=['Crow-like thing'])
    def test_single_species_selections_deduplicated(self):
        self.assertEqual(len(studio.select(studio.catalogue(),names=['rook','Corvus frugilegus'])),1)
    def test_reference_seed_is_byte_identical_and_approved(self):
        state=studio.load_state(self.out);studio.seed_reference(self.out,state)
        self.assertEqual((self.out/'prepared/erithacus_rubecula.png').read_bytes(),studio.REFERENCE.read_bytes())
        self.assertEqual(state['birds'][studio.ROBIN]['status'],'approved')
    def test_prompt_uses_actual_reference_style_and_target(self):
        item=studio.select(studio.catalogue(),names=['rook'])[0]
        prompt=studio.prompt_for(item)
        self.assertIn('Corvus frugilegus',prompt);self.assertIn('STYLE REFERENCE',prompt)
        self.assertIn('No flat vector',prompt)
    def test_api_request_uses_one_image_and_no_input_fidelity(self):
        item=studio.catalogue()[1];fields=studio.request_fields(item,args('generate'))
        self.assertEqual(fields['model'],'gpt-image-2-2026-04-21')
        self.assertNotIn('input_fidelity',fields);self.assertEqual(fields['n'],'1')
        payload,ctype=studio.multipart(fields,studio.REFERENCE.read_bytes())
        self.assertEqual(payload.count(b'name="image[]"'),1)
        self.assertIn(studio.REFERENCE.read_bytes(),payload)
        self.assertTrue(ctype.startswith('multipart/form-data; boundary='))
    def test_prompt_change_changes_fingerprint(self):
        item=studio.catalogue()[1]
        a=studio.fingerprint(item,args('generate'))
        b=studio.fingerprint(item,args('generate','--quality','medium'))
        self.assertNotEqual(a,b)
    def test_plan_never_calls_api_or_creates_output(self):
        with mock.patch.object(studio,'api_edit',side_effect=AssertionError('API used')):
            with contextlib.redirect_stdout(io.StringIO()):studio.generate(args('generate','--set','all','--plan'),self.out)
        self.assertFalse(self.out.exists())
    def test_blank_generation_rejected(self):
        b=io.BytesIO();Image.new('RGB',(300,300),'white').save(b,format='PNG')
        with self.assertRaises(ValueError):studio.normalise(b.getvalue())
    def test_normalisation_safe_dimensions(self):
        raw, warnings=studio.normalise(fake_png())
        with Image.open(io.BytesIO(raw)) as im:self.assertEqual(im.size,(960,800))
        self.assertEqual(warnings,[])
    def test_nonwhite_edge_warns(self):
        b=io.BytesIO();Image.new('RGB',(300,300),(180,180,180)).save(b,format='PNG')
        raw, warnings=studio.normalise(b.getvalue());self.assertTrue(warnings)
    def test_exact_palette_in_native_thumbnail(self):
        im=studio.panel_preview(studio.REFERENCE,(102,100))
        self.assertEqual(im.size,(102,100))
        self.assertTrue(set(im.getdata()) <= {(0,0,0),(255,255,255),(255,0,0),(255,255,0),(0,0,255),(0,255,0)})
    def do_generate(self,*parts):
        with mock.patch.dict(os.environ,{'OPENAI_API_KEY':'test-key-not-valid'}),\
             contextlib.redirect_stdout(io.StringIO()):
            studio.generate(args('generate','--yes','--delay','0',*parts),self.out)
    def test_generate_resumes_without_repeat_paid_calls(self):
        with mock.patch.object(studio,'api_edit',return_value=(fake_png(),{'request_id':'fixture'})) as api:
            self.do_generate('--set','proof');self.assertEqual(api.call_count,4)
            self.do_generate('--set','proof');self.assertEqual(api.call_count,4)
        state=studio.load_state(self.out)
        self.assertEqual(len(state['birds']),5)
        self.assertTrue((self.out/'review.html').exists())
    def test_max_calls_is_a_hard_cap(self):
        with mock.patch.object(studio,'api_edit',return_value=(fake_png(),{})) as api:
            self.do_generate('--set','all','--max-calls','2');self.assertEqual(api.call_count,2)
    def test_original_robin_never_generates(self):
        with mock.patch.object(studio,'api_edit',side_effect=AssertionError('API used')):
            self.do_generate('--species','robin')
    def test_uncertain_posts_are_not_silently_retried(self):
        with mock.patch.object(studio,'api_edit',side_effect=studio.ApiFailure('timeout')) as api:
            with self.assertRaises(RuntimeError):self.do_generate('--species','rook')
            with self.assertRaises(RuntimeError):self.do_generate('--species','rook')
            self.assertEqual(api.call_count,1)
    def test_known_rejection_not_auto_retried_in_same_run(self):
        with mock.patch.object(studio,'api_edit',side_effect=studio.ApiFailure('401',False)) as api:
            with self.assertRaises(RuntimeError):self.do_generate('--set','proof')
            self.assertEqual(api.call_count,1)
    def test_changed_quality_requires_explicit_regeneration(self):
        with mock.patch.object(studio,'api_edit',return_value=(fake_png(),{})):
            self.do_generate('--species','rook')
            with self.assertRaises(RuntimeError):self.do_generate('--species','rook','--quality','medium')
    def test_regeneration_requires_explicit_species(self):
        with self.assertRaises(ValueError):self.do_generate('--set','all','--regenerate')
    def test_corrupt_prepared_file_invalidates_approval(self):
        state=studio.load_state(self.out);studio.seed_reference(self.out,state)
        (self.out/'prepared/erithacus_rubecula.png').write_bytes(b'bad')
        self.assertFalse(studio.valid_prepared(self.out,state['birds'][studio.ROBIN]))
    def test_missing_images_cannot_be_approved(self):
        with self.assertRaises(ValueError):studio.approve(args('approve','--set','proof','--yes'),self.out)
    def test_full_export_requires_all_53_approved(self):
        with self.assertRaises(ValueError):studio.export_pack(args('export','--zip',str(self.out/'x.zip')),self.out)
    def test_partial_export_apply_preserves_config_state_and_adds_alias(self):
        with mock.patch.object(studio,'api_edit',return_value=(fake_png(),{})):
            self.do_generate('--set','proof')
        with contextlib.redirect_stdout(io.StringIO()):
            studio.approve(args('approve','--set','proof','--yes'),self.out)
            zpath=Path(self.temp.name)/'pack.zip'
            studio.export_pack(args('export','--allow-partial','--zip',str(zpath)),self.out)
        with zipfile.ZipFile(zpath) as z:
            self.assertTrue(all('token' not in x and not x.endswith('.ttf') for x in z.namelist()))
            self.assertIn('garden_ink_art_pack/custom/coloeus_monedula.png',z.namelist())
            info=json.loads(z.read('garden_ink_art_pack/PACK_INFO.json'))
            self.assertEqual(info['species_count'],5);self.assertFalse(info['complete_catalogue'])
            z.extractall(Path(self.temp.name)/'extracted')
        target=Path(self.temp.name)/'garden_ink'
        (target/'gardenink').mkdir(parents=True);(target/'assets/custom').mkdir(parents=True)
        (target/'dashboard.py').write_text('# fixture')
        (target/'config.json').write_text('KEEP_CONFIG');(target/'token.txt').write_text('KEEP_TOKEN')
        (target/'assets/manifest.json').write_text('{}');(target/'assets/species_catalog.json').write_text('[]')
        (target/'state').mkdir();(target/'state/cooldown').write_text('KEEP_COOLDOWN')
        with contextlib.redirect_stdout(io.StringIO()):installer.install(Path(self.temp.name)/'extracted/garden_ink_art_pack',target)
        self.assertEqual((target/'config.json').read_text(),'KEEP_CONFIG')
        self.assertEqual((target/'token.txt').read_text(),'KEEP_TOKEN')
        self.assertEqual((target/'state/cooldown').read_text(),'KEEP_COOLDOWN')
        self.assertTrue((target/'assets/custom/corvus_monedula.png').exists())
        self.assertTrue((target/'assets/custom/coloeus_monedula.png').exists())
    def test_redirects_refused(self):
        self.assertIsNone(studio.NoRedirect().redirect_request(None,None,302,'',{},'https://example.org'))
    def test_atomic_json_no_leftover_temporary_files(self):
        studio.write_json(self.out/'a.json',{'x':1})
        self.assertEqual(json.loads((self.out/'a.json').read_text()),{'x':1})
        self.assertEqual([x.name for x in self.out.iterdir()],['a.json'])


class ServiceTests(unittest.TestCase):
    def test_fix_script_does_not_ship_wrong_working_directory_quote(self):
        text=(ROOT/'service.sh').read_text()
        self.assertIn('WorkingDirectory=$ROOT\n',text)
        self.assertNotIn('WorkingDirectory="$ROOT"',text)
        self.assertIn('systemd-analyze verify',text)
        self.assertLess(text.index('    verify_unit\n'),text.index('    "${SUDO[@]}" install -m 0644'))
    def test_shell_syntax(self):
        for p in (ROOT/'service.sh',ROOT/'autoart-service.sh',PROJECT/'art_studio/art.sh'):
            r=subprocess.run(['bash','-n',str(p)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)


if __name__=='__main__':unittest.main()
