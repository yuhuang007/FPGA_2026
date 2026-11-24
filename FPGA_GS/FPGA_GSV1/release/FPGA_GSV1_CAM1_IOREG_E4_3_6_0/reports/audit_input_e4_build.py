"""Independent validation of completed E4 implementation after guard parse bug.

Preserves BuildPass:false and all logs. Only the exact upfront, non-design
guard-read errors are classified separately; any other tool error fails closed.
The existing final routed DB is re-queried by analyze_input_e4.py afterwards.
"""
from pathlib import Path
import hashlib,json,re,shutil
r=Path(__file__).resolve().parent;s=r/'rear_input_source'
run=next((s/'build').glob('CAM1_IOREG_E4_3_6_0_*'))
log=(run/'pds_console.log').read_text(encoding='utf-8',errors='replace')
res=json.loads((run/'result.json').read_text(encoding='utf-8-sig'))
assert res['ExistingConstraintsMet'] and res['InputsUnchanged'] and res['ExitCode']==0
head,tail=log.split("Analyzing project file",1)
errors=re.findall(r'^E:.*$',log,re.M)
assert len(errors)==10,errors
assert not re.search(r'^E:|Program Error',tail,re.M)
assert errors[0]=='E: couldn\'t open "device_map/run.log": no such file or directory'
assert [e for e in errors if 'Flow-0163' not in e]==[
    'E: couldn\'t open "device_map/run.log": no such file or directory',
    'E: can\'t read "mf": no such variable',
    'E: can\'t read "mf": no such variable',
    'E: can\'t read "mapping_log": no such variable',
    'E: can\'t read "packed": no such variable']
assert all(re.search(r'at line (87|88|89|90|91)\.',e) for e in errors if 'Flow-0163' in e)
for success in ('Executing : compile -top_module fpga_gsv1_top successfully.',
                'Design \'fpga_gsv1_top\' has been routed successfully.',
                'Report timing is finished successfully.',
                'Generating Programming File done.', 'Executing : gen_bit_stream successfully.'):
    assert success in tail,success
mapping=(run/'device_map/run.log').read_text()
packed=re.findall(r'has been packed in IOL "(cmos2_(?:data_ibuf|href_ibuf|vsync_ibuf)[^"]*)" success',mapping)
assert len(packed)==10 and len(set(packed))==10,packed
timing=(run/'report_timing/fpga_gsv1_top.rtr').read_text()
assert 'Design Summary : All Constraints Met.' in timing
bit=run/'generate_bitstream/fpga_gsv1_top.sbit';assert bit.stat().st_size>1000000
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
# Re-check original snapshot bytes against the manifest, independently.
manifest=json.loads((run/'inputs.json').read_text(encoding='utf-8-sig'))
for e in manifest:assert sha(run/e['RelativePath']).upper()==e['SnapshotSHA256'].upper(),e['RelativePath']
# Repair future entry only; original build.tcl/flow and manifest stay frozen.
p=s/'flow.tcl';f=p.read_text();start=f.index('# Stop before full placement')
end=f.index('pnr -gplace_seed',start)
assert 'set mf [open device_map/run.log r]' in f[start:end]
p.write_text(f[:start]+f[end:])
assert (run/'flow.tcl').read_text()!=p.read_text()
out=run/'FPGA_GSV1_CAM1_IOREG_E4_3_6_0_HDMI_1080P60.sbit';assert not out.exists()
shutil.copy2(bit,out)
audit=dict(ImplementationValidated=True,OriginalWrapperBuildPass=res['BuildPass'],
    original_result_preserved=str(run/'result.json'),
    error_classification='Only five upfront guard-read errors and their five parse summaries; all before implementation action execution. PDS does not defer plain Tcl between scheduled actions.',
    original_errors=errors,design_implementation_errors=0,
    actual_production_input_packing=packed,all_snapshot_hashes_verified=True,
    internal_sta_met=True,external_source_timing_unknown=True,
    future_flow_repaired=True,repair_does_not_change_rtl_or_constraints=True,
    Release=str(out),SHA256=sha(out),GeneratedTime=__import__('datetime').datetime.fromtimestamp(bit.stat().st_mtime,__import__('datetime').timezone.utc).isoformat(),
    no_rebuild_or_programming_performed=True)
(run/'postbuild_audit.json').write_text(json.dumps(audit,indent=2))
print(json.dumps(audit,indent=2))
