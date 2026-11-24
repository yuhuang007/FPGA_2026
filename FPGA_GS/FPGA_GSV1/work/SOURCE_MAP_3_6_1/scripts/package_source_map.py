from pathlib import Path
import json,hashlib,shutil,datetime,re
R=Path(__file__).resolve().parents[1];P=R.parents[1];version='SOURCE_MAP_3_6_1';release=P/'release'/('FPGA_GSV1_'+version+'_CANDIDATE')
assert not release.exists(),release
builds=list((R/'build').glob(version+'_*'));assert len(builds)==1,builds
B=builds[0];br=json.loads((B/'result.json').read_text(encoding='utf-8-sig'));assert br['BuildPass'] and br['ExistingConstraintsMet'] and br['InputsUnchanged'],br
checks={k:json.loads((R/'reports'/('check_'+k)/'result.json').read_text()) for k in ['owner','display','keys','health','event','cancel','network']}
assert all(x['pass'] and x['inputs_unchanged'] for x in checks.values()),checks
# Bind passing simulations to the actual build snapshot and packaged fixtures.
for check in checks.values():
 for relative,expected in check['input_hashes'].items():
  assert hashlib.sha256((R/relative).read_bytes()).hexdigest()==expected,relative
  if relative.startswith('rtl/'):
   assert hashlib.sha256((B/relative).read_bytes()).hexdigest()==expected,relative
release.mkdir();source=release/'source';source.mkdir();evidence=release/'evidence';evidence.mkdir()
for name in ['rtl','vendor','constraints','config']:shutil.copytree(B/name,source/name)
shutil.copyfile(B/'flow.tcl',source/'flow.tcl')
for name in ['scripts','sim','tools']:shutil.copytree(R/name,source/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copytree(R/'tools',release/'tools',ignore=shutil.ignore_patterns('__pycache__','*.pyc'));shutil.copytree(R/'config',release/'config')
for name in ['report_timing','device_map','constraint_check']:
 shutil.copytree(B/name,evidence/name,ignore=shutil.ignore_patterns('*.db','*.adf'))
for name in ['inputs.json','result.json','pds_console.log']:shutil.copyfile(B/name,evidence/name)
for name in ['baseline_hashes.json','scope.json','full_build_console.txt','timing_resources.json']:shutil.copyfile(R/'reports'/name,evidence/name)
for k in checks:shutil.copytree(R/'reports'/('check_'+k),evidence/('check_'+k),ignore=shutil.ignore_patterns('*.vvp'))
shutil.copytree(R/'reports/network_timeout_20261027',evidence/'network_timeout_20261027')
bit=release/('FPGA_GSV1_'+version+'_HDMI_1080P60.sbit');shutil.copy2(br['Release'],bit)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rollback=P/'release/FPGA_GSV1_CAM0_OV5640_3_5_9_READBACK/FPGA_GSV1_CAM0_OV5640_3_5_9_READBACK_HDMI_1080P60.sbit';assert sha(rollback)=='f760692d6a1e7695d4005945d0ba977468d8857c4b36c45dc57bd98e7283acb1'
# All compiled inputs, including vendor/constraints, exactly match the packaged source.
manifest=json.loads((B/'inputs.json').read_text(encoding='utf-8-sig'));assert all(sha(source/x['RelativePath'])==x['SnapshotSHA256'].lower() for x in manifest)
artifact={'version':'3.6.1 SOURCE_MAP','classification':'complete_function_candidate_pending_board','baseline':'3.5.9-R0 READBACK original exposure; OV3660 rotate180/25fps; TXDET1','bitstream':str(bit),'sha256':sha(bit),'generated_Asia_Shanghai':datetime.datetime.fromtimestamp(bit.stat().st_mtime,datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'build':str(B),'build_pass':True,'declared_STA_pass':True,'internal_STA_pass':True,'constraints_unchanged_from_R0':True,'all_compiled_inputs_match_packaged_source':True,'source_map':json.loads((R/'config/source_map.json').read_text(encoding='utf-8')),'checks':{k:{'pass':v['pass'],'board_measured':False} for k,v in checks.items()},'simulation_limits':['Production MAC/core/store/upload/arbiter/readers used. Packet/line memory contract models and native DDR service BFM; not analogue DDR PHY or external RGMII eye signoff.','Display mapping tested in five full1080p60 views using unchanged six-cycle processing bypass; no repeated algorithm regression. Health/title and KEY6 behavior checked separately.'],'external_timing_limits':['TXDET1 nominal2ns PHY TX model retained; device delay PVT/PCB skew not signed off.','CAM1 DOVDD/source output timing and DVP external eye remain unknown; inherited input constraints unchanged.'],'known_issues':['CAM1 colored horizontal stripes unresolved; no E5 BLC experiments or other IQ changes included.','Upload throttling may omit a KEY-referenced frame; host must use exact ID or UNKNOWN, never substitute another frame.','Four sources20fps is not complete and is not claimed.'],'rollback':str(rollback),'rollback_sha256':sha(rollback),'programmed_by_agent':False,'hardware_verified':False,'pi_service_modified':False,'camera_register_tables_changed':False}
artifact['uart_revision']='N2 35M'
artifact['fixture_correction']='Initial dual-MAC run timed out with zero publications. Concurrent GMII host tasks shared static Verilog task locals across waits. Corrected packet task to automatic; retained original fixture, log and result under evidence/network_timeout_20261027. No production RTL or bitstream change for this correction.'
artifact['timing_resources']=json.loads((R/'reports/timing_resources.json').read_text())
(release/'artifact.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding='utf-8')
(release/'source_manifest.json').write_text(json.dumps({str(p.relative_to(source)).replace('\\','/'):sha(p) for p in source.rglob('*') if p.is_file()},indent=2),encoding='utf-8')
files=[p for p in release.rglob('*') if p.is_file() and p.name!='SHA256SUMS'];(release/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(release)).replace('\\','/')+'\n' for p in sorted(files)),encoding='utf-8')
print(json.dumps(artifact,ensure_ascii=False,indent=2))
