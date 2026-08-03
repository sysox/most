import uuid

from most.models import new_id


def test_ids_are_uuidv7():
    identifier = uuid.UUID(new_id())
    assert identifier.version == 7
    assert identifier.variant == uuid.RFC_4122
