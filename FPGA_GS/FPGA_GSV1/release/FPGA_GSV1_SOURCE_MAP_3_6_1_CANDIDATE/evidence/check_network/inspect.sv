module inspect;
always @(posedge map_network_tb.clk) begin
 if(map_network_tb.core1.rs==4 && map_network_tb.core1.rx_packets<8)
 $display("PARSE type=%d len=%d pframe=%d idx=%d off=%d session=%h online=%b healthy=%b profile=%h fmt=%h w=%d h=%d plen=%d count=%d",map_network_tb.core1.p_type,map_network_tb.core1.length,map_network_tb.core1.p_frame,map_network_tb.core1.p_index,map_network_tb.core1.p_offset,map_network_tb.core1.p_session,map_network_tb.online1,map_network_tb.healthy,map_network_tb.core1.head[335:328],map_network_tb.core1.head[327:320],map_network_tb.core1.head[223:208],map_network_tb.core1.head[207:192],map_network_tb.core1.p_len,map_network_tb.core1.head[127:112]);
end
initial begin #3000000;
 $display("SHORT pubs=%d j=%d rx=%d bad=%d crc=%h over=%h rejectformat=%d check=%d profile=%d session=%d seq=%d begin=%d waits=%d DDR=%d assembly=%b next=%d ready=%b pending=%h state=%d",map_network_tb.pub_count,map_network_tb.j,map_network_tb.core1.rx_packets,map_network_tb.core1.bad_packets,map_network_tb.crc,map_network_tb.over,map_network_tb.core1.reject_format,map_network_tb.core1.reject_checksum,map_network_tb.core1.reject_profile,map_network_tb.core1.reject_session,map_network_tb.core1.sequence_errors,map_network_tb.core1.begin_requests,map_network_tb.core1.begin_wait_cycles,map_network_tb.core1.ddr_beats,map_network_tb.core1.assembly,map_network_tb.core1.next_index,map_network_tb.store_ready,map_network_tb.pend,map_network_tb.core1.rs);
 $finish;end
endmodule
