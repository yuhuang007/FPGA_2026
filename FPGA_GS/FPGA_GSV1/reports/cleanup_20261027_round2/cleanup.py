"""Explicit, reversible historical-intermediate cleanup. Never prunes source trees."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import stat
import time
import zipfile

ROOT = Path(r'E:\zhoumian\FPGA\FPGA_GS\FPGA_GSV1').resolve()
OUT = ROOT / 'reports/cleanup_20261027_round2'
ARCHIVE = ROOT.parent / '_archive/cleanup_20261027_round2/historical_generated_and_logs.zip'
STAGES = {'compile', 'device_map', 'place_route', 'report_timing', 'synthesize', 'generate_bitstream'}
OLD_WORK = ['CAM1_sensor_compat', 'CAM1_rotate20', 'M3_05A_3_4A', 'M3_06_3_5',
            'M3_06_E1_integrated_3_5_4', 'M3_06_fix_3_5_1', 'M3_06_fix_3_5_2',
            'M3_06_fix_3_5_3', 'M3_06_front15_txdet1', 'M3_06_front15_txobs1', 'M3_06_front15_txp2']
PARTIAL = ROOT / 'orangepi/pc_traffic_20261024/data/public_datasets/charlotte_eval_pilot_r1/CTLD-day_img.7z.partial'

def safe(p):
    absolute = p.absolute()
    resolved = p.resolve()
    if absolute != resolved or ROOT not in resolved.parents:
        raise RuntimeError(f'Unsafe path: {p}')
    for ancestor in [p, *p.parents]:
        if ancestor == ROOT.parent:
            break
        if ancestor.exists() and ancestor.stat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise RuntimeError(f'Reparse point: {ancestor}')
    return p

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(4*1024*1024), b''):
            h.update(b)
    return h.hexdigest()

def save(name, data):
    (OUT/name).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

def entry(p):
    safe(p)
    s = p.stat()
    return dict(path=p.relative_to(ROOT).as_posix(), bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, sha256=sha(p))

def protected():
    paths = set()
    for name in ['release', 'rtl', 'constraints', 'vendor', 'config', 'docs',
                 'work/SOURCE_MAP_3_6_1', 'work/CAM_quality_3_6_0', 'work/CAM0_motion',
                 'work/NET2_OFFICIAL_BASELINE_E1', 'orangepi/m407', 'orangepi/oneclick',
                 'orangepi/m406', 'orangepi/m406r2', 'tools/front_video_oneclick']:
        paths.update(p for p in (ROOT/name).rglob('*') if p.is_file())
    # Preserve every actual source/constraint/script/bitstream, including historical snapshots.
    extensions = {'.v', '.sv', '.vh', '.vhd', '.vhdl', '.pds', '.fdc', '.sdc', '.tcl',
                  '.py', '.ps1', '.cmd', '.sh', '.sbit', '.rknn', '.pt', '.onnx', '.hex', '.mif', '.mem'}
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if not d.startswith('.venv') and d not in {'site-packages', '__pycache__', '.git'}]
        for name in files:
            p = Path(base)/name
            if p.suffix.lower() in extensions:
                paths.add(p)
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}

def candidates():
    files = set()
    roots = [p for p in (ROOT/'build').iterdir() if p.is_dir() and re.fullmatch(r'(?:M1_\d+|M2_\d+|M3_0\d)_.*', p.name)]
    roots += [ROOT/'work'/n for n in OLD_WORK]
    for top in roots:
        for p in top.rglob('*'):
            if (p.is_file() and p.suffix.lower() in {'.db', '.adf', '.vm', '.netlist'}
                    and any(s in STAGES for s in p.relative_to(top).parts[:-1])):
                files.add(safe(p))
    files.update(safe(p) for p in (ROOT/'reports/NET2_front15_quality_20261023').rglob('*.console.log') if p.is_file())
    # Require all selected historical artifacts to have been inactive for at least 24 hours.
    return sorted(p for p in files if time.time()-p.stat().st_mtime > 86400)

def matches(p, e):
    s=p.stat()
    return s.st_size==e['bytes'] and s.st_mtime_ns==e['mtime_ns'] and sha(p)==e['sha256']

def cleanup():
    if (OUT/'manifest.json').exists() or ARCHIVE.exists():
        raise RuntimeError('Existing cleanup preserved. Inspect results; do not rerun.')
    files=candidates()
    before=protected()
    save('protected_before.json', before)
    entries=[entry(p) for p in files]
    partial=entry(PARTIAL) if PARTIAL.exists() else None
    save('plan.json', dict(archive=str(ARCHIVE), files=entries, incomplete_download=partial))
    print(json.dumps(dict(stage='plan', files=len(entries), archive_input_bytes=sum(e['bytes'] for e in entries),
                          incomplete_bytes=partial['bytes'] if partial else 0)), flush=True)
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=3, allowZip64=True) as z:
        for i,e in enumerate(entries):
            p=safe(ROOT/e['path'])
            if not matches(p,e): raise RuntimeError(f'Changed before archive: {p}')
            z.write(p,e['path'])
            if (i+1)%150==0: print(f'Archived {i+1}/{len(entries)}',flush=True)
        z.writestr('CLEANUP_MANIFEST.json',json.dumps(entries,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(ARCHIVE) as z:
        for e in entries:
            h=hashlib.sha256()
            with z.open(e['path']) as stream:
                for b in iter(lambda:stream.read(4*1024*1024),b''): h.update(b)
            if h.hexdigest()!=e['sha256']:raise RuntimeError(f'Archive verification failed: {e["path"]}')
    manifest=dict(archive=str(ARCHIVE), archive_sha256=sha(ARCHIVE), archive_bytes=ARCHIVE.stat().st_size,
                  files=entries, incomplete_download=partial, all_archive_members_verified=True)
    save('manifest.json',manifest)
    print('Archive verified. Removing only exact, unchanged manifest files.',flush=True)
    deleted=[]
    for e in entries:
        p=safe(ROOT/e['path'])
        if not matches(p,e):raise RuntimeError(f'Changed before deletion: {p}')
        p.unlink()
        deleted.append(e['path'])
    if partial:
        p=safe(PARTIAL)
        if not matches(p,partial):raise RuntimeError('Incomplete download changed; preserved.')
        p.unlink()
    save('removal_result.json',dict(deleted=deleted,incomplete_download_deleted=bool(partial)))
    # Attach a recovery pointer without altering any source or archived evidence reports.
    for top in ['build', 'reports/NET2_front15_quality_20261023', *['work/'+n for n in OLD_WORK]]:
        prefix=top+'/'
        selected=[e['path'] for e in entries if e['path'].startswith(prefix)]
        if selected:
            (ROOT/top/'ARCHIVED_GENERATED_20261027.json').write_text(json.dumps(dict(
                manifest=str(OUT/'manifest.json'),archive=str(ARCHIVE),paths=selected,
                recovery_command=f'python "{OUT / "cleanup.py"}" --restore'),ensure_ascii=False,indent=2),encoding='utf-8')
    changed=[name for name,h in before.items() if not (ROOT/name).is_file() or sha(ROOT/name)!=h]
    removed_bytes=sum(e['bytes'] for e in entries)+(partial['bytes'] if partial else 0)
    result=dict(passed=not changed,protected_files=len(before),protected_changed=changed,
                removed_files=len(deleted)+(1 if partial else 0),removed_bytes=removed_bytes,
                archive_bytes=manifest['archive_bytes'],net_reclaimed_bytes=removed_bytes-manifest['archive_bytes'],
                archive=str(ARCHIVE),archive_sha256=manifest['archive_sha256'])
    save('verification_result.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    if changed: raise RuntimeError('Protected file comparison failed; inspect report.')

def restore(apply=False):
    m=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    archive=Path(m['archive'])
    if sha(archive)!=m['archive_sha256']:raise RuntimeError('Archive SHA mismatch')
    missing=[e for e in m['files'] if not (ROOT/e['path']).exists()]
    print(f'Missing archived files: {len(missing)}. Apply: {apply}. Incomplete download is intentionally not backed up.')
    if not apply:return
    with zipfile.ZipFile(archive) as z:
        for e in missing:
            p=safe(ROOT/e['path']);p.parent.mkdir(parents=True,exist_ok=True)
            data=z.read(e['path'])
            if hashlib.sha256(data).hexdigest()!=e['sha256']:raise RuntimeError('Member SHA mismatch')
            with p.open('xb') as f:f.write(data)
            os.utime(p,ns=(e['mtime_ns'],e['mtime_ns']))
    print('Restored without overwriting any existing files.')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--restore',action='store_true')
    args=parser.parse_args()
    if args.restore:restore(args.apply)
    elif args.apply:cleanup()
    else:
        files=candidates()
        print(json.dumps(dict(files=len(files),bytes=sum(p.stat().st_size for p in files),
                              partial_bytes=PARTIAL.stat().st_size if PARTIAL.exists() else 0),indent=2))
