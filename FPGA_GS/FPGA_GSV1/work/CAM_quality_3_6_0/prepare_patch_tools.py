from pathlib import Path
r=Path(__file__).resolve().parent
p=r.parents[1]/'release/FPGA_GSV1_CAM1_GAIN8_E2_3_6_0/tools/cam1/read_net2_diag.ps1'
s=p.read_text(encoding='utf-8-sig').replace('^N2 35O ','^N2 35[OP] ').replace('No N2 35O line','No N2 35O/35P line')
(r/'rear_pixels_source/scripts/read_net2_diag.ps1').write_text(s,encoding='utf-8-sig')
p=r/'rear_pixels_source/scripts/decode_cam1_rate.py'
s=p.read_text(encoding='utf-8').replace("if not line.startswith('N2 35O '):", "if not line.startswith(('N2 35O ', 'N2 35P ')):")
p.write_text(s,encoding='utf-8')
print('Existing COM23 reader and rate decoder accept35P; original35O retained.')
