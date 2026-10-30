from datetime import UTC

import pytest
from app.adapters.acris import AcrisShapeAdapter

NGSI_LD_ACRIS_SAMPLE = [
    {
        "id": "urn:ngsi-ld:TerminalFacility:mqi-t2",
        "type": "TerminalFacility",
        "terminalAreaLocation": {"type": "Property", "value": {"identifier": "T2"}},
        "airportTrafficFlowType": {"type": "Property", "value": "international"},
    },
    {
        "id": "urn:ngsi-ld:CheckpointFacility:mqi-t2-ckp-3",
        "type": "CheckpointFacility",
        "checkpointAreaLocation": {
            "type": "Property",
            "value": {"identifier": "T2-CKP-3", "name": "T2 North", "terminal": "T2"},
        },
    },
    {
        "id": "urn:ngsi-ld:PassengerQueue:mqi-t2-ckp-3-0905",
        "type": "PassengerQueue",
        "queueLocation": {"type": "Relationship", "object": "urn:ngsi-ld:CheckpointFacility:mqi-t2-ckp-3"},
        "checkpointAreaLocation": {"type": "Property", "value": {"identifier": "T2-CKP-3"}},
        "countMeasurementTime": {"type": "Property", "value": "2026-10-14T09:05:00Z"},
        "waitTime": {"type": "Property", "value": {"value": 14, "unit": "minute"}},
        "passengerCount": {"type": "Property", "value": 87},
    },
]


def test_representative_ngsi_ld_acris_entities_map_to_canonical_rows():
    adapter = AcrisShapeAdapter()
    entities = adapter.parse_entity(NGSI_LD_ACRIS_SAMPLE)
    terminals, checkpoints, measurements = adapter.canonical_from_entities(entities)

    assert terminals[0].name == "T2"
    assert terminals[0].kind == "international"
    assert checkpoints[0].id == "urn:ngsi-ld:CheckpointFacility:mqi-t2-ckp-3"
    assert checkpoints[0].terminal == "T2"
    assert measurements[0].checkpoint_id == "T2-CKP-3"
    assert measurements[0].headcount_est == 87
    assert measurements[0].wait_min == 14
    assert measurements[0].measured_at.tzinfo == UTC


def test_acris_adapter_rejects_unknown_or_incomplete_ngsi_ld_entities():
    adapter = AcrisShapeAdapter()
    with pytest.raises(ValueError, match="unsupported type"):
        adapter.parse_entity({"id": "urn:example:1", "type": "MadeUpEntity"})
    with pytest.raises(ValueError, match="measurement time"):
        adapter.parse_entity({
            "type": "PassengerQueue",
            "checkpointAreaLocation": {"type": "Property", "value": {"identifier": "T2-CKP-3"}},
            "passengerCount": {"type": "Property", "value": 2},
        })
