"""Logical/physical input provenance, separate from the unchanged GSV3 protocol.

This local preparation record is not FPGA telemetry. A packet's source=0 does
not demonstrate NET_RX provenance. Review the actual handoff before enabling it.
"""
import json
from pathlib import Path

EXPECTED_PROFILE=dict(width=1280,height=720,pixel_format='RGB565',byte_order='little',fragment_bytes=1280,fragment_count=1440)

def load(path=None):
    path=Path(path) if path else Path(__file__).with_name('source_contract.json')
    result=json.loads(path.read_text(encoding='utf-8-sig'))
    if result.get('logical_source')!='LIVE_FRONT' or result.get('expected_physical_source')!='NET_RX':
        raise ValueError('M407来源配置必须是逻辑前摄LIVE_FRONT，预期物理源NET_RX')
    reviewed=bool(result.get('fpga_handoff_summary')
                  and result.get('reviewed_wire_profile')==EXPECTED_PROFILE
                  and result.get('reviewed_event_frame_origin')=='NET_RX_COMPLETE_FRAME')
    verified=bool(reviewed and result.get('physical_source_verified') is True
                  and result.get('runtime_source_evidence'))
    result['handoff_reviewed']=reviewed
    result['physical_source_verified']=verified
    result['status']=('NET_RX_SOURCE_CONFIRMED_ACCEPTANCE_PENDING' if verified else
                      'HANDOFF_REVIEWED_WAITING_BOARD_SOURCE' if reviewed else 'WAITING_FPGA_HANDOFF')
    result['display_name']='实时前摄／FPGA网口1输入'
    result['current_upload_provenance']='NET_RX_SOURCE_CONFIRMED' if verified else 'UNVERIFIED_FPGA_UPLOAD'
    result['physical_acceptance_passed']=False
    return result

def permits_real_result(source_contract):
    return source_contract.get('physical_source_verified') is True
