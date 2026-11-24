"""Validate archived bytes against manifests without touching source files."""
import csv
import hashlib
import io
import json
import sys
import time
import zipfile
from pathlib import Path

root = Path(sys.argv[1])
archives = sorted(root.glob(sys.argv[2] if len(sys.argv) > 2 else '*.zip'))
results = []
checksums = []
for archive in archives:
    failures = []
    count = size = 0
    tick = time.monotonic()
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            failures.append('duplicate_zip_members')
        unsafe = [n for n in names if n.startswith(('/', '\\')) or '..' in Path(n).parts or ':' in n]
        failures.extend('unsafe_path:' + n for n in unsafe)
        manifests = [n for n in names if n.startswith('交付元数据/') and n.endswith('/manifest.tsv')]
        rows = list(csv.DictReader(io.StringIO(z.read(manifests[0]).decode('utf-8')), delimiter='\t'))
        expected = {r['path']:r for r in rows}
        for info in z.infolist():
            h = hashlib.sha256()
            nbytes = 0
            with z.open(info) as src:
                while True:
                    block = src.read(1024*1024)
                    if not block:
                        break
                    h.update(block)
                    nbytes += len(block)
            if info.filename in expected:
                row = expected[info.filename]
                if nbytes != int(row['archived_bytes']) or h.hexdigest() != row['sha256']:
                    failures.append('content_mismatch:' + info.filename)
            count += 1
            size += nbytes
            if time.monotonic()-tick >= 10:
                print(json.dumps({'event':'validation_progress','archive':archive.name,'members':count,'total':len(names),'GiB':round(size/2**30,2)},ensure_ascii=False),flush=True)
                tick = time.monotonic()
        dependency_check = None
        if archive.name.startswith('01_'):
            prefix = 'FPGA_GS/FPGA_GSV1/'
            depname = prefix+'docs/handoff/20261024/FPGA_R0构建依赖闭包.tsv'
            deps = list(csv.DictReader(io.StringIO(z.read(depname).decode('utf-8-sig')),delimiter='\t'))
            depbad = []
            for dep in deps:
                path = prefix+dep['Path'].replace('\\','/')
                row = expected.get(path)
                if row is None:
                    depbad.append('missing:'+path)
                elif dep.get('SHA256_existing') and row['sha256'].lower() != dep['SHA256_existing'].lower():
                    depbad.append('hash_diff:'+path)
            failures.extend(depbad)
            dependency_check = {'required':len(deps),'problems':depbad}
            critical = {
                'release/FPGA_GSV1_CAM0_OV5640_3_5_9_READBACK/FPGA_GSV1_CAM0_OV5640_3_5_9_READBACK_HDMI_1080P60.sbit':'f760692d6a1e7695d4005945d0ba977468d8857c4b36c45dc57bd98e7283acb1',
                'release/FPGA_GSV1_CAM1_OV3660_3_5_8_ROTATE25_CANDIDATE/FPGA_GSV1_CAM1_OV3660_3_5_8_ROTATE25_CANDIDATE_HDMI_1080P60.sbit':'e89ef7785f00ddfb569eb0d3754ca92b1a49a558483609ada051b3bab3c7d36a',
                'release/FPGA_GSV1_M3_06_3_5_5_TXDET1_CANDIDATE/FPGA_GSV1_M3_06_3_5_5_TXDET1_CANDIDATE_HDMI_1080P60.sbit':'540cb7a916be7f5c2d5a392705b06f7075e0e38156bc3ac14a7fd8189e6a9b8e',
            }
            for rel, sha in critical.items():
                if expected.get(prefix+rel,{}).get('sha256') != sha:
                    failures.append('baseline_bitstream_hash:'+rel)
            for historical in ['build/M1_01_1_0_20261020_155534_191/','build/M1_02_1_1_20261020_172931_733/']:
                if not any(n.startswith(prefix+historical) and '/rtl/' in n for n in names):
                    failures.append('historical_rtl_missing:'+historical)
    h = hashlib.sha256()
    with archive.open('rb') as src:
        for block in iter(lambda:src.read(4*1024*1024),b''):
            h.update(block)
    digest = h.hexdigest()
    checksums.append(digest+'  '+archive.name)
    result = {'archive':archive.name,'archive_bytes':archive.stat().st_size,'sha256':digest,'source_files':len(rows),'zip_members':count,'checked_uncompressed_bytes':size,'crc_all_members':'passed','manifest_sha256':'passed' if not failures else 'failed','R0_dependency_check':dependency_check,'failures':failures}
    results.append(result)
    (root/(archive.stem+'_metadata')/'integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'event':'validated',**result},ensure_ascii=False),flush=True)
combined = {}
for report in root.glob('*_metadata/integrity.json'):
    prior = json.loads(report.read_text(encoding='utf-8'))
    combined[prior['archive']] = prior
combined.update({r['archive']:r for r in results})
results = [combined[k] for k in sorted(combined)]
checksums = [r['sha256']+'  '+r['archive'] for r in results]
(root/'SHA256SUMS.txt').write_text('\n'.join(checksums)+'\n',encoding='utf-8')
(root/'完整性验证.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
if any(r['failures'] for r in results):
    sys.exit(1)
print('ALL_ARCHIVES_VERIFIED',flush=True)
