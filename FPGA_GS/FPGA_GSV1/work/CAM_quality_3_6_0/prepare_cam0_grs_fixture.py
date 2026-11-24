from pathlib import Path
import re,json,hashlib
r=Path('work/CAM_quality_3_6_0'); o=r/'reports/front_grs_regression';o.mkdir(exist_ok=True)
s=(r/'source/rtl/reuse/cmos_8_16bit.v').read_text(errors='replace')
m=(r/'reports/front_mapped_startup/cmos_8_16bit_mapped.v').read_text()
qs=re.findall(r'GTP_DFF(?:_\w+)?\s.*?\.INIT\(1\'b0\)\).*?\.Q\s*\(([^)]+)\)',m,re.S)
regs=sorted(set(re.sub(r'\[\d+\]','',q.strip()) for q in qs))
expected={'cnt','de_i_r','de_i_r1','de_o','de_out1','de_out2','de_out3','enble','pdata_i_reg','pdata_o','pdata_out1','pdata_out2','pdata_out3','vs_i_reg'}
assert set(regs)==expected,(set(regs),expected)
s=s.replace('endmodule','// Simulation fixture only: exact INIT=0 of the existing synthesized GRS-enabled FFs.\ninitial begin\n'+''.join('    '+q+" = '0;\n" for q in regs)+'end\nendmodule')
(o/'cmos_8_16bit_grs_fixture.v').write_text(s)
t=(r/'source/sim/cam0_front30_tb.sv').read_text()
t=t.replace('actual byte72MHz','actual byte84MHz').replace('exactly1800*800 SYS cycles,40ms per new input','740 rows x3784 byte cycles /84MHz =33.335ms per new input')
t=t.replace('reg vs=0,href=0;','reg cam_ready=0;\n reg vs=0,href=0;')
t=t.replace('gearbox(.pclk(bc),.rst_n(rst)','gearbox(.pclk(bc),.rst_n(cam_ready)').replace('.source_ready(rst)', '.source_ready(cam_ready)')
t=t.replace('rst=1;#1;rst=0;#999;rst=1;idle(100);','rst=1;#1;rst=0;#999;rst=1;idle(400);cam_ready=1;idle(100);')
t=t.replace('if(published!=4 || dut.rejected_count!=1 || consecutive!=2)', 'if(published!=expected_publications || dut.rejected_count!=1 || consecutive!=2)')
t=t.replace('// One startup frame was not published in the first run; the capture monitor\n  // may still count it. The fifth offered frame is deliberately malformed.','// GRS-aware startup must preserve all five geometrically complete frames;\n  // only the fifth offered frame (id4) is malformed. No expected good/bad count was relaxed.')
t=t.replace('integer frame_done=0;', '''// Exact synthesized GRS initialization for the stopped-clock release pair.
 initial monitor.pipeline_release=0;
 always @(posedge vc) if(rst && ((^ {running,cvs,cde,ide}) === 1'bx))
  $fatal(1,"unknown camera startup control after mapped GRS");
 integer expected_publications=0,verdicts=0; reg [5:0] seen_publications=0;
 always @(posedge vc) if(rst && result_valid) begin
  if(result_id>5 || errors!==(result_id==4 ? 8'h01:8'h00))
   $fatal(1,"independent verdict id%0d errors%h",result_id,errors);
  verdicts++; if(result_id!=4) expected_publications++;
  $display("CAM0_VERDICT id=%0d errors=%h expected_complete=%0d",result_id,errors,expected_publications);$fflush();
 end
 integer frame_done=0;''')
t=t.replace('previous_pub=$realtime;old_pub=published;', '''if(dut.front_three_slots.owner.pending_id>5 || dut.front_three_slots.owner.pending_id==4
     || seen_publications[dut.front_three_slots.owner.pending_id]) $fatal(1,"invalid/duplicate publication");
  seen_publications[dut.front_three_slots.owner.pending_id]=1;
  previous_pub=$realtime;old_pub=published;''')
t=t.replace('if(status[143:128]!=5', '''if(verdicts!=6 || seen_publications!==6'b101111) $fatal(1,"first-frame/recovery coverage %d %b",verdicts,seen_publications);
  $display("CAM0_FINAL good=%0d bad=%0d pubs=%0d writes=%0d reads=%0d displays=%0d independent=%0d third_writes=%0d read_faults=%0d",status[143:128],status[175:160],published,checked_w,checked_r,displayed,independent_displays,third_writes,dut.read_fault_count);$fflush();
  if(status[143:128]!=5''')
(o/'cam0_front30_grs_tb.sv').write_text(t)
(o/'fixture_identity.json').write_text(json.dumps({'grs_initialized_registers':regs,'mapped_proof':'../front_mapped_startup/cmos_8_16bit_mapped.v','production_capture_modified':False,'original_geometry_assertion':'5 good /1 bad retained','new_oracle':'every verdict error/id, unique publications0,1,2,3,5, complete source pixels, DDR/display protection','real_startup':'separate global reset and delayed camera init_done; divided clock stopped before first VS','monitor_pipeline_release_init':'00, proven GTP_DFF_C GRS_EN TRUE INIT0 in synthesized video_capture_status','preserved_additional_failure':'partial_without_monitor_grs.log + startup_trace.log: gearbox-only GRS was insufficient; stopped-clock permit pipeline remained X without actual mapped monitor GRS','no_X_assertion':'running/capture VS-DE/packed DE checked at every camera pixel clock'},indent=2))
