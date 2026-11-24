"""Package one passing pre-DDR pixel-location experiment; never overwrite release."""
from datetime import datetime
from pathlib import Path
import hashlib,json,re,shutil
r=Path(__file__).resolve().parent;root=r.parents[1];source=r/'rear_pixels_source'
run=source/'build/CAM1_RAW_E3_3_6_0_20261024_203852_117'
res=json.loads((run/'result.json').read_text(encoding='utf-8-sig'))
assert all(res[k] for k in ('BuildPass','ExistingConstraintsMet','InputsUnchanged'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
bit=Path(res['Release']);assert sha(bit)==res['SHA256'].lower()
timing=(run/'report_timing/fpga_gsv1_top.rtr').read_text()
summaries=[]
for name,body in re.findall(r'((?:Setup|Hold|Recovery|Removal|Pulse Width) Summary\([^\n]+\):)\s*\n(.*?)(?=\n={8,})',timing,re.S):
    rows=[]
    for line in body.splitlines():
        m=re.search(r'(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s*$',line)
        if m:rows.append((float(m[1]),int(m[3])))
    assert rows and all(n==0 for _,n in rows),name
    summaries.append(dict(summary=name,worst_slack_ns=min(x[0] for x in rows),failing_endpoints=0))
assert len(summaries)==10
prr=(run/'place_route/fpga_gsv1_top.prr').read_text().split('Device Utilization Summary :')[1]
value=lambda key:float(re.search(r'\|\s*'+re.escape(key)+r'\s*\|\s*(\d+(?:\.\d+)?)',prr)[1])
resources={k:value('Use of '+k) for k in ('CLMA','CLMS','DRM','PLL')}
for key in ('LUT','FF'):
    resources[key]=sum(float(n) for n in re.findall(r'\|\s+'+key+r'\s+\|\s*(\d+)',prr)[:2])
assert resources['DRM']>=109, 'Check actual16DRM patch mapping'
evidence=dict(existing_constraints_met=True,summaries=summaries,resources=resources,
              constraints_changed=False,
              limits=['Inherited external PHY PVT/PCB and camera pad electrical-model limits remain.',
                      'Positive internal STA does not prove incoming pixel data or sensor image quality correct.'])
(r/'reports/patch_timing_resources.json').write_text(json.dumps(evidence,indent=2)+'\n')
dest=root/'release/FPGA_GSV1_CAM1_RAW_E3_3_6_0';assert not dest.exists()
dest.mkdir()
for folder in ('rtl','vendor','constraints','config'):
    shutil.copytree(run/folder,dest/'source'/folder)
shutil.copy2(run/'flow.tcl',dest/'source/flow.tcl')
for folder in ('scripts','sim'):
    shutil.copytree(source/folder,dest/'source'/folder,ignore=shutil.ignore_patterns('__pycache__'))
out=dest/'reports';out.mkdir()
for name in ('dark_video_findings.json','GAIN8_findings.json','GAIN8_after_cover_uart.txt',
             'GAIN8_after_cover_decode.json','patch_checks.json','patch_timing_resources.json',
             'cam1_patch_checked.log','cam1_patch_tags.log','patch_uart.log',
             'patch_uart_line.txt','patch_first_build_aborted.json'):
    shutil.copy2(r/'reports'/name,out/name)
for name in ('result.json','inputs.json','pds_console.log'):
    shutil.copy2(run/name,out/name)
for name in ('report_timing','place_route'):
    (out/name).mkdir()
    for p in (run/name).iterdir():
        if p.is_file() and p.suffix in ('.rtr','.prr','.prt','.txt','.log'):
            shutil.copy2(p,out/name/p.name)
refs=root/'release/FPGA_GSV1_CAM1_OV3660_3_5_8_ROTATE25_CANDIDATE/reports/sources'
(out/'sources').mkdir()
for name in ('OV3660_datasheet.txt','esp32_camera_LICENSE.txt','THIRD_PARTY_NOTICES.md',
             'sensors_ov3660.c','sensors_private_include_ov3660_settings.h','manifest.json'):
    shutil.copy2(refs/name,out/'sources'/name)
tools=dest/'tools/cam1';tools.mkdir(parents=True)
for name in ('read_net2_diag.ps1','decode_cam1_patch.py','decode_cam1_rate.py'):
    shutil.copy2(source/'scripts'/name,tools/name)
shutil.copy2(bit,dest/bit.name)
artifact=dict(version='3.6.0 CAM1 RAW E3 pre-DDR pixel-location experiment',
    bitstream=str(dest/bit.name),sha256=sha(bit),generated_utc=res['GeneratedTime'],
    generated_local=datetime.fromtimestamp(bit.stat().st_mtime).astimezone().isoformat(),
    programmed=False,board_verified=False,green_line_fixed=False,
    behavior='20s after reset: freeze one accepted native16x720 strip at source x1120 before DDR/filter/OSD; repeat480 pages with frame ID and whole-strip CRC on existing UART.',
    sensor_configuration='R0 original tables, including OV3660 original gain ceiling15.5x; no GAIN8/profile/SCCB writes added.',
    uart='N2 35P,40 words @20Hz; C1R8 W12..19 retained; C1PX W20..39. Existing COM reader recognition updated to O/P.',
    main_video_path_affected=False,cam0_owner_fix_included=False,cam0_exposure_changed=False,
    rollback=str(root/'release/FPGA_GSV1_CAM0_OV5640_3_5_9_READBACK/FPGA_GSV1_CAM0_OV5640_3_5_9_READBACK_HDMI_1080P60.sbit'),
    rollback_sha256='f760692d6a1e7695d4005945d0ba977468d8857c4b36c45dc57bd98e7283acb1',
    manual_operation='Cover rear lens BEFORE download; keep original+rear single view and COM23 free; confirm download. One55s serial capture then decode. No Pi LIVE or other function tests.',
    interpretation='Visible lines in native strip locate defect upstream of DDR; sensor/ISP versus DVP still requires evidence. Clean strip is only this region/frame, not proof of full clean video.',
    build=str(run),timing=evidence)
(dest/'artifact.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
entries=[sha(p)+'  '+p.relative_to(dest).as_posix() for p in sorted(dest.rglob('*')) if p.is_file()]
(dest/'SHA256SUMS').write_text('\n'.join(entries)+'\n')
print(json.dumps(artifact,ensure_ascii=False,indent=2))
