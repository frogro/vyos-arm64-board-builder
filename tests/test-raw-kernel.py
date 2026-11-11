#!/usr/bin/env python3
import importlib.util
import json
import os
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
s=importlib.util.spec_from_file_location('kernel',Path(__file__).resolve().parents[1]/'tools/ensure-raw-kernel.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Kernel(unittest.TestCase):
    def source(self, root, revision=None):
        (root/'data/live-build-config/archives').mkdir(parents=True)
        (root/'data/defaults.toml').write_text('kernel_version="6.18.50"\nkernel_flavor="vyos"\nvyos_mirror="https://example.test"\nvyos_branch="rolling"\n')
        if revision is not None:
            with (root/'data/defaults.toml').open('a') as out: out.write('kernel_revision='+json.dumps(revision)+'\n')
        (root/'data/live-build-config/archives/vyos-dev.key.chroot').write_text('fixture')
    def test_candidate(self):
        self.assertIsNone(m.candidate(''))
        self.assertIsNone(m.candidate('  Candidate: (none)'))
        self.assertEqual(m.candidate('  Candidate: 6.18.50-1'),'6.18.50-1')
    def test_missing_only_after_successful_index_check(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.source(root)
            with patch.object(m,'run') as run, patch.object(m.subprocess,'check_output',return_value=''):
                self.assertTrue(m.probe(root,root/'packages',root/'result.json'))
                self.assertEqual(run.call_count,1)
                self.assertIn('APT::Update::Error-Mode=any',run.call_args.args)
            with patch.object(m,'run',side_effect=subprocess.CalledProcessError(100,'apt-get')):
                with self.assertRaises(subprocess.CalledProcessError):m.probe(root,root/'packages',root/'result.json')
    def test_repository_companion_can_force_rebuild(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.source(root)
            replies=[' Candidate: 6.18.50-1', ' Candidate: 4.1.15-1',
                     'Package: jool\nDepends: linux-image-6.18.54-vyos\n']
            with patch.object(m,'run') as run,patch.object(m.subprocess,'check_output',side_effect=replies):
                self.assertTrue(m.probe(root,root/'packages',root/'result.json'))
                self.assertEqual(run.call_count,1)
                self.assertEqual(json.loads((root/'result.json').read_text())['mode'],'source-required')

    def test_package_identity(self):
        with patch.object(m.subprocess,'check_output',side_effect=['Package: linux-image-6.18.50-vyos\nArchitecture: arm64\nVersion: 6.18.50-1\n','-rw-r--r-- root/root 1 today ./boot/vmlinuz-6.18.50-vyos\ndrwxr-xr-x root/root 0 today ./lib/modules/6.18.50-vyos/\n']):
            self.assertEqual(m.validate(Path('kernel.deb'),'6.18.50-vyos')['Architecture'],'arm64')
        for name,arch in [('linux-image-6.18.51-vyos','arm64'),('linux-image-6.18.50-vyos','amd64')]:
            with patch.object(m.subprocess,'check_output',return_value=f'Package: {name}\nArchitecture: {arch}\nVersion: 1\n'):
                with self.assertRaises(ValueError):m.validate(Path('kernel.deb'),'6.18.50-vyos')
    def test_companion_abi(self):
        for release in ('6.18.50-vyos', '6.18.54-vyos'):
            info=f'Package: jool\nArchitecture: arm64\nDepends: linux-image-{release}, libc6\n'
            with patch.object(m.subprocess,'check_output',return_value=info):
                if release == '6.18.50-vyos':
                    m.validate_companion(Path('jool.deb'),release,'jool')
                else:
                    with self.assertRaisesRegex(ValueError,'ABI mismatch'):
                        m.validate_companion(Path('jool.deb'),'6.18.50-vyos','jool')

    def test_complete_bundle_and_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.source(root);packages=root/'packages';packages.mkdir()
            (packages/'kernel.deb').write_bytes(b'kernel')
            metadata=root/'kernel.json'
            with patch.object(m.subprocess,'check_output',return_value='abc\n'),patch.object(m,'validate',return_value={}),patch.object(m,'validate_companion'):
                m.record(packages/'kernel.deb','6.18.50-vyos','exact-source-build',root,metadata)
                with self.assertRaisesRegex(ValueError,'Incomplete'):m.verify_artifact(root,packages,metadata)
                for name in m.COMPANIONS:(packages/(name+'_1_arm64.deb')).write_bytes(name.encode())
                m.bundle_record(packages,metadata,'6.18.50-vyos')
                m.verify_artifact(root,packages,metadata)
                (packages/'jool_1_arm64.deb').write_bytes(b'wrong')
                with self.assertRaisesRegex(ValueError,'checksum'):m.verify_artifact(root,packages,metadata)

    def test_checksum_and_source_binding(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.source(root);packages=root/'packages';packages.mkdir()
            (packages/'kernel.deb').write_bytes(b'kernel')
            metadata=root/'kernel.json'
            with patch.object(m.subprocess,'check_output',return_value='abc\n'),patch.object(m,'validate',return_value={}),patch.object(m,'COMPANIONS',()):
                m.record(packages/'kernel.deb','6.18.50-vyos','exact-source-build',root,metadata)
                m.verify_artifact(root,packages,metadata)
                (packages/'kernel.deb').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'checksum'):m.verify_artifact(root,packages,metadata)

    def test_revision_identity(self):
        for revision, expected in [(None, '6.18.50-vyos'), ('1', '6.18.50-1-vyos'),
                                   ('12', '6.18.50-12-vyos'), (2, '6.18.50-2-vyos')]:
            with self.subTest(revision=revision), tempfile.TemporaryDirectory() as d:
                root=Path(d);self.source(root, revision)
                self.assertEqual(m.expected(root)[1], expected)
        for revision in ('', '0', '-1', '../1', '1-vyos', '1.2', True, 1.5):
            with self.subTest(invalid=revision), tempfile.TemporaryDirectory() as d:
                root=Path(d);self.source(root, revision)
                with self.assertRaises(ValueError):m.expected(root)

    def deb(self, directory, name, release, module_release=None, companion=False):
        tree=directory/(name+'.tree');(tree/'DEBIAN').mkdir(parents=True)
        control=f'Package: {name}\nArchitecture: arm64\nVersion: 1\nMaintainer: Test <test@example.invalid>\nDescription: ABI fixture\n'
        if companion:control+=f'Depends: linux-image-{release}\n'
        (tree/'DEBIAN/control').write_text(control)
        if not companion:
            (tree/'boot').mkdir();(tree/'boot'/('vmlinuz-'+release)).write_bytes(b'kernel')
            modules=tree/'usr/lib/modules'/(module_release or release);modules.mkdir(parents=True)
            (modules/'fixture.ko').write_bytes(b'fixture')
        target=directory/(name+'_1_arm64.deb')
        subprocess.run(['dpkg-deb','--build','--root-owner-group',str(tree),str(target)],check=True,stdout=subprocess.DEVNULL)
        return target

    def test_real_package_import_and_verification_old_and_revised(self):
        for revision in (None, '1', '2'):
            with self.subTest(revision=revision), tempfile.TemporaryDirectory() as d:
                root=Path(d);self.source(root,revision);release=m.expected(root)[1]
                subprocess.run(['git','init','-q',str(root)],check=True)
                subprocess.run(['git','-C',str(root),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-q','--allow-empty','-m','fixture'],check=True)
                output=root/'scripts/package-build/linux-kernel';output.mkdir(parents=True)
                self.deb(output,'linux-image-'+release,release)
                for name in m.COMPANIONS:self.deb(output,name,release,companion=True)
                packages=root/'packages';metadata=root/'kernel.json'
                m.import_built(root,packages,metadata)
                m.verify_artifact(root,packages,metadata)
                self.assertEqual(json.loads(metadata.read_text())['kernel_release'],release)
                pref=(root/'data/live-build-config/archives/exact-kernel.pref.chroot').read_text()
                self.assertIn('Package: linux-image-'+release+'\n',pref)
                with (root/'data/defaults.toml').open('a') as out:
                    if revision is None:out.write('kernel_revision="3"\n')
                if revision is not None:
                    path=root/'data/defaults.toml';path.write_text(path.read_text().replace('kernel_revision='+json.dumps(revision),'kernel_revision="3"'))
                with self.assertRaisesRegex(ValueError,'provenance mismatch'):
                    m.verify_artifact(root,packages,metadata)

    def test_real_package_rejects_wrong_module_revision(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            deb=self.deb(root,'linux-image-6.18.62-2-vyos','6.18.62-2-vyos',module_release='6.18.62-1-vyos')
            with self.assertRaisesRegex(ValueError,'module tree ABI mismatch'):
                m.validate(deb,'6.18.62-2-vyos')

    def test_repository_uses_revision_and_rejects_companion_revision(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.source(root,'2')
            replies=[' Candidate: 6.18.50-2', ' Candidate: 4.1.15-1',
                     'Package: jool\nDepends: linux-image-6.18.50-1-vyos\n']
            with patch.object(m,'run') as run,patch.object(m.subprocess,'check_output',side_effect=replies) as query:
                self.assertTrue(m.probe(root,root/'packages',root/'result.json'))
                self.assertIn('linux-image-6.18.50-2-vyos:arm64',query.call_args_list[0].args[0])
                self.assertEqual(run.call_count,1)

    def test_repository_downloads_and_verifies_both_identities(self):
        for revision in (None,'2'):
            with self.subTest(revision=revision),tempfile.TemporaryDirectory() as d:
                root=Path(d);self.source(root,revision);release=m.expected(root)[1]
                subprocess.run(['git','init','-q',str(root)],check=True)
                subprocess.run(['git','-C',str(root),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-q','--allow-empty','-m','fixture'],check=True)
                original=m.subprocess.check_output
                def query(args,**kwargs):
                    if args[0]=='apt-cache':
                        if 'policy' in args:return ' Candidate: 1\n'
                        return f'Package: {args[-1].split(":")[0]}\nDepends: linux-image-{release}\n'
                    return original(args,**kwargs)
                def run(*args,**kwargs):
                    if 'download' in args:
                        name=args[-1].split(':')[0]
                        self.deb(Path(kwargs['cwd']),name,release,companion=name in m.COMPANIONS)
                packages=root/'packages';metadata=root/'kernel.json'
                with patch.object(m,'run',run),patch.object(m.subprocess,'check_output',query):
                    self.assertFalse(m.probe(root,packages,metadata))
                m.verify_artifact(root,packages,metadata)
                self.assertEqual(json.loads(metadata.read_text())['mode'],'signed-repository')

    def test_builder_retention_with_real_argument_parsers(self):
        wrapper=Path(__file__).resolve().parents[1]/'tools/build-raw-kernel.py'
        for option in ('--keep-kernel','--dont-keep-kernel','--unknown-retention'):
            with self.subTest(option=option),tempfile.TemporaryDirectory() as d:
                root=Path(d)
                (root/'build.py').write_text("from argparse import ArgumentParser\nimport json\nfrom pathlib import Path\np=ArgumentParser()\np.add_argument('--packages',nargs='+')\np.add_argument("+repr(option)+",action='store_true')\na=p.parse_args()\nPath('args.json').write_text(json.dumps(vars(a)))\n")
                proc=subprocess.run([sys.executable,str(wrapper)],cwd=root,text=True,capture_output=True)
                if option=='--unknown-retention':
                    self.assertNotEqual(proc.returncode,0);self.assertFalse((root/'args.json').exists())
                else:
                    self.assertEqual(proc.returncode,0,proc.stderr)
                    args=json.loads((root/'args.json').read_text())
                    self.assertEqual(len(args['packages']),6)
                    self.assertEqual(args[option[2:].replace('-','_')],option=='--keep-kernel')

    def test_board_localversion_matches_raw_package(self):
        repo=Path(__file__).resolve().parents[1]
        for revision in (None,'2'):
            with self.subTest(revision=revision),tempfile.TemporaryDirectory() as d:
                root=Path(d);source=root/'cache/vyos-build';self.source(source,revision)
                (root/'tools').symlink_to(repo/'tools',target_is_directory=True)
                for flavor in ('','custom'):
                    env={**os.environ,'ROOT_DIR':str(root),'KERNEL_FLAVOR':flavor}
                    suffix=subprocess.check_output(['bash','-ec','source "$1"; vyos_kernel_localversion','bash',str(repo/'sources/vyos.sh')],env=env,text=True).strip()
                    defaults=m.expected(source)[0]
                    if flavor:defaults['kernel_flavor']=flavor
                    self.assertEqual('6.18.50'+suffix,m.kernel_release(defaults))

if __name__=='__main__':unittest.main()
